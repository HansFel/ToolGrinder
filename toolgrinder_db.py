import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = 2


class ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect_database(path):
    connection = sqlite3.connect(path, factory=ClosingConnection)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


def initialize_database(path, template_dir):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with connect_database(path) as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS schema_info (
                version INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS cutter_templates (
                id INTEGER PRIMARY KEY,
                source_name TEXT UNIQUE,
                name TEXT NOT NULL,
                cutter_type TEXT NOT NULL DEFAULT 'Schaftfraeser',
                material TEXT NOT NULL DEFAULT 'VHM',
                version INTEGER NOT NULL DEFAULT 1,
                active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
                config_json TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                source_sha256 TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS cutters (
                id INTEGER PRIMARY KEY,
                tool_uid TEXT NOT NULL UNIQUE,
                template_id INTEGER NOT NULL REFERENCES cutter_templates(id),
                current_diameter REAL NOT NULL,
                current_length REAL,
                sharpening_count INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'ready',
                location TEXT,
                notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS grinding_strategies (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                version INTEGER NOT NULL DEFAULT 1,
                status TEXT NOT NULL DEFAULT 'released',
                description_de TEXT NOT NULL,
                description_en TEXT NOT NULL,
                parameters_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(name, version)
            );

            CREATE TABLE IF NOT EXISTS grinding_tools (
                id INTEGER PRIMARY KEY,
                tool_uid TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                tool_type TEXT NOT NULL,
                specification TEXT NOT NULL,
                diameter REAL NOT NULL,
                max_rpm REAL,
                status TEXT NOT NULL DEFAULT 'ready',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sharpening_jobs (
                id INTEGER PRIMARY KEY,
                job_number TEXT NOT NULL UNIQUE,
                cutter_id INTEGER NOT NULL REFERENCES cutters(id),
                strategy_id INTEGER REFERENCES grinding_strategies(id),
                mode TEXT NOT NULL,
                status TEXT NOT NULL,
                start_diameter REAL,
                target_diameter REAL,
                result_diameter REAL,
                parameter_snapshot_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                completed_at TEXT
            );
            """
        )
        row = db.execute("SELECT version FROM schema_info LIMIT 1").fetchone()
        if row is None:
            db.execute("INSERT INTO schema_info(version) VALUES (?)", (SCHEMA_VERSION,))
        elif row["version"] == 1:
            columns = {
                column["name"]
                for column in db.execute("PRAGMA table_info(cutter_templates)").fetchall()
            }
            if "metadata_json" not in columns:
                db.execute(
                    "ALTER TABLE cutter_templates "
                    "ADD COLUMN metadata_json TEXT NOT NULL DEFAULT '{}'"
                )
            db.execute("UPDATE schema_info SET version = ?", (SCHEMA_VERSION,))
        elif row["version"] != SCHEMA_VERSION:
            raise RuntimeError(
                f"Unsupported ToolGrinder database version {row['version']}; expected {SCHEMA_VERSION}"
            )
        import_templates(db, template_dir)
        seed_reference_data(db)


def import_templates(db, template_dir):
    now = utc_now()
    for path in sorted(Path(template_dir).glob("*.json")):
        raw = path.read_bytes()
        config = json.loads(raw.decode("utf-8"))
        cutter = config.get("fraeser", {})
        name = path.stem
        material = cutter.get("material", infer_material(name))
        cutter_type = cutter.get("typ", "Schaftfraeser")
        db.execute(
            """
            INSERT OR IGNORE INTO cutter_templates(
                source_name, name, cutter_type, material, config_json,
                source_sha256, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                path.name,
                name,
                cutter_type,
                material,
                json.dumps(config, ensure_ascii=False, separators=(",", ":")),
                hashlib.sha256(raw).hexdigest(),
                now,
                now,
            ),
        )


def infer_material(name):
    upper = name.upper()
    if "HSS" in upper:
        return "HSS"
    return "VHM"


def seed_reference_data(db):
    now = utc_now()
    strategy_count = db.execute("SELECT COUNT(*) AS count FROM grinding_strategies").fetchone()["count"]
    if strategy_count == 0:
        strategies = (
            (
                "Standard Schaftfraeser",
                "Umfang und Stirn fuer Standard-Schaftfraeser.",
                "Peripheral and end grinding for standard end mills.",
                {"modes": ["edge", "front", "both"], "requires_measurement": True},
            ),
            (
                "Nur Vermessen",
                "Beruehrungslose Vorbereitung und LinuxCNC-Tastablauf.",
                "Preparation and LinuxCNC probing cycle only.",
                {"modes": ["measure"], "requires_measurement": False},
            ),
        )
        db.executemany(
            """
            INSERT INTO grinding_strategies(
                name, description_de, description_en, parameters_json, created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            [
                (name, de, en, json.dumps(parameters, separators=(",", ":")), now)
                for name, de, en, parameters in strategies
            ],
        )

    tool_count = db.execute("SELECT COUNT(*) AS count FROM grinding_tools").fetchone()["count"]
    if tool_count == 0:
        db.executemany(
            """
            INSERT INTO grinding_tools(
                tool_uid, name, tool_type, specification, diameter, max_rpm,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ("GW-EDGE-01", "Schruppscheibe", "edge", "1A1 CBN", 125.0, 6000.0, now, now),
                ("GW-FINISH-01", "Schlichtscheibe", "edge", "12V9 SD", 100.0, 7000.0, now, now),
                ("GW-FRONT-01", "Stirnscheibe", "front", "11V9 SD", 75.0, 8000.0, now, now),
            ),
        )

    cutter_count = db.execute("SELECT COUNT(*) AS count FROM cutters").fetchone()["count"]
    if cutter_count == 0:
        templates = db.execute(
            "SELECT id, name, config_json FROM cutter_templates WHERE active = 1 ORDER BY id LIMIT 3"
        ).fetchall()
        for index, template in enumerate(templates, start=1):
            config = json.loads(template["config_json"])
            cutter = config.get("fraeser", {})
            diameter = float(cutter.get("durchmesser", 0.0))
            length = cutter.get("schneidenlaenge")
            db.execute(
                """
                INSERT INTO cutters(
                    tool_uid, template_id, current_diameter, current_length,
                    sharpening_count, status, location, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'ready', 'Magazin A', ?, ?)
                """,
                (
                    f"TG-{datetime.now().year}-{index:03d}",
                    template["id"],
                    diameter,
                    float(length) if length is not None else None,
                    index - 1,
                    now,
                    now,
                ),
            )


def template_summary(row):
    config = json.loads(row["config_json"])
    cutter = config.get("fraeser", {})
    metadata = json.loads(row["metadata_json"] or "{}")
    return {
        "id": row["id"],
        "name": row["name"],
        "type": row["cutter_type"],
        "material": row["material"],
        "version": row["version"],
        "diameter": cutter.get("durchmesser"),
        "flutes": cutter.get("schneidenanzahl"),
        "cutting_length": cutter.get("schneidenlaenge"),
        "helix": cutter.get("drall_grad_pro_mm"),
        "metadata": metadata,
        "active": bool(row["active"]),
    }


def list_cutter_templates(db):
    rows = db.execute(
        "SELECT * FROM cutter_templates WHERE active = 1 ORDER BY name COLLATE NOCASE"
    ).fetchall()
    return [template_summary(row) for row in rows]


def get_cutter_template(db, template_id):
    row = db.execute("SELECT * FROM cutter_templates WHERE id = ?", (template_id,)).fetchone()
    if row is None:
        return None
    result = template_summary(row)
    result["config"] = json.loads(row["config_json"])
    result["updated_at"] = row["updated_at"]
    return result


def update_cutter_template(db, template_id, payload):
    current = get_cutter_template(db, template_id)
    if current is None:
        return None
    config = current["config"]
    cutter = config.setdefault("fraeser", {})
    actions = config.setdefault("aktionen", {})
    edge = actions.setdefault("schneiden", {})
    front = actions.setdefault("front", {})
    mappings = (
        ("diameter", cutter, "durchmesser", float),
        ("flutes", cutter, "schneidenanzahl", int),
        ("cutting_length", cutter, "schneidenlaenge", float),
        ("helix", cutter, "drall_grad_pro_mm", float),
        ("target_diameter", edge, "durchmesser_geschaerft", float),
        ("front_x_end", front, "x_end", float),
    )
    for source, target, key, converter in mappings:
        if source in payload:
            target[key] = converter(payload[source])
    name = str(payload.get("name", current["name"])).strip()
    if not name:
        raise ValueError("Template name must not be empty")
    material = str(payload.get("material", current["material"])).strip() or current["material"]
    cutter_type = str(payload.get("type", current["type"])).strip() or current["type"]
    metadata = dict(current.get("metadata") or {})
    metadata_fields = {
        "tool_family": "end_mill",
        "cutting_direction": "right",
        "helix_direction": "right",
        "corner_style": "square",
        "corner_radius": None,
        "corner_chamfer": None,
        "helix_angle_deg": None,
        "helix_value_source": "unknown",
        "rake_angle_deg": None,
        "clearance_angle_deg": None,
        "center_cutting": True,
        "variable_pitch": False,
        "coating": None,
        "shank_form": "cylindrical",
        "coolant_supply": "none",
    }
    for key, default in metadata_fields.items():
        if key in payload:
            value = payload[key]
            if key in {
                "corner_radius", "corner_chamfer", "helix_angle_deg",
                "rake_angle_deg", "clearance_angle_deg",
            }:
                value = None if value in (None, "") else float(value)
            elif key in {"center_cutting", "variable_pitch"}:
                value = bool(value)
            elif key == "helix_value_source":
                if value not in {"manufacturer", "measured", "unknown"}:
                    raise ValueError("Invalid helix value source")
            else:
                value = optional_text(value)
            metadata[key] = value
        elif key not in metadata:
            metadata[key] = default
    now = utc_now()
    db.execute(
        """
        UPDATE cutter_templates
        SET name = ?, cutter_type = ?, material = ?, config_json = ?, metadata_json = ?,
            version = version + 1, updated_at = ?
        WHERE id = ?
        """,
        (
            name,
            cutter_type,
            material,
            json.dumps(config, ensure_ascii=False, separators=(",", ":")),
            json.dumps(metadata, ensure_ascii=False, separators=(",", ":")),
            now,
            template_id,
        ),
    )
    return get_cutter_template(db, template_id)


def create_cutter_template(db, source_template_id, name):
    source = get_cutter_template(db, source_template_id)
    if source is None:
        raise ValueError("Source template not found")
    now = utc_now()
    cursor = db.execute(
        """
        INSERT INTO cutter_templates(
            name, cutter_type, material, config_json, metadata_json, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            name,
            source["type"],
            source["material"],
            json.dumps(source["config"], ensure_ascii=False, separators=(",", ":")),
            json.dumps(source.get("metadata", {}), ensure_ascii=False, separators=(",", ":")),
            now,
            now,
        ),
    )
    return get_cutter_template(db, cursor.lastrowid)


def list_cutters(db):
    rows = db.execute(
        """
        SELECT c.*, t.name AS template_name, t.material
        FROM cutters c
        JOIN cutter_templates t ON t.id = c.template_id
        ORDER BY c.updated_at DESC
        """
    ).fetchall()
    return [dict(row) for row in rows]


def create_cutter(db, payload):
    tool_uid = required_text(payload, "tool_uid")
    template_id = positive_integer(payload, "template_id")
    diameter = positive_number(payload, "current_diameter")
    length = optional_positive_number(payload, "current_length")
    status = status_value(payload.get("status", "ready"))
    now = utc_now()
    cursor = db.execute(
        """
        INSERT INTO cutters(
            tool_uid, template_id, current_diameter, current_length,
            sharpening_count, status, location, notes, created_at, updated_at
        ) VALUES (?, ?, ?, ?, 0, ?, ?, ?, ?, ?)
        """,
        (
            tool_uid,
            template_id,
            diameter,
            length,
            status,
            optional_text(payload.get("location")),
            optional_text(payload.get("notes")),
            now,
            now,
        ),
    )
    return get_cutter(db, cursor.lastrowid)


def get_cutter(db, cutter_id):
    row = db.execute(
        """
        SELECT c.*, t.name AS template_name, t.material
        FROM cutters c
        JOIN cutter_templates t ON t.id = c.template_id
        WHERE c.id = ?
        """,
        (cutter_id,),
    ).fetchone()
    return dict(row) if row else None


def update_cutter(db, cutter_id, payload):
    current = get_cutter(db, cutter_id)
    if current is None:
        return None
    values = {
        "tool_uid": required_text(payload, "tool_uid", current["tool_uid"]),
        "template_id": positive_integer(payload, "template_id", current["template_id"]),
        "current_diameter": positive_number(
            payload, "current_diameter", current["current_diameter"]
        ),
        "current_length": optional_positive_number(
            payload, "current_length", current["current_length"]
        ),
        "status": status_value(payload.get("status", current["status"])),
        "location": optional_text(payload.get("location", current["location"])),
        "notes": optional_text(payload.get("notes", current["notes"])),
    }
    db.execute(
        """
        UPDATE cutters
        SET tool_uid = ?, template_id = ?, current_diameter = ?, current_length = ?,
            status = ?, location = ?, notes = ?, updated_at = ?
        WHERE id = ?
        """,
        (
            values["tool_uid"],
            values["template_id"],
            values["current_diameter"],
            values["current_length"],
            values["status"],
            values["location"],
            values["notes"],
            utc_now(),
            cutter_id,
        ),
    )
    return get_cutter(db, cutter_id)


def list_strategies(db):
    rows = db.execute(
        "SELECT * FROM grinding_strategies ORDER BY name, version DESC"
    ).fetchall()
    results = []
    for row in rows:
        item = dict(row)
        item["parameters"] = json.loads(item.pop("parameters_json"))
        results.append(item)
    return results


def create_strategy_version(db, payload):
    name = required_text(payload, "name")
    previous = db.execute(
        "SELECT MAX(version) AS version FROM grinding_strategies WHERE name = ?",
        (name,),
    ).fetchone()
    version = int(previous["version"] or 0) + 1
    status = payload.get("status", "draft")
    if status not in {"draft", "released", "retired"}:
        raise ValueError("Invalid strategy status")
    modes = payload.get("modes", ["edge"])
    if not isinstance(modes, list) or not modes or any(
        mode not in {"edge", "front", "both", "measure"} for mode in modes
    ):
        raise ValueError("Strategy needs at least one valid mode")
    parameters = {
        "modes": modes,
        "requires_measurement": bool(payload.get("requires_measurement", False)),
    }
    cursor = db.execute(
        """
        INSERT INTO grinding_strategies(
            name, version, status, description_de, description_en,
            parameters_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            name,
            version,
            status,
            required_text(payload, "description_de"),
            required_text(payload, "description_en"),
            json.dumps(parameters, separators=(",", ":")),
            utc_now(),
        ),
    )
    return get_strategy(db, cursor.lastrowid)


def get_strategy(db, strategy_id):
    row = db.execute(
        "SELECT * FROM grinding_strategies WHERE id = ?", (strategy_id,)
    ).fetchone()
    if row is None:
        return None
    result = dict(row)
    result["parameters"] = json.loads(result.pop("parameters_json"))
    return result


def list_grinding_tools(db):
    return [dict(row) for row in db.execute(
        "SELECT * FROM grinding_tools ORDER BY tool_type, name"
    ).fetchall()]


def create_grinding_tool(db, payload):
    now = utc_now()
    cursor = db.execute(
        """
        INSERT INTO grinding_tools(
            tool_uid, name, tool_type, specification, diameter, max_rpm,
            status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            required_text(payload, "tool_uid"),
            required_text(payload, "name"),
            tool_type_value(payload.get("tool_type")),
            required_text(payload, "specification"),
            positive_number(payload, "diameter"),
            optional_positive_number(payload, "max_rpm"),
            status_value(payload.get("status", "ready")),
            now,
            now,
        ),
    )
    return get_grinding_tool(db, cursor.lastrowid)


def get_grinding_tool(db, tool_id):
    row = db.execute(
        "SELECT * FROM grinding_tools WHERE id = ?", (tool_id,)
    ).fetchone()
    return dict(row) if row else None


def update_grinding_tool(db, tool_id, payload):
    current = get_grinding_tool(db, tool_id)
    if current is None:
        return None
    values = {
        "tool_uid": required_text(payload, "tool_uid", current["tool_uid"]),
        "name": required_text(payload, "name", current["name"]),
        "tool_type": tool_type_value(payload.get("tool_type", current["tool_type"])),
        "specification": required_text(
            payload, "specification", current["specification"]
        ),
        "diameter": positive_number(payload, "diameter", current["diameter"]),
        "max_rpm": optional_positive_number(
            payload, "max_rpm", current["max_rpm"]
        ),
        "status": status_value(payload.get("status", current["status"])),
    }
    db.execute(
        """
        UPDATE grinding_tools
        SET tool_uid = ?, name = ?, tool_type = ?, specification = ?,
            diameter = ?, max_rpm = ?, status = ?, updated_at = ?
        WHERE id = ?
        """,
        (
            values["tool_uid"],
            values["name"],
            values["tool_type"],
            values["specification"],
            values["diameter"],
            values["max_rpm"],
            values["status"],
            utc_now(),
            tool_id,
        ),
    )
    return get_grinding_tool(db, tool_id)


def list_recent_jobs(db, limit=8):
    rows = db.execute(
        """
        SELECT j.*, c.tool_uid, t.name AS template_name
        FROM sharpening_jobs j
        JOIN cutters c ON c.id = j.cutter_id
        JOIN cutter_templates t ON t.id = c.template_id
        ORDER BY j.created_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [dict(row) for row in rows]


def required_text(payload, key, default=None):
    value = payload.get(key, default)
    text = str(value).strip() if value is not None else ""
    if not text:
        raise ValueError(f"{key} must not be empty")
    return text


def optional_text(value):
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def positive_number(payload, key, default=None):
    value = payload.get(key, default)
    number = float(value)
    if number <= 0:
        raise ValueError(f"{key} must be greater than zero")
    return number


def optional_positive_number(payload, key, default=None):
    value = payload.get(key, default)
    if value in (None, ""):
        return None
    number = float(value)
    if number <= 0:
        raise ValueError(f"{key} must be greater than zero")
    return number


def positive_integer(payload, key, default=None):
    value = payload.get(key, default)
    number = int(value)
    if number <= 0:
        raise ValueError(f"{key} must be a positive integer")
    return number


def status_value(value):
    if value not in {"ready", "maintenance", "blocked", "retired"}:
        raise ValueError("Invalid status")
    return value


def tool_type_value(value):
    if value not in {"edge", "front", "probe"}:
        raise ValueError("Invalid grinding tool type")
    return value

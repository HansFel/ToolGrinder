import json
import os
import shutil
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request, send_file

from Grinder import (
    generiere_front_gcode,
    generiere_gcode,
    generiere_linuxcnc_vermess_gcode,
    validate_front_config,
    validate_machine_limits_config,
    validate_probe_config,
)
from toolgrinder_db import (
    connect_database,
    create_cutter,
    create_cutter_template,
    create_grinding_tool,
    create_strategy_version,
    get_cutter,
    get_cutter_template,
    get_grinding_tool,
    get_strategy,
    initialize_database,
    list_cutter_templates,
    list_cutters,
    list_grinding_tools,
    list_recent_jobs,
    list_strategies,
    update_cutter,
    update_cutter_template,
    update_grinding_tool,
)


BASE_DIR = Path(__file__).resolve().parent
TOOLLIB_DIR = BASE_DIR / "ToolLib"
DATA_DIR = Path(os.environ.get("GRINDER_DATA_DIR", BASE_DIR / "data"))
GENERATED_DIR = DATA_DIR / "generated"


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        MAX_CONTENT_LENGTH=2 * 1024 * 1024,
        DATABASE=str(DATA_DIR / "toolgrinder.sqlite3"),
        GENERATED_DIR=str(GENERATED_DIR),
        TOOLLIB_DIR=str(TOOLLIB_DIR),
    )
    if test_config:
        app.config.update(test_config)
    Path(app.config["GENERATED_DIR"]).mkdir(parents=True, exist_ok=True)
    initialize_database(app.config["DATABASE"], app.config["TOOLLIB_DIR"])

    def open_db():
        return connect_database(app.config["DATABASE"])

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/templates/<path:name>")
    def api_template(name):
        return jsonify(load_template(name))

    @app.get("/api/bootstrap")
    def api_bootstrap():
        with open_db() as db:
            return jsonify(
                {
                    "templates": list_cutter_templates(db),
                    "cutters": list_cutters(db),
                    "strategies": list_strategies(db),
                    "grinding_tools": list_grinding_tools(db),
                    "recent_jobs": list_recent_jobs(db),
                }
            )

    @app.get("/api/cutter-templates/<int:template_id>")
    def api_cutter_template(template_id):
        with open_db() as db:
            template = get_cutter_template(db, template_id)
        if template is None:
            abort(404)
        return jsonify(template)

    @app.patch("/api/cutter-templates/<int:template_id>")
    def api_update_cutter_template(template_id):
        payload = request.get_json(silent=True) or {}
        try:
            with open_db() as db:
                template = update_cutter_template(db, template_id, payload)
        except (TypeError, ValueError) as exc:
            return jsonify({"ok": False, "errors": [str(exc)]}), 400
        if template is None:
            abort(404)
        return jsonify({"ok": True, "template": template})

    @app.post("/api/cutter-templates")
    def api_create_cutter_template():
        payload = request.get_json(silent=True) or {}
        try:
            source_id = int(payload["source_template_id"])
            name = str(payload["name"]).strip()
            if not name:
                raise ValueError("Name darf nicht leer sein.")
            with open_db() as db:
                template = create_cutter_template(db, source_id, name)
        except (KeyError, TypeError, ValueError, sqlite3.IntegrityError) as exc:
            return jsonify({"ok": False, "errors": [str(exc)]}), 400
        return jsonify({"ok": True, "template": template}), 201

    @app.get("/api/cutters/<int:cutter_id>")
    def api_cutter(cutter_id):
        with open_db() as db:
            cutter = get_cutter(db, cutter_id)
        if cutter is None:
            abort(404)
        return jsonify(cutter)

    @app.post("/api/cutters")
    def api_create_cutter():
        return database_write(
            open_db, lambda db, payload: create_cutter(db, payload), "cutter", 201
        )

    @app.patch("/api/cutters/<int:cutter_id>")
    def api_update_cutter(cutter_id):
        return database_write(
            open_db,
            lambda db, payload: update_cutter(db, cutter_id, payload),
            "cutter",
        )

    @app.get("/api/grinding-tools/<int:tool_id>")
    def api_grinding_tool(tool_id):
        with open_db() as db:
            tool = get_grinding_tool(db, tool_id)
        if tool is None:
            abort(404)
        return jsonify(tool)

    @app.post("/api/grinding-tools")
    def api_create_grinding_tool():
        return database_write(
            open_db,
            lambda db, payload: create_grinding_tool(db, payload),
            "grinding_tool",
            201,
        )

    @app.patch("/api/grinding-tools/<int:tool_id>")
    def api_update_grinding_tool(tool_id):
        return database_write(
            open_db,
            lambda db, payload: update_grinding_tool(db, tool_id, payload),
            "grinding_tool",
        )

    @app.get("/api/strategies/<int:strategy_id>")
    def api_strategy(strategy_id):
        with open_db() as db:
            strategy = get_strategy(db, strategy_id)
        if strategy is None:
            abort(404)
        return jsonify(strategy)

    @app.post("/api/strategies")
    def api_create_strategy():
        return database_write(
            open_db,
            lambda db, payload: create_strategy_version(db, payload),
            "strategy",
            201,
        )

    @app.post("/api/generate")
    def api_generate():
        payload = request.get_json(silent=True) or {}
        mode = payload.get("mode", "both")
        if mode not in {"edge", "front", "both", "measure"}:
            return jsonify({"ok": False, "errors": ["Ungueltiger Modus."]}), 400

        try:
            strategy_id = payload.get("strategy_id")
            if strategy_id is not None:
                with open_db() as db:
                    strategy = get_strategy(db, int(strategy_id))
                if strategy is None:
                    raise ValueError("Schleifstrategie wurde nicht gefunden.")
                if strategy["status"] != "released":
                    raise ValueError("Nur freigegebene Schleifstrategien duerfen G-Code erzeugen.")
                if mode not in strategy["parameters"].get("modes", []):
                    raise ValueError(
                        f'Die Strategie "{strategy["name"]}" erlaubt den Modus "{mode}" nicht.'
                    )
            cfg = payload.get("config")
            if cfg is None and payload.get("template_id") is not None:
                with open_db() as db:
                    template = get_cutter_template(db, int(payload["template_id"]))
                if template is None:
                    raise ValueError("Fraeser-Vorlage wurde nicht gefunden.")
                cfg = template["config"]
            if isinstance(cfg, str):
                cfg = json.loads(cfg)
            if not isinstance(cfg, dict):
                raise ValueError("Konfiguration muss ein JSON-Objekt sein.")
        except Exception as exc:
            return jsonify({"ok": False, "errors": [f"JSON konnte nicht gelesen werden: {exc}"]}), 400

        errors = validate_config(cfg, mode)
        if errors:
            return jsonify({"ok": False, "errors": errors}), 400

        job_id = uuid.uuid4().hex[:12]
        job_dir = Path(app.config["GENERATED_DIR"]) / job_id
        job_dir.mkdir(parents=True, exist_ok=False)
        cfg = prepare_output_names(cfg)

        try:
            created = []
            with pushd(job_dir):
                if mode in {"edge", "both"}:
                    generiere_gcode(cfg, "web-config.json")
                    created.append(output_name(cfg, "edge"))
                if mode in {"front", "both"}:
                    generiere_front_gcode(cfg, "web-config.json")
                    created.append(output_name(cfg, "front"))
                if mode == "measure":
                    generiere_linuxcnc_vermess_gcode(cfg, "web-config.json")
                    created.append(output_name(cfg, "measure"))

            files = []
            for name in created:
                path = job_dir / name
                if path.exists():
                    files.append(
                        {
                            "name": name,
                            "bytes": path.stat().st_size,
                            "download_url": f"/download/{job_id}/{name}",
                            "preview": path.read_text(encoding="utf-8", errors="replace")[:6000],
                        }
                    )

            if not files:
                return jsonify({"ok": False, "errors": ["Es wurde keine Ausgabedatei erzeugt."]}), 500
            record_generated_job(open_db, payload, mode, cfg)
            return jsonify({"ok": True, "job_id": job_id, "files": files})
        except Exception as exc:
            shutil.rmtree(job_dir, ignore_errors=True)
            return jsonify({"ok": False, "errors": [str(exc)]}), 500

    @app.get("/download/<job_id>/<path:filename>")
    def download(job_id, filename):
        if not safe_name(job_id) or Path(filename).name != filename:
            abort(404)
        path = Path(app.config["GENERATED_DIR"]) / job_id / filename
        if not path.exists():
            abort(404)
        return send_file(path, as_attachment=True, download_name=filename)

    @app.get("/health")
    def health():
        return {"ok": True}

    return app


def database_write(open_db, operation, result_key, success_status=200):
    payload = request.get_json(silent=True) or {}
    try:
        with open_db() as db:
            result = operation(db, payload)
    except (TypeError, ValueError, sqlite3.IntegrityError) as exc:
        return jsonify({"ok": False, "errors": [str(exc)]}), 400
    if result is None:
        abort(404)
    return jsonify({"ok": True, result_key: result}), success_status


def record_generated_job(open_db, payload, mode, cfg):
    cutter_id = payload.get("cutter_id")
    if cutter_id is None:
        return
    strategy_id = payload.get("strategy_id")
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    number = f"JOB-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:5].upper()}"
    edge = cfg.get("aktionen", {}).get("schneiden", {})
    with open_db() as db:
        cutter = db.execute("SELECT current_diameter FROM cutters WHERE id = ?", (int(cutter_id),)).fetchone()
        if cutter is None:
            return
        db.execute(
            """
            INSERT INTO sharpening_jobs(
                job_number, cutter_id, strategy_id, mode, status,
                start_diameter, target_diameter, parameter_snapshot_json, created_at
            ) VALUES (?, ?, ?, ?, 'generated', ?, ?, ?, ?)
            """,
            (
                number,
                int(cutter_id),
                int(strategy_id) if strategy_id is not None else None,
                mode,
                cutter["current_diameter"],
                edge.get("durchmesser_geschaerft"),
                json.dumps(cfg, ensure_ascii=False, separators=(",", ":")),
                now,
            ),
        )


def list_templates():
    if not TOOLLIB_DIR.exists():
        return []
    return [
        {"name": p.name, "label": p.stem}
        for p in sorted(TOOLLIB_DIR.glob("*.json"))
        if p.is_file()
    ]


def load_template(name):
    path = TOOLLIB_DIR / Path(name).name
    if not path.exists():
        abort(404)
    return json.loads(path.read_text(encoding="utf-8"))


def validate_config(cfg, mode):
    errors = []
    errors.extend(validate_machine_limits_config(cfg))
    if mode == "measure":
        errors.extend(validate_probe_config(cfg))
    if mode in {"edge", "both"}:
        for key in ("maschine", "fraeser"):
            if key not in cfg:
                errors.append(f'Missing section "{key}"')
        action = cfg.get("aktionen", {}).get("schneiden")
        if not action:
            errors.append('Missing section "aktionen.schneiden"')
        else:
            for key in ("zustellung_pro_pass", "feed"):
                try:
                    if float(action.get(key, 0)) <= 0:
                        errors.append(f"aktionen.schneiden.{key} muss > 0 sein")
                except Exception:
                    errors.append(f"aktionen.schneiden.{key} muss eine Zahl sein")
    if mode in {"front", "both"}:
        ok, front_errors = validate_front_config(cfg)
        if not ok:
            errors.extend(front_errors)
    return errors


def prepare_output_names(cfg):
    cfg = json.loads(json.dumps(cfg))
    actions = cfg.setdefault("aktionen", {})
    edge = actions.setdefault("schneiden", {})
    front = actions.setdefault("front", {})
    edge["ausgabe_datei"] = Path(edge.get("ausgabe_datei") or "fraeser_kanten.ngc").name
    front["ausgabe_datei"] = Path(front.get("ausgabe_datei") or "fraeser_front.ngc").name
    if edge["ausgabe_datei"] == front["ausgabe_datei"]:
        front["ausgabe_datei"] = f"front_{front['ausgabe_datei']}"
    measure = actions.setdefault("vermessen", {})
    measure["ausgabe_datei"] = Path(measure.get("ausgabe_datei") or "fraeser_vermessen.ngc").name
    return cfg


def output_name(cfg, mode):
    if mode == "measure":
        return cfg.get("aktionen", {}).get("vermessen", {}).get("ausgabe_datei", "fraeser_vermessen.ngc")
    if mode == "front":
        return cfg.get("aktionen", {}).get("front", {}).get("ausgabe_datei", "fraeser_front.ngc")
    return cfg.get("aktionen", {}).get("schneiden", {}).get("ausgabe_datei", "fraeser_kanten.ngc")


def safe_name(value):
    return value and all(ch.isalnum() or ch in "-_" for ch in value)


@contextmanager
def pushd(path):
    old = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old)


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")), debug=True)

import json
import os
import shutil
import uuid
from contextlib import contextmanager
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


BASE_DIR = Path(__file__).resolve().parent
TOOLLIB_DIR = BASE_DIR / "ToolLib"
DATA_DIR = Path(os.environ.get("GRINDER_DATA_DIR", BASE_DIR / "data"))
GENERATED_DIR = DATA_DIR / "generated"


def create_app():
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    @app.get("/")
    def index():
        templates = list_templates()
        initial = load_template(templates[0]["name"]) if templates else {}
        return render_template(
            "index.html",
            templates=templates,
            initial_config=json.dumps(initial, indent=2, ensure_ascii=False),
        )

    @app.get("/api/templates/<path:name>")
    def api_template(name):
        return jsonify(load_template(name))

    @app.post("/api/generate")
    def api_generate():
        payload = request.get_json(silent=True) or {}
        mode = payload.get("mode", "both")
        if mode not in {"edge", "front", "both", "measure"}:
            return jsonify({"ok": False, "errors": ["Ungueltiger Modus."]}), 400

        try:
            cfg = payload.get("config")
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
        job_dir = GENERATED_DIR / job_id
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
            return jsonify({"ok": True, "job_id": job_id, "files": files})
        except Exception as exc:
            shutil.rmtree(job_dir, ignore_errors=True)
            return jsonify({"ok": False, "errors": [str(exc)]}), 500

    @app.get("/download/<job_id>/<path:filename>")
    def download(job_id, filename):
        if not safe_name(job_id) or Path(filename).name != filename:
            abort(404)
        path = GENERATED_DIR / job_id / filename
        if not path.exists():
            abort(404)
        return send_file(path, as_attachment=True, download_name=filename)

    @app.get("/health")
    def health():
        return {"ok": True}

    return app


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

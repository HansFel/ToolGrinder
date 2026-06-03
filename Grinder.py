import json
import math
import os
import argparse
import sys
import re

def resource_path(*paths):
    """Return a path to a resource, supporting PyInstaller _MEIPASS extraction."""
    base = getattr(sys, '_MEIPASS', os.path.dirname(__file__))
    return os.path.join(base, *paths)


def can_use_gui():
    """Check whether a GUI can be started on this system (tkinter available and display present on Linux)."""
    try:
        import tkinter as _tk
    except Exception:
        return False
    # On Linux headless systems, require DISPLAY or WAYLAND_DISPLAY
    if sys.platform.startswith('linux'):
        if not (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')):
            return False
    return True

# -------------------------------------------------
# G-CODE GENERATOR: FRAESER SCHAERFEN
# -------------------------------------------------

def lade_konfiguration(dateiname):
    with open(dateiname, "r", encoding="utf-8") as f:
        return json.load(f)


# --- GUI / state helpers -------------------------------------------------
# Speicherort des letzten Konfigurationspfads: bevorzugt im Projekt-Root, falls nicht möglich im Benutzer-Home.
PROJECT_STATE = os.path.join(os.path.dirname(__file__), '.grinder_last_config.json')
HOME_STATE = os.path.join(os.path.expanduser('~'), '.grinder_last_config.json')


def read_last_config_path():
    """Liefert den zuletzt verwendeten Config-Pfad oder None. Prüft zuerst Projekt-Root, dann Home."""
    for state in (PROJECT_STATE, HOME_STATE):
        try:
            if os.path.exists(state):
                with open(state, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('last_config')
        except Exception:
            continue
    return None


def save_last_config_path(path):
    """Speichert den zuletzt verwendeten Config-Pfad; bevorzugt Projekt-Root, sonst Home."""
    for state in (PROJECT_STATE, HOME_STATE):
        try:
            with open(state, 'w', encoding='utf-8') as f:
                json.dump({'last_config': path}, f)
            return
        except Exception:
            continue
    # Wenn alles scheitert, nichts tun
    return None


def choose_config_via_gui(initial_path=None):
    """Öffnet ein Datei-Dialog (tkinter) zur Auswahl einer JSON-Datei.
    Wenn das nicht möglich ist (z.B. headless) wird None zurückgegeben.
    Gibt '' zurück wenn Dialog abgebrochen wurde, None wenn GUI nicht verfügbar.
    """
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        initialdir = None
        if initial_path and os.path.exists(initial_path):
            initialdir = os.path.dirname(initial_path)
        filename = filedialog.askopenfilename(
            title="Konfigurationsdatei wählen",
            initialdir=initialdir or os.getcwd(),
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        root.destroy()
        # Unterscheide zwischen abgebrochen ('') und nicht verfügbar (None)
        return filename if filename else ''
    except Exception:
        # Keine GUI verfügbar
        return None


def choose_config_interactive(initial_path=None):
    """Fallback: Eingabeaufforderung in der Konsole, mit Vorschlag des letzten Pfads."""
    prompt = "Pfad zur Konfigurationsdatei eingeben"
    if initial_path:
        prompt += f" [Enter für: {initial_path}]"
    prompt += ": "
    try:
        val = input(prompt).strip()
    except Exception:
        val = ''
    if not val and initial_path:
        return initial_path
    return val or None


def choose_config(initial_path=None):
    """Versucht GUI, falls nicht möglich: interaktives Prompt, sonst None."""
    cfg = choose_config_via_gui(initial_path)
    if cfg is None:
        # GUI nicht verfügbar -> CLI Prompt verwenden
        return choose_config_interactive(initial_path)
    # GUI war verfügbar: cfg ist entweder ein Pfad oder '' (abgebrochen)
    return cfg if cfg else None


def validate_front_config(cfg):
    """Validate 'front' section in configuration. Returns (True, []) or (False, [errors]).
    Module-level function so it can be reused by FrontGrinder and tests.
    Supports both old and new JSON structure.
    """
    errors = []
    # Support new structure: aktionen.front or old structure: front
    f = cfg.get('aktionen', {}).get('front') if 'aktionen' in cfg else cfg.get('front')
    if not f:
        errors.append('Missing section "aktionen.front" or "front"')
        return False, errors
    # x_start / x_end
    try:
        x_start = float(f.get('x_start', 0.0))
        x_end = float(f.get('x_end', 0.0))
        if x_end <= x_start:
            errors.append('front.x_end must be greater than front.x_start')
    except Exception:
        errors.append('front.x_start and front.x_end must be numbers')
    # max_tiefe (optional in new structure)
    if 'max_tiefe' in f:
        try:
            max_tiefe = float(f.get('max_tiefe', -1.0))
            if max_tiefe >= 0:
                errors.append('front.max_tiefe should be negative (depth)')
        except Exception:
            errors.append('front.max_tiefe must be a number')
    # zustellung_pro_pass
    try:
        zp = float(f.get('zustellung_pro_pass', 0.0))
        if zp <= 0:
            errors.append('front.zustellung_pro_pass must be > 0')
    except Exception:
        errors.append('front.zustellung_pro_pass must be a number')
    # feed
    try:
        feed = float(f.get('feed', 0.0))
        if feed <= 0:
            errors.append('front.feed must be > 0')
    except Exception:
        errors.append('front.feed must be a number')
    # spindle - check in schleifscheibe_Front or old structure
    try:
        if 'schleifscheibe_Front' in cfg:
            spindle = float(cfg['schleifscheibe_Front'].get('drehzahl', 0.0))
        else:
            spindle = float(f.get('spindle', 0.0))
        if spindle <= 0:
            errors.append('schleifscheibe_Front.drehzahl or front.spindle must be > 0')
    except Exception:
        errors.append('schleifscheibe_Front.drehzahl or front.spindle must be a number')
    # ausgabe_datei is optional (has fallback in code)
    # No need to validate it as required
    # Werkzeug diameter required for radius-based plunge
    try:
        if 'fraeser' in cfg:
            diam = float(cfg['fraeser'].get('durchmesser', 0.0))
        else:
            w = cfg.get('werkzeug_front', cfg.get('werkzeug', {}))
            diam = float(w.get('durchmesser', 0.0))
        if diam <= 0:
            errors.append('fraeser.durchmesser (or werkzeug_front/werkzeug.durchmesser) must be > 0 (required for radius-based plunge)')
    except Exception:
        errors.append('fraeser.durchmesser must be a number')
    return (len(errors) == 0, errors)


def compute_front_start_positions(cfg):
    """Compute list of (pass_index, start_x, depth) tuples for front passes.
    Depth is always 0 (not used anymore), computed as number of passes from (x_end - x_start) / zustellung_pro_pass.
    Supports both old and new JSON structure.
    """
    # Support new structure: aktionen.front or old structure: front
    f = cfg.get('aktionen', {}).get('front') if 'aktionen' in cfg else cfg.get('front', {})
    if not f:
        return []
    base_x = float(f.get('x_start', 0.0))
    x_end = float(f.get('x_end', 0.0))
    x_step = float(f.get('zustellung_pro_pass', 0.01))

    # Berechne anzahl_passe automatisch
    distance = abs(x_end - base_x)
    anzahl_passe = math.ceil(distance / x_step) + 1 if x_step > 0 else 1

    starts = []
    for p in range(1, anzahl_passe + 1):
        current_start = base_x + (p - 1) * x_step
        if (x_end >= base_x and current_start > x_end) or (x_end < base_x and current_start < x_end):
            current_start = x_end
        starts.append((p, current_start, 0.0))
        if abs(current_start - x_end) < 0.0001:
            break
    return starts


def werkzeug_radius(cfg):
    """Radius des zu schleifenden Werkzeugs.

    Maschinenkonvention: Z0 liegt im Drehmittelpunkt des Werkzeugs, die obere
    Tangente liegt bei +Radius. Bestehende Einstellwerte fuer Zustellung und
    Sicherheitsabstand bleiben bedienseitig relativ zur oberen Tangente und
    werden vor der Ausgabe in Maschinen-Z umgerechnet.
    """
    if 'fraeser' in cfg:
        w = cfg['fraeser']
    else:
        w = cfg.get('werkzeug_front', cfg.get('werkzeug_edge', cfg.get('werkzeug', {})))
    return float(w.get('durchmesser', 0.0)) / 2.0


def z_von_oberer_tangente(cfg, z_rel):
    """Konvertiert alte/top-bezogene Z-Werte auf Z0 im Werkzeug-Drehmittelpunkt."""
    return werkzeug_radius(cfg) + float(z_rel)


AXIS_WORD_RE = re.compile(r'([XYZA])\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+))', re.IGNORECASE)


def machine_limits(cfg):
    """Return optional axis limits from maschine.limits.

    Expected keys are x_min/x_max, y_min/y_max, z_min/z_max and a_min/a_max.
    Missing axes are intentionally ignored so existing configs keep working.
    """
    return cfg.get('maschine', {}).get('limits', {}) or {}


def validate_machine_limits_config(cfg):
    """Validate the optional machine limit section and return a list of errors."""
    errors = []
    limits = machine_limits(cfg)
    for axis in ('x', 'y', 'z', 'a'):
        min_key = f'{axis}_min'
        max_key = f'{axis}_max'
        has_min = min_key in limits
        has_max = max_key in limits
        if not has_min and not has_max:
            continue

        min_value = None
        max_value = None
        if has_min:
            try:
                min_value = float(limits[min_key])
            except Exception:
                errors.append(f'maschine.limits.{min_key} muss eine Zahl sein')
        if has_max:
            try:
                max_value = float(limits[max_key])
            except Exception:
                errors.append(f'maschine.limits.{max_key} muss eine Zahl sein')
        if min_value is not None and max_value is not None and min_value > max_value:
            errors.append(f'maschine.limits.{min_key} darf nicht groesser als {max_key} sein')
    return errors


def parse_gcode_axes(line):
    """Extract explicit X/Y/Z/A words from one G-code line."""
    code = line.split(';', 1)[0].split('(', 1)[0]
    return {axis.upper(): float(value) for axis, value in AXIS_WORD_RE.findall(code)}


def validate_gcode_against_machine_limits(lines, cfg, tolerance=0.0001):
    """Check generated G-code against optional machine limits."""
    errors = validate_machine_limits_config(cfg)
    limits = machine_limits(cfg)
    if errors or not limits:
        return errors

    for line_no, line in enumerate(lines, start=1):
        axes = parse_gcode_axes(line)
        for axis, value in axes.items():
            axis_key = axis.lower()
            min_key = f'{axis_key}_min'
            max_key = f'{axis_key}_max'
            if min_key in limits and value < float(limits[min_key]) - tolerance:
                errors.append(
                    f'Zeile {line_no}: {axis}={value:.3f} unterschreitet {min_key}={float(limits[min_key]):.3f} | {line}'
                )
            if max_key in limits and value > float(limits[max_key]) + tolerance:
                errors.append(
                    f'Zeile {line_no}: {axis}={value:.3f} ueberschreitet {max_key}={float(limits[max_key]):.3f} | {line}'
                )
    return errors


def ensure_gcode_within_machine_limits(lines, cfg):
    """Raise ValueError if generated G-code violates configured machine limits."""
    errors = validate_gcode_against_machine_limits(lines, cfg)
    if errors:
        raise ValueError('Maschinenlimit verletzt:\n- ' + '\n- '.join(errors))


def probe_config(cfg):
    """Return probing setup for measuring the cutter with a LinuxCNC touch probe."""
    return cfg.get('aktionen', {}).get('vermessen', cfg.get('vermessen', {})) or {}


def probe_ball_radius(cfg):
    """Radius of the touch probe ball in mm."""
    p = probe_config(cfg)
    if 'tastkugel_durchmesser' in p:
        return float(p.get('tastkugel_durchmesser')) / 2.0
    tastkopf = cfg.get('tastkopf', {})
    return float(tastkopf.get('kugel_durchmesser', 0.0)) / 2.0


def validate_probe_config(cfg):
    """Validate optional probing configuration for LinuxCNC measurement cycles."""
    errors = []
    p = probe_config(cfg)
    if not p:
        return errors
    try:
        if probe_ball_radius(cfg) <= 0:
            errors.append('aktionen.vermessen.tastkugel_durchmesser muss > 0 sein')
    except Exception:
        errors.append('aktionen.vermessen.tastkugel_durchmesser muss eine Zahl sein')
    for key in ('probe_feed', 'rapid_feed', 'retract'):
        try:
            if float(p.get(key, 0.0)) <= 0:
                errors.append(f'aktionen.vermessen.{key} muss > 0 sein')
        except Exception:
            errors.append(f'aktionen.vermessen.{key} muss eine Zahl sein')
    return errors


def sign_from_direction(direction):
    """Return +1 or -1 from a probing direction like +X, -Z, plus or minus."""
    text = str(direction).strip().upper()
    if text.startswith('+'):
        return 1.0
    if text.startswith('-'):
        return -1.0
    raise ValueError(f'Ungueltige Tastrichtung: {direction}')


def korrigiere_tastpunkt_linear(kugelzentrum, richtung, kugel_durchmesser):
    """Convert a probed ball-center coordinate to the contacted surface coordinate.

    LinuxCNC reports the controlled point, normally the probe ball center. If the
    probe moved in -X, the contacted surface is one ball radius below the center
    along X. If it moved in +X, it is one ball radius above the center.
    """
    radius = float(kugel_durchmesser) / 2.0
    return float(kugelzentrum) + sign_from_direction(richtung) * radius


def berechne_durchmesser_aus_z_antastung(z_kugelzentrum, kugel_durchmesser, z_mitte=0.0, richtung='-Z'):
    """Calculate cutter diameter from a Z probe hit on the outside diameter."""
    oberflaeche_z = korrigiere_tastpunkt_linear(z_kugelzentrum, richtung, kugel_durchmesser)
    return 2.0 * abs(float(oberflaeche_z) - float(z_mitte))


def berechne_drall_grad_pro_mm(x1, a1, x2, a2):
    """Calculate helix slope in degrees per mm from two probe points."""
    dx = float(x2) - float(x1)
    if abs(dx) < 0.000001:
        raise ValueError('X-Abstand fuer Drallmessung darf nicht 0 sein')
    return (float(a2) - float(a1)) / dx


def gcode_linuxcnc_probe_header(cfg, config_file=None):
    p = probe_config(cfg)
    m = cfg.get('maschine', {})
    lines = []
    lines.append('%')
    lines.append('(ToolGrinder Vermessen - LinuxCNC)')
    if config_file:
        lines.append(f'(Vorlage: {config_file})')
    lines.append('(Tastpositionen werden von LinuxCNC in #5061..#5069 abgelegt)')
    lines.append('G21')
    lines.append('G90 G94')
    lines.append('G40')
    if m.get('nullpunkt') and m['nullpunkt'].get('code'):
        lines.append(m['nullpunkt']['code'])
    safe_z = float(p.get('safe_z', m.get('safe_z', 20.0)))
    lines.append(f'G0 Z{safe_z:.3f}')
    return lines


def linuxcnc_probe_move(axis, target, feed, label):
    axis = str(axis).upper()
    lines = []
    lines.append(f'({label})')
    lines.append(f'G38.2 {axis}{float(target):.3f} F{float(feed):.3f}')
    lines.append(f'(Probe result: X=#5061 Y=#5062 Z=#5063 A=#5064 success=#5070)')
    return lines


def generiere_linuxcnc_vermess_gcode(cfg, config_file=None):
    """Generate a conservative LinuxCNC probing program for cutter setup."""
    errors = validate_probe_config(cfg)
    if errors:
        raise ValueError('Fehler in Vermess-Konfiguration:\n- ' + '\n- '.join(errors))
    p = probe_config(cfg)
    if not p:
        raise ValueError('Keine Section "aktionen.vermessen" in der Konfiguration gefunden.')

    ausgabe = p.get('ausgabe_datei', 'fraeser_vermessen.ngc')
    feed = float(p.get('probe_feed', 50.0))
    retract = float(p.get('retract', 2.0))
    safe_z = float(p.get('safe_z', cfg.get('maschine', {}).get('safe_z', 20.0)))
    lines = gcode_linuxcnc_probe_header(cfg, config_file)
    lines.append(f'(Tastkugel Durchmesser: {probe_ball_radius(cfg) * 2.0:.3f} mm)')

    front_target = p.get('front_x_probe_target')
    if front_target is not None:
        lines += linuxcnc_probe_move('X', front_target, feed, 'Stirnkante in X antasten')
        lines.append(f'G0 X[#5061 + {retract:.3f}]')

    diameter_target = p.get('diameter_z_probe_target')
    if diameter_target is not None:
        lines.append(f'G0 Z{safe_z:.3f}')
        lines += linuxcnc_probe_move('Z', diameter_target, feed, 'Aussendurchmesser in Z antasten')
        lines.append(f'G0 Z[#5063 + {retract:.3f}]')

    helix_points = p.get('drall_messpunkte', [])
    if helix_points:
        lines.append('(Drallmessung: jede Messposition manuell/halbautomatisch auf dieselbe Schneide ausrichten)')
        for idx, point in enumerate(helix_points, start=1):
            x = float(point.get('x', 0.0))
            z = float(point.get('z_sicher', safe_z))
            lines.append(f'(Drall Messpunkt {idx})')
            lines.append(f'G0 Z{z:.3f}')
            lines.append(f'G0 X{x:.3f}')
            if 'z_probe_target' in point:
                lines += linuxcnc_probe_move('Z', point['z_probe_target'], feed, f'Drall Messpunkt {idx} Z antasten')
                lines.append(f'G0 Z[#5063 + {retract:.3f}]')

    lines.append(f'G0 Z{safe_z:.3f}')
    lines.append('M30')
    lines.append('%')
    ensure_gcode_within_machine_limits(lines, cfg)
    with open(ausgabe, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(lines))
    print(f'Vermess-G-Code erzeugt: {ausgabe}')


# -------------------------------------------------
# FRONT G-CODE GENERATOR: FRONTFLÄCHEN SCHÄRFEN
# -------------------------------------------------

def gcode_front_header(cfg, config_file=None):
    from datetime import datetime
    m = cfg.get('maschine', {})
    # Support new structure: aktionen.front or old structure: front
    f = cfg.get('aktionen', {}).get('front') if 'aktionen' in cfg else cfg.get('front', {})
    # Support new structure: schleifscheibe_Front or old structure: schleifscheibe
    s = cfg.get('schleifscheibe_Front', cfg.get('schleifscheibe', {}))
    lines = []
    lines.append('%')
    lines.append('(Front-Grinder G-Code)')
    lines.append(f"(Erstellt: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')})")
    if config_file:
        lines.append(f"(Vorlage: {config_file})")
    if m.get('nullpunkt') and m['nullpunkt'].get('code'):
        lines.append(m['nullpunkt']['code'])
    # Werkzeugwechsel (optional) - use schleifscheibe_Front if available
    tool_no = s.get('tool_number')
    if tool_no is not None:
        try:
            tn = int(tool_no)
            lines.append(f"T{tn} M6   (Werkzeugwechsel Front)")
        except Exception:
            lines.append(f"(Ungültige tool_number: {tool_no})")
    # Anfahren der Sicherheitshöhe
    lines.append(f"G0 Z{z_von_oberer_tangente(cfg, f.get('z_sicher', 5.0)):.3f}")
    # Spindel starten in Sicherheitshöhe
    sp = s.get('drehzahl', f.get('spindle'))
    if sp:
        try:
            sv = int(sp)
            lines.append(f"M3 S{sv}   (Spindel ein)")
            dwell = int(f.get('spindle_dwell_ms', 1000))
            lines.append(f"G4 P{dwell/1000.0}")
        except Exception:
            lines.append(f"(Ungültiger Spindelwert: {sp})")
    lines.append('G90 G94')
    
    # Calculate and move to Y offset position (once at start)
    cutting_angle = f.get('cutting_angle', 0.0)
    if cutting_angle > 0:
        grinding_wheel_radius = float(s.get('durchmesser', 100.0)) / 2.0
        angle_rad = math.radians(cutting_angle)
        y_offset = grinding_wheel_radius * math.sin(angle_rad)
        y_start = m.get('start_y', 0.0)
        y_grinding = y_start - y_offset
        lines.append(f"(Y offset for cutting angle {cutting_angle}°: {y_offset:.3f})")
        lines.append(f"G0 Y{y_grinding:.3f}")
    
    return lines


def gcode_front_pass(cfg, idx, tiefe, start_x=None):
    # Support new structure: aktionen.front or old structure: front
    f = cfg.get('aktionen', {}).get('front') if 'aktionen' in cfg else cfg.get('front', {})
    # Support new structure: fraeser or old structure: werkzeug_front/werkzeug
    if 'fraeser' in cfg:
        w = cfg['fraeser']
    else:
        w = cfg.get('werkzeug_front', cfg.get('werkzeug', {}))
    # Support new structure: schleifscheibe_Front or old structure: schleifscheibe
    s = cfg.get('schleifscheibe_Front', cfg.get('schleifscheibe', {}))
    m = cfg.get('maschine', {})
    lines = []
    base_x1 = f.get('x_start', 0.0)
    feed = f.get('feed', 200.0)
    z_sicher = z_von_oberer_tangente(cfg, f.get('z_sicher', 5.0))
    retract_x = f.get('retract_x', m.get('safe_z', 5.0))

    # Determine actual start X for this pass
    if start_x is None:
        x1 = base_x1
    else:
        x1 = start_x

    # Tool radius
    radius = float(w.get('durchmesser', 0.0)) / 2.0
    # Z plunge: nur Fräserradius (nicht mehr depth-abhängig)
    z_plunge = 0.0
    
    # X Sicherheitsabstand (in Minus-Richtung vom Startpunkt)
    x_safe = x1 - float(retract_x)
    
    # Rückzugshöhe für sichere X-Bewegung (aus schleifscheibe_Front oder Fallback)
    safe_z_retract = z_von_oberer_tangente(
        cfg, s.get('rueckzug_hoehe_Z', f.get('rueckzug_hoehe_Z', 2.0))
    )

    # Vorbereitung: Anfahrt zum Startpunkt bei Sicherheitshöhe
    lines.append(f"(Pass {idx} at X {x1})")
    lines.append(f"G0 X{x1} Z{z_sicher:.3f}")
    
    # Für jede Schneide: Z senken → X minus → Z heben
    anz = int(w.get('schneidenanzahl', 1))
    base_a = m.get('a_start', 0.0)
    angle_step = 360.0 / max(1, anz)
    
    for sch in range(anz):
        a_pos = base_a + sch * angle_step
        lines.append(f"(Schneide {sch+1} | A={a_pos:.3f})")
        # Rotation zur Schneide
        lines.append(f"G0 A{a_pos:.3f}")
        # Z senken bis Fräserradius-Tiefe
        lines.append(f"G1 Z{z_plunge:.3f} F{feed}")
        # X in Minus-Richtung auf Sicherheitsabstand
        lines.append(f"G1 X{x_safe} F{feed}")
        # Z heben auf sichere Höhe (Z0 + Sicherheitsabstand) um Schneidekante zu schützen
        lines.append(f"G0 Z{safe_z_retract:.3f}")
        # Zurück zur Startposition X (für nächste Schneide)
        lines.append(f"G0 X{x1}")
        # Z auf Arbeitshöhe für nächste Schneide (nur wenn nicht letzte Schneide)
        if sch < anz - 1:
            lines.append(f"G0 Z{z_sicher:.3f}")
    
    return lines


def gcode_front_footer(cfg):
    m = cfg.get('maschine', {})
    f = cfg.get('aktionen', {}).get('front') if 'aktionen' in cfg else cfg.get('front', {})
    lines = []
    # Return to start Y position
    y_start = m.get('start_y', 0.0)
    lines.append(f'G0 Y{y_start}')
    lines.append('G0 Z{0:.3f}'.format(z_von_oberer_tangente(cfg, f.get('z_sicher', 5.0))))
    lines.append('M5')
    lines.append('M30')
    return lines


def generiere_front_gcode(cfg, config_file=None):
    """Generate front-face grinding G-Code. Supports both old and new JSON structure."""
    # Support new structure: aktionen.front or old structure: front
    f = cfg.get('aktionen', {}).get('front') if 'aktionen' in cfg else cfg.get('front')
    if not f:
        raise ValueError('Keine Section "aktionen.front" oder "front" in der Konfiguration gefunden.')
    
    # ausgabe_datei from front section or fallback to ausgabe.datei
    ausgabe = f.get('ausgabe_datei') or cfg.get('ausgabe', {}).get('datei', 'fraeser_front.ngc')

    lines = []
    lines += gcode_front_header(cfg, config_file)

    base_x = f.get('x_start', 0.0)
    x_end = f.get('x_end', 10.0)
    x_step = f.get('zustellung_pro_pass', 0.01)  # x_step = zustellung_pro_pass
    
    # Berechne anzahl_passe automatisch aus (x_end - x_start) / zustellung_pro_pass
    distance = abs(x_end - base_x)
    anzahl_passe = math.ceil(distance / x_step) + 1 if x_step > 0 else 1
    
    for p in range(1, anzahl_passe + 1):
        # Compute start X for this pass
        current_start = base_x + (p - 1) * float(x_step)
        # Cap to x_end to avoid overshoot
        if (x_end >= base_x and current_start > x_end) or (x_end < base_x and current_start < x_end):
            current_start = x_end
        lines += gcode_front_pass(cfg, p, 0.0, start_x=current_start)
        # Stop wenn x_end erreicht
        if abs(current_start - x_end) < 0.0001:
            break

    lines += gcode_front_footer(cfg)

    ensure_gcode_within_machine_limits(lines, cfg)

    with open(ausgabe, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(lines))

    print(f'Front G-Code erzeugt: {ausgabe}')


# --- JSON-Editor (Tkinter) ----------------------------------------------

def edit_config_gui(path):
    """Öffnet ein Textfenster zum Editieren der JSON-Datei.
    Gibt den finalen Pfad zurück (bei Save As möglich) oder None wenn abgebrochen.
    """
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox
    except Exception:
        return path

    # Read current content
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        content = f"(Fehler beim Lesen der Datei: {e})\n"

    final_path = path
    saved = {'flag': False}

    def do_save(save_path):
        data = text.get('1.0', 'end-1c')
        # Validate JSON
        try:
            json.loads(data)
        except Exception as e:
            messagebox.showerror('Ungültiges JSON', f'JSON-Fehler: {e}')
            return False
        try:
            with open(save_path, 'w', encoding='utf-8') as f:
                f.write(data)
            saved['flag'] = True
            messagebox.showinfo('Gespeichert', f'Datei gespeichert: {save_path}')
            return True
        except Exception as e:
            messagebox.showerror('Fehler', f'Fehler beim Speichern: {e}')
            return False

    def on_save():
        nonlocal final_path
        if do_save(final_path):
            # Update last path
            save_last_config_path(final_path)

    def on_create_template():
        """Erstellt ein neues JSON-Template mit Standardwerten"""
        nonlocal final_path
        if not saved['flag']:
            response = messagebox.askyesnocancel(
                'Nicht gespeicherte Änderungen',
                'Es gibt nicht gespeicherte Änderungen. Möchten Sie diese speichern?'
            )
            if response is None:  # Cancel
                return
            if response:  # Yes
                if not do_save(final_path):
                    on_save_as()
        
        # Template-Struktur
        template = {
            "maschine": {
                "safe_z": 20.0,
                "start_x": 0.0,
                "start_y": 0.0,
                "a_start": 0.0,
                "a_end": 360.0,
                "a_steps": 360,
                "feed_traverse": 800.0,
                "nullpunkt": {
                    "code": "G54",
                    "x": 0.0,
                    "y": 0.0,
                    "z": 0.0,
                    "a": 0.0
                }
            },
            "schleifscheibe_Schneiden": {
                "durchmesser": 100.0,
                "drehzahl": 3000,
                "tool_number": 1,
                "schleifvorschub": 200.0,
                "zustellung_pro_pass": 0.05
            },
            "schleifscheibe_Front": {
                "durchmesser": 80.0,
                "drehzahl": 3500,
                "tool_number": 2,
                "schleifvorschub": 200.0,
                "rueckzug_hoehe_Z": 2.0
            },
            "fraeser": {
                "durchmesser": 12.0,
                "schneidenanzahl": 4,
                "drall_grad_pro_mm": 2.0,
                "schneidenlaenge": 10.0
            },
            "aktionen": {
                "schneiden": {
                    "durchmesser_geschaerft": 11.5,
                    "zustellung_pro_pass": 0.05,
                    "erster_ruecken_grad": 20.0,
                    "ruecken_grad": 220.0,
                    "ruecken_tiefe_delta": 0.02,
                    "ruecken_schritte": 10,
                    "feed": 200.0,
                    "ausgabe_datei": "fraeser_kanten.ngc"
                },
                "front": {
                    "zustellung_pro_pass": 0.01,
                    "max_tiefe": -0.5,
                    "x_start": 0.0,
                    "x_end": 3.0,
                    "z_sicher": 5.0,
                    "feed": 200.0,
                    "ausgabe_datei": "fraeser_front.ngc",
                    "retract_x": 1.0,
                    "spindle_on_first_pass": True,
                    "spindle_dwell_ms": 1000,
                    "cutting_angle": 3.0
                }
            }
        }
        
        # Template im Editor anzeigen
        pretty = json.dumps(template, indent=4, ensure_ascii=False)
        text.delete('1.0', 'end')
        text.insert('1.0', pretty)
        apply_syntax_highlight()
        update_line_numbers()
        update_status()
        saved['flag'] = False
        final_path = None  # Zurücksetzen, da es sich um ein neues Dokument handelt
        root.title("Grinder — Konfigurationseditor — Neues Template")
        
        # Direkt als neues Dokument speichern lassen
        if messagebox.askyesno('Template erstellt', 'Neues Template wurde erstellt. Möchten Sie es jetzt speichern?'):
            on_save_as()

    def on_save_as():
        nonlocal final_path
        # Bestimme initialdir aus final_path
        initialdir = os.path.dirname(final_path) if final_path else None
        initialfile = os.path.basename(final_path) if final_path else None
        newp = filedialog.asksaveasfilename(title='Speichern unter', defaultextension='.json', filetypes=[('JSON', '*.json'), ('Alle Dateien', '*.*')], initialdir=initialdir, initialfile=initialfile)
        if newp:
            if do_save(newp):
                final_path = newp

    def on_open():
        nonlocal final_path
        newp = filedialog.askopenfilename(title='Öffnen', filetypes=[('JSON', '*.json'), ('Alle Dateien', '*.*')])
        if not newp:
            return
        try:
            with open(newp, 'r', encoding='utf-8') as f:
                data = f.read()
            # Set content
            text.delete('1.0', 'end')
            text.insert('1.0', data)
            final_path = newp
            saved['flag'] = False
            root.title(f"Grinder — Konfigurationseditor — {os.path.basename(final_path)}")
            apply_syntax_highlight()
            update_line_numbers()
            update_status()
        except Exception as e:
            messagebox.showerror('Fehler', f'Fehler beim Öffnen der Datei: {e}')

    def on_close():
        if saved['flag']:
            root.destroy()
        else:
            if messagebox.askyesno('Beenden', 'Änderungen wurden nicht gespeichert. Trotzdem beenden?'):
                root.destroy()

    def on_generate():
        """Validiert aktuelle JSON, führt die Sicherheit-Checklist und erzeugt den G-Code."""
        data = text.get('1.0', 'end-1c')
        valid, err = validate_json_string(data)
        if not valid:
            if not messagebox.askyesno('Ungültiges JSON', f'JSON ist ungültig:\n{err}\nTrotzdem fortfahren?'):
                return
        # Versuche zu parsen
        try:
            cfg = json.loads(data)
        except Exception as e:
            messagebox.showerror('Fehler', f'Kann JSON nicht parsen: {e}')
            return

        # Sicherheits-Checkliste (einfaches Modal)
        s_schneiden = cfg.get('schleifscheibe_Schneiden', {})
        checklist = [
            (f"safe_z (Sicherheitsabstand) = {cfg.get('maschine', {}).get('safe_z')}", 'safe_z'),
            (f"start_x = {cfg.get('maschine', {}).get('start_x')}", 'start_x'),
            (f"schleifscheibe_Schneiden.drehzahl = {s_schneiden.get('drehzahl')}", 'drehzahl'),
            (f"schleifscheibe_Schneiden.schleifvorschub = {s_schneiden.get('schleifvorschub')}", 'schleifvorschub')
        ]
        check_text = '\n'.join([c[0] for c in checklist])
        if not messagebox.askyesno('Sicherheits-Checkliste', f'Bitte überprüfen Sie vor dem Start die folgenden Werte:\n\n{check_text}\n\nIst alles in Ordnung?'):
            return

        # Falls noch nicht gespeichert, frage nach Speichern
        if not final_path or not os.path.exists(final_path) or not saved['flag']:
            if messagebox.askyesno('Speichern', 'Konfiguration speichern bevor G-Code erzeugt wird?'):
                if not do_save(final_path):
                    # Falls save failed oder kein Pfad -> Save As
                    if messagebox.askyesno('Speichern unter', 'Soll die Konfiguration unter einem neuen Namen gespeichert werden?'):
                        on_save_as()

        # Erzeuge G-Code mit aktuellem cfg
        try:
            generiere_gcode(cfg, os.path.basename(final_path) if final_path else None)
            out = cfg.get('ausgabe', {}).get('datei', '(keine ausgabe.datei gesetzt)')
            messagebox.showinfo('G-Code erzeugt', f'G-Code wurde erzeugt:\n{out}')
            saved['flag'] = True
            save_last_config_path(final_path)
            update_status()

            # Option: Ordner öffnen
            if messagebox.askyesno('Öffnen?', 'Ordner mit der erzeugten Datei im Explorer öffnen?'):
                try:
                    folder = os.path.abspath(os.path.dirname(out))
                    if os.name == 'nt':
                        os.startfile(folder)
                    else:
                        import subprocess
                        subprocess.Popen(['xdg-open', folder])
                except Exception as e:
                    messagebox.showerror('Fehler', f'Ordner konnte nicht geöffnet werden: {e}')

        except Exception as e:
            messagebox.showerror('Fehler beim Generieren', f'Fehler beim Erzeugen des G-Codes: {e}')

    def on_generate_front():
        """Validiert aktuelle JSON, führt die Sicherheit-Checklist und erzeugt den Front G-Code."""
        data = text.get('1.0', 'end-1c')
        valid, err = validate_json_string(data)
        if not valid:
            if not messagebox.askyesno('Ungültiges JSON', f'JSON ist ungültig:\n{err}\nTrotzdem fortfahren?'):
                return
        # Versuche zu parsen
        try:
            cfg = json.loads(data)
        except Exception as e:
            messagebox.showerror('Fehler', f'Kann JSON nicht parsen: {e}')
            return

        # Validiere Front-Konfiguration
        ok, errors = validate_front_config(cfg)
        if not ok:
            err_msg = '\n'.join(errors)
            if not messagebox.askyesno('Front-Konfiguration fehlerhaft', f'Fehler in Front-Konfiguration:\n{err_msg}\n\nTrotzdem fortfahren?'):
                return

        # Sicherheits-Checkliste (einfaches Modal)
        s_front = cfg.get('schleifscheibe_Front', {})
        f = cfg.get('aktionen', {}).get('front', cfg.get('front', {}))
        checklist = [
            (f"z_sicher (Sicherheitshöhe) = {f.get('z_sicher')}", 'z_sicher'),
            (f"x_start = {f.get('x_start')}", 'x_start'),
            (f"x_end = {f.get('x_end')}", 'x_end'),
            (f"front.feed = {f.get('feed')}", 'feed'),
            (f"schleifscheibe_Front.drehzahl = {s_front.get('drehzahl')}", 'drehzahl')
        ]
        check_text = '\n'.join([c[0] for c in checklist])
        if not messagebox.askyesno('Sicherheits-Checkliste Front', f'Bitte überprüfen Sie vor dem Start die folgenden Werte:\n\n{check_text}\n\nIst alles in Ordnung?'):
            return

        # Falls noch nicht gespeichert, frage nach Speichern
        if not final_path or not os.path.exists(final_path) or not saved['flag']:
            if messagebox.askyesno('Speichern', 'Konfiguration speichern bevor Front G-Code erzeugt wird?'):
                if not do_save(final_path):
                    # Falls save failed oder kein Pfad -> Save As
                    if messagebox.askyesno('Speichern unter', 'Soll die Konfiguration unter einem neuen Namen gespeichert werden?'):
                        on_save_as()

        # Erzeuge Front G-Code mit aktuellem cfg
        try:
            generiere_front_gcode(cfg, os.path.basename(final_path) if final_path else None)
            out = f.get('ausgabe_datei', cfg.get('ausgabe', {}).get('datei', 'fraeser_front.ngc'))
            messagebox.showinfo('Front G-Code erzeugt', f'Front G-Code wurde erzeugt:\n{out}')
            saved['flag'] = True
            save_last_config_path(final_path)
            update_status()

            # Option: Ordner öffnen
            if messagebox.askyesno('Öffnen?', 'Ordner mit der erzeugten Datei im Explorer öffnen?'):
                try:
                    folder = os.path.abspath(os.path.dirname(out))
                    if os.name == 'nt':
                        os.startfile(folder)
                    else:
                        import subprocess
                        subprocess.Popen(['xdg-open', folder])
                except Exception as e:
                    messagebox.showerror('Fehler', f'Ordner konnte nicht geöffnet werden: {e}')

        except Exception as e:
            messagebox.showerror('Fehler beim Generieren', f'Fehler beim Erzeugen des Front G-Codes: {e}')

    def on_insert_front():
        data = text.get('1.0', 'end-1c')
        valid, err = validate_json_string(data)
        if not valid:
            if not messagebox.askyesno('Ungültiges JSON', f'JSON ist ungültig: {err}\nVorlage trotzdem einfügen (Bestehende Werte könnten überschrieben werden)?'):
                return
            cfg = {}
        else:
            try:
                cfg = json.loads(data)
            except Exception:
                cfg = {}
        if 'front' in cfg:
            if not messagebox.askyesno('Ersetzen?', 'Section "front" existiert bereits. Überschreiben?'):
                return
        cfg['front'] = {
            "anzahl_passe": 5,
            "zustellung_pro_pass": 0.05,
            "max_tiefe": -0.5,
            "x_start": 0.0,
            "x_end": 10.0,
            "z_sicher": 5.0,
            "feed": 200.0,
            "spindle": 3000,
            "ausgabe_datei": "fraeser_front.ngc"
        }
        pretty = json.dumps(cfg, indent=4, ensure_ascii=False)
        text.delete('1.0', 'end')
        text.insert('1.0', pretty)
        apply_syntax_highlight()
        update_line_numbers()
        update_status()
        saved['flag'] = False

    def on_validate_front():
        data = text.get('1.0', 'end-1c')
        valid, err = validate_json_string(data)
        if not valid:
            messagebox.showerror('Ungültiges JSON', f'JSON-Fehler: {err}')
            return
        cfg = json.loads(data)
        ok, errors = validate_front_config(cfg)
        if ok:
            messagebox.showinfo('Validierung', 'Front-Konfiguration ist gültig.')
        else:
            messagebox.showerror('Fehler in Front-Konfiguration', '\n'.join(errors))

    def on_preview_front():
        data = text.get('1.0', 'end-1c')
        valid, err = validate_json_string(data)
        if not valid:
            messagebox.showerror('Ungültiges JSON', f'JSON-Fehler: {err}')
            return
        cfg = json.loads(data)
        starts = compute_front_start_positions(cfg)
        if not starts:
            messagebox.showinfo('Keine Front-Section', 'Kein Abschnitt "front" in der Konfiguration gefunden.')
            return
        # Show modal with preview table
        pv = tk.Toplevel(root)
        pv.title('Front Passes Vorschau')
        pv.geometry('400x300')
        lbl = tk.Label(pv, text='Pass	Start X	Depth (Z)')
        lbl.pack(anchor='w', padx=6, pady=6)
        txt = tk.Text(pv, wrap='none', font=('Consolas', 10), height=10)
        txt.pack(fill='both', expand=True, padx=6, pady=6)
        for p, sx, d in starts:
            txt.insert('end', f"{p}\t{sx}\t{d}\n")
        btnf = tk.Frame(pv)
        btnf.pack(fill='x')
        def do_copy():
            pv.clipboard_clear()
            pv.clipboard_append(txt.get('1.0', 'end-1c'))
            messagebox.showinfo('Kopiert', 'Vorschau in Zwischenablage kopiert')
        copy_btn = tk.Button(btnf, text='Kopieren', command=do_copy)
        copy_btn.pack(side='left', padx=6, pady=6)
        close_btn2 = tk.Button(btnf, text='Schließen', command=pv.destroy)
        close_btn2.pack(side='right', padx=6, pady=6)

    def on_upload_edge():
        """Upload Edge G-Code to server"""
        data = text.get('1.0', 'end-1c')
        try:
            cfg = json.loads(data)
        except Exception as e:
            messagebox.showerror('Fehler', f'Kann JSON nicht parsen: {e}')
            return
        
        # Get output filename
        if 'aktionen' in cfg and 'schneiden' in cfg['aktionen']:
            out = cfg['aktionen']['schneiden'].get('ausgabe_datei', 'fraeser_kanten.ngc')
        else:
            out = cfg.get("ausgabe", {}).get("datei", "fraeser_schaerfen.ngc")
        
        if not os.path.exists(out):
            messagebox.showerror('Fehler', f'Datei nicht gefunden: {out}\\nBitte zuerst G-Code generieren.')
            return
        
        # Select server
        servers = load_servers()
        if not servers:
            if messagebox.askyesno('Keine Server', 'Keine Server konfiguriert. Möchten Sie welche anlegen?'):
                manage_servers_gui(root)
                servers = load_servers()
        
        if servers:
            choices = [f"{s.get('name')} ({s.get('type')}@{s.get('host')})" for s in servers]
            import tkinter as tk
            from tkinter import simpledialog
            sel = simpledialog.askinteger('Server wählen', '\\n'.join([f"{i+1}: {c}" for i, c in enumerate(choices)]) + '\\n\\nGeben Sie die Nummer ein:', parent=root, minvalue=1, maxvalue=len(choices))
            if sel is not None:
                target = servers[sel-1]
                try:
                    if target.get('type') == 'ftp':
                        upload_via_ftp(out, target)
                    else:
                        upload_via_sftp(out, target)
                    messagebox.showinfo('Upload', 'Upload erfolgreich')
                except Exception as e:
                    messagebox.showerror('Upload fehlgeschlagen', f'Fehler beim Upload: {e}')

    def on_upload_front():
        """Upload Front G-Code to server"""
        data = text.get('1.0', 'end-1c')
        try:
            cfg = json.loads(data)
        except Exception as e:
            messagebox.showerror('Fehler', f'Kann JSON nicht parsen: {e}')
            return
        
        # Get output filename
        f = cfg.get('aktionen', {}).get('front', cfg.get('front', {}))
        out = f.get('ausgabe_datei', 'fraeser_front.ngc')
        
        if not os.path.exists(out):
            messagebox.showerror('Fehler', f'Datei nicht gefunden: {out}\\nBitte zuerst G-Code generieren.')
            return
        
        # Select server
        servers = load_servers()
        if not servers:
            if messagebox.askyesno('Keine Server', 'Keine Server konfiguriert. Möchten Sie welche anlegen?'):
                manage_servers_gui(root)
                servers = load_servers()
        
        if servers:
            choices = [f"{s.get('name')} ({s.get('type')}@{s.get('host')})" for s in servers]
            import tkinter as tk
            from tkinter import simpledialog
            sel = simpledialog.askinteger('Server wählen', '\\n'.join([f"{i+1}: {c}" for i, c in enumerate(choices)]) + '\\n\\nGeben Sie die Nummer ein:', parent=root, minvalue=1, maxvalue=len(choices))
            if sel is not None:
                target = servers[sel-1]
                try:
                    if target.get('type') == 'ftp':
                        upload_via_ftp(out, target)
                    else:
                        upload_via_sftp(out, target)
                    messagebox.showinfo('Upload', 'Upload erfolgreich')
                except Exception as e:
                    messagebox.showerror('Upload fehlgeschlagen', f'Fehler beim Upload: {e}')

    root = tk.Tk()
    root.title(f"Grinder — Konfigurationseditor — {os.path.basename(path)}")
    root.geometry('900x600')

    # Menüleiste erstellen
    menubar = tk.Menu(root)
    root.config(menu=menubar)

    # Datei-Menü
    file_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="Datei", menu=file_menu)
    file_menu.add_command(label="Neues Template...", command=on_create_template, accelerator="Ctrl+N")
    file_menu.add_separator()
    file_menu.add_command(label="Öffnen...", command=on_open, accelerator="Ctrl+O")
    file_menu.add_command(label="Speichern", command=on_save, accelerator="Ctrl+S")
    file_menu.add_command(label="Speichern unter...", command=on_save_as, accelerator="Ctrl+Shift+S")
    file_menu.add_separator()
    file_menu.add_command(label="Schließen", command=on_close, accelerator="Ctrl+Q")

    # Bearbeiten-Menü
    edit_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="Bearbeiten", menu=edit_menu)
    edit_menu.add_command(label="Formatieren", command=lambda: do_format_action(), accelerator="Ctrl+F")
    edit_menu.add_separator()
    edit_menu.add_command(label="Insert Front Template", command=on_insert_front)
    edit_menu.add_command(label="Validate Front", command=on_validate_front)
    edit_menu.add_command(label="Preview Front Passes", command=on_preview_front)

    # G-Code-Menü
    gcode_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="G-Code", menu=gcode_menu)
    gcode_menu.add_command(label="Erzeugen (Edge)", command=on_generate, accelerator="F5")
    gcode_menu.add_command(label="Erzeugen (Front)", command=on_generate_front, accelerator="F6")
    gcode_menu.add_separator()
    gcode_menu.add_command(label="Upload Edge", command=on_upload_edge)
    gcode_menu.add_command(label="Upload Front", command=on_upload_front)

    # Einstellungen-Menü
    settings_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="Einstellungen", menu=settings_menu)
    settings_menu.add_command(label="Server verwalten...", command=lambda: manage_servers_gui(root))

    # Hilfe-Menü
    help_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="Hilfe", menu=help_menu)
    help_menu.add_command(label="Über Grinder", command=lambda: messagebox.showinfo("Über Grinder", "Grinder CNC G-Code Generator\n\nFür Fräser-Schärfoperationen\nVersion 1.0"))

    # Keyboard shortcuts
    root.bind('<Control-n>', lambda e: on_create_template())
    root.bind('<Control-o>', lambda e: on_open())
    root.bind('<Control-s>', lambda e: on_save())
    root.bind('<Control-Shift-S>', lambda e: on_save_as())
    root.bind('<Control-q>', lambda e: on_close())
    root.bind('<Control-f>', lambda e: do_format_action())
    root.bind('<F5>', lambda e: on_generate())
    root.bind('<F6>', lambda e: on_generate_front())

    # Toolbar (reduziert) - nur wichtigste Buttons
    btn_frame = tk.Frame(root)
    btn_frame.pack(fill='x')

    gen_btn = tk.Button(btn_frame, text='G-Code (Edge)', command=on_generate)
    gen_btn.pack(side='left', padx=4, pady=4)
    gen_front_btn = tk.Button(btn_frame, text='G-Code (Front)', command=on_generate_front)
    gen_front_btn.pack(side='left', padx=4, pady=4)
    upload_edge_btn = tk.Button(btn_frame, text='Upload Edge', command=on_upload_edge)
    upload_edge_btn.pack(side='left', padx=4, pady=4)
    upload_front_btn = tk.Button(btn_frame, text='Upload Front', command=on_upload_front)
    upload_front_btn.pack(side='left', padx=4, pady=4)
    save_btn = tk.Button(btn_frame, text='Speichern', command=on_save)
    save_btn.pack(side='left', padx=4, pady=4)

    # Main area: line numbers + text with scrollbars
    frame = tk.Frame(root)
    frame.pack(fill='both', expand=True)

    lineno = tk.Text(frame, width=6, padx=4, pady=4, takefocus=0, borderwidth=0, background='#f0f0f0', state='disabled', font=('Consolas',10))
    lineno.pack(side='left', fill='y')

    text_frame = tk.Frame(frame)
    text_frame.pack(side='left', fill='both', expand=True)

    text = tk.Text(text_frame, wrap='none', font=('Consolas', 10), undo=True)
    text.insert('1.0', content)
    text.pack(fill='both', expand=True, side='left')

    yscroll = tk.Scrollbar(text_frame, orient='vertical', command=lambda *args: (text.yview(*args), lineno.yview(*args)))
    yscroll.pack(side='right', fill='y')
    text.configure(yscrollcommand=yscroll.set)

    xscroll = tk.Scrollbar(root, orient='horizontal', command=text.xview)
    xscroll.pack(side='bottom', fill='x')
    text.configure(xscrollcommand=xscroll.set)

    def update_line_numbers(event=None):
        lines = int(text.index('end-1c').split('.')[0])
        lineno.config(state='normal')
        lineno.delete('1.0', 'end')
        for i in range(1, lines + 1):
            lineno.insert('end', f"{i}\n")
        lineno.config(state='disabled')

    def validate_json_string(s):
        try:
            json.loads(s)
            return True, None
        except Exception as e:
            return False, str(e)

    def update_status():
        data = text.get('1.0', 'end-1c')
        valid, err = validate_json_string(data)
        if valid:
            msg = 'Valid JSON'
        else:
            msg = f'Invalid JSON: {err}'
        idx = text.index('insert')
        # add bytes and saved status
        size = len(data.encode('utf-8'))
        saved_state = 'saved' if saved['flag'] else 'unsaved'
        status.set(f"{msg} | Cursor: {idx} | Size: {size} bytes | {saved_state}")
        return valid

    def apply_syntax_highlight():
        # Simple JSON regex based highlighting
        import re
        content = text.get('1.0', 'end-1c')
        # Clear tags
        for tag in ('string', 'number', 'bool', 'null', 'bracket', 'key'):
            text.tag_remove(tag, '1.0', 'end')
        if not content:
            return
        # Strings
        for m in re.finditer(r'"(.*?)(?<!\\)"', content):
            start = f"1.0+{m.start()}c"
            end = f"1.0+{m.end()}c"
            text.tag_add('string', start, end)
        # Keys ("...":)
        for m in re.finditer(r'"(.*?)(?<!\\)"\s*:', content):
            start = f"1.0+{m.start()}c"
            end = f"1.0+{m.end()-1}c"
            text.tag_add('key', start, end)
        # Numbers
        for m in re.finditer(r'(-?\b\d+\.?\d*([eE][-+]?\d+)?\b)', content):
            start = f"1.0+{m.start()}c"
            end = f"1.0+{m.end()}c"
            text.tag_add('number', start, end)
        # booleans
        for m in re.finditer(r'\b(true|false)\b', content):
            start = f"1.0+{m.start()}c"
            end = f"1.0+{m.end()}c"
            text.tag_add('bool', start, end)
        # null
        for m in re.finditer(r'\bnull\b', content):
            start = f"1.0+{m.start()}c"
            end = f"1.0+{m.end()}c"
            text.tag_add('null', start, end)
        # brackets
        for m in re.finditer(r'[\[\]\{\}]', content):
            start = f"1.0+{m.start()}c"
            end = f"1.0+{m.end()}c"
            text.tag_add('bracket', start, end)

    # Configure tags
    text.tag_configure('string', foreground='#a31515')
    text.tag_configure('key', foreground='#0451a5', font=('Consolas', 10, 'bold'))
    text.tag_configure('number', foreground='#098658')
    text.tag_configure('bool', foreground='#0000ff')
    text.tag_configure('null', foreground='#7a7a7a')
    text.tag_configure('bracket', foreground='#1e90ff', font=('Consolas', 10, 'bold'))

    def do_format_action():
        data = text.get('1.0', 'end-1c')
        try:
            obj = json.loads(data)
            pretty = json.dumps(obj, indent=4, ensure_ascii=False)
            text.delete('1.0', 'end')
            text.insert('1.0', pretty)
            update_line_numbers()
            update_status()
            apply_syntax_highlight()
        except Exception as e:
            messagebox.showerror('Formatieren fehlgeschlagen', f'JSON-Fehler: {e}')

    # Bind events
    text.bind('<KeyRelease>', lambda e: (update_line_numbers(), update_status(), apply_syntax_highlight()))
    text.bind('<ButtonRelease-1>', lambda e: update_status())
    text.bind('<Control-s>', lambda e: (on_save(), 'break'))
    text.bind('<Control-S>', lambda e: (on_save(), 'break'))
    text.bind('<Control-f>', lambda e: (do_format_action(), 'break'))

    # Status bar
    status = tk.StringVar()
    status.set('Bereit')
    status_label = tk.Label(root, textvariable=status, anchor='w')
    status_label.pack(fill='x', side='bottom')

    update_line_numbers()
    update_status()
    apply_syntax_highlight()

    # Make window modal
    root.protocol('WM_DELETE_WINDOW', on_close)
    root.mainloop()

    return final_path


# --- Ende JSON-Editor --------------------------------------------------


# --- Upload / Server Management -----------------------------------------
SERVERS_STATE = os.path.join(os.path.dirname(__file__), '.grinder_servers.json')


def load_servers():
    """Lädt Server-Einträge, versucht Passwörter aus Keyring zu ergänzen (falls genutzt)."""
    try:
        if os.path.exists(SERVERS_STATE):
            with open(SERVERS_STATE, 'r', encoding='utf-8') as f:
                servers = json.load(f)
                # Try to restore passwords from keyring if not present
                try:
                    import keyring
                except Exception:
                    keyring = None
                for s in servers:
                    if (not s.get('password')) and keyring:
                        pw = keyring.get_password('Grinder-'+s.get('name',''), s.get('username') or '')
                        if pw:
                            s['password'] = pw
                    # Try to restore key passphrase from keyring if not present
                    if (not s.get('key_passphrase')) and keyring:
                        kp = keyring.get_password('Grinder-key-'+s.get('name',''), s.get('username') or '')
                        if kp:
                            s['key_passphrase'] = kp
                return servers
    except Exception:
        pass
    return []


def save_servers(servers):
    """Speichert Server-Metadaten ohne Passwörter (wenn Keyring gewünscht) oder mit Passwörtern (fallback)."""
    # If keyring available and server has flag 'use_keyring', move password to keyring
    try:
        try:
            import keyring
        except Exception:
            keyring = None
        to_store = []
        for s in servers:
            s_copy = s.copy()
            if s_copy.get('use_keyring') and s_copy.get('password') and keyring:
                try:
                    keyring.set_password('Grinder-'+s_copy.get('name',''), s_copy.get('username') or '', s_copy.get('password'))
                except Exception:
                    pass
                # remove plain password from saved file
                s_copy.pop('password', None)
            # If a key passphrase is set and use_keyring requested, store it securely and remove from JSON
            if s_copy.get('use_keyring') and s_copy.get('key_passphrase') and keyring:
                try:
                    keyring.set_password('Grinder-key-'+s_copy.get('name',''), s_copy.get('username') or '', s_copy.get('key_passphrase'))
                except Exception:
                    pass
                s_copy.pop('key_passphrase', None)
            to_store.append(s_copy)
        with open(SERVERS_STATE, 'w', encoding='utf-8') as f:
            json.dump(to_store, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def upload_via_ftp(local_path, server):
    from ftplib import FTP
    host = server.get('host')
    port = int(server.get('port') or 21)
    user = server.get('username') or 'anonymous'
    pwd = server.get('password') or ''
    remote_dir = server.get('remote_path') or '.'
    with FTP() as ftp:
        ftp.connect(host, port, timeout=10)
        ftp.login(user, pwd)
        # change dir if needed
        try:
            ftp.cwd(remote_dir)
        except Exception:
            pass
        with open(local_path, 'rb') as f:
            ftp.storbinary(f'STOR {os.path.basename(local_path)}', f)


def upload_via_sftp(local_path, server):
    import paramiko
    host = server.get('host')
    port = int(server.get('port') or 22)
    user = server.get('username')
    pwd = server.get('password')
    keypath = server.get('key_path')
    remote_dir = server.get('remote_path') or '.'

    # Use SSHClient for better compatibility with banners and host key handling
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    # Prepare connection kwargs
    connect_kwargs = {
        'hostname': host,
        'port': port,
        'username': user,
        'timeout': 10,
        'banner_timeout': 200,  # Longer timeout for banner
        'auth_timeout': 30
    }
    
    # Try key-based authentication first
    if keypath:
        passphrase = server.get('key_passphrase')
        try:
            import keyring
        except Exception:
            keyring = None
        if (not passphrase) and keyring and server.get('use_keyring'):
            passphrase = keyring.get_password('Grinder-key-'+server.get('name',''), user or '')
        
        # Try to load the key
        key = None
        last_exc = None
        for key_class in [paramiko.Ed25519Key, paramiko.RSAKey, paramiko.ECDSAKey]:
            try:
                key = key_class.from_private_key_file(keypath, password=passphrase)
                break
            except Exception as e:
                last_exc = e
        
        # If key loading failed and no passphrase, prompt for one
        if key is None and not passphrase:
            try:
                import tkinter as tk
                from tkinter import simpledialog
                root = tk.Tk()
                root.withdraw()
                p = simpledialog.askstring('Passphrase', f'Passphrase für Schlüssel {keypath}:', show='*')
                root.destroy()
                if p:
                    for key_class in [paramiko.Ed25519Key, paramiko.RSAKey, paramiko.ECDSAKey]:
                        try:
                            key = key_class.from_private_key_file(keypath, password=p)
                            if keyring and server.get('use_keyring'):
                                try:
                                    keyring.set_password('Grinder-key-'+server.get('name',''), user or '', p)
                                except Exception:
                                    pass
                            break
                        except Exception as e:
                            last_exc = e
            except Exception:
                pass
        
        if key:
            connect_kwargs['pkey'] = key
        else:
            raise RuntimeError(f'Unable to load private key {keypath}: {last_exc}')
    elif pwd:
        connect_kwargs['password'] = pwd
    else:
        # Try agent and look for keys
        connect_kwargs['allow_agent'] = True
        connect_kwargs['look_for_keys'] = True
    
    try:
        client.connect(**connect_kwargs)
        sftp = client.open_sftp()
        try:
            try:
                sftp.chdir(remote_dir)
            except IOError:
                try:
                    sftp.mkdir(remote_dir)
                    sftp.chdir(remote_dir)
                except Exception:
                    sftp.chdir('.')
            sftp.put(local_path, os.path.basename(local_path))
        finally:
            sftp.close()
            client.close()
    except Exception as e:
        client.close()
        raise RuntimeError(f'SFTP Upload fehlgeschlagen: {e}')


def manage_servers_gui(parent):
    try:
        import tkinter as tk
        from tkinter import simpledialog, messagebox, filedialog
    except Exception:
        return

    servers = load_servers()

    dlg = tk.Toplevel(parent)
    dlg.title('Grinder — Server Verwaltung')
    dlg.geometry('700x420')

    listbox = tk.Listbox(dlg)
    listbox.pack(fill='both', expand=True)

    def refresh_list():
        listbox.delete(0, 'end')
        for s in servers:
            listbox.insert('end', f"{s.get('name')} ({s.get('type')}@{s.get('host')}:{s.get('port')})")

    def add_server():
        # Detailed addition dialog
        form = tk.Toplevel(dlg)
        form.title('Neuer Server')
        tk.Label(form, text='Name').grid(row=0, column=0)
        name_e = tk.Entry(form)
        name_e.grid(row=0, column=1)
        tk.Label(form, text='Typ (ftp|sftp)').grid(row=1, column=0)
        type_e = tk.Entry(form)
        type_e.insert(0, 'sftp')
        type_e.grid(row=1, column=1)
        tk.Label(form, text='Host').grid(row=2, column=0)
        host_e = tk.Entry(form)
        host_e.grid(row=2, column=1)
        tk.Label(form, text='Port').grid(row=3, column=0)
        port_e = tk.Entry(form)
        port_e.insert(0, '22')
        port_e.grid(row=3, column=1)
        tk.Label(form, text='Benutzer').grid(row=4, column=0)
        user_e = tk.Entry(form)
        user_e.grid(row=4, column=1)
        tk.Label(form, text='Passwort').grid(row=5, column=0)
        pwd_e = tk.Entry(form, show='*')
        pwd_e.grid(row=5, column=1)
        tk.Label(form, text='Remote Pfad').grid(row=6, column=0)
        rpath_e = tk.Entry(form)
        rpath_e.insert(0, '.')
        rpath_e.grid(row=6, column=1)
        tk.Label(form, text='Key-Pfad (SFTP)').grid(row=7, column=0)
        key_e = tk.Entry(form)
        key_e.grid(row=7, column=1)
        def browse_key():
            p = filedialog.askopenfilename(title='Key-Datei wählen')
            if p:
                key_e.delete(0, 'end')
                key_e.insert(0, p)
        tk.Button(form, text='Key wählen', command=browse_key).grid(row=7, column=2)
        use_keyring_var = tk.IntVar(value=1)
        tk.Checkbutton(form, text='Password im System-Keyring speichern', variable=use_keyring_var).grid(row=8, column=0, columnspan=2)
        tk.Label(form, text='Timeout (s)').grid(row=9, column=0)
        timeout_e = tk.Entry(form)
        timeout_e.insert(0, '10')
        timeout_e.grid(row=9, column=1)
        passive_var = tk.IntVar(value=1)
        tk.Checkbutton(form, text='FTP passive', variable=passive_var).grid(row=10, column=0, columnspan=2)
        def do_add():
            name = name_e.get().strip()
            if not name:
                messagebox.showerror('Fehler', 'Name erforderlich')
                return
            stype = type_e.get().strip() or 'sftp'
            server = {
                'name': name,
                'type': stype,
                'host': host_e.get().strip(),
                'port': port_e.get().strip(),
                'username': user_e.get().strip(),
                'password': pwd_e.get().strip(),
                'remote_path': rpath_e.get().strip(),
                'key_path': key_e.get().strip(),
                'use_keyring': bool(use_keyring_var.get()),
                'timeout': int(timeout_e.get().strip() or 10),
                'ftp_passive': bool(passive_var.get())
            }
            servers.append(server)
            save_servers(servers)
            refresh_list()
            form.destroy()
        tk.Button(form, text='Hinzufügen', command=do_add).grid(row=11, column=0, columnspan=3)

    def delete_server():
        sel = listbox.curselection()
        if not sel:
            return
        i = sel[0]
        if messagebox.askyesno('Löschen', f'Server {servers[i].get("name")} löschen?'):
            servers.pop(i)
            save_servers(servers)
            refresh_list()

    def edit_server():
        sel = listbox.curselection()
        if not sel:
            return
        i = sel[0]
        s = servers[i]
        form = tk.Toplevel(dlg)
        form.title('Server bearbeiten')
        tk.Label(form, text='Name').grid(row=0, column=0)
        name_e = tk.Entry(form)
        name_e.insert(0, s.get('name',''))
        name_e.grid(row=0, column=1)
        tk.Label(form, text='Typ (ftp|sftp)').grid(row=1, column=0)
        type_e = tk.Entry(form)
        type_e.insert(0, s.get('type','sftp'))
        type_e.grid(row=1, column=1)
        tk.Label(form, text='Host').grid(row=2, column=0)
        host_e = tk.Entry(form)
        host_e.insert(0, s.get('host',''))
        host_e.grid(row=2, column=1)
        tk.Label(form, text='Port').grid(row=3, column=0)
        port_e = tk.Entry(form)
        port_e.insert(0, s.get('port','22'))
        port_e.grid(row=3, column=1)
        tk.Label(form, text='Benutzer').grid(row=4, column=0)
        user_e = tk.Entry(form)
        user_e.insert(0, s.get('username',''))
        user_e.grid(row=4, column=1)
        tk.Label(form, text='Passwort').grid(row=5, column=0)
        pwd_e = tk.Entry(form, show='*')
        pwd_e.insert(0, s.get('password',''))
        pwd_e.grid(row=5, column=1)
        tk.Label(form, text='Remote Pfad').grid(row=6, column=0)
        rpath_e = tk.Entry(form)
        rpath_e.insert(0, s.get('remote_path','.'))
        rpath_e.grid(row=6, column=1)
        tk.Label(form, text='Key-Pfad (SFTP)').grid(row=7, column=0)
        key_e = tk.Entry(form)
        key_e.insert(0, s.get('key_path',''))
        key_e.grid(row=7, column=1)
        def browse_key():
            p = filedialog.askopenfilename(title='Key-Datei wählen')
            if p:
                key_e.delete(0, 'end')
                key_e.insert(0, p)
        tk.Button(form, text='Key wählen', command=browse_key).grid(row=7, column=2)
        use_keyring_var = tk.IntVar(value=1 if s.get('use_keyring') else 0)
        tk.Checkbutton(form, text='Password im System-Keyring speichern', variable=use_keyring_var).grid(row=8, column=0, columnspan=2)
        tk.Label(form, text='Timeout (s)').grid(row=9, column=0)
        timeout_e = tk.Entry(form)
        timeout_e.insert(0, str(s.get('timeout', 10)))
        timeout_e.grid(row=9, column=1)
        passive_var = tk.IntVar(value=1 if s.get('ftp_passive') else 0)
        tk.Checkbutton(form, text='FTP passive', variable=passive_var).grid(row=10, column=0, columnspan=2)
        def do_update():
            s['name'] = name_e.get().strip()
            s['type'] = type_e.get().strip()
            s['host'] = host_e.get().strip()
            s['port'] = port_e.get().strip()
            s['username'] = user_e.get().strip()
            s['password'] = pwd_e.get().strip()
            s['remote_path'] = rpath_e.get().strip()
            s['key_path'] = key_e.get().strip()
            s['use_keyring'] = bool(use_keyring_var.get())
            s['timeout'] = int(timeout_e.get().strip() or 10)
            s['ftp_passive'] = bool(passive_var.get())
            save_servers(servers)
            refresh_list()
            form.destroy()
        tk.Button(form, text='Speichern', command=do_update).grid(row=11, column=0, columnspan=3)

    def test_connection():
        sel = listbox.curselection()
        if not sel:
            messagebox.showinfo('Info', 'Bitte wählen Sie einen Server aus')
            return
        s = servers[sel[0]]
        try:
            # get password from keyring if needed
            pwd = s.get('password')
            try:
                import keyring
            except Exception:
                keyring = None
            if (not pwd) and keyring and s.get('use_keyring'):
                pwd = keyring.get_password('Grinder-'+s.get('name',''), s.get('username') or '')
            if s.get('type') == 'ftp':
                from ftplib import FTP
                ftp = FTP()
                ftp.connect(s.get('host'), int(s.get('port') or 21), timeout=int(s.get('timeout',10)))
                if s.get('ftp_passive'):
                    ftp.set_pasv(True)
                if s.get('username'):
                    ftp.login(s.get('username'), pwd or '')
                else:
                    ftp.login()
                ftp.quit()
                messagebox.showinfo('OK', 'FTP Verbindung erfolgreich')
            else:
                import paramiko
                t = paramiko.Transport((s.get('host'), int(s.get('port') or 22)))
                if s.get('key_path'):
                    key = paramiko.RSAKey.from_private_key_file(s.get('key_path'))
                    t.connect(username=s.get('username'), pkey=key)
                else:
                    t.connect(username=s.get('username'), password=pwd or '')
                t.close()
                messagebox.showinfo('OK', 'SFTP Verbindung erfolgreich')
        except Exception as e:
            messagebox.showerror('Fehler', f'Verbindung fehlgeschlagen: {e}')

    btn_frame = tk.Frame(dlg)
    btn_frame.pack(fill='x')
    tk.Button(btn_frame, text='Hinzufügen', command=add_server).pack(side='left', padx=4, pady=4)
    tk.Button(btn_frame, text='Bearbeiten', command=edit_server).pack(side='left', padx=4, pady=4)
    tk.Button(btn_frame, text='Test Verbindung', command=test_connection).pack(side='left', padx=4, pady=4)
    tk.Button(btn_frame, text='Löschen', command=delete_server).pack(side='left', padx=4, pady=4)
    tk.Button(btn_frame, text='Schließen', command=dlg.destroy).pack(side='right', padx=4, pady=4)

    refresh_list()
# --- Ende Upload / Server Management ------------------------------------


# --- Ende GUI / state helpers -------------------------------------------


def gcode_header(cfg, config_file=None):
    from datetime import datetime
    m = cfg["maschine"]
    # Support new structure: schleifscheibe_Schneiden or old structure: schleifscheibe
    s = cfg.get("schleifscheibe_Schneiden", cfg.get("schleifscheibe", {}))

    lines = []
    lines.append("(Fräser Schärfen – automatisch generiert)")
    lines.append(f"(Erstellt: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')})")
    if config_file:
        lines.append(f"(Vorlage: {config_file})")
    lines.append("G21   (mm)")
    lines.append("G90   (absolute Positionierung)")
    lines.append("G17   (XY-Ebene)")
    lines.append(f"G0 Z{m['safe_z']:.3f}")

    # Werkzeugwechsel (optional, z.B. T1 M6) - use schleifscheibe_Schneiden if available
    tool_no = s.get("tool_number")
    if tool_no is not None:
        try:
            tool_no_int = int(tool_no)
            lines.append(f"T{tool_no_int} M6   (Werkzeugwechsel Edge)")
        except Exception:
            lines.append(f"(Ungültige tool_number: {tool_no})")

    # Spindel starten
    lines.append(f"S{s.get('drehzahl', 3000)} M3   (Spindel EIN, Schleifscheibe)")
    
    # Werkstück-Nullpunkt (optional, z.B. G54)
    nullpunkt = m.get("nullpunkt")
    if nullpunkt:
        code = nullpunkt.get("code", "G54")
        lines.append(f"{code}   (Werkstücknullpunkt)")
    
    # Position anfahren nach Nullpunkt
    lines.append(f"G0 X{m['start_x']:.3f} Y{m['start_y']:.3f} A{m['a_start']:.3f}")
    lines.append("")
    
    # optional: schnelle Verfahrbewegung zum Nullpunkt, falls definiert
    if nullpunkt:
        pos_parts = []
        if "x" in nullpunkt:
            pos_parts.append(f"X{nullpunkt['x']:.3f}")
        if "y" in nullpunkt:
            pos_parts.append(f"Y{nullpunkt['y']:.3f}")
        if "z" in nullpunkt:
            pos_parts.append(f"Z{nullpunkt['z']:.3f}")
        if "a" in nullpunkt:
            pos_parts.append(f"A{nullpunkt['a']:.3f}")
        if pos_parts:
            lines.append("G0 " + " ".join(pos_parts))
            lines.append("")

    return lines


def gcode_footer(cfg):
    m = cfg["maschine"]
    lines = []
    lines.append("(Ende Schleifprogramm)")
    lines.append(f"G0 Z{m['safe_z']:.3f}")
    lines.append("M5   (Spindel AUS)")
    lines.append("G0 X0 Y0 A0")
    lines.append("M30")
    return lines


def berechne_x_aus_drall(a_winkel_grad, werkzeug):
    """
    Helix-Approximation mit neuer Konvention:
    - "drall_grad_pro_mm": Grad pro mm (z.B. 2.0 = 2° pro 1 mm), bevorzugt
      X-Verschiebung für einen Winkel = Winkel / (Grad pro mm)
    - Rückwärtskompatibilität: falls nur "drall_steigung" vorhanden ist, wird
      dieser Wert als mm pro 360° interpretiert (alte Konvention) und entspricht
      mm_per_grad = drall_steigung / 360
      X-Verschiebung = Winkel * mm_per_grad
    """
    if "drall_grad_pro_mm" in werkzeug:
        grad_pro_mm = werkzeug["drall_grad_pro_mm"]
        if grad_pro_mm == 0:
            raise ValueError("werkzeug.drall_grad_pro_mm darf nicht 0 sein")
        x_offset = a_winkel_grad / grad_pro_mm
    else:
        # alte Konvention: mm pro 360°
        mm_per_360 = werkzeug["drall_steigung"]
        mm_per_grad = mm_per_360 / 360.0
        x_offset = a_winkel_grad * mm_per_grad
    return x_offset


def gcode_schleifpass(cfg, pass_num, z_tiefe):
    m = cfg["maschine"]
    # Support new structure: schleifscheibe_Schneiden or old structure: schleifscheibe
    s = cfg.get("schleifscheibe_Schneiden", cfg.get("schleifscheibe", {}))
    # Support new structure: fraeser or old structure: werkzeug_edge/werkzeug
    if 'fraeser' in cfg:
        w = cfg['fraeser']
    else:
        w = cfg.get("werkzeug_edge", cfg.get("werkzeug", {}))
    
    # Get ruecken parameters from aktionen.schneiden (new structure) or werkzeug (old structure)
    aktion_schneiden = cfg.get('aktionen', {}).get('schneiden', {})

    a_start = m["a_start"]
    a_end = m["a_end"]
    a_steps = m["a_steps"]
    z_arbeit = z_von_oberer_tangente(cfg, z_tiefe)

    lines = []
    lines.append(f"(Schleifdurchgang {pass_num}, Z={z_arbeit:.3f}, Top-Rel={z_tiefe:.3f})")
    lines.append(f"G1 Z{z_arbeit:.3f} F{s.get('schleifvorschub', 200.0):.3f}")

    # Für jede Schneide separat schleifen
    for schneide in range(w["schneidenanzahl"]):
        lines.append(f"(Schneide {schneide + 1})")
        # Startwinkel für diese Schneide
        offset = 360.0 / w["schneidenanzahl"] * schneide
        start_angle = a_start + offset

        # Wenn Schneidenlänge konfiguriert ist: lineare X-Bewegung (+X) mit gleichzeitiger A-Drehung
        if "schneidenlaenge" in w and w["schneidenlaenge"] > 0:
            length = w["schneidenlaenge"]
            # Bestimme Gesamtdrehung in Grad (vorzugsweise drall_grad_pro_mm)
            if "drall_grad_pro_mm" in w:
                degrees_total = w["drall_grad_pro_mm"] * length
            else:
                # Rückwärtskompatibel: drall_steigung = mm pro 360°
                mm_per_360 = w.get("drall_steigung")
                if not mm_per_360:
                    raise ValueError("Kein Drall angegeben (drall_grad_pro_mm oder drall_steigung fehlt)")
                degrees_total = (360.0 / mm_per_360) * length

            # Wenn nur Start und Ende ausgegeben werden sollen
            if s.get("start_end_only", True):
                x_start = m["start_x"]
                a_start_pos = start_angle
                x_end = m["start_x"] + length
                a_end_pos = start_angle + degrees_total
                lines.append(f"G1 X{x_start:.3f} A{a_start_pos:.3f} F{s.get('schleifvorschub', 200.0):.3f}")
                lines.append(f"G1 X{x_end:.3f} A{a_end_pos:.3f} F{s.get('schleifvorschub', 200.0):.3f}")
            else:
                steps = int(w.get("schneiden_schritte", a_steps))
                for i in range(steps + 1):
                    frac = i / steps
                    x = m["start_x"] + frac * length
                    a_pos = start_angle + frac * degrees_total
                    lines.append(f"G1 X{x:.3f} A{a_pos:.3f} F{s.get('schleifvorschub', 200.0):.3f}")

            # Optional: Schneiderrücken nachschleifen genau nach deinen Schritten
            # Schrittfolge pro Schneide:
            # 1) Nach dem Hauptpass: Z anheben auf Sicherheitsabstand
            # 2) Für jede Rückenstufe p=1..N:
            #    a) G0 X=start_x A= start_angle + p*angle_step
            #    b) G1 Z=pass_depth - p*ruecken_tiefe_delta
            #    c) G1 X = start_x + length  A = start_angle + drall_total + p*angle_step
            #    d) G0 Z = pass_depth + lift_after_pass (Sicherheitsabstand)
            # Read ruecken parameters from aktionen.schneiden (new) or werkzeug (old)
            ruecken_grad = aktion_schneiden.get("ruecken_grad", w.get("ruecken_grad", 0.0))
            if ruecken_grad and ruecken_grad > 0 and "schneidenlaenge" in w and w["schneidenlaenge"] > 0:
                # Schritt 1 (neu): Nach dem Hauptpass Z anheben auf Sicherheitsabstand
                lift_initial = s.get("rueckzug_hoehe_Z", 2.0)
                z_lift_initial = z_arbeit + lift_initial
                if z_lift_initial > m["safe_z"]:
                    z_lift_initial = m["safe_z"]
                lines.append(f"G0 Z{z_lift_initial:.3f}")

                ruecken_delta = aktion_schneiden.get("ruecken_tiefe_delta", w.get("ruecken_tiefe_delta", 0.2))  # Tiefe pro Rückenstufe
                length = w["schneidenlaenge"]

                steps_r = int(aktion_schneiden.get("ruecken_schritte", w.get("ruecken_schritte", max(1, int(w.get("schneiden_schritte", a_steps))))))
                # Gesamtdrehung (Drall) der Hauptbewegung über die Länge
                if "drall_grad_pro_mm" in w:
                    drall_total = w["drall_grad_pro_mm"] * length
                else:
                    mm_per_360 = w.get("drall_steigung")
                    if not mm_per_360:
                        raise ValueError("Kein Drall angegeben (drall_grad_pro_mm oder drall_steigung fehlt)")
                    drall_total = (360.0 / mm_per_360) * length

                # erster_ruecken_grad ist der Startwinkel für den Rücken (Offset zur Schneide)
                erster_ruecken_grad = aktion_schneiden.get("erster_ruecken_grad", w.get("erster_ruecken_grad", 0.0))
                angle_step = ruecken_grad / steps_r

                for p in range(1, steps_r + 1):
                    # Z für diesen Rücken-Durchgang (stufenweise tiefer)
                    z_ruecken_top_rel = z_tiefe - p * ruecken_delta
                    z_ruecken_pass = z_von_oberer_tangente(cfg, z_ruecken_top_rel)

                    # Start-Winkel: Schneide + erster_ruecken_grad + inkrementelle Schritte
                    # (p-1) weil der erste Pass (p=1) genau bei erster_ruecken_grad starten soll
                    start_a = start_angle + erster_ruecken_grad + (p - 1) * angle_step
                    end_a = start_angle + erster_ruecken_grad + drall_total + (p - 1) * angle_step

                    # Schritt 3: Zurück nach X=start, A=start_a (auf Sicherheits-Höhe bereits)
                    lines.append(f"G0 X{m['start_x']:.3f} A{start_a:.3f}")
                    # Schritt 4: Senken auf Z_ruecken_pass
                    lines.append(f"G1 Z{z_ruecken_pass:.3f} F{s.get('schleifvorschub', 200.0):.3f}")
                    # Schritt 5: Schleifen von X=start -> X=start+length mit A von start_a -> end_a
                    lines.append(f"G1 X{(m['start_x'] + length):.3f} A{end_a:.3f} F{s.get('schleifvorschub', 200.0):.3f}")
                    # Schritt 6: Z heben auf Sicherheitsabstand
                    lift = s.get("rueckzug_hoehe_Z", 2.0)
                    z_lift_pos = z_ruecken_pass + lift
                    if z_lift_pos > m["safe_z"]:
                        z_lift_pos = m["safe_z"]
                    lines.append(f"G0 Z{z_lift_pos:.3f}")

                # Am Ende der Rückenserie: zurück auf Pass-Tiefe (für Konsistenz)
                lines.append(f"G0 Z{z_arbeit:.3f}")

            # Nach dem Schliff: Z um Sicherheitsabstand anheben, dann zurück zum Start-X und A der nächsten Schneide
            lift = s.get("rueckzug_hoehe_Z", 2.0)
            z_lift_pos = z_arbeit + lift
            if z_lift_pos > m["safe_z"]:
                z_lift_pos = m["safe_z"]
            lines.append(f"G0 Z{z_lift_pos:.3f}")
            next_offset = 360.0 / w["schneidenanzahl"] * ((schneide + 1) % w["schneidenanzahl"])
            lines.append(f"G0 X{m['start_x']:.3f}")
            lines.append(f"G0 A{a_start + next_offset:.3f}")
            lines.append("")

        else:
            # Fallback auf bisheriges Verhalten: A-Achse + X-Helix (vertikale Steigung)
            for i in range(a_steps + 1):
                a = a_start + (a_end - a_start) * (i / a_steps)
                a_gesamt = a + offset
                x = m["start_x"] + berechne_x_aus_drall(a, w)
                lines.append(
                    f"G1 A{a_gesamt:.3f} X{x:.3f} F{s.get('schleifvorschub', 200.0):.3f}"
                )

            # Zurück zum Startwinkel dieser Schneide
            lines.append(f"G0 A{a_start + offset:.3f}")
            lines.append("")

    # Nach dem Pass zurück in Sicherheits-Z
    lines.append(f"G0 Z{m['safe_z']:.3f}")
    lines.append("")
    return lines


def generiere_gcode(cfg, config_file=None):
    # Support new structure: schleifscheibe_Schneiden or old structure: schleifscheibe
    s = cfg.get("schleifscheibe_Schneiden", cfg.get("schleifscheibe", {}))
    # Support new structure: aktionen.schneiden or old structure: ausgabe
    if 'aktionen' in cfg and 'schneiden' in cfg['aktionen']:
        ausgabe_datei = cfg['aktionen']['schneiden'].get('ausgabe_datei', 'fraeser_kanten.ngc')
    else:
        ausgabe_datei = cfg.get("ausgabe", {}).get("datei", "fraeser_schaerfen.ngc")

    lines = []
    lines += gcode_header(cfg, config_file)

    aktuelle_tiefe = 0.0
    # Support new structure: aktionen.schneiden or old structure: schleifscheibe
    if 'aktionen' in cfg and 'schneiden' in cfg['aktionen']:
        aktion = cfg['aktionen']['schneiden']
        zustellung = aktion.get('zustellung_pro_pass', 0.05)
        
        # Berechne anzahl_passe und max_tiefe aus durchmesser und durchmesser_geschaerft
        if 'durchmesser_geschaerft' in aktion and 'fraeser' in cfg:
            fraeser_durchmesser = cfg['fraeser'].get('durchmesser', 12.0)
            durchmesser_geschaerft = aktion['durchmesser_geschaerft']
            material_abzutragen = abs(fraeser_durchmesser - durchmesser_geschaerft)
            # max_tiefe = -(durchmesser - durchmesser_geschaerft) / 2
            max_tiefe = -material_abzutragen / 2.0
            # anzahl_passe = (durchmesser - durchmesser_geschaerft) / zustellung_pro_pass / 2
            anzahl_passe = max(1, int(material_abzutragen / zustellung / 2))
        else:
            anzahl_passe = int(aktion.get('anzahl_passe', 20))
            max_tiefe = aktion.get('max_tiefe', -1.0)
    else:
        anzahl_passe = s.get("anzahl_passe", 20)
        zustellung = s.get("zustellung_pro_pass", 0.05)
        max_tiefe = s.get("max_tiefe", -1.0)
        
    for p in range(1, anzahl_passe + 1):
        aktuelle_tiefe -= zustellung
        if aktuelle_tiefe < max_tiefe:
            aktuelle_tiefe = max_tiefe
        lines += gcode_schleifpass(cfg, p, aktuelle_tiefe)
        if aktuelle_tiefe <= max_tiefe:
            break

    lines += gcode_footer(cfg)

    ensure_gcode_within_machine_limits(lines, cfg)

    with open(ausgabe_datei, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"G-Code erzeugt: {ausgabe_datei}")


if __name__ == "__main__":
    # Standard-Konfigurationsdatei (kann per CLI überschrieben werden)
    default_config = resource_path("ToolLib", "template1.json")

    # CLI-Optionen: Default ist None -> bei Fehlen starten wir Auswahl
    parser = argparse.ArgumentParser(description="G-Code Generator für Fräser Schärfen")
    parser.add_argument("-c", "--config", help="Pfad zur Konfigurationsdatei (JSON). Wenn nicht gesetzt: GUI zur Auswahl (falls möglich)", default=None)
    parser.add_argument("--edit", action='store_true', help='Öffnet nach Auswahl den JSON-Editor (Save / Save As)')
    parser.add_argument("--open", help='Pfad zu einer beliebigen JSON-Datei zum Öffnen im Editor; Programm beendet danach', default=None)
    parser.add_argument("--nogui", action='store_true', help='Keine GUI verwenden; interaktiver CLI-Modus')
    parser.add_argument("--mode", choices=['edge', 'front', 'both', 'measure'], default='edge', help='Generierungsmodus: edge, front, both oder measure (LinuxCNC Vermessen). Standard: edge')
    args = parser.parse_args()

    # Handle --open: öffne die angegebene Datei im Editor und beende das Programm danach
    if args.open is not None:
        open_path = args.open
        if open_path == '':
            # leerer Wert: Dialog öffnen (nur falls GUI möglich)
            if args.nogui or not can_use_gui():
                open_path = choose_config_interactive(read_last_config_path())
            else:
                open_path = choose_config(read_last_config_path())
        # Falls kein Pfad festgelegt, Dialog öffnen
        if not open_path:
            print('Keine Datei angegeben zum Öffnen.', file=sys.stderr)
            sys.exit(1)
        if args.nogui or not can_use_gui():
            print('Editor benötigt eine GUI, die hier nicht verfügbar ist.', file=sys.stderr)
            sys.exit(1)
        try:
            newp = edit_config_gui(open_path)
            if newp:
                save_last_config_path(newp)
        except Exception:
            print('Editor konnte nicht geöffnet werden.', file=sys.stderr)
        sys.exit(0)

    config_datei = args.config
    edit_requested = args.edit

    # Wenn kein Pfad per CLI angegeben: Konfig auswählen (GUI oder Prompt). Respect --nogui
    if not config_datei:
        last = read_last_config_path()
        if not args.nogui and can_use_gui():
            chosen = choose_config(last)
        else:
            chosen = choose_config_interactive(last)
        if chosen:
            config_datei = chosen
        elif last and os.path.exists(last):
            # Kein Auswahl getroffen, aber letzter Pfad vorhanden -> verwenden
            config_datei = last
        else:
            # Fallback: benutze default template, falls vorhanden
            if os.path.exists(default_config):
                print(f"Keine Auswahl getroffen — benutze Standard-Konfiguration: {default_config}")
                config_datei = default_config
            else:
                print("Keine Konfigurationsdatei angegeben und kein Default gefunden.", file=sys.stderr)
                sys.exit(1)

    # Validierung
    if not os.path.exists(config_datei):
        print(f"Konfigurationsdatei nicht gefunden: {config_datei}", file=sys.stderr)
        sys.exit(1)

    # Wenn die Konfiguration per Auswahl oder ohne -c ermittelt wurde: ggf. Editor öffnen
    # Wenn -c nicht gesetzt => Auswahlvorgang hat stattgefunden, wir öffnen den Editor automatisch
    # Wenn -c gesetzt und --edit angegeben => ebenfalls Editor öffnen
    try:
        was_cli = args.config is not None
    except Exception:
        was_cli = False

    # Öffne Editor wenn gewünscht
    try:
        if (not was_cli) or edit_requested:
            new_path = edit_config_gui(config_datei)
            if new_path:
                config_datei = new_path
    except Exception:
        # Wenn GUI nicht verfügbar, weiter ohne Editor
        pass

    # Merke den zuletzt gewählten Pfad
    try:
        save_last_config_path(config_datei)
    except Exception:
        pass

    cfg = lade_konfiguration(config_datei)
    
    # Mode-basierte Generierung
    mode = args.mode
    
    if mode == 'edge' or mode == 'both':
        try:
            generiere_gcode(cfg, os.path.basename(config_datei))
        except Exception as e:
            print(f'Fehler bei Edge G-Code Generierung: {e}', file=sys.stderr)
            if mode == 'edge':
                sys.exit(1)
    
    if mode == 'front' or mode == 'both':
        # Validate front config
        ok, errors = validate_front_config(cfg)
        if not ok:
            print('Fehler in front-Konfiguration:', file=sys.stderr)
            for e in errors:
                print(f'- {e}', file=sys.stderr)
            if mode == 'front':
                sys.exit(1)
        else:
            try:
                generiere_front_gcode(cfg, os.path.basename(config_datei))
            except Exception as e:
                print(f'Fehler bei Front G-Code Generierung: {e}', file=sys.stderr)
                if mode == 'front':
                    sys.exit(1)

    if mode == 'measure':
        try:
            generiere_linuxcnc_vermess_gcode(cfg, os.path.basename(config_datei))
        except Exception as e:
            print(f'Fehler bei Vermess-G-Code Generierung: {e}', file=sys.stderr)
            sys.exit(1)

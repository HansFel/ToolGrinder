#!/usr/bin/env python3
"""FrontGrinder: G-Code Erzeuger für Frontschärfen (Frontface grinding)
Verwendet dieselbe JSON-Konfigurationsdatei wie `Grinder.py`, Abschnitt `front`.
Beispiel-Konfiguration (ToolLib/template1.json):

"front": {
  "anzahl_passe": 5,
  "zustellung_pro_pass": 0.05,
  "max_tiefe": -0.5,
  "x_start": 0.0,
  "x_end": 10.0,
  "z_sicher": 5.0,
  "feed": 200.0,
  "spindle": 3000,
  "ausgabe_datei": "fraeser_front.ngc",
  "cutting_angle": 3.0
}

Aufruf: python FrontGrinder.py -c ToolLib/template1.json --nogui
"""

import os
import sys
import argparse
import math
from Grinder import (
    lade_konfiguration,
    resource_path,
    read_last_config_path,
    save_last_config_path,
    choose_config,
    choose_config_interactive,
    can_use_gui,
    edit_config_gui,
    validate_front_config,
)


def gcode_front_header(cfg):
    m = cfg.get('maschine', {})
    f = cfg.get('front', {})
    lines = []
    lines.append('%')
    lines.append('(Front-Grinder G-Code)')
    if m.get('nullpunkt') and m['nullpunkt'].get('code'):
        lines.append(m['nullpunkt']['code'])
    # Werkzeugwechsel (optional)
    w = cfg.get('werkzeug', {})
    tool_no = w.get('tool_number')
    if tool_no is not None:
        try:
            tn = int(tool_no)
            lines.append(f"T{tn} M6   (Werkzeugwechsel)")
        except Exception:
            lines.append(f"(Ungültige tool_number: {tool_no})")
    # Anfahren der Sicherheitshöhe (Spindel-Start kann auf den ersten Pass verschoben werden)
    lines.append(f"G0 Z{f.get('z_sicher', 5.0)}")
    # Spindelstart hier nur, wenn nicht auf ersten Pass verschoben
    if not f.get('spindle_on_first_pass', True):
        sp = f.get('spindle')
        if sp:
            try:
                sv = int(sp)
                lines.append(f"M3 S{sv}   (Spindel ein)")
                dwell = int(f.get('spindle_dwell_ms', 1000))
                lines.append(f"G4 P{dwell/1000.0}")
            except Exception:
                lines.append(f"(Ungültiger Spindelwert: {sp})")
    lines.append('G90 G94')
    return lines


def gcode_front_pass(cfg, idx, tiefe, start_x=None):
    f = cfg.get('front', {})
    w = cfg.get('werkzeug', {})
    m = cfg.get('maschine', {})
    s = cfg.get('schleifscheibe', {})
    lines = []
    base_x1 = f.get('x_start', 0.0)
    x2 = f.get('x_end', 10.0)
    feed = f.get('feed', 200.0)
    z_sicher = f.get('z_sicher', 5.0)
    retract_x = f.get('retract_x', m.get('safe_z', 5.0))

    # Determine actual start X for this pass
    if start_x is None:
        x1 = base_x1
    else:
        x1 = start_x

    # Tool radius
    radius = float(w.get('durchmesser', 0.0)) / 2.0
    # Z plunge: move from Z0 down by radius plus current pass depth
    z_plunge = -(radius) + tiefe

    # Calculate Y offset based on cutting angle and grinding wheel diameter
    cutting_angle = f.get('cutting_angle', 0.0)  # in degrees
    grinding_wheel_radius = float(s.get('durchmesser', 100.0)) / 2.0
    if cutting_angle > 0:
        # Y offset = grinding_wheel_radius * (1 - cos(angle))
        angle_rad = math.radians(cutting_angle)
        y_offset = grinding_wheel_radius * (1.0 - math.cos(angle_rad))
    else:
        y_offset = 0.0
    
    y_start = m.get('start_y', 0.0)
    y_grinding = y_start - y_offset  # move Y minus

    # Anfahrt: zum Start bei sicherer Höhe
    lines.append(f"(Pass {idx} at depth {tiefe}, start X {x1}, cutting angle {cutting_angle}°, Y offset {y_offset:.3f})")
    lines.append(f"G0 X{x1} Y{y_start} Z{z_sicher}")
    # Move to grinding Y position
    if y_offset > 0:
        lines.append(f"G0 Y{y_grinding:.3f}")
    # Absenken in Z auf Plunge-Tiefe
    lines.append(f"G1 Z{z_plunge} F{feed}")
    # Für jede Schneide: Rotation + Schnitt
    anz = int(w.get('schneidenanzahl', 1))
    base_a = m.get('a_start', 0.0)
    angle_step = 360.0 / max(1, anz)
    x_retract = x2 - float(retract_x)
    for sch in range(anz):
        a_pos = base_a + sch * angle_step
        lines.append(f"(Schneide {sch+1} | A={a_pos:.3f})")
        # Schnellrotationsposition vor Schnitt
        lines.append(f"G0 A{a_pos:.3f}")
        # Schnittbewegung
        lines.append(f"G1 X{x2} F{feed}")
        # Rückzug in X
        lines.append(f"G0 X{x_retract}")
        # Rückfahrt zum Start (bei Z noch in Plunge)
        lines.append(f"G0 X{x1} Z{z_plunge}")
    # Nach allen Schneiden: Auf Z0 und dann auf Sicherheitsabstand hochfahren
    lines.append(f"G0 Z0")
    lines.append(f"G0 Z{z_sicher}")
    # Return Y to start position
    if y_offset > 0:
        lines.append(f"G0 Y{y_start}")
    return lines


def gcode_front_footer(cfg):
    m = cfg.get('maschine', {})
    lines = []
    lines.append('G0 Z{0}'.format(cfg.get('front',{}).get('z_sicher', 5.0)))
    lines.append('M5')
    lines.append('M30')
    return lines


def generiere_front_gcode(cfg):
    f = cfg.get('front')
    if not f:
        raise ValueError('Keine Section "front" in der Konfiguration gefunden.')
    ausgabe = f.get('ausgabe_datei') or cfg.get('ausgabe', {}).get('datei', 'fraeser_front.ngc')

    lines = []
    lines += gcode_front_header(cfg)

    aktuelle_tiefe = 0.0
    base_x = f.get('x_start', 0.0)
    x_end = f.get('x_end', 10.0)
    x_step = f.get('x_step', 0.0)
    for p in range(1, f.get('anzahl_passe', 1) + 1):
        aktuelle_tiefe -= f.get('zustellung_pro_pass', 0.1)
        if aktuelle_tiefe < f.get('max_tiefe', -1.0):
            aktuelle_tiefe = f.get('max_tiefe', -1.0)
        # Compute start X for this pass (progressive inward step towards x_end)
        current_start = base_x + (p - 1) * float(x_step)
        # Cap to x_end to avoid overshoot
        if (x_end >= base_x and current_start > x_end) or (x_end < base_x and current_start < x_end):
            current_start = x_end
        lines += gcode_front_pass(cfg, p, aktuelle_tiefe, start_x=current_start)
        if aktuelle_tiefe <= f.get('max_tiefe', -1.0):
            break

    lines += gcode_front_footer(cfg)

    with open(ausgabe, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(lines))

    print(f'Front G-Code erzeugt: {ausgabe}')


if __name__ == '__main__':
    default_config = resource_path('ToolLib', 'template1.json')
    parser = argparse.ArgumentParser(description='Front-G-Code Generator für Fräser-Front')
    parser.add_argument('-c', '--config', help='Pfad zur Konfigurationsdatei (JSON). Wenn nicht gesetzt: GUI zur Auswahl (falls möglich)', default=None)
    parser.add_argument('--edit', action='store_true', help='Öffnet nach Auswahl den JSON-Editor (Save / Save As)')
    parser.add_argument('--open', help='Pfad zu einer beliebigen JSON-Datei zum Öffnen im Editor; Programm beendet danach', default=None)
    parser.add_argument('--nogui', action='store_true', help='Keine GUI verwenden; interaktiver CLI-Modus')
    args = parser.parse_args()

    # Handle --open similar to Grinder
    if args.open is not None:
        open_path = args.open
        if open_path == '':
            if args.nogui or not can_use_gui():
                open_path = choose_config_interactive(read_last_config_path())
            else:
                open_path = choose_config(read_last_config_path())
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

    if not config_datei:
        last = read_last_config_path()
        if not args.nogui and can_use_gui():
            chosen = choose_config(last)
        else:
            chosen = choose_config_interactive(last)
        if chosen:
            config_datei = chosen
        elif last and os.path.exists(last):
            config_datei = last
        else:
            if os.path.exists(default_config):
                print(f'Keine Auswahl getroffen — benutze Standard-Konfiguration: {default_config}')
                config_datei = default_config
            else:
                print('Keine Konfigurationsdatei angegeben und kein Default gefunden.', file=sys.stderr)
                sys.exit(1)

    if not os.path.exists(config_datei):
        print(f'Konfigurationsdatei nicht gefunden: {config_datei}', file=sys.stderr)
        sys.exit(1)

    try:
        cfg = lade_konfiguration(config_datei)
    except Exception as e:
        print(f'Konfig konnte nicht geladen werden: {e}', file=sys.stderr)
        sys.exit(1)

    # Optional: open editor
    if edit_requested:
        if args.nogui or not can_use_gui():
            print('Editor benötigt eine GUI, die hier nicht verfügbar ist.', file=sys.stderr)
        else:
            newp = edit_config_gui(config_datei)
            if newp:
                config_datei = newp
                cfg = lade_konfiguration(config_datei)
                save_last_config_path(newp)

    # Validate front config before generating
    ok, errors = validate_front_config(cfg)
    if not ok:
        print('Fehler in front-Konfiguration:', file=sys.stderr)
        for e in errors:
            print(f'- {e}', file=sys.stderr)
        sys.exit(1)

    generiere_front_gcode(cfg)


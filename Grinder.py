import json
import math
import os
import argparse
import sys

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
    """
    errors = []
    f = cfg.get('front')
    if not f:
        errors.append('Missing section "front"')
        return False, errors
    # x_start / x_end
    try:
        x_start = float(f.get('x_start', 0.0))
        x_end = float(f.get('x_end', 0.0))
        if x_end <= x_start:
            errors.append('front.x_end must be greater than front.x_start')
    except Exception:
        errors.append('front.x_start and front.x_end must be numbers')
    # max_tiefe
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
    # feed / spindle
    try:
        feed = float(f.get('feed', 0.0))
        if feed <= 0:
            errors.append('front.feed must be > 0')
    except Exception:
        errors.append('front.feed must be a number')
    try:
        spindle = float(f.get('spindle', 0.0))
        if spindle <= 0:
            errors.append('front.spindle must be > 0')
    except Exception:
        errors.append('front.spindle must be a number')
    if not f.get('ausgabe_datei'):
        errors.append('front.ausgabe_datei must be set')
    # Werkzeug diameter required for radius-based plunge
    try:
        diam = float(cfg.get('werkzeug', {}).get('durchmesser', 0.0))
        if diam <= 0:
            errors.append('werkzeug.durchmesser must be > 0 (required for radius-based plunge)')
    except Exception:
        errors.append('werkzeug.durchmesser must be a number')
    return (len(errors) == 0, errors)


def compute_front_start_positions(cfg):
    """Compute list of (pass_index, start_x, depth) tuples for front passes.
    Depth is always 0 (not used anymore), computed as number of passes from (x_end - x_start) / zustellung_pro_pass.
    """
    f = cfg.get('front', {})
    if not f:
        return []
    base_x = float(f.get('x_start', 0.0))
    x_end = float(f.get('x_end', 0.0))
    x_step = float(f.get('zustellung_pro_pass', 0.01))

    # Berechne anzahl_passe automatisch
    distance = abs(x_end - base_x)
    anzahl_passe = int(distance / x_step) + 1 if x_step > 0 else 1

    starts = []
    for p in range(1, anzahl_passe + 1):
        current_start = base_x + (p - 1) * x_step
        if (x_end >= base_x and current_start > x_end) or (x_end < base_x and current_start < x_end):
            current_start = x_end
        starts.append((p, current_start, 0.0))
        if abs(current_start - x_end) < 0.0001:
            break
    return starts


# -------------------------------------------------
# FRONT G-CODE GENERATOR: FRONTFLÄCHEN SCHÄRFEN
# -------------------------------------------------

def gcode_front_header(cfg):
    m = cfg.get('maschine', {})
    f = cfg.get('front', {})
    s = cfg.get('schleifscheibe', {})
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
    f = cfg.get('front', {})
    w = cfg.get('werkzeug', {})
    m = cfg.get('maschine', {})
    lines = []
    base_x1 = f.get('x_start', 0.0)
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
    # Z plunge: nur Fräserradius (nicht mehr depth-abhängig)
    z_plunge = -radius
    
    # X Sicherheitsabstand (in Minus-Richtung vom Startpunkt)
    x_safe = x1 - float(retract_x)

    # Vorbereitung: Anfahrt zum Startpunkt bei Sicherheitshöhe
    lines.append(f"(Pass {idx} at X {x1})")
    lines.append(f"G0 X{x1} Z{z_sicher}")
    
    # Start spindle before first pass if spindle_on_first_pass is True
    if idx == 1 and f.get('spindle_on_first_pass', True):
        sp = f.get('spindle')
        if sp:
            try:
                sv = int(sp)
                lines.append(f"M3 S{sv}   (Spindel ein)")
                dwell = int(f.get('spindle_dwell_ms', 1000))
                lines.append(f"G4 P{dwell/1000.0}")
            except Exception:
                pass
    
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
        lines.append(f"G1 Z{z_plunge} F{feed}")
        # X in Minus-Richtung auf Sicherheitsabstand
        lines.append(f"G1 X{x_safe} F{feed}")
        # Z heben bis Sicherheitsabstand
        lines.append(f"G0 Z{z_sicher}")
        # Zurück zur Startposition X (für nächste Schneide)
        lines.append(f"G0 X{x1}")
    
    return lines


def gcode_front_footer(cfg):
    m = cfg.get('maschine', {})
    f = cfg.get('front', {})
    lines = []
    # Return to start Y position
    y_start = m.get('start_y', 0.0)
    lines.append(f'G0 Y{y_start}')
    lines.append('G0 Z{0}'.format(f.get('z_sicher', 5.0)))
    lines.append('M5')
    lines.append('M30')
    return lines


def generiere_front_gcode(cfg):
    """Generate front-face grinding G-Code."""
    f = cfg.get('front')
    if not f:
        raise ValueError('Keine Section "front" in der Konfiguration gefunden.')
    ausgabe = f.get('ausgabe_datei') or cfg.get('ausgabe', {}).get('datei', 'fraeser_front.ngc')

    lines = []
    lines += gcode_front_header(cfg)

    base_x = f.get('x_start', 0.0)
    x_end = f.get('x_end', 10.0)
    x_step = f.get('zustellung_pro_pass', 0.01)  # x_step = zustellung_pro_pass
    
    # Berechne anzahl_passe automatisch aus (x_end - x_start) / zustellung_pro_pass
    distance = abs(x_end - base_x)
    anzahl_passe = int(distance / x_step) + 1 if x_step > 0 else 1
    
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

    def on_save_as():
        nonlocal final_path
        newp = filedialog.asksaveasfilename(title='Speichern unter', defaultextension='.json', filetypes=[('JSON', '*.json'), ('Alle Dateien', '*.*')])
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
        checklist = [
            (f"safe_z (Sicherheitsabstand) = {cfg.get('maschine', {}).get('safe_z')}", 'safe_z'),
            (f"start_x = {cfg.get('maschine', {}).get('start_x')}", 'start_x'),
            (f"schleifscheibe.drehzahl = {cfg.get('schleifscheibe', {}).get('drehzahl')}", 'drehzahl'),
            (f"schleifscheibe.schleifvorschub = {cfg.get('schleifscheibe', {}).get('schleifvorschub')}", 'schleifvorschub')
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
            generiere_gcode(cfg)
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

            # Option: Upload
            if messagebox.askyesno('Upload', 'Möchten Sie die erzeugte Datei auf einen Server hochladen?'):
                servers = load_servers()
                if not servers:
                    if messagebox.askyesno('Keine Server', 'Keine Server konfiguriert. Möchten Sie welche anlegen?'):
                        manage_servers_gui(root)
                        servers = load_servers()
                # Wähle Server
                if servers:
                    choices = [f"{s.get('name')} ({s.get('type')}@{s.get('host')})" for s in servers]
                    import tkinter as tk
                    from tkinter import simpledialog
                    sel = simpledialog.askinteger('Server wählen', '\n'.join([f"{i+1}: {c}" for i, c in enumerate(choices)]) + '\n\nGeben Sie die Nummer ein:', parent=root, minvalue=1, maxvalue=len(choices))
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

        except Exception as e:
            messagebox.showerror('Fehler beim Generieren', f'Fehler beim Erzeugen des G-Codes: {e}')

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

    root = tk.Tk()
    root.title(f"Grinder — Konfigurationseditor — {os.path.basename(path)}")
    root.geometry('900x600')

    # Top frame: buttons
    btn_frame = tk.Frame(root)
    btn_frame.pack(fill='x')

    open_btn = tk.Button(btn_frame, text='Öffnen...', command=on_open)
    open_btn.pack(side='left', padx=4, pady=4)
    gen_btn = tk.Button(btn_frame, text='G-Code erzeugen', command=on_generate)
    gen_btn.pack(side='left', padx=4, pady=4)
    save_btn = tk.Button(btn_frame, text='Speichern', command=on_save)
    save_btn.pack(side='left', padx=4, pady=4)
    saveas_btn = tk.Button(btn_frame, text='Speichern unter...', command=on_save_as)
    saveas_btn.pack(side='left', padx=4, pady=4)
    format_btn = tk.Button(btn_frame, text='Formatieren', command=lambda: do_format_action())
    format_btn.pack(side='left', padx=4, pady=4)
    insert_front_btn = tk.Button(btn_frame, text='Insert Front Template', command=on_insert_front)
    insert_front_btn.pack(side='left', padx=4, pady=4)
    validate_front_btn = tk.Button(btn_frame, text='Validate Front', command=on_validate_front)
    validate_front_btn.pack(side='left', padx=4, pady=4)
    preview_front_btn = tk.Button(btn_frame, text='Preview Front Passes', command=on_preview_front)
    preview_front_btn.pack(side='left', padx=4, pady=4)
    close_btn = tk.Button(btn_frame, text='Schließen', command=on_close)
    close_btn.pack(side='right', padx=4, pady=4)

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

    # First, try an SSH agent / key lookup via SSHClient (allow_agent=True, look_for_keys=True)
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(host, port=port, username=user, allow_agent=True, look_for_keys=True, timeout=10)
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
            return
        finally:
            sftp.close()
    except Exception:
        # Agent/Key-based connect failed; proceed to explicit keypath / password
        pass

    # Try explicit private key file (with passphrase from server entry or keyring, prompt if necessary)
    passphrase = server.get('key_passphrase')
    try:
        import keyring
    except Exception:
        keyring = None
    if (not passphrase) and keyring and server.get('use_keyring'):
        passphrase = keyring.get_password('Grinder-key-'+server.get('name',''), server.get('username') or '')

    t = paramiko.Transport((host, port))
    if keypath:
        key = None
        last_exc = None
        try:
            key = paramiko.Ed25519Key.from_private_key_file(keypath, password=passphrase)
        except Exception as e:
            last_exc = e
        if key is None:
            try:
                key = paramiko.RSAKey.from_private_key_file(keypath, password=passphrase)
            except Exception as e:
                last_exc = e
        if key is None:
            # If interactive prompt possible, ask for passphrase
            try:
                import tkinter as tk
                from tkinter import simpledialog
                root = tk.Tk()
                root.withdraw()
                p = simpledialog.askstring('Passphrase', f'Passphrase für Schlüssel {keypath}:', show='*')
                root.destroy()
            except Exception:
                p = None
            if p:
                try:
                    key = paramiko.Ed25519Key.from_private_key_file(keypath, password=p)
                except Exception:
                    try:
                        key = paramiko.RSAKey.from_private_key_file(keypath, password=p)
                    except Exception:
                        key = None
                if p and server.get('use_keyring') and keyring:
                    try:
                        keyring.set_password('Grinder-key-'+server.get('name',''), server.get('username') or '', p)
                    except Exception:
                        pass
        if key is None:
            raise RuntimeError(f'Unable to load private key {keypath}: {last_exc}')
        t.connect(username=user, pkey=key)
    else:
        t.connect(username=user, password=pwd)

    sftp = paramiko.SFTPClient.from_transport(t)
    try:
        try:
            sftp.chdir(remote_dir)
        except IOError:
            # try to create
            try:
                sftp.mkdir(remote_dir)
                sftp.chdir(remote_dir)
            except Exception:
                sftp.chdir('.')
        sftp.put(local_path, os.path.basename(local_path))
    finally:
        sftp.close()
        t.close()


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


def gcode_header(cfg):
    m = cfg["maschine"]
    s = cfg["schleifscheibe"]

    lines = []
    lines.append("(Fräser Schärfen – automatisch generiert)")
    lines.append("G21   (mm)")
    lines.append("G90   (absolute Positionierung)")
    lines.append("G17   (XY-Ebene)")
    lines.append(f"G0 Z{m['safe_z']:.3f}")

    # Werkzeugwechsel (optional, z.B. T1 M6)
    w = cfg.get("werkzeug", {})
    tool_no = w.get("tool_number")
    if tool_no is not None:
        try:
            tool_no_int = int(tool_no)
            lines.append(f"T{tool_no_int} M6   (Werkzeugwechsel)")
        except Exception:
            lines.append(f"(Ungültige tool_number: {tool_no})")

    # Spindelstart hier nur, wenn nicht auf ersten Pass verschoben
    if not s.get('spindle_on_first_pass', True):
        try:
            dreh = int(s.get('drehzahl'))
            dwell = int(s.get('spindle_dwell_ms', 1000))
            lines.append(f"M3 S{dreh}   (Spindel ein)")
            lines.append(f"G4 P{dwell/1000.0}")
        except Exception:
            # kein gültiger Spindelwert gegeben
            pass

    lines.append(f"G0 X{m['start_x']:.3f} Y{m['start_y']:.3f} A{m['a_start']:.3f}")

    # Werkstück-Nullpunkt (optional, z.B. G54)
    nullpunkt = m.get("nullpunkt")
    if nullpunkt:
        code = nullpunkt.get("code", "G54")
        lines.append(f"{code}   (Werkstücknullpunkt)")
        # optional: schnelle Verfahrbewegung zum Nullpunkt, nur vorhandene Achsen verwenden
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

    lines.append(f"S{s['drehzahl']} M3   (Spindel EIN, Schleifscheibe)")
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
    s = cfg["schleifscheibe"]
    w = cfg["werkzeug"]

    a_start = m["a_start"]
    a_end = m["a_end"]
    a_steps = m["a_steps"]

    lines = []
    lines.append(f"(Schleifdurchgang {pass_num}, Z={z_tiefe:.3f})")
    lines.append(f"G1 Z{z_tiefe:.3f} F{s['schleifvorschub']:.3f}")

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
                lines.append(f"G1 X{x_start:.3f} A{a_start_pos:.3f} F{s['schleifvorschub']:.3f}")
                lines.append(f"G1 X{x_end:.3f} A{a_end_pos:.3f} F{s['schleifvorschub']:.3f}")
            else:
                steps = int(w.get("schneiden_schritte", a_steps))
                for i in range(steps + 1):
                    frac = i / steps
                    x = m["start_x"] + frac * length
                    a_pos = start_angle + frac * degrees_total
                    lines.append(f"G1 X{x:.3f} A{a_pos:.3f} F{s['schleifvorschub']:.3f}")

            # Optional: Schneiderrücken nachschleifen genau nach deinen Schritten
            # Schrittfolge pro Schneide:
            # 1) Nach dem Hauptpass: Z anheben auf Sicherheitsabstand
            # 2) Für jede Rückenstufe p=1..N:
            #    a) G0 X=start_x A= start_angle + p*angle_step
            #    b) G1 Z=pass_depth - p*ruecken_tiefe_delta
            #    c) G1 X = start_x + length  A = start_angle + drall_total + p*angle_step
            #    d) G0 Z = pass_depth + lift_after_pass (Sicherheitsabstand)
            ruecken_grad = w.get("ruecken_grad", 0.0)
            if ruecken_grad and ruecken_grad > 0 and "schneidenlaenge" in w and w["schneidenlaenge"] > 0:
                # Schritt 1 (neu): Nach dem Hauptpass Z anheben auf Sicherheitsabstand
                lift_initial = s.get("lift_after_pass", 1.0)
                z_lift_initial = z_tiefe + lift_initial
                if z_lift_initial > m["safe_z"]:
                    z_lift_initial = m["safe_z"]
                lines.append(f"G0 Z{z_lift_initial:.3f}")

                ruecken_delta = w.get("ruecken_tiefe_delta", 0.2)  # Tiefe pro Rückenstufe
                length = w["schneidenlaenge"]

                steps_r = int(w.get("ruecken_schritte", max(1, int(w.get("schneiden_schritte", a_steps)))))
                # Gesamtdrehung (Drall) der Hauptbewegung über die Länge
                if "drall_grad_pro_mm" in w:
                    drall_total = w["drall_grad_pro_mm"] * length
                else:
                    mm_per_360 = w.get("drall_steigung")
                    if not mm_per_360:
                        raise ValueError("Kein Drall angegeben (drall_grad_pro_mm oder drall_steigung fehlt)")
                    drall_total = (360.0 / mm_per_360) * length

                angle_step = ruecken_grad / steps_r

                for p in range(1, steps_r + 1):
                    # Z für diesen Rücken-Durchgang (stufenweise tiefer)
                    z_ruecken_pass = z_tiefe - p * ruecken_delta
                    if z_ruecken_pass < s["max_tiefe"]:
                        z_ruecken_pass = s["max_tiefe"]

                    start_a = start_angle + p * angle_step
                    end_a = start_angle + drall_total + p * angle_step

                    # Schritt 3: Zurück nach X=start, A=start_a (auf Sicherheits-Höhe bereits)
                    lines.append(f"G0 X{m['start_x']:.3f} A{start_a:.3f}")
                    # Schritt 4: Senken auf Z_ruecken_pass
                    lines.append(f"G1 Z{z_ruecken_pass:.3f} F{s['schleifvorschub']:.3f}")
                    # Schritt 5: Schleifen von X=start -> X=start+length mit A von start_a -> end_a
                    lines.append(f"G1 X{(m['start_x'] + length):.3f} A{end_a:.3f} F{s['schleifvorschub']:.3f}")
                    # Schritt 6: Z heben auf Sicherheitsabstand
                    lift = s.get("lift_after_pass", 1.0)
                    z_lift_pos = z_ruecken_pass + lift
                    if z_lift_pos > m["safe_z"]:
                        z_lift_pos = m["safe_z"]
                    lines.append(f"G0 Z{z_lift_pos:.3f}")

                # Am Ende der Rückenserie: zurück auf Pass-Tiefe (für Konsistenz)
                lines.append(f"G0 Z{z_tiefe:.3f}")

            # Nach dem Schliff: Z um Sicherheitsabstand anheben, dann zurück zum Start-X und A der nächsten Schneide
            lift = s.get("lift_after_pass", 1.0)
            z_lift_pos = z_tiefe + lift
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
                    f"G1 A{a_gesamt:.3f} X{x:.3f} F{s['schleifvorschub']:.3f}"
                )

            # Zurück zum Startwinkel dieser Schneide
            lines.append(f"G0 A{a_start + offset:.3f}")
            lines.append("")

    # Nach dem Pass zurück in Sicherheits-Z
    lines.append(f"G0 Z{m['safe_z']:.3f}")
    lines.append("")
    return lines


def generiere_gcode(cfg):
    s = cfg["schleifscheibe"]
    ausgabe_datei = cfg["ausgabe"]["datei"]

    lines = []
    lines += gcode_header(cfg)

    # Spindelstart beim ersten Pass (falls konfiguriert)
    if s.get('drehzahl') and s.get('spindle_on_first_pass', True):
        try:
            dreh = int(s.get('drehzahl'))
            dwell = int(s.get('spindle_dwell_ms', 1000))
            lines.append(f"M3 S{dreh}   (Spindel ein)")
            lines.append(f"G4 P{dwell/1000.0}")
        except Exception:
            pass

    aktuelle_tiefe = 0.0
    for p in range(1, s["anzahl_passe"] + 1):
        aktuelle_tiefe -= s["zustellung_pro_pass"]
        if aktuelle_tiefe < s["max_tiefe"]:
            aktuelle_tiefe = s["max_tiefe"]
        lines += gcode_schleifpass(cfg, p, aktuelle_tiefe)
        if aktuelle_tiefe <= s["max_tiefe"]:
            break

    lines += gcode_footer(cfg)

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
    parser.add_argument("--mode", choices=['edge', 'front', 'both'], default='edge', help='Generierungsmodus: edge (Schneidekanten), front (Frontfläche), both (beides). Standard: edge')
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
            generiere_gcode(cfg)
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
                generiere_front_gcode(cfg)
            except Exception as e:
                print(f'Fehler bei Front G-Code Generierung: {e}', file=sys.stderr)
                if mode == 'front':
                    sys.exit(1)
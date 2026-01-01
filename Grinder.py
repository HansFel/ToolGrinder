import json
import math
import os

# -------------------------------------------------
# G-CODE GENERATOR: FRAESER SCHAERFEN
# -------------------------------------------------

def lade_konfiguration(dateiname):
    with open(dateiname, "r") as f:
        return json.load(f)


def gcode_header(cfg):
    m = cfg["maschine"]
    s = cfg["schleifscheibe"]

    lines = []
    lines.append("(Fräser Schärfen – automatisch generiert)")
    lines.append("G21   (mm)")
    lines.append("G90   (absolute Positionierung)")
    lines.append("G17   (XY-Ebene)")
    lines.append(f"G0 Z{m['safe_z']:.3f}")
    lines.append(f"G0 X{m['start_x']:.3f} Y{m['start_y']:.3f} A{m['a_start']:.3f}")

    # Werkzeugwechsel (optional, z.B. T1 M6)
    w = cfg.get("werkzeug", {})
    tool_no = w.get("tool_number")
    if tool_no is not None:
        try:
            tool_no_int = int(tool_no)
            lines.append(f"T{tool_no_int} M6   (Werkzeugwechsel)")
        except Exception:
            lines.append(f"(Ungültige tool_number: {tool_no})")

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

    aktuelle_tiefe = 0.0
    for p in range(1, s["anzahl_passe"] + 1):
        aktuelle_tiefe -= s["zustellung_pro_pass"]
        if aktuelle_tiefe < s["max_tiefe"]:
            aktuelle_tiefe = s["max_tiefe"]
        lines += gcode_schleifpass(cfg, p, aktuelle_tiefe)
        if aktuelle_tiefe <= s["max_tiefe"]:
            break

    lines += gcode_footer(cfg)

    with open(ausgabe_datei, "w") as f:
        f.write("\n".join(lines))

    print(f"G-Code erzeugt: {ausgabe_datei}")


if __name__ == "__main__":
    config_datei = os.path.join(os.path.dirname(__file__), "ToolLib", "template1.json")
    cfg = lade_konfiguration(config_datei)
    generiere_gcode(cfg)
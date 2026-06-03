# ToolGrinder

G-Code Generator zum Schleifen von Werkzeugen auf einer vierachsigen CNC
mit X/Y/Z/A-Achsen und Schleifmittel in der Spindel.

## Optionale Maschinenlimits

Wenn in der Konfiguration `maschine.limits` gesetzt ist, prueft ToolGrinder
den erzeugten G-Code vor dem Schreiben gegen diese Achsgrenzen. Nicht gesetzte
Grenzen werden ignoriert.

```json
{
  "maschine": {
    "limits": {
      "x_min": -5.0,
      "x_max": 120.0,
      "y_min": -40.0,
      "y_max": 40.0,
      "z_min": 0.0,
      "z_max": 80.0,
      "a_min": -360.0,
      "a_max": 720.0
    }
  }
}
```

Bei einer Verletzung bricht die Generierung mit einer Fehlermeldung inklusive
G-Code-Zeile ab.

## LinuxCNC Vermessen

Der Modus `measure` erzeugt einen LinuxCNC-Messablauf mit `G38.2`. LinuxCNC
legt erfolgreiche Tastpunkte in `#5061` bis `#5069` ab; `#5070` zeigt den
Tasterfolg. Die Software nutzt diese Konvention als Grundlage fuer:

- Stirnkante/Laenge in X-Richtung
- Durchmesserermittlung ueber Z-Antastung mit Tastkugelradius-Korrektur
- Drallberechnung aus zwei Messpunkten: `(A2 - A1) / (X2 - X1)`

Beispiel:

```powershell
python Grinder.py -c ToolLib\template1.json --mode measure
```

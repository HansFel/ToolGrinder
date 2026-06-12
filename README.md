# ToolGrinder

G-Code Generator zum Schleifen von Werkzeugen auf einer vierachsigen CNC
mit X/Y/Z/A-Achsen und Schleifmittel in der Spindel.

## Datenbank-Weboberflaeche

Die Weboberflaeche unter `http://127.0.0.1:8080` verwendet SQLite als fuehrende
Datenquelle. Verwaltet werden:

- Fraeser-Vorlagen und konkrete physische Fraeser
- Schleifwerkzeuge
- versionierte Schleifstrategien
- erzeugte Auftraege mit unveraenderlichem Parameter-Snapshot

Vorhandene Dateien aus `ToolLib/*.json` werden beim ersten Start importiert.
JSON bleibt als internes Kompatibilitaetsformat fuer die bestehenden
Generatorfunktionen erhalten, wird in der normalen Weboberflaeche aber nicht
direkt bearbeitet.

Drallwerte koennen als Herstellerwinkel in Grad, als an der Maschine gemessene
A/X-Steigung in Grad/mm oder als noch unbekannt gespeichert werden. Eine
Umrechnung erfolgt nur bewusst und verwendet den aktuellen Werkzeugdurchmesser.

Die Anwendung ist Deutsch/Englisch umschaltbar.

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

Der Modus `measure` erzeugt einen LinuxCNC-Messablauf mit `G38.3`. Nach jedem
Tastversuch wird `#5070` geprueft; bei fehlendem Kontakt bricht das Programm mit
einer verstaendlichen Meldung ab. Die Pruefung wird ueber `#<_task>` waehrend
der grafischen Vorschau unterdrueckt. LinuxCNC
legt erfolgreiche Tastpunkte in `#5061` bis `#5069` ab; `#5070` zeigt den
Tasterfolg. Die Software nutzt diese Konvention als Grundlage fuer:

- Stirnkante/Laenge in X-Richtung
- Durchmesserermittlung ueber Z-Antastung mit Tastkugelradius-Korrektur:
  die A-Achse wird in kleinen Schritten gedreht, bis der hoechste Z-Tastpunkt
  gefunden ist. Der Suchwinkel entspricht einer Schneidenteilung:
  `360 / schneidenanzahl`, also 360 Grad bei Einschneider, 180 Grad bei
  Zweischneider und 120 Grad bei Dreischneider. Bei rechtsdrehendem Fraeser
  faehrt der Mittelpunkt der Tastkugel in Y auf den Tastkugelradius.
- automatische Drallberechnung aus zwei X-Messpositionen. An beiden Positionen
  wird die hoechste Schneidenlage gesucht. Die Winkeldifferenz wird auf die
  naechste Schneidenteilung normalisiert und als
  `(A2 - A1) / (X2 - X1)` berechnet.

Messwerte werden als `DEBUG`-Meldungen ausgegeben. Optional kopiert der Ablauf
sie zusaetzlich in konfigurierbare LinuxCNC-Benutzerparameter. Parameter im
Bereich `31` bis `5000` werden von LinuxCNC ueber die Parameterdatei persistent
gespeichert:

```json
{
  "aktionen": {
    "vermessen": {
      "ergebnis_parameter": {
        "stirnkante_x": 4901,
        "durchmesser": 4902,
        "drall_grad_pro_mm": 4903,
        "beste_a_position": 4904
      }
    }
  }
}
```

Beispiel:

```powershell
python Grinder.py -c ToolLib\template1.json --mode measure
```

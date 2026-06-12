# Recherche: Rotierende Zerspanwerkzeuge

## Ziel für ToolGrinder

ToolGrinder muss drei unterschiedliche Arten von Daten getrennt behandeln:

1. **Katalog- und Vorlagendaten** beschreiben einen Werkzeugtyp.
2. **Physische Werkzeugdaten** beschreiben ein einzelnes, wiederholt
   nachgeschärftes Werkzeug.
3. **Kinematische Schleifparameter** beschreiben die Maschinenbewegung, mit der
   eine Geometrie hergestellt wird.

Diese Trennung entspricht dem Grundgedanken von ISO 13399: Werkzeugdaten werden
als strukturierte Informationsobjekte und Beziehungen ausgetauscht, statt als
herstellerspezifischer Freitext.

## Relevante Normen und Quellen

- **ISO 13399-1** definiert ein allgemeines Informationsmodell für Darstellung
  und Austausch von Zerspanwerkzeugdaten.
- **ISO 3002-1** definiert Grundbegriffe für Werkzeugflächen, Schneiden,
  Bewegungen, Referenzebenen und Werkzeugwinkel.
- Herstellerinformationen zeigen, dass Durchmesser, Radius, Drallwinkel,
  Teilung, Rundlauf und Verschleiß für Auswahl, Fertigung und Prüfung relevant
  sind.

## Werkzeugfamilien

Für die erste ToolGrinder-Klassifikation:

- Schaftfräser, scharfkantig
- Schaftfräser mit Eckenradius
- Kugelkopffräser
- Torusfräser
- Bohrer
- Reibahle
- Senker

Später können Gewindebohrer, Formfräser, Stufenbohrer und Sonderwerkzeuge
ergänzt werden. Nicht jede Familie kann mit derselben Schleifstrategie oder
derselben Messroutine bearbeitet werden.

## Erforderliche Stammdaten

### Identität und Werkstoff

- Werkzeugfamilie und Ausführung
- Schneidstoff: VHM, HSS, PKD oder weitere
- Beschichtung
- Hersteller- und Artikelkennung
- Rechts- oder linksschneidend

### Hauptabmessungen

- Nenndurchmesser
- aktueller Ist-Durchmesser
- Schaftdurchmesser
- Gesamtlänge
- Schneidenlänge
- aktueller Stirn- beziehungsweise Längenbezug
- Eckenradius oder Eckenfase

### Schneidengeometrie

- Schneidenzahl
- Drallrichtung
- Drallwinkel in Grad
- Spanwinkel
- Freiwinkel und gegebenenfalls mehrere Freiflächen
- Zentrumschnitt
- gleiche oder ungleiche Teilung
- konstante oder variable Drallwinkel
- Stirnschneidenform

### Schnittstellen und Versorgung

- Schaftform, beispielsweise zylindrisch oder Weldon
- Spann- und Auskraglänge
- interne oder externe Kühlmittelzufuhr
- zulässige Drehzahl
- Rundlaufanforderung

## Wichtige Trennung: Drallwinkel und Maschinensteigung

Der **Drallwinkel** ist ein geometrischer Winkel zwischen Schneide und
Werkzeugachse. Er wird in Grad gespeichert.

Die vorhandene ToolGrinder-Größe `drall_grad_pro_mm` beschreibt dagegen die
gekoppelte A/X-Bewegung des Generators in Grad pro Millimeter. Sie ist eine
kinematische Maschinen- beziehungsweise Strategiekenngröße.

Diese Werte dürfen nicht gleichgesetzt werden. Eine spätere Umrechnung muss die
tatsächliche Werkzeuggeometrie, den Radius, das Koordinatensystem und die
gewählte Schleifkinematik ausdrücklich berücksichtigen und separat getestet
werden.

## Konsequenz für Strategien

Eine Schleifstrategie muss mindestens filtern nach:

- Werkzeugfamilie
- Schneidstoff und gegebenenfalls Beschichtung
- Schneidenzahl
- Schneid- und Drallrichtung
- Eckenform
- Durchmesserbereich
- verfügbarem Schleifwerkzeug
- Maschinen- und Achslimits

Variable Teilung oder variable Drallwinkel benötigen schneidenspezifische
Geometriedaten. Ein einzelner globaler Winkel oder A-Versatz reicht dafür nicht.

## Mess- und Lebenslaufdaten

Vor und nach jeder Schärfung sollten gespeichert werden:

- Durchmesser
- Gesamtlänge oder definierter Stirnbezug
- Eckenradius beziehungsweise Fase
- Drallwinkel, sofern messbar
- Rundlauf
- sichtbare Schäden und Ausbrüche
- Anzahl bisheriger Schärfungen
- verwendete Strategieversion und Schleifwerkzeuge
- erzeugter G-Code und Prüfsumme

## Umsetzungsstand

Die Datenbank speichert die zusätzlichen Merkmale als strukturierte
Vorlagen-Metadaten. Sie beeinflussen die Bewegungsrechnung noch nicht
automatisch. Damit können wir die Werkzeugbibliothek fachlich vervollständigen,
ohne bestehende G-Code-Geometrie stillschweigend zu verändern.

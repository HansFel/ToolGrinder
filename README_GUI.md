# GUI Problem-Behebung

## Problem
Die GUI öffnet nicht, wenn kein Pfad angegeben wird.

## Ursache
Tkinter ist in Ihrer Python-Installation nicht verfügbar.

## Lösungen

### Lösung 1: Python neu installieren (mit tkinter)
1. Laden Sie Python von python.org herunter
2. Bei der Installation: **Stellen Sie sicher, dass "tcl/tk and IDLE" ausgewählt ist**
3. Installieren Sie Python neu

### Lösung 2: Tkinter nachinstallieren
Falls Sie Python via Microsoft Store installiert haben:
```cmd
pip install tk
```

Falls das nicht funktioniert, müssen Sie Python mit vollständiger tkinter-Unterstützung neu installieren.

### Lösung 3: CLI-Modus verwenden (aktuelle Workaround)
Wenn das Programm ohne Parameter gestartet wird und keine GUI verfügbar ist, 
erscheint ein Text-Prompt:

```cmd
python Grinder.py
```

**Wichtig**: Drücken Sie einfach **Enter** (nichts eingeben), um die zuletzt verwendete 
Konfigurationsdatei zu nutzen, oder geben Sie einen neuen Pfad ein:

```
Pfad zur Konfigurationsdatei eingeben [Enter für: C:\...\template1.json]: 
```
- **Nur Enter drücken** → verwendet letzten Pfad
- **Neuen Pfad eingeben** → verwendet neuen Pfad

### Lösung 4: Pfad direkt angeben
Die einfachste Lösung ist, den Pfad direkt anzugeben:

```cmd
python Grinder.py -c ToolLib\template1.json
```

Mit Mode-Auswahl:
```cmd
python Grinder.py -c ToolLib\template1.json --mode both
```

## Prüfen ob GUI verfügbar ist
```cmd
python test_gui.py
```

Wenn "✓ GUI funktioniert vollständig!" erscheint, ist tkinter korrekt installiert.

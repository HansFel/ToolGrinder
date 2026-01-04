#!/usr/bin/env python3
import sys
import os

print("Testing GUI availability...")
print(f"Platform: {sys.platform}")
print(f"DISPLAY: {os.environ.get('DISPLAY', 'not set')}")

try:
    import tkinter as tk
    print("✓ tkinter import OK")
    
    try:
        root = tk.Tk()
        print("✓ Tk() created OK")
        root.withdraw()
        print("✓ withdraw() OK")
        
        # Test file dialog
        from tkinter import filedialog
        print("✓ filedialog import OK")
        
        root.destroy()
        print("✓ GUI funktioniert vollständig!")
        
    except Exception as e:
        print(f"✗ Fehler beim Erstellen von Tk: {e}")
        
except ImportError as e:
    print(f"✗ tkinter nicht verfügbar: {e}")

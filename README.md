# scripts

## Photo Batch Tool

Windows-Programm (Python + Tkinter) zur automatisierten Bildbearbeitung für
Serienfotos: Ordnerüberwachung, Serienerkennung anhand des EXIF-Zeitstempels,
Fotoauswahl per GUI, automatische Hintergrundentfernung, interaktiver
Kreis-Ausschnitt und Export als kreisrundes PNG in exakter physischer Größe
(Standard 19×19 mm) für z.B. Lasergravur.

### Ablauf

1. **Ordnerüberwachung** – ein konfigurierter Eingangsordner wird laufend
   überwacht (`watchdog`). Neue Fotos werden anhand ihres EXIF-Zeitstempels
   zu Serien gebündelt (Standard-Zeitfenster: 60 Sekunden). Für jede Serie
   öffnet sich ein Auswahldialog mit Miniaturansichten; Auswahl per Klick,
   Zifferntaste (1–9) oder Pfeiltasten + Enter. Einzelfoto-Serien werden
   ebenfalls kurz bestätigt, sofern nicht "Automatisch übernehmen" aktiviert
   ist. Nach Verarbeitung wandert die komplette Serie in den
   Erledigt-Ordner (Unterordner je Serie), damit nichts doppelt verarbeitet
   wird.
2. **Hintergrund entfernen** – das ausgewählte Foto wird mit `rembg`
   freigestellt (transparenter Hintergrund).
3. **Interaktiver Kreis-Ausschnitt** – im Vorschaufenster lässt sich ein
   Kreis per Maus verschieben und der Radius per Mausrad oder Schieberegler
   anpassen, mit Live-Vorschau des Ergebnisses. Der Radius wird automatisch
   auf die Bildgrenzen begrenzt.
4. **Zuschneiden** – nach Bestätigung wird kreisrund zugeschnitten, alles
   außerhalb des Kreises wird transparent.
5. **Skalierung** – der Ausschnitt wird auf exakt die konfigurierte
   Zielgröße (Standard 19×19 mm) bei der konfigurierten Ziel-DPI (Standard
   300 DPI) skaliert.
6. **Export** – Speicherung als PNG mit transparentem Hintergrund und
   DPI-Metadaten im Ausgabeordner. Der Dateiname enthält den
   Serien-Zeitstempel und optional einen Kundennamen.

Alle Ordner, das Zeitfenster, die Ziel-DPI und die Zielgröße sind über den
Button **Einstellungen** in der GUI konfigurierbar und werden in
`%APPDATA%\PhotoBatchTool\config.json` gespeichert.

### Installation

Voraussetzung: Python 3.10+ für Windows (von python.org, enthält Tkinter).

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

`rembg` lädt beim ersten Aufruf ein KI-Modell (~170 MB) herunter –
dafür ist beim ersten Start eine Internetverbindung nötig.

### Starten

```powershell
python main.py
```

### Als eigenständige .exe bauen (PyInstaller)

```powershell
pip install pyinstaller
pyinstaller PhotoBatchTool.spec
```

Die fertige `PhotoBatchTool.exe` liegt danach in `dist\`. Hinweise:

- Manche Virenscanner melden PyInstaller-EXEs fälschlich als verdächtig
  (False Positive) – ggf. Ausnahme hinzufügen.
- Das rembg-Modell wird nicht in die EXE eingebettet, sondern beim ersten
  Start heruntergeladen und lokal zwischengespeichert
  (`%USERPROFILE%\.u2net`).

### Projektstruktur

```
main.py                        Einstiegspunkt
photo_batch_tool/
  config.py                    Konfiguration (Laden/Speichern als JSON)
  exif_utils.py                EXIF-Zeitstempel auslesen
  series_builder.py            Gruppierung neuer Fotos zu Serien
  watcher.py                   Ordnerüberwachung (watchdog)
  processing/
    background_removal.py      rembg-Anbindung
    circle_crop.py              Kreisförmiger Zuschnitt
    export.py                   Skalierung + PNG-Export mit DPI-Metadaten
    errors.py                   Fehlerklassen (kein Objekt erkannt, Radius zu groß, ...)
  gui/
    main_window.py              Hauptfenster, Ablaufsteuerung
    series_selector.py           Serien-Auswahldialog
    circle_crop_editor.py        Interaktiver Kreis-Editor
    settings_dialog.py           Einstellungsdialog
```

### Bekannte Grenzen

- Erste `rembg`-Ausführung ist langsam (Modell-Download/-Ladezeit).
- Unterstützte Bildformate: JPEG, PNG, TIFF, BMP.

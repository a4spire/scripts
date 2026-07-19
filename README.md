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

### Serienerkennung per Bildvergleich (bei größerem Zeitabstand)

Ein zu großer Zeitabstand reißt eine Serie normalerweise auseinander, auch
wenn die Fotos eigentlich zusammengehören (z.B. weil zwischen zwei Aufnahmen
eine Pause war). Ist **„Ähnliche Fotos trotz größerem Zeitabstand zur
selben Serie zählen"** aktiviert (Standard: an), vergleicht das Programm
in diesem Fall zusätzlich zwei aufeinanderfolgende Fotos per
Bild-Fingerabdruck (Differenz-Hash): Sind sie sich eindeutig sehr ähnlich,
zählen sie trotzdem zur selben Serie – aber nur bis zu einer zusätzlichen
Zeitspanne über das normale Zeitfenster hinaus (Standard: 240 Sekunden),
damit tatsächlich unabhängige Fotos nicht versehentlich zusammengelegt
werden.

Zwei Einstellungen dazu:

- **Ähnlichkeits-Schwellenwert** (Standard 8, Skala 0–64): wie streng der
  Vergleich ist. 0 = nur bei praktisch identischen Bildern; höhere Werte
  erlauben mehr Unterschied (z.B. leicht andere Belichtung/Rahmung) und
  erhöhen damit auch das Risiko falscher Zusammenlegungen.
- **Zusätzliche Zeit für Ähnlichkeitserkennung (Sekunden)**: wie weit über
  das normale Zeitfenster hinaus die Ähnlichkeitsprüfung überhaupt greifen
  darf.

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

### Fertige .exe ohne eigenen Build herunterladen

Ein GitHub-Actions-Workflow (`.github/workflows/build-windows-exe.yml`)
baut die `.exe` automatisch auf einem `windows-latest`-Runner bei jedem
Push auf diesen Branch (oder manuell über "Run workflow").

So kommst du an die Datei:

1. GitHub → Tab **Actions** → Workflow **"Build Windows EXE"** öffnen.
2. Den neuesten (grünen) Lauf anklicken.
3. Unter **Artifacts** `PhotoBatchTool-windows-exe` herunterladen (ZIP)
   und entpacken – enthält `PhotoBatchTool.exe`.

Kein lokales Python oder PyInstaller nötig, nur ein Browser und ein
GitHub-Account mit Zugriff auf das Repo.

### Projektstruktur

```
main.py                        Einstiegspunkt
photo_batch_tool/
  config.py                    Konfiguration (Laden/Speichern als JSON)
  exif_utils.py                EXIF-Zeitstempel auslesen
  series_builder.py            Gruppierung neuer Fotos zu Serien
  image_similarity.py          Bild-Fingerabdruck (dHash) für Ähnlichkeitsvergleich
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

### Modell wird beim Build eingebettet (keine Internetverbindung beim Endnutzer nötig)

Der GitHub-Actions-Workflow lädt das U2Net-Modell (~170 MB) bereits während
des Windows-Builds herunter (der Build-Runner hat garantiert Internetzugang)
und bettet es in die `.exe` ein. Beim ersten Start kopiert das Programm das
eingebettete Modell automatisch nach `%USERPROFILE%\.u2net\u2net.onnx` – der
Endnutzer-Rechner braucht dafür **keine eigene Internetverbindung mehr**.
Das gilt nur für die per GitHub Actions gebaute `.exe` aus diesem Repo, nicht
für einen manuellen `pyinstaller`-Build ohne den Modell-Download-Schritt aus
der Workflow-Datei.

### Fehlerbehebung: Hintergrundentfernung hängt / reagiert nicht

Falls trotzdem keine Reaktion kommt (z.B. bei `python main.py` aus dem
Quellcode ohne eingebettetes Modell, oder wenn der Build ohne den
Modell-Download-Schritt lief): `rembg` versucht dann beim allerersten Aufruf,
das Modell selbst herunterzuladen, von

```
https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net.onnx
```

und legt es lokal ab unter:

```
%USERPROFILE%\.u2net\u2net.onnx
```

Ist diese Datei noch nicht vorhanden (oder unvollständig/0 Byte), scheitert
der Download meist an fehlendem Internet oder einer Firewall/einem Proxy,
die die Verbindung nicht ablehnen, sondern einfach hängen lassen. Das
Programm bricht die Hintergrundentfernung nach spätestens 5 Minuten
(erster Lauf) bzw. 90 Sekunden (danach, wenn das Modell schon lokal liegt)
mit einer Fehlermeldung ab – bis dahin kann es aber wie ein Einfrieren
wirken.

**Abhilfe:**

1. Die offizielle, per GitHub Actions gebaute `.exe` verwenden (siehe oben) –
   die braucht gar keinen eigenen Download mehr.
2. Falls doch ein eigener Download nötig ist: prüfen, ob der Rechner
   grundsätzlich Internetzugang hat (z.B. eine beliebige Webseite im Browser
   öffnen). Falls nicht: Netzwerk/Firewall des Test-Rechners prüfen bzw. mit
   der IT-Abteilung klären, dass ausgehende HTTPS-Verbindungen zu
   `github.com` erlaubt sind.
3. **Ohne Internet auf dem Zielrechner:** Die Datei `u2net.onnx` (~170 MB,
   z.B. von einem anderen Rechner mit funktionierendem Internet oder direkt
   über obige URL) manuell nach `%USERPROFILE%\.u2net\u2net.onnx` kopieren –
   danach braucht `rembg` keine Internetverbindung mehr.

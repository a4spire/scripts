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

### Lizenzsystem

Das Programm prüft beim Start eine Lizenz:

- **Erstinstallation**: automatische Testphase von 6 Monaten ab dem ersten
  Programmstart (Installationsdatum wird in
  `%APPDATA%\PhotoBatchTool\license.json` und zusätzlich in der Windows-Registry
  gespeichert, damit das Löschen einer der beiden Stellen die Testphase nicht
  zurücksetzt).
- Läuft die Testphase ab (oder ein eingegebener Lizenzschlüssel), öffnet sich
  beim nächsten Start ein Dialog, der einen gültigen Lizenzschlüssel verlangt.
  Ohne gültigen Schlüssel lässt sich das Programm nicht weiter nutzen.
- Über den Button **Lizenz verwalten** im Hauptfenster lässt sich jederzeit
  der aktuelle Status einsehen oder ein neuer Schlüssel eingeben (z.B. Upgrade
  von der Testphase auf eine bezahlte Lizenz).

**Technisch**: Lizenzschlüssel sind mit Ed25519 signierte, Base32-kodierte
Zeichenketten (`XXXXX-XXXXX-...`), die ein Ablaufdatum enthalten. Die App
enthält nur den **öffentlichen** Schlüssel (`photo_batch_tool/licensing.py`,
`PUBLIC_KEY_B64`) und kann damit ausschließlich Signaturen *prüfen* – neue
gültige Schlüssel lassen sich nur mit dem privaten Schlüssel erzeugen, der
ausschließlich lokal beim Entwickler liegt (`keygen/keys/private_key.pem`,
per `.gitignore` von Git ausgeschlossen). Das ist bewusst kein
hundertprozentiger Kopierschutz (ein versierter Nutzer könnte lokale Dateien
manipulieren), aber ein für ein Werkzeug dieser Größenordnung angemessener
Schutz gegen einfaches Weiterreichen oder Zurücksetzen der Testphase.

#### Keygen-Tool (nur für dich als Entwickler/Verkäufer)

`keygen/keygen.py` ist ein separates, kleines Tkinter-Tool – es wird **nicht**
in die Kunden-EXE gebaut (es liegt außerhalb von `photo_batch_tool/` und wird
von `main.py` nicht importiert).

```powershell
python keygen\keygen.py
```

Beim ersten Start erzeugt es automatisch ein neues Ed25519-Schlüsselpaar unter
`keygen/keys/private_key.pem` und zeigt den zugehörigen **öffentlichen**
Schlüssel an (Button "Kopieren"). Dieser muss einmalig in
`photo_batch_tool/licensing.py` als `PUBLIC_KEY_B64` eingetragen werden,
bevor die Kunden-EXE gebaut wird (ist in diesem Repo bereits erledigt).

Im Tool selbst: Gültigkeitsdauer (Tage/Monate/Jahre) und optional eine
Kunden-Referenz eingeben, auf "Schlüssel generieren" klicken – der fertige
Lizenzschlüssel erscheint zum Kopieren oder Speichern als `.lic`-Datei.
Alle erzeugten Schlüssel werden zur eigenen Buchhaltung lokal in
`keygen/issued_keys.csv` protokolliert (ebenfalls von Git ausgeschlossen).

**Wichtig:** `keygen/keys/private_key.pem` ist das "Geheimnis" des gesamten
Systems – wer diese Datei besitzt, kann beliebig viele gültige Lizenzen
erzeugen. Niemals committen, teilen oder auf einem Kundenrechner ablegen.
Sicher (z.B. Passwort-Manager, verschlüsseltes Offline-Backup) aufbewahren;
bei Verlust müssen ein neues Schlüsselpaar erzeugt und der neue öffentliche
Schlüssel in `licensing.py` eingetragen werden (bereits ausgegebene alte
Lizenzschlüssel werden dadurch ungültig).

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
  watcher.py                   Ordnerüberwachung (watchdog)
  license_format.py            Gemeinsames Schlüssel-Binärformat (keine Geheimnisse)
  licensing.py                 Lizenzprüfung (Public Key), Testphasen-Tracking
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
    license_dialog.py            Lizenz-Aktivierungs-/Statusdialog
keygen/
  keygen.py                     Entwickler-Tool zum Erzeugen von Lizenzschlüsseln
  keys/private_key.pem          Privater Schlüssel (lokal, NICHT in Git)
```

### Bekannte Grenzen

- Erste `rembg`-Ausführung ist langsam (Modell-Download/-Ladezeit).
- Unterstützte Bildformate: JPEG, PNG, TIFF, BMP.

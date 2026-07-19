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
3. **Interaktiver Kreis-Ausschnitt** – der Kreis wird per Gesichtserkennung
   automatisch vorpositioniert: Zentrum in der Mitte aller erkannten Köpfe,
   Radius so groß, dass alle Köpfe mit kleinem Rand hineinpassen (werden
   keine Gesichter erkannt, startet der Kreis mittig im Bild). Im
   Vorschaufenster lässt sich der Kreis per Klick verschieben, per Ziehpunkt
   am Kreisrand direkt in der Größe anpassen, oder per Mausrad/Schieberegler
   skalieren – mit Live-Vorschau des Ergebnisses. Der Radius wird automatisch
   auf die Bildgrenzen begrenzt.
4. **Zuschneiden** – nach Bestätigung wird kreisrund zugeschnitten, alles
   außerhalb des Kreises wird transparent.
5. **Skalierung** – der Ausschnitt wird auf exakt die konfigurierte
   Zielgröße (Standard 19×19 mm) bei der konfigurierten Ziel-DPI (Standard
   300 DPI) skaliert.
6. **Export** – Speicherung als PNG mit transparentem Hintergrund und
   DPI-Metadaten im Ausgabeordner. Der Dateiname enthält den
   Serien-Zeitstempel und optional einen Kundennamen (die Abfrage danach
   lässt sich in den Einstellungen abschalten, falls nicht relevant).

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

### Gesichtserkennung für die Kreis-Vorpositionierung

Die Standardposition des Kreises im Kreis-Editor wird per Gesichtserkennung
(OpenCV, Haar-Cascade-Klassifikatoren für Frontal- und Profilgesichter)
bestimmt – ganz ohne Modell-Download, die Klassifikatoren sind im
`opencv-python-headless`-Paket selbst enthalten. Erkennt das Programm ein
oder mehrere Gesichter, wird das Zentrum auf die Mitte aller erkannten
Köpfe gelegt und der Radius so gewählt, dass alle Köpfe plus ein kleiner
Rand (15 %) hineinpassen. Ohne erkanntes Gesicht (z.B. bei Rückenansicht,
ungewöhnlichem Winkel oder Nicht-Personen-Fotos) startet der Kreis wie
zuvor mittig im Bild. Das ist immer nur ein Startwert – der Kreis lässt
sich danach frei verschieben und in der Größe anpassen.

### Automatische Qualitätsprüfung (verschwommen, Belichtung, Augen/Gesicht)

Bevor eine Serie zur Auswahl angezeigt wird, prüft das Programm optional
jedes Foto auf typische Qualitätsprobleme:

- **Verschwommen**: Schärfe-Metrik (Varianz der Laplace-Transformation,
  ein etabliertes, einfaches Verfahren) – niedriger Wert = unscharf.
- **Über-/Unterbelichtung**: mittlere Helligkeit außerhalb eines
  einstellbaren Bereichs (Standard 40–220 auf einer Skala 0–255).
- **Augen evtl. geschlossen**: Heuristik auf Basis der Gesichtserkennung –
  wird ein Gesicht erkannt, aber innerhalb des oberen Gesichtsbereichs kein
  Auge gefunden (OpenCV-Augen-Cascade), gilt das als Hinweis auf
  geschlossene Augen. Das ist kein zuverlässiger Test (Brille, Seitenwinkel,
  schlechtes Licht können Augen ebenfalls "verstecken"), sondern nur ein
  zusätzliches Warnsignal.
- **Kein Gesicht erkannt**: separat gemeldet, falls für den Anwendungsfall
  (Kopf-/Porträtfotos) relevant.

Zwei Modi, einstellbar unter **Einstellungen → Automatische
Qualitätsprüfung**:

- **Nur markieren** (Standard): alle Fotos bleiben auswählbar, betroffene
  zeigen im Auswahldialog eine Warnung mit den erkannten Gründen.
- **Automatisch aussortieren**: betroffene Fotos werden gar nicht erst zur
  Auswahl angezeigt und landen nach Abschluss der Serie automatisch in
  `<Erledigt-Ordner>\aussortiert\<Serien-Zeitstempel>\` – nicht gelöscht,
  sondern nur aus dem Weg geräumt, damit sie sich bei Bedarf wiederfinden
  lassen. Sollte eine ganze Serie ausschließlich aus solchen Fotos bestehen,
  werden trotzdem alle zur Auswahl angezeigt (mit Warnung), damit immer eine
  Wahl möglich bleibt.

Schwellenwerte (Schärfe, Mindest-/Maximalhelligkeit) sind ebenfalls in den
Einstellungen justierbar; die Funktion lässt sich auch komplett abschalten.

**Bewusst nicht automatisch ausgewertet** (zur Transparenz): mehrere
Gesichter im Bild (kann bei Gruppenfotos legitim sein, keine
Qualitätsaussage) und sehr niedrige Bildauflösung. Bei Bedarf lässt sich
das ergänzen.

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
  (`%USERPROFILE%\.u2net`). Siehe Abschnitt "Fehlerbehebung" unten für
  Details zum Download-Mechanismus.

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
    background_removal.py      rembg-Anbindung + eigener Modell-Download (Timeout/Retry)
    face_detection.py           Gesichtserkennung (OpenCV) für Kreis-Vorpositionierung
    quality_check.py            Qualitätsprüfung (Unschärfe, Belichtung, Augen/Gesicht)
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
- Die Gesichtserkennung ist ein Best-Effort-Startwert (Haar-Cascade-Verfahren):
  funktioniert gut bei einigermaßen frontal/seitlich sichtbaren Gesichtern,
  kann bei ungünstigen Winkeln, starker Verdeckung oder sehr kleinen Gesichtern
  auch mal nichts finden – dann startet der Kreis mittig im Bild.
- Die Qualitätsprüfung (insbesondere "Augen evtl. geschlossen") ist eine
  Heuristik, kein zuverlässiger Test – als Warnsignal gedacht, nicht als
  Garantie.

### Modell-Download: eigener Mechanismus mit Timeout und Wiederholung

Das Programm lädt das rembg-U2Net-Modell (~170 MB) beim ersten Bedarf selbst
herunter, statt sich auf rembg's eingebauten Downloader zu verlassen (der hat
kein Timeout und kann bei einer Firewall, die Verbindungen still fallen lässt
statt sie abzulehnen, unbegrenzt hängen bleiben). Der eigene Download:

- läuft mit einem Timeout von 20 Sekunden pro Versuch, bis zu 3 Versuche mit
  kurzer Pause dazwischen (Fehlschlag also spätestens nach ca. 1 Minute klar
  erkennbar, nicht nach mehreren Minuten stillem Warten),
- schreibt zunächst in eine temporäre Datei und verschiebt sie erst nach
  erfolgreicher Prüfsummen-Kontrolle (MD5) an den Zielpfad – ein Abbruch
  mitten im Download (Absturz, Kill, Stromausfall) kann daher nie eine
  kaputte/halbe Datei am erwarteten Ort hinterlassen; beim nächsten Start
  wird einfach sauber neu heruntergeladen,
- lädt von `https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net.onnx`
  nach `%USERPROFILE%\.u2net\u2net.onnx` (Speicherort und URL direkt aus dem
  rembg-Quellcode verifiziert, nicht geraten).

### Fehlerbehebung: Hintergrundentfernung hängt / reagiert nicht

Scheitert der Download nach den 3 Versuchen, meldet das Programm einen
klaren Fehler statt zu hängen. Mögliche Ursachen und Abhilfen:

1. Prüfen, ob der Rechner grundsätzlich Internetzugang hat (z.B. eine
   beliebige Webseite im Browser öffnen). Falls nicht: Netzwerk/Firewall
   des Test-Rechners prüfen bzw. mit der IT-Abteilung klären, dass
   ausgehende HTTPS-Verbindungen zu `github.com` erlaubt sind.
2. **Ohne Internet auf dem Zielrechner:** Die Datei `u2net.onnx` (~170 MB,
   z.B. von einem anderen Rechner mit funktionierendem Internet, oder
   direkt über obige URL) manuell nach `%USERPROFILE%\.u2net\u2net.onnx`
   kopieren – danach ist kein eigener Download mehr nötig.

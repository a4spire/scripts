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
   zu Serien gebündelt (Standard-Zeitfenster: 15 Sekunden). Für jede Serie
   öffnet sich ein Auswahldialog mit Miniaturansichten; das best bewertete
   Foto (siehe Qualitätsprüfung) ist bereits vorausgewählt. Auswahl per
   Klick, Zifferntaste (1–9) oder Pfeiltasten + Enter. Einzelfoto-Serien
   werden ebenfalls kurz bestätigt, sofern nicht "Automatisch übernehmen"
   aktiviert ist. Nach Verarbeitung wandert die **komplette** Serie
   (ausgewähltes Foto, nicht gewählte Fotos und ggf. aussortierte Fotos) aus
   dem Überwachungsordner in den Erledigt-Ordner (Unterordner je Serie),
   damit nichts doppelt verarbeitet wird und keine Restbestände im
   Überwachungsordner liegen bleiben.
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
   lässt sich in den Einstellungen abschalten, falls nicht relevant). Direkt
   danach kann optional die Anzahl abgegebener Vouchers abgefragt werden
   (ebenfalls über die Einstellungen an-/abschaltbar, standardmäßig aus) –
   die Eingabe wird im Protokoll festgehalten ("Vouchers abgegeben: N").

Alle Ordner, das Zeitfenster, die Ziel-DPI und die Zielgröße sind über den
Button **Einstellungen** in der GUI konfigurierbar und werden in
`%APPDATA%\PhotoBatchTool\config.json` gespeichert. Das Einstellungsfenster
ist frei in der Größe veränderbar (Ziehen am Fensterrand) und scrollt seinen
Inhalt, falls er nicht auf den Bildschirm passt -- "Speichern" und
"Abbrechen" bleiben dabei immer sichtbar am unteren Rand.

### Wie lange dauert die Verarbeitung, und "Jetzt scannen"

Im Normalbetrieb (Modell bereits heruntergeladen) dauert die
Hintergrundentfernung eines Fotos typischerweise wenige Sekunden bis
niedrige zweistellige Sekunden, abhängig von Fotogröße und Hardware. Das
Protokoll zeigt das jetzt transparent an:

- "Erkennung nach X,Xs" -- wie lange die Serienerkennung (Zeitfenster) gebraucht hat.
- "Hintergrundentfernung abgeschlossen in X,Xs: <Dateiname>" -- reine Verarbeitungszeit dieses Schritts.
- "Gesamtdauer seit Erkennung: X,Xs" -- alles zusammen, von der Serienerkennung bis zum fertigen Export.

Zwei Optimierungen sorgen dafür, dass das so schnell wie möglich geht:

- Das rembg-KI-Modell wird nur **einmal** geladen und danach für alle Fotos
  wiederverwendet, statt bei jedem Foto neu von der Festplatte geladen zu
  werden (das Neuladen allein kostet spürbar Zeit und wiederholt sich sonst
  bei jedem einzelnen Foto).
- Große Kamerafotos werden vor der Hintergrundentfernung intern verkleinert
  (die konfigurierte Zielgröße/DPI bestimmt, wie stark -- mit großzügigem
  Puffer für Gesichtserkennung und Kreiszuschnitt). Das finale Ergebnis wird
  davon nicht sichtbar schlechter, da der Export ohnehin nur wenige hundert
  Pixel groß ist (z.B. 224×224 px bei 19 mm/300 DPI).

Falls die Hintergrundentfernung bei bereits vorhandenem Modell trotzdem
länger als 90 Sekunden für ein einzelnes Foto braucht, erscheint eine
Fehlermeldung dazu (ungewöhnlich großes/komplexes Foto oder ausgelastete
Hardware, kein Internet-/Firewall-Hinweis in diesem Fall -- der ist nur beim
allerersten Modell-Download relevant, siehe unten).

Der Button **"Jetzt scannen"** löst die Erkennung/Verarbeitung sofort aus,
statt auf den Ablauf des Zeitfensters zu warten -- praktisch, wenn bereits
Fotos im Überwachungsordner liegen und man nicht warten möchte, oder um die
Überwachung bei Bedarf manuell anzustoßen. Läuft die Überwachung noch nicht,
wird sie dabei automatisch gestartet.

### Mehrere Fotos gleichzeitig verarbeiten

Die Hintergrundentfernung mehrerer Serien kann parallel laufen (Standard: je
nach CPU-Kernanzahl bis zu 4 gleichzeitig, siehe Protokoll-Meldung beim
Start "Bis zu N Foto(s) können gleichzeitig..."), statt eine Serie komplett
abzuwarten, bevor die nächste überhaupt angefangen wird. Nur die
Dialogfenster (Fotoauswahl, Kreisausschnitt, Kundennamen-Abfrage) erscheinen
weiterhin nacheinander -- pro Serie jeweils ein Fenster gleichzeitig, damit
nichts durcheinandergerät --, während die eigentliche (langsame)
Hintergrundentfernung mehrerer Serien im Hintergrund parallel läuft.

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
  `<Erledigt-Ordner>\_aussortiert\<Datum>\` – nicht gelöscht, sondern nur aus
  dem Weg geräumt, damit sie sich bei Bedarf wiederfinden lassen. Bewusst
  **nicht** pro Serie getrennt: Aussortierte Fotos aus mehreren Serien am
  gleichen Tag landen in einem gemeinsamen Tagesordner statt in vielen
  einzelnen Serien-Unterordnern (bei gleichnamigen Dateien wird automatisch
  eine Zahl angehängt, damit nichts überschrieben wird). Sollte eine ganze
  Serie ausschließlich aus solchen Fotos bestehen, werden trotzdem alle zur
  Auswahl angezeigt (mit Warnung), damit immer eine Wahl möglich bleibt.

Schwellenwerte (Schärfe, Mindest-/Maximalhelligkeit) sind ebenfalls in den
Einstellungen justierbar; die Funktion lässt sich auch komplett abschalten.

**Bewusst nicht automatisch ausgewertet** (zur Transparenz): mehrere
Gesichter im Bild (kann bei Gruppenfotos legitim sein, keine
Qualitätsaussage) und sehr niedrige Bildauflösung. Bei Bedarf lässt sich
das ergänzen.

#### Bei eindeutiger Auswahl automatisch bestätigen

Zusätzliche Option (nur wirksam im Modus "Automatisch aussortieren"):
Bleibt nach dem Aussortieren schlechter Fotos aus einer mehrteiligen Serie
genau **ein** unmarkiertes Foto übrig – z.B. weil von drei Fotos zwei
aussortiert wurden –, wird dieses eine Foto automatisch übernommen, ganz
ohne Auswahldialog. Das ist eine eigene, bewusst getrennte Einstellung von
"Einzelfoto-Serien automatisch übernehmen": Eine Serie, die von vornherein
nur aus einem einzigen Foto besteht, fragt weiterhin kurz nach, sofern
dieses Foto Qualitätsprobleme zeigt oder die separate Option dafür nicht
aktiviert ist – "eindeutig" bedeutet hier ausdrücklich "durch Aussortieren
eindeutig geworden", nicht "es gab ohnehin nur eins".

### Vorauswahl des best bewerteten Fotos

Im Auswahldialog ist immer automatisch das nach Qualitätskriterien am besten
bewertete Foto der Serie markiert (nicht nur bei aktivierter Qualitätsfilterung
mit "Automatisch aussortieren", sondern auch im Standardmodus "Nur
markieren"). Bewertet wird – nur innerhalb derselben Serie, nicht als
absoluter Vergleichswert – zuerst danach, ob ein Foto überhaupt als
qualitativ auffällig markiert wurde (unauffällige Fotos gewinnen immer),
dann nach Schärfe, dann nach Belichtungsnähe zu einem neutralen Mittelton.
Ist die Qualitätsprüfung deaktiviert, bleibt es beim bisherigen Verhalten
(erstes Foto der Serie vorausgewählt). Das ist immer nur ein Vorschlag – jede
andere Auswahl bleibt per Klick, Zifferntaste oder Pfeiltasten möglich.

### Automatische Bestätigung per Zeitlimit

Zwei unabhängige Zeitlimits, jeweils unter **Einstellungen**, nach demselben
Prinzip:

- **Auswahl-Zeitlimit (Fotoauswahl)**: Läuft der Countdown im
  Foto-Auswahldialog ab, wird die zu diesem Zeitpunkt markierte Auswahl
  automatisch bestätigt (Standard: das vorausgewählte, best bewertete Foto,
  sofern nicht manuell umgestellt).
- **Auswahl-Zeitlimit (Kreisausschnitt)**: Läuft der Countdown im
  Kreis-Editor ab, wird der zu diesem Zeitpunkt eingestellte Kreisausschnitt
  automatisch bestätigt (Standard: die Vorpositionierung per
  Gesichtserkennung, sofern nicht manuell verschoben/skaliert).

Bei beiden wird der Countdown sichtbar angezeigt. Sobald manuell eingegriffen
wird – ein anderes Foto per Klick/Pfeiltasten ausgewählt, oder der Kreis per
Ziehen, Ziehpunkt, Mausrad oder Schieberegler verändert – wird der Countdown
endgültig abgebrochen (nicht nur pausiert oder zurückgesetzt): Ab diesem
Zeitpunkt ist die manuelle Eingabe maßgeblich, und nur noch die
Bestätigen-Aktion (Button, Enter, Doppelklick) schließt den Dialog ab.

Ist eines der beiden Zeitlimits auf **0 Sekunden** gesetzt, wird der
jeweilige Dialog gar nicht erst angezeigt: Die Vorauswahl (best bewertetes
Foto bzw. Gesichtserkennungs-Kreis) wird sofort automatisch übernommen.
Beim Auswahl-Zeitlimit hat das Vorrang vor allen anderen automatischen
Modi (Einzelfoto-Auto-Übernahme, eindeutige Auswahl nach Aussortierung).
Werden beide Zeitlimits auf 0 gesetzt, läuft eine Serie komplett ohne
Rückfrage durch – geeignet für einen vollautomatischen Batch-Betrieb.

### Vollautomatischer Schnellmodus (Erkennung + Verarbeitung unter 20 Sekunden)

In den Einstellungen übernimmt der Button **"Schnellmodus übernehmen"**
(oben in der Einstellungen-Übersicht) mit einem Klick eine Kombination aus
bereits vorhandenen Optionen, die eine Serie komplett ohne Rückfrage
verarbeitet:

- Zeitfenster Serienerkennung auf 10 Sekunden
- Einzelfoto-Serien automatisch übernehmen: an
- Kundennamen-Abfrage beim Export: aus (eine offene Modal-Abfrage würde die
  Verarbeitung sonst anhalten, bis jemand etwas eintippt)
- Automatische Qualitätsprüfung an, Modus "Automatisch aussortieren"
- Bei eindeutiger Auswahl automatisch bestätigen: an
- Beide Zeitlimits (Fotoauswahl, Kreisausschnitt) an und auf 0 Sekunden

Die Felder werden nur befüllt, nicht sofort gespeichert – vor dem Klick auf
"Speichern" lässt sich alles noch prüfen oder anpassen (z.B. andere
Ordner, DPI/Zielgröße, Ähnlichkeits-Einstellungen).

Damit das Zeitbudget von ca. 20 Sekunden ab dem letzten Foto einer Serie
zuverlässig eingehalten wird, wurden außerdem folgende Stellen im Programm
beschleunigt:

- Der Ordnerüberwachungs-Ordner wird per `watchdog`-Ereignis sofort
  benachrichtigt; die Prüfung, ob eine Datei fertig geschrieben ist
  (Dateigröße stabil), pollt jetzt alle 0,2 statt 0,5 Sekunden.
- Das Zeitfenster zur Serienerkennung (siehe oben) läuft als Debounce-Timer:
  Er läuft `Zeitfenster`-Sekunden nach dem jeweils letzten Foto ab, bevor
  die Serie zur Verarbeitung freigegeben wird – ein niedrigerer Wert (z.B.
  10 Sekunden) senkt diese Wartezeit direkt. Ein zu niedriger Wert
  verringert allerdings die Toleranz für Pausen zwischen Aufnahmen
  derselben Serie; Fotos, die weiter auseinanderliegen, werden nur dann noch
  zusammengeführt, wenn die Bildähnlichkeits-Erkennung sie **innerhalb**
  desselben Erkennungsfensters als zusammengehörig erkennt.
- Die GUI prüft alle 150 statt 300 Millisekunden auf eine fertig erkannte
  Serie.
- Im Protokoll wird jetzt transparent protokolliert, wie lange die
  Erkennung gedauert hat ("Erkennung nach X,Xs") und wie viel Zeit
  insgesamt von der Erkennung bis zum Abschluss der Serie (Export +
  Verschieben) vergangen ist ("Gesamtdauer seit Erkennung: X,Xs") – so lässt
  sich das 20-Sekunden-Ziel im laufenden Betrieb direkt nachvollziehen.

Eine Ausnahme bleibt unvermeidbar: Beim allerersten Start muss das
rembg-KI-Modell heruntergeladen werden (siehe unten), was mehrere Minuten
dauern kann. Das 20-Sekunden-Ziel gilt für den Normalbetrieb mit bereits
vorhandenem Modell.

### Drag & Drop für die Batch-Verarbeitung

Im Hauptfenster gibt es ein Ablagefeld ("Fotos oder Ordner hierher ziehen für
Batch-Verarbeitung"); Drag & Drop funktioniert aber auf dem gesamten
Fenster, nicht nur auf dem Feld selbst. Man kann:

- einzelne Fotos,
- mehrere Fotos gleichzeitig, oder
- einen ganzen Ordner (z.B. den kompletten Inhalt einer Speicherkarte,
  inklusive Unterordnern)

hineinziehen. Alle enthaltenen, unterstützten Bilddateien werden **als
Kopie** in den Überwachungsordner übernommen (die Originaldateien bleiben
unangetastet, egal woher sie stammen) und durchlaufen danach exakt denselben
Prozess wie normal per Ordnerüberwachung ankommende Fotos: Serienerkennung,
Auswahl, Hintergrundentfernung, Kreisausschnitt, Export und Verschieben nach
Erledigt. Läuft die Überwachung noch nicht, wird sie durch das Ablegen
automatisch gestartet.

Voraussetzung ist das Paket `tkinterdnd2` (in `requirements.txt` enthalten
und in der PyInstaller-.exe mitgebaut). Fehlt es zur Laufzeit, wird das
Ablagefeld entsprechend beschriftet und im Protokoll ein Hinweis ausgegeben
– der Rest der Anwendung (inkl. normaler Ordnerüberwachung) funktioniert
davon unabhängig weiter.

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

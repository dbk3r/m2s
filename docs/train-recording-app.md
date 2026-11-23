# Aufnahme-App

Desktop-Fenster für den Ablauf in `songs/aufnahme/reihenfolge.txt`. Die Notenordner direkt unter `songs/aufnahme` sind die Textvorlage. Die App kopiert sie in den Ordner des Sängers und geht diese Kopie durch. Sie erfindet keine neuen Zeilen, Noten oder Lautstärken.

## Ablauf

Oben links der Sänger. Hinzufügen legt `songs/aufnahme/<name>` an und kopiert die Textvorlage hinein. Entfernen löscht diesen Ordner samt Aufnahmen, nach einer Rückfrage. Wechseln lädt die Jobs dieses Sängers.

Darunter jede Aufnahmesituation, geordnet wie der Plan. Zuerst `c2`, dann `d#2`, `f#2`, `a2`, `c3`, `d#3`, `f#3`, `a3`, `c4`, `d#4`, `f#4`, `a4`, `c5`. Unter jeder Note zuerst `leise`, dann `laut`, darin die Dateien `001` bis `165`.

Ein Klick öffnet rechts den Text aus der TXT, die Tonhöhe des Ordners und die Lautstärke des Ordners.

Ein Knopf schaltet zwischen Aufnahme und Stopp. Dieselbe Taste ist die Leertaste. Eine neue Aufnahme ersetzt den Take, der noch nicht übernommen wurde. Anhören spielt ihn ab. Übernehmen legt ihn unter demselben Namen wie die TXT ab und markiert den Job als erledigt. Verwerfen löscht den Take. „Ganze Note auslassen“ markiert die noch offenen Jobs dieser Note, ohne eine WAV zu schreiben.

Eine WAV, die schon neben der TXT liegt, gilt als erledigt.

## Anzeige

Die Nadel ist ein Stimmgerät. Bezug ist die Note des Ordners, Kammerton a4 = 440 Hz. Daneben steht der gerade erkannte Ton in derselben Schreibweise wie die Ordner, zum Beispiel `gesungen d#3`, und die Abweichung in Cent. Liegt kein brauchbarer Ton im Puffer, steht dort „kein Ton“.

Die Farben der Nadel sind nur die Anzeige: bis 35 Cent mittig, bis 80 Cent daneben, darüber weit daneben. Der Rand der Skala ist ein Halbton, 100 Cent. Sie sind keine Abnahme. Übernehmen entscheidet die singende Person.

Der Pegelbalken läuft von −60 bis 0 dBFS. Für `leise` ist die grüne Spanne −36 bis −24 dBFS, für `laut` −18 bis −8 dBFS, jeweils als RMS. Darunter steht `lauter`, `leiser` oder `passt`. Das sind Anzeige-Spannen wie die Cent-Bänder, keine Abnahme. Eine LUFS-Zahl steht in der Studie nicht.

Unter dem Text steht die Erinnerung aus dem Plan: Atem vor und nach der Zeile, kein Vibrato, kein Hall. Atem und Vibrato prüft die App nicht.

Nach Stopp prüft die App den Take und schreibt `brauchbar` oder `nochmal` mit dem Grund. Geprüft wird die Länge 3–6 Sekunden, der Median der erkannten Tonhöhe gegen die 80-Cent-Grenze der Anzeige, der RMS genau dieser Stellen gegen die Spanne der Dynamik, und ob eine Probe am digitalen Anschlag liegt. Übernehmen bleibt an. Die Studie nimmt Clips außerhalb von 3 bis 6 Sekunden nicht ins erste Training.

## Dateien

Aufnahme: 44100 Hz, mono, 24 Bit PCM. Das ist die gesperrte Rate des Vocoders, damit diese WAV später nicht noch einmal gewandelt werden muss. 48 kHz bleibt in der Studie erlaubt, diese App nimmt es nicht auf.

Beispiel: die Vorlage `songs/aufnahme/c3/leise/001_ich_liebe_dich.txt` wird für den Sänger `denis` zu `songs/aufnahme/denis/c3/leise/001_ich_liebe_dich.wav`.

Der Stand der Jobs liegt in `songs/aufnahme/<name>/record.sqlite`. Die Vorlage bleibt unverändert. `corpus_dir` im Training ist dieser Sängerordner, und `name` in `transcriptions.csv` ist der Pfad darin, zum Beispiel `c3/leise/001_ich_liebe_dich`.

Die App hat eine eigene Python-Umgebung. Die Trainings-venv auf Windows bleibt bei den DiffSinger-Paketen, darunter `numpy<2`.

## Start

```bash
uv sync --group record
uv run --group record python -m m2s record --root songs/aufnahme
```

Das Mikrofon muss für das Terminal oder die App freigegeben sein.

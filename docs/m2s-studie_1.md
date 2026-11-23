# Studie 1 — MIDI zu deutschem Gesang

Stand der Quellenprüfung: 23. November 2026.
Diese Datei ist das Protokoll der Machbarkeitsstudie. Die fünf Widersprüche zwischen Vorgabe und Quellen sind unten entschieden. Die Länge der Phonemliste und die Step-Zahl des Akustikmodells bleiben Messgrößen. Der Frame-Abstand ist entschieden.

## Gegenstand und späteres Ziel

Studie 1 prüft, ob aus trockenem deutschem Gesang ein DiffSinger-Modell entsteht, das in OpenUtau aus MIDI-Noten und deutschem Text hörbaren Gesang macht. Gemessen wird die Machbarkeit und die Klangqualität an festen deutschen Prüffällen.

Das spätere Produkt ist ein VST-Plugin mit Pianoroll. JUCE, C++ und der Editor beginnen erst, wenn Studie 1 die Go-Entscheidung unten erfüllt. Dieselbe Schnittstelle, die OpenUtau schon speist (Phonemfolge, Phonemdauern, Tonhöhe, Mel-Spektrogramm, Vocoder), ist die Schnittstelle, die der Pianoroll später bedienen muss. Studie 1 beweist diese Schnittstelle, sie baut sie nicht in C++ nach.

Die Gesangs-Regeln werden in Studie 1 in Python geprüft. Die C++-Portierung gehört zum VST, nicht zu dieser Studie.

## Zwei Schritte

Die vier Phasen unten sind der Arbeitsweg. Sie werden nicht als Annahmen abgearbeitet.

**Schritt 1 — Beleg.** Jede Festlegung entsteht als Datei mit Herkunft: Dump-Datum, Commit oder Release, gemessene Gerätezeile, oder eine Tabelle aus den eigenen Aufnahmen. Fehlt der Beleg, gilt die Festlegung nicht, und das Training startet nicht.

**Schritt 2 — Test- und Analysesystem.** Dieselben Prüffälle laufen nach jedem Training erneut. Ein Befund darf nur eine der drei Änderungen auslösen, die Phase 4 schon nennt: gezielte Nachaufnahme, Korrektur der eingefrorenen Phonemregeln mit neuem Alignment, oder weiteres Training desselben Modells. Das System schreibt die Änderung zurück in die Artefakte von Schritt 1.

## Quellen, die Schritt 1 wieder öffnet

Vor dem ersten Training werden Commit und Release gepinnt. Die Tabelle ist der Kenntnisstand vom 23. November 2026, keine ewige Konfiguration.

| Baustein | Belegte Quelle | Was die Quelle sagt |
| --- | --- | --- |
| Akustik- und Varianzmodell | [openvpi/DiffSinger](https://github.com/openvpi/DiffSinger), [BestPractices.md](https://github.com/openvpi/DiffSinger/blob/main/docs/BestPractices.md), [GettingStarted.md](https://github.com/openvpi/DiffSinger/blob/main/docs/GettingStarted.md) | Wörterbuch je Sprache als Textdatei `Silbe<Tab>Phonem Phonem …`. Globale reservierte Tags `SP` und `AP` (`SP` dort „space“, `AP` dort „aspiration“). Trainingslabel `transcriptions.csv` mit `name`, `ph_seq`, `ph_dur` (Sekunden) und WAV/FLAC. Export: `python scripts/export.py acoustic --exp …` und `python scripts/export.py variance --exp …`. |
| `hop_size` im Fork | [ConfigurationSchemas.md](https://github.com/openvpi/DiffSinger/blob/dur_diffusion/docs/ConfigurationSchemas.md) | `hop_size` ist die Schrittweite in Samples, Default 512, Sichtbarkeit acoustic und variance, als reserved geführt. |
| Vocoder | [openvpi/vocoders, Release 2024.02](https://github.com/openvpi/vocoders/releases/tag/nsf-hifigan-44.1k-hop512-128bin-2024.02) | NSF-HiFiGAN, 44100 Hz, 128 Mel-Bänder, Hop 512, Fenster 2048, Mel 40–16000 Hz. Tonumfang des Release bis C6 (1046,5 Hz). Lizenz laut Release-Text: CC BY-NC-SA 4.0. Update 2024-08-03: das neue ONNX erwartet log-E-Mels, das ältere log10. |
| Vocoder-Finetuning | [openvpi/SingingVocoders](https://github.com/openvpi/SingingVocoders), [configs/ft_hifigan.yaml](https://github.com/openvpi/SingingVocoders/blob/main/configs/ft_hifigan.yaml) | Finetuning über `ft_hifigan.yaml` und `finetune_ckpt_path`. Dieselbe Datei setzt `audio_sample_rate: 44100`, `audio_num_mel_bins: 128`, `hop_size: 512`, `fft_size: 2048`, `win_size: 2048`, `upsample_rates: [8, 8, 2, 2, 2]`. Die README sagt, beim Finetuning die übrigen Mel-Parameter nicht zu ändern. Produkt der `upsample_rates` ist 512. |
| Forced Alignment | [qiuqiao/SOFA](https://github.com/qiuqiao/SOFA) | Gesangs-Aligner. Ausgabeformat `textgrid` (Praat) und `transcriptions.csv`. Default-Wörterbuch `dictionary/opencpop-extension.txt`. Trainingslabel wie DiffSinger (`name`, `ph_seq`, `ph_dur`). Ein deutsches Gesangs-Checkpoint ist in dieser README nicht enthalten; vorhandene `.ckpt` liegen in den Discussions. `--save_confidence` schreibt `confidence.csv`. AP-Detektor ist ein eigener Schritt (`LoudnessSpectralcentroidAPDetector`). |
| Offline-Wörterbuch | [tatuylonen/wiktextract](https://github.com/tatuylonen/wiktextract/), [Kaikki, dewiktionary raw](https://kaikki.org/dewiktionary/rawdata.html), [Wikimedia-Dump dewiktionary](https://dumps.wikimedia.org/dewiktionary/) | Wiktextract liest einen `pages-articles`-Dump und schreibt JSONL. Aussprache steckt in `sounds[].ipa` (Schema der deutschen Ausgabe). Kaikki veröffentlicht bereits extrahiertes dewiktionary-JSONL. |
| Fallback-G2P | [lingjzhu/CharsiuG2P](https://github.com/lingjzhu/CharsiuG2P) | ByT5, mehrsprachig, Wort muss schon tokenisiert sein, jedes Wort braucht ein Sprachpräfix. Die Sprachkürzelliste steht im Repository, nicht in diesem Plan. |
| Hörtest-Umgebung | [DiffSingerGermanPhonemizer.cs](https://github.com/stakira/OpenUtau/blob/cc700f92/OpenUtau.Core/DiffSinger/Phonemizers/DiffSingerGermanPhonemizer.cs), [DiffSingerBasePhonemizer.cs](https://github.com/stakira/OpenUtau/blob/cc700f92/OpenUtau.Core/DiffSinger/DiffSingerBasePhonemizer.cs) | `GetDictionaryName()` gibt `dsdict-de.yaml` zurück. Fehlt die Datei, fällt der Loader auf `dsdict.yaml` zurück. Gesucht wird neben `dsconfig.yaml`: im Ordner `dsdur`, wenn dort eine `dsconfig.yaml` liegt, sonst im Sängerordner. Ein Wörterbucheintrag schlägt das eingebaute `GermanG2p`. Dessen Symbole (`aa`, `ax`, `er`, `ch`, `rr`, …) sind nicht das Trainingsset. |
| Glottisschlag | [Pompino-Marschall & Żygis, ZASPiL 52 (2010)](https://zaspil.leibniz-zas.de/article/download/380/381/746), dort Alber (2001); [Wilkins, Kap. 12](https://users.monash.edu.au/~ewilkins/textbook/CHAP12.PDF) | Standarddeutsch: `ʔ` am linken Rand einer vokalisch anlautenden betonten Silbe und am linken Rand eines vokalisch anlautenden Wortes, Präfixes oder Stamms. Das Lehrbuch transkribiert `erinnern` mit beiden Stellen. |
| R | [Duden, Die Aussprache von „r“](https://www.duden.de/sprachwissen/sprachratgeber/Die-Aussprache-von-%E2%80%9Er%E2%80%9C), [Ausspracheschlüssel, Universität Bremen](https://web.fb10.uni-bremen.de/hackmack/phonmorph/pdf/ausspracheschl%C3%BCssel_deutsch.pdf) | Konsonantische r-Varianten sind ein Phonem. Das Deutsche Aussprachewörterbuch schreibt den uvularen Reibelaut `ʁ`. Vokalisiertes `ɐ` ist nach Langvokal (außer der Sonderfall langes a) und in `-er` die Standardlautung. Duden führt `r` im Wörterverzeichnis als Deckzeichen, nicht als eigenes Gesangsphonem. |

## Aufgelöste Widersprüche

### 1. Frame-Abstand: 512, nicht 256

`ft_hifigan.yaml` des Finetuning-Checkpoints setzt `audio_sample_rate: 44100`, `hop_size: 512`, `win_size: 2048`, `fft_size: 2048`, `audio_num_mel_bins: 128`, `fmin: 40`, `fmax: 16000`. Die `upsample_rates` sind `[8, 8, 2, 2, 2]`, das Produkt ist 512. Die README von SingingVocoders sagt, beim Finetuning die übrigen Mel-Parameter nicht zu ändern. `hop_size: 256` und `win_size: 1024` lassen sich mit diesem Checkpoint nicht finetunen.

Studie 1 sperrt deshalb die Werte des Checkpoints. Die Frame-Dauer ist 512 / 44100 s = 11,6 ms. Der Wunsch nach etwa 5,8 ms bleibt eine Messfrage in Schritt 2 (Plosive `p`, `t`, `k` und Zischlaute `s`, `ʃ`, `ç`). Ein anderer Hop ist erst ein neuer Vocoder, dessen Upsampling zum neuen Hop passt, nicht eine geänderte Zahl in `ft_hifigan.yaml`.

`audio.lock.yaml` übernimmt zusätzlich die Mel-Basis des gepinnten ONNX. Der Release vom 3. August 2024 erwartet im neuen ONNX log-E, das ältere Paket log10. Training und Export nutzen das Paket, dessen Basis in der Lock-Datei steht.

### 2. Zwei Dateien, ein Inhalt; der OpenUtau-Name ist `dsdict-de.yaml`

Die Vorgabe und der deutsche Phonemizer nennen dieselbe Datei. `DiffSingerGermanPhonemizer` lädt `dsdict-de.yaml`. Das Training in DiffSinger liest daneben die Tab-Datei `Silbe<Tab>Phonem Phonem …` aus BestPractices. `dsconfig.yaml` ist die Export-Config, kein Wörterbuch. `dsdict.txt` ist der alte Paketname und wird von diesem Loader nicht gelesen.

Beide Wörterbücher enthalten dieselben Einträge aus der Wiktionary-Map nach den Regeln in Abschnitt 4. `dsdict-de.yaml` hat die von OpenUtau gelesene Form `symbols` (jeder Laut mit Typ) und `entries` (`grapheme`, `phonemes`). `SP` und `AP` trägt der Phonemizer selbst als Vokal ein; sie stehen trotzdem in `symbols`, damit die Datei allein lesbar bleibt. Ein `replacements`-Block mappt jedes Symbol von `GermanG2p` auf das eingefrorene IPA-Symbol, sonst erzeugt ein Wörterbuchfehltreffer `ax` oder `er` in einem Modell, das diese Zeichen nie gesehen hat. Die Paare werden aus dem Quelltext von `GermanG2p` abgeschrieben, sobald `phonemes.txt` existiert.

### 3. Glottisschlag: beide Stellen aus dem Beispiel

Die engere Formulierung „nur vor betonten Wortanfängen“ erzeugt `erinnern` nicht. Das Beispiel `ʔɛɐ̯ˈʔɪnɐn` hat ein `ʔ` am Wortanfang und ein zweites vor der betonten Silbe `ɪn`. Dieselbe Zweiteilung steht bei Alber (2001), zitiert in ZASPiL 52, und im Lehrbuchbeispiel `erinnern`.

Die Regel lautet:

- Beginnt das Wort mit einem Vokal, steht davor `ʔ`. Das gilt auch, wenn diese Silbe unbetont ist (`er-`).
- Beginnt eine betonte Silbe mit einem Vokal, steht vor diesem Vokal `ʔ`. Die Betonung ist das IPA-Zeichen `ˈ`.

Für `erinnern` liefert das beide Verschlüsse. Ein unbetonter vokalisch anlautender Wortinnenlaut ohne eigenen Stamm- oder Präfixrand bekommt kein zusätzliches `ʔ`. Akzeptanz ist die Phonemfolge `ʔ ɛ ɐ ˈʔ ɪ n ɐ n`. `ɐ̯` ist derselbe Laut `ɐ` mit Unsilblichkeitszeichen, kein zweites Phonem.

### 4. Silbenanlautendes R wird `ʁ`, Silbenende bleibt `ɐ`

Zielsymbol im Anlaut ist `ʁ`. `ʀ` und, falls der Dump das Deckzeichen `r` enthält, auch `r` werden im Silbenanlaut zu `ʁ`. Das ist die Schreibweise des Deutschen Aussprachewörterbuchs für den konsonantischen R-Laut und die Vereinheitlichung, die die Vorgabe zwischen `ʁ` und `ʀ` verlangt.

Am Silbenende bleibt vokalisiertes `ɐ`. Das ist die Standardlautung nach Langvokal und in `-er` (Duden-Sprachratgeber; Testvektor `wir` → `viːɐ`). Ein konsonantisches R an dieser Stelle wird dafür zu `ɐ`. `̯` erzeugt kein eigenes Phonem.

### 5. Schwa: `ə` im Wörterbuch, Öffnung ab dem Median der gesungenen `-e`

Eine Hertz-Grenze steht in keiner der gelesenen Quellen, und die Tonhöhe ist beim Wörterbuchbau nicht bekannt. Das Offline-Wörterbuch speichert deshalb `ə`.

Die Öffnung läuft erst, wenn die MIDI-Note der Silbe bekannt ist. Die Grenze ist der Median der MIDI-Noten aller Trainingsnoten, deren Text auf `-e` endet und deren Phonem `ə` ist. Kleinere oder gleiche Note: `ə`. Größere Note: der offenere Vokal.

`ə` ist ungerundet. Der ungerundete offenere Vokal aus der Vorgabe ist `ɛ`. `œ` ist der gerundete Partner und wird nur verwendet, wenn die Lexikon-IPA dieser Silbe schon gerundet ist (`ø`, `œ`). Für die Endung `-e` ist das Ziel über dem Median `ɛ`. Der Median wird nach dem Alignment in die Regeldatei geschrieben. Bis dahin ist die Methode fest und die Zahl offen, weil sie aus den Aufnahmen gezählt wird.

## Schritt 1 — Belegbare Durchführung

Reihenfolge ist bindend. Audio wird erst aufgenommen, wenn das Phonem-Set als Datei existiert. Training startet erst, wenn die Audio-Parameter von Vocoder und Akustikmodell dieselbe gepinnte Config sind.

### 1. Phonem-Set aus dem Lexikon, nicht aus einer Soll-Länge

Vorgabe: etwa 45–50 deutsche Gesangsphoneme, Beispiele `a:`, `a`, `e:`, `ɛ`, `ə`, `p`, `t`, `k`, `ʃ`, `ç`, `x`, `ʔ`, dazu `SP` und `AP`.

Beleg:

- Dump oder Kaikki-JSONL mit Datum laden. Pro Zeile `word` und `sounds[].ipa` nur für deutsche Einträge übernehmen. Mehrfachaussprachen bleiben mehrere Einträge. Leere, abgebrochene und nicht-IPA-Werte entfallen nach der Regel, die das Extrakt-Skript selbst ausgibt; die Regel steht im Skriptkopf mit Verweis auf die verworfenen Muster aus dem Dump.
- IPA in Symbole zerlegen. Häufigkeitstabelle schreiben: Symbol, Anzahl Wörter, drei Beispielwörter.
- Die feste Liste ist die Menge der Symbole, die nach den Regeln in Abschnitt 4 in den Aufnahmen vorkommen können, vereinigt mit `SP` und `AP`. Die Beispiele der Vorgabe müssen in dieser Liste liegen, sobald sie im Lexikon vorkommen. Die Länge 45–50 ist die Erwartung der Vorgabe; die gezählte Länge ist der Beleg. Weicht sie ab, bleibt die gezählte Liste, und die Abweichung geht ins Protokoll.
- `SP` und `AP` bekommen die reservierten Namen aus BestPractices, damit das Training sie als globale Tags erkennt. Im Glossar dieser Studie heißt `SP` kurze Pause und `AP` Atemgeräusch, weil die Aufnahmen Atem an den Clip-Rändern behalten und SOFA diese Stellen als AP kennzeichnet. Die Gleichsetzung mit den englischen Beschreibungen „space“ und „aspiration“ steht in derselben Glossarzeile, damit später niemand ein zweites Symbol einführt.
- Datei: `phonemes.txt`, eine Zeile pro Symbol, plus `phonemes.counts.tsv` mit der Häufigkeit.

### 2. Offline-Wörterbuch

Vorgabe: deutsches Wiktionary, IPA über wiktextract, Ablage als JSON oder binäre Hash-Map Wort → IPA.

Beleg:

- Entweder den Dump selbst mit wiktextract nach JSONL ziehen oder das datierte Kaikki-JSONL verwenden. Im Provenienzblock stehen URL, Dump-Datum und der Lizenztext, den die Dump-Seite angibt.
- Daraus eine Map nur mit `word` → Liste von IPA-Strings. Dialekt-Tags aus `sounds[].tags` bleiben am Eintrag, sie werden nicht still verworfen. Welche Variante die Aufnahmen treffen, entscheidet der Hörvergleich in Schritt 2 an den Wörtern, die mehr als eine IPA haben.
- Die Map wird gegen die DiffSinger-Wörterbuchform geschnitten: Silbe, Tab, Phoneme aus der eingefrorenen Liste, getrennt durch Leerzeichen. Silben, deren Symbole nicht in `phonemes.txt` stehen, landen in `dictionary.rejected.tsv` und blockieren das Training nicht, sie dürfen aber nicht lautlos auf ein Nachbarphonem fallen.

### 3. Fallback für unbekannte Wörter

Vorgabe: CharsiuG2P oder ByT5-G2P für unbekannte Wörter, Eigennamen und Neologismen.

Beleg:

- CharsiuG2P ist das ByT5-Modell aus dem genannten Repository. Das Sprachpräfix für Deutsch wird aus der Sprachliste dieses Repositorys abgeschrieben, nicht geraten.
- Reihenfolge: Map-Treffer zuerst, Charsiu nur bei Fehltreffer. Ausgabe von Charsiu durchläuft dieselbe Symbolprüfung. Symbole außerhalb von `phonemes.txt` kommen in `g2p.rejected.tsv`.
- Ein fester Satz von Wörtern, die absichtlich nicht in der Map liegen (ein Eigenname, ein erfundenes Kompositum, ein Wort mit `ch`), wird mit Eingabe, Roh-IPA und angenommener oder verworfener Phonemfolge archiviert. Ohne diese drei Zeilen gilt der Fallback als nicht angeschlossen.

### 4. Gesangs-Post-Processing

Das Python-Skript setzt die drei Entscheidungen aus „Aufgelöste Widersprüche“. Die C++-Portierung bleibt beim VST.

- Glottisschlag nach der zweiteiligen Regel. Akzeptanz: `erinnern` → `ʔ ɛ ɐ ˈʔ ɪ n ɐ n`.
- Silbenanlaut `ʁ` / `ʀ` / `r` → `ʁ`. Silbenende → `ɐ`. Akzeptanz: `wir` → `viːɐ`.
- `-e` bleibt im Wörterbuch `ə`. Liegt die MIDI-Note über dem Median der gesungenen `-e`, wird daraus `ɛ`, außer die Lexikon-IPA dieser Silbe ist gerundet, dann `œ`.

Beleg:

- `rules/vectors.tsv` enthält Orthographie, IPA aus der Map, Phonemfolge der Regel und `status`. `erinnern` und `wir` starten als `belegt` gegen die Akzeptanzfolgen. Eine Zeile auf `-e` ohne Note bleibt `ə`. Zwei Zeilen mit Note, eine unter und eine über dem später eingetragenen Median, prüfen `ə` gegen `ɛ`.
- Der Median steht erst nach dem Alignment in `rules/schwa-median.txt` (Note, Anzahl der verwendeten `-e`-Noten, Hash der `transcriptions.csv`). Ein Render vor dieser Datei lässt jedes `-e` bei `ə`.

### 5. Aufnahme

Vorgabe: 1,5 bis 3 Stunden trockener Gesang, mehrere Tonlagen, verschiedene Dynamiken. Reaper oder Audacity. Kein Hall, kein Delay, Popfilter. 44,1 kHz oder 48 kHz, 24-Bit WAV. Schnitte an Atempausen, Clips 3 bis 6 Sekunden. Atemgeräusche am Anfang und Ende behalten, später `AP`.

Beleg, keine dieser Zahlen ist eine nachgewiesene Untergrenze:

- Pro Session eine Zeile: Datum, Raum, Mikrofon, Abstand, Popfilter ja/nein, Sample-Rate, Bit-Tiefe, Pegel, ob Hall oder Delay in der Kette war. Ein Clip mit Raumhall oder ohne Popfilter-Vermerk kommt nicht in die Trainingsmenge.
- Dauer der behaltenen Clips in Stunden, gezählt aus den WAV-Längen, nicht geschätzt. Unter 1,5 Stunden startet nur der 15-Minuten-Pilot aus Abschnitt 6, nicht das volle Akustiktraining. Über 3 Stunden ist erlaubt; die Vorgabe nennt die Spanne für ein erstes Modell.
- Liegt die Aufnahme bei 48 kHz, wird auf die in Abschnitt 7 gepinnte Rate resampled. Original und Resample bleiben beide erhalten. Die Resample-Rate ist die des Vocoder-Checkpoints, nicht eine dritte Rate.
- Clip-Länge 3–6 Sekunden und der Schnitt an Atempausen sind das Schnittprotokoll. Clips außerhalb der Spanne werden gezählt und vom ersten Training ausgeschlossen, nicht nachträglich gedehnt.

### 6. Text, G2P, SOFA

Vorgabe: zu jeder WAV eine TXT mit dem gesungenen Text. G2P aus Abschnitt 1–4 erzeugt die Phonemfolge. SOFA legt die Phoneme auf die Aufnahme (TextGrid). Zuerst etwa 15 Minuten, Prüfung in Praat, grobe Fehler von Hand, SOFA auf die eigene Stimme nachtrainieren, danach der Rest.

Beleg:

- Paare `name.wav` / `name.txt`. Das G2P-Skript schreibt `name.lab` und die Zeile in `transcriptions.csv` (`name`, `ph_seq`, nach dem Alignment auch `ph_dur` in Sekunden), passend zu DiffSinger und zum SOFA-Trainingsformat.
- Vor dem ersten SOFA-Lauf: in den SOFA-Discussions und Releases nach einem Checkpoint suchen, dessen Wörterbuch die eingefrorenen deutschen Symbole enthält. Liegt keiner, ist das der Beleg, dass das Default-`opencpop`-Wörterbuch nicht verwendet wird. Der 15-Minuten-Pilot wird dann mit dem eigenen Wörterbuch aligniert, in Praat korrigiert und ist die Trainingsmenge für das eigene SOFA-Checkpoint. Schwache Labels ohne `ph_dur` sind laut SOFA-Diskussion zulässig; das erste eigene Checkpoint entsteht aus den manuell korrigierten vollen Labels.
- Praat-Korrektur wird gezählt: geänderte Grenzen geteilt durch alle Grenzen des 15-Minuten-Subsets, plus die Liste der Phoneme, die betroffen waren. Diese Quote ist die Messgröße. Ein Schwellenwert, ab dem der Rest „nahezu fehlerfrei“ gilt, wird erst nach diesem Subset aus den gesehenen Fehlerarten notiert. Bis dahin ist „nahezu fehlerfrei“ eine Hoffnung der Vorgabe, kein Abnahmekriterium.
- `confidence.csv` (`--save_confidence`) wird aufgehoben. Atem an den Clip-Rändern muss als `AP` im TextGrid stehen. Fehlt `AP` an hörbarem Atem, ist der AP-Detektor oder das Label falsch, und der Clip geht nicht ins Training.
- Erst das nachtrainierte Checkpoint aligniert die übrigen Stunden. Stichproben daraus gehen erneut durch Praat; die zweite Korrekturquote landet in derselben Tabelle.

### 7. Parameter sperren, dann trainieren

Vorgabe: NVIDIA-GPU, ideal 12–16 GB, alternativ Cloud (RunPod oder Vast.ai). Python, PyTorch mit CUDA. OpenVPI-DiffSinger und Community-NSF-HiFiGAN. Vocoder-Finetuning des OpenVPI-Checkpoints. Varianzmodell für Tonhöhe, Dauer und Energie. Akustikmodell aus MIDI-Noten, Phonemen und Tonhöhe zum Mel. Planwert 100.000–200.000 Steps je nach Datenmenge. Die Audio-Parameter sind die des Checkpoints, nicht 256 / 1024.

Beleg, in dieser Reihenfolge:

1. `torch.cuda` Gerätezeile und VRAM in `env.txt`. 12–16 GB sind die Vorgabe, nicht der Nachweis, dass diese Menge reicht. Reicht der Speicher für die Batch-Größe der gepinnten Config nicht, wird die Batch-Größe der Config gesenkt und die Zeile ergänzt. Eine andere Architektur wird nicht eingeführt.
2. Commit von DiffSinger und SingingVocoders sowie der genaue Release-Dateiname des Vocoder-Checkpoints werden gepinnt.
3. `audio.lock.yaml` enthält die gesperrten Werte: `sample_rate: 44100`, `hop_size: 512`, `win_size: 2048`, `fft_size: 2048`, `num_mel_bins: 128`, `fmin: 40`, `fmax: 16000`, plus die Mel-Basis des gepinnten ONNX. Dieselben Zahlen stehen in der DiffSinger-`config.yaml`. Ein Unterschied bricht den Lauf ab. `hop_size: 256` und `win_size: 1024` werden nicht geschrieben.
4. Vocoder zuerst finetunen, dann Varianz (Dauer, Pitch, Energie), dann das akustische Diffusionsmodell. Die Step-Zahl 100.000–200.000 ist der Planwert der Vorgabe für das Akustikmodell. Beendet wird nach der Kurve im Trainer-Log und nach dem Hörtest in Schritt 2, nicht weil ein Zähler diese Spanne erreicht hat. Die SingingVocoders-README nennt für ein Vocoder-Finetuning eine deutlich kürzere Größenordnung; die dort gelesene Zahl wird beim Pinnen aus der README des gepinnten Commits abgeschrieben und gilt nur für den Vocoder.
5. Das DiffSinger-Wörterbuch in der `config.yaml` zeigt auf die Tab-Datei aus Abschnitt 2. `extra_phonemes` enthält nur Symbole, die in `phonemes.txt` stehen und nicht schon im Wörterbuch liegen, darunter `SP` und `AP`, falls der Fork sie nicht schon reserviert hat. Der gepinnte Code entscheidet das, ein zweites Blicklesen von BestPractices am selben Commit.

### 8. Export zur Hörprüfung

Vorgabe: ONNX von Akustikmodell und NSF-HiFiGAN, deutsches Mapping, deutsche MIDI-Melodie und Lyrics in OpenUtau. Prüffälle: `ç` gegen `x`, Glottisschlag an Vokalanfängen, lange Vokale auf hohen Tönen. Unsaubere Laute: 10–15 kurze Sätze mit genau diesen Kombinationen nachnehmen, durch SOFA, Training fortsetzen.

Beleg:

- Export nur über die Skripte des gepinnten DiffSinger- und SingingVocoders-Stands. `vocoder.yaml` muss dieselben Zahlen tragen wie `audio.lock.yaml`, einschließlich der Mel-Basis.
- OpenUtau bekommt `dsdict-de.yaml` neben der `dsconfig.yaml` und den Phonemizer `DIFFS DE`. Inhalt und `replacements` wie in der Entscheidung zum Dateinamen. Die Tab-Datei bleibt die Trainingsquelle.
- Eine feste MIDI-Datei und eine feste Lyric-Datei werden vor dem ersten Hörtest eingefroren und danach nicht mehr umgeschrieben, damit Durchgänge vergleichbar sind. Sie enthalten mindestens die drei Prüffälle der Vorgabe und die Testvektoren `erinnern`, `wir` und ein Wort auf `-e` auf einer tiefen und einer hohen Note. Die hohe Note liegt nicht über dem Tonumfang, den der gepinnte Vocoder-Release angibt (im 2024.02-Release: C6).
- Lizenzzeile des Vocoder-Release in `env.txt`. CC BY-NC-SA, wie im Release 2024.02 ausgeschrieben, erlaubt das Hören in dieser Studie. Dieselbe Zeile ist der Beleg, dass ein späteres VST diese Gewichte nicht mit ausliefert, solange der Release-Text so lautet. Ein selbst trainierter Vocoder ohne diese Gewichte ist eine eigene Entscheidung nach der Go-Zeile, nicht Teil des ersten Finetunings.

## Schritt 2 — Test- und Analysesystem

Das System ist eine Tabelle `runs.tsv`, eine Zeile pro Hördurchgang. Es ersetzt keine Phase. Es ist die einzige Stelle, an der ein Ergebnis eine Änderung an den Dateien aus Schritt 1 auslösen darf.

Spalten, alle aus Artefakten, keine geschätzten Noten:

| Spalte | Herkunft |
| --- | --- |
| `run_id`, Git-Commit der Regeln, Hash von `phonemes.txt` und `audio.lock.yaml` | Dateien von Schritt 1 |
| Stunden Audio, Clip-Anzahl, Sample-Rate vor und nach Resample | WAV-Längen und Session-Log |
| SOFA-Checkpoint, Korrekturquote 15-Minuten-Subset, Korrekturquote der Stichprobe aus dem Rest, Anteil Clips mit `AP` an hörbarem Atem | Praat-Zählung, `confidence.csv` |
| Vocoder- und Akustik-Checkpoint, Step aus dem Trainer-Log | Experimentordner |
| Dieselbe eingefrorene MIDI, gerendert in der gepinnten OpenUtau-Version | WAV des Renderns, abgelegt unter `runs/<run_id>/` |
| `ç`/`x`, Glottisschlag, langer Vokal auf hoher Note, `wir`, `-e` tief, `-e` hoch | je `hörbar` / `nicht hörbar` / `nicht im Take`, plus die TextGrid-Stelle |
| Ausgelöste Änderung | genau eine: Nachaufnahme, Regeländerung, weiteres Training, oder keine |

Regeln des Systems:

- Ein `nicht hörbar` an `ç`/`x`, am Glottisschlag oder an langen hohen Vokalen erzeugt einen Nachaufnahme-Auftrag von 10–15 kurzen Sätzen, die nur diese Kombination enthalten, wie in der Vorgabe. Die Sätze werden als TXT geschrieben, aufgenommen, durch dasselbe G2P und das nachtrainierte SOFA geschickt und an den nächsten Trainingslauf angehängt. Sie ersetzen die alte Menge nicht.
- Die Regeln für Glottis, R und Schwa gelten. Ein Hörurteil ändert sie nur zusammen mit einer TextGrid-Stelle und einer neuen `run_id`: fehlender zweiter Knacklaut in der Aufnahme, durchgängig gesungenes `ʀ` statt `ʁ`, oder ein hohes `-e`, das gerundet als `œ` besser sitzt als `ɛ`. Liegt zwischen `-e` unter und über dem Median kein hörbarer Unterschied, bleiben alle `-e` bei `ə`, und der Median wird nicht angewendet.
- Plosive `p`, `t`, `k` und Zischlaute `s`, `ʃ`, `ç` werden auf derselben MIDI mitgehört. Klingeln sie bei 11,6 ms verwaschen, lautet der Befund „Hop 512 reicht für diese Stimme nicht“. Studie 1 trainiert dafür keinen zweiten Vocoder. Der Befund ist eine Zeile in `runs.tsv` und sperrt den Hop nicht um.
- Weiteres Training ohne neue Daten ist erlaubt, solange das Trainer-Log noch fällt und der vorherige `run_id` an derselben MIDI schlechter war. Die Spanne 100.000–200.000 wird dabei als Beobachtungsfenster mitgeschrieben, nicht als Stopp.

Jedes `runs.tsv`-Urteil, das eine Datei von Schritt 1 ändert, macht den nächsten Durchgang zu einem neuen `run_id`. Alte WAVs bleiben liegen.

## Go / No-Go für das VST

Go nur, wenn alle Punkte als Dateien existieren:

- `phonemes.txt` ist die gezählte Liste, die Prüflaute `ç`, `x`, `ʔ`, `ɐ`, `ə` enthält, und `SP`/`AP` sind die reservierten Tags.
- `audio.lock.yaml` ist identisch in Vocoder-Config, DiffSinger-Config und exportiertem `vocoder.yaml`.
- Ein `run_id` hat auf der eingefrorenen MIDI die drei Vorgabe-Prüffälle auf `hörbar`, und `wir` behält `ɐ`.
- Die Korrekturquote der Stichprobe nach dem SOFA-Nachtraining steht in `runs.tsv`. Der Schwellenwert ist der, den Abschnitt 6 nach dem Piloten notiert hat, und die Stichprobe liegt darunter.
- `env.txt` enthält die Vocoder-Lizenz. Go für ein VST, das diese Gewichte mitliefert, gibt es unter dem gelesenen CC-BY-NC-SA-Text nicht. Go für den Bau des Editors und für ein Modell, dessen Vocoder unter einer dafür geeigneten Lizenz neu trainiert wurde, ist davon getrennt und hier noch nicht entschieden.

No-Go, solange einer der Punkte fehlt. Ein No-Go nennt die `run_id` und die offene Spalte. Es startet keinen Plugin-Code.

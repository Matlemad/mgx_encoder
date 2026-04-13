# MGX Encoder

Local structural music genome extractor. Analyzes a final stereo mix (or YouTube audio) and produces an **MGX-v1** JSON fingerprint.

---

## Quick Start (run-through completo)

### 1. Prerequisiti

- **Python 3.11+**
- **ffmpeg** (necessario per yt-dlp e la conversione audio)
- **git** (per clonare la repo)

Installa ffmpeg se non lo hai:

```bash
# macOS
brew install ffmpeg

# Ubuntu / Debian
sudo apt install ffmpeg

# Windows (via chocolatey)
choco install ffmpeg
```

### 2. Clona la repo

```bash
git clone https://github.com/TUO-USER/mgx.git
cd mgx/mgx_encoder
```

### 3. Crea il virtual environment e installa le dipendenze

```bash
python3 -m venv .venv
source .venv/bin/activate      # macOS / Linux
# .venv\Scripts\activate       # Windows

pip install -r requirements.txt
```

### 4. Avvia l'app

```bash
streamlit run app.py
```

Si apre automaticamente il browser su `http://localhost:8501`.

### 5. Analizza un brano

1. **Carica un file** (WAV, MP3 o FLAC) oppure **incolla un URL YouTube**
2. Clicca **Run MGX Encoding**
3. Attendi il completamento della progress bar
4. Esplora i risultati nelle tab (R, M, H, X, F, C)
5. Scarica il **JSON** e/o il **Report Markdown** con i bottoni in fondo

### 6. Dove trovo i file di output?

```
mgx_encoder/
  outputs/
    mgx_output.json     ← genoma MGX-v1 completo
    mgx_report.md       ← report leggibile
    plots/              ← grafici debug (se abilitati)
```

### 7. Sessioni successive

Ogni volta che vuoi riusare l'app:

```bash
cd mgx/mgx_encoder
source .venv/bin/activate
streamlit run app.py
```

---

## Struttura del progetto

```
mgx_encoder/
  app.py                  ← UI Streamlit
  requirements.txt        ← dipendenze Python
  README.md               ← questo file
  .venv/                  ← virtual environment (generato da te)
  src/
    __init__.py
    audio_loader.py       ← caricamento file audio
    youtube_loader.py     ← download YouTube via yt-dlp + cookie
    preprocessing.py      ← HPSS, band splits, tuning, multi-chroma
    multipass.py          ← 6 pass di analisi del segnale
    rhythm.py             ← R: tempo, groove, swing
    melody.py             ← M: pitch, intervalli, contorno, feature invarianti
    harmony.py            ← H: key, modo, accordi, feature invarianti
    motif.py              ← X: ripetizioni, auto-similarita
    form.py               ← F: segmentazione in sezioni
    confidence.py         ← C: confidenze, coerenza, warning
    report.py             ← generazione report Markdown
    utils.py              ← helper (JSON encoder, I/O)
  outputs/                ← file di output generati
  temp/                   ← file temporanei (download YouTube)
  examples/               ← (vuota, per file di esempio)
```

---

## YouTube Authentication

YouTube spesso blocca i download senza autenticazione. L'app supporta tre metodi:

1. **Auto-detect** (default) — prova a leggere i cookie dai browser installati
2. **Selezione browser** — scegli Chrome, Firefox, Safari, Edge o Brave dal dropdown
3. **File cookies.txt** — fornisci il path a un file in formato Netscape

Per esportare i cookie manualmente: [guida yt-dlp](https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp).

---

## Opzioni nell'interfaccia

| Opzione | Cosa fa |
|---------|---------|
| **Save debug plots** | Genera waveform, mel spectrogram e chroma in `outputs/plots/` |
| **Show intermediate passes** | Mostra i dati grezzi per ogni pass di analisi nelle tab |

---

## MGX-v1 — Formato JSON di output

Il JSON ha 7 sezioni top-level:

```json
{ "meta": {}, "R": {}, "M": {}, "H": {}, "X": {}, "F": {}, "C": {} }
```

---

### meta — Metadata

Informazioni sulla sorgente audio e la sessione di analisi.

| Campo | Tipo | Descrizione |
|-------|------|-------------|
| `source` | string | `"file"` o `"youtube"` |
| `filename` | string | Nome del file analizzato |
| `youtube_url` | string / null | URL YouTube se usato |
| `title` | string / null | Titolo del video YouTube |
| `duration_sec` | float | Durata in secondi |
| `sample_rate` | int | Sample rate originale (es. 44100) |
| `analysis_sample_rate` | int | SR di analisi (sempre 22050) |
| `notes` | list | Errori o avvisi durante il processing |

---

### R — Rhythm

Analisi ritmica: tempo, regolarita, groove.

| Campo | Tipo | Range | Descrizione |
|-------|------|-------|-------------|
| `bpm` | float | 30–300 | Tempo stimato in battiti/minuto |
| `bpm_confidence` | float | 0–1 | Concordanza BPM tra i pass. Alto = stabile |
| `time_signature` | string | 4/4, 3/4, 6/8 | Metrica stimata |
| `beat_regularity` | float | 0–1 | Equidistanza dei beat. 1.0 = metronomo |
| `groove_complexity` | float | 0–1 | Complessita ritmica. 0 = semplice, 1 = poliritmico |
| `swing_ratio` | float | 0.3–0.7 | 0.5 = dritto; >0.5 = swing/shuffle |
| `onset_density` | float | 0+ | Densita media degli attacchi |
| `polyrhythm_flag` | bool | — | `true` se groove_complexity > 0.7 |

---

### M — Melody

Analisi melodica: contorno, intervalli, stabilita.

#### Feature dipendenti dall'arrangiamento

| Campo | Tipo | Range | Descrizione |
|-------|------|-------|-------------|
| `pitch_range_hz` | float | 0+ | Escursione melodica in Hz |
| `pitch_mean_hz` | float | 0+ | Frequenza media del pitch predominante |
| `pitch_std_hz` | float | 0+ | Deviazione standard del pitch |
| `mean_interval_semitones` | float | 0+ | Intervallo medio tra note (semitoni, valore assoluto) |
| `contour_direction` | float | -1 / +1 | +1 = ascendente, -1 = discendente, 0 = bilanciato |
| `stepwise_ratio` | float | 0–1 | Proporzione di intervalli <= 2 semitoni |
| `voiced_ratio` | float | 0–1 | % frame con pitch valido. Basso = molto percussivo |
| `vocal_likelihood` | float | 0–1 | Probabilita euristica di presenza vocale |
| `pitch_confidence` | float | 0–1 | Confidenza melodia (concordanza pass + voiced ratio) |
| `pitch_class_histogram` | 12 float | 0–1 | Distribuzione note melodiche su C, C#, D, ... B |
| `contour_symbols` | list | — | Contorno: "U" = sale, "D" = scende, "R" = ripete (max 200) |

#### Feature invarianti (per confronto cross-arrangement)

Queste feature rimangono stabili anche se il brano viene riarrangiato con tempo, timbro o tonalita diversi.

| Campo | Tipo | Invariante a | Descrizione |
|-------|------|-------------|-------------|
| `interval_histogram` | 25 float | Trasposizione, tempo, timbro | Distribuzione degli intervalli da -12 a +12 semitoni. Due versioni della stessa melodia (anche in key diverse) producono lo stesso istogramma |
| `contour_bigrams` | dict (9 coppie) | Trasposizione, tempo, timbro | Frequenza delle coppie di movimenti melodici: UU, UD, UR, DU, DD, DR, RU, RD, RR. Cattura la "forma" della melodia |
| `pitch_class_profile_relative` | 12 float | Trasposizione | Come `pitch_class_histogram` ma ruotato cosi che la key center = indice 0. Stessa melodia in C e in E producono lo stesso profilo |
| `pc_transition_matrix` | 12x12 float | Tempo, timbro | Matrice di transizione: quale pitch class segue quale (normalizzata per riga). Cattura le progressioni melodiche tipiche |

---

### H — Harmony

Analisi armonica: tonalita, modo, accordi, ambiguita.

#### Tonalita

| Campo | Tipo | Range | Descrizione |
|-------|------|-------|-------------|
| `key` / `key_center` | string | C...B | Centro tonale stimato |
| `mode` / `key_mode` | string | major/minor | Modo stimato |
| `key_confidence` | float | 0–1 | Confidenza sulla key (gap candidati + concordanza chroma + sezioni) |
| `key_candidates` | list | — | Top 3 tonalita con `key`, `mode`, `score`. Se le prime due sono vicine = key ambigua |
| `mode_ambiguity` | string | low/moderate/high | Ambiguita major/minor. `high` = tipico di power chord senza terza |
| `tuning_offset_cents` | float | ~-50/+50 | Detuning rispetto a La=440Hz. Compensato internamente |

#### Accordi

| Campo | Tipo | Descrizione |
|-------|------|-------------|
| `chord_tier` | int 1/2/3 | Livello di dettaglio: **1** = accordi pieni (Em7), **2** = solo root (E), **3** = solo emphasis |
| `chord_sequence` | list | Sequenza accordi deduplicata (tier 1, max 64) |
| `root_sequence` | list | Sequenza root armonici (tier <=2, max 64) |
| `harmonic_emphasis` | 12 float | Profilo energetico per pitch class |
| `chord_confidence` | float 0–1 | Confidenza riconoscimento accordi |

#### Profilo armonico

| Campo | Tipo | Descrizione |
|-------|------|-------------|
| `chroma_profile` | 12 float | Distribuzione energetica C...B (chroma CQT armonica, tuning-corrected) |
| `harmonic_change_rate` | float | Velocita media cambio armonico. Alto = armonia dinamica |
| `chroma_entropy` | float 0–3.58 | Entropia chroma. 0 = una nota sola; ~3.5 = distribuzione uniforme |
| `tonnetz_centroid` | 6 float | Posizione media nello spazio Tonnetz (relazioni di quinta e terza) |
| `section_weighted_key` | dict/null | Key stimata pesando sezioni per energia e inversamente per percussivita |
| `notes` | list | Ambiguita, disaccordi tra metodi |

#### Feature invarianti (per confronto cross-arrangement)

| Campo | Tipo | Invariante a | Descrizione |
|-------|------|-------------|-------------|
| `chroma_profile_relative` | 12 float | Trasposizione | Profilo chroma ruotato con key center = indice 0. Stessa progressione armonica in key diverse produce lo stesso profilo |
| `harmonic_emphasis_relative` | 12 float | Trasposizione | Come harmonic_emphasis ma relativo alla key |
| `relative_root_functions` | list | Trasposizione | Sequenza di gradi: I, IV, V, bVII... invece di nomi assoluti. La stessa progressione in C (C-F-G) e in E (E-A-B) produce la stessa sequenza (I-IV-V) |
| `relative_chord_functions` | list | Trasposizione | Come sopra ma con qualita accordo (Imin7, IV, V7...) |
| `harmonic_rhythm_per_beat` | float | Tempo | Cambi armonici per beat. Normalizzato per BPM, quindi invariante al tempo |

**Come funziona il key detection**: 5 rappresentazioni chroma (CQT, STFT, CENS su mix e armonico) con pesi diversi, correlate con template Krumhansl-Kessler + Temperley per 24 tonalita. Voto pesato + stima per sezioni che riduce il peso di intro, fill e passaggi percussivi.

---

### X — Motif

Pattern ripetitivi e auto-similarita.

| Campo | Tipo | Range | Descrizione |
|-------|------|-------|-------------|
| `repetition_density` | float | 0–1 | Densita coppie simili / totale possibile. 1.0 = tutto uguale |
| `mean_self_similarity` | float | 0–1 | Similarita media tra segmenti ripetuti |
| `n_motif_pairs` | int | 0+ | Coppie con similarita >= 0.85 (cosine su MFCC) |
| `estimated_unique_motifs` | int | 0+ | Motivi distinti (cluster union-find). Pop tipico: 1–5 |
| `motif_confidence` | float | 0–1 | Proporzionale al numero di coppie trovate |
| `notes` | list | — | Avvisi |

---

### F — Form

Struttura formale: segmentazione in sezioni.

| Campo | Tipo | Descrizione |
|-------|------|-------------|
| `sections` | list | Sezioni con `label` (S0, S1...), `start_sec`, `end_sec` |
| `section_sequence` | list | Sequenza etichette (es. S0, S1, S0, S2, S0) |
| `n_sections` | int | Sezioni totali |
| `n_unique_sections` | int | Tipi di sezione distinti |
| `structural_repetition` | float 0–1 | 1 - (uniche/totali). Pop tipico: ~0.4–0.6 |
| `form_confidence` | float 0–1 | Cresce col numero di sezioni |
| `notes` | list | Avvisi |

Le etichette sono strutturali (S0, S1...), **non semantiche** — il sistema non distingue "strofa" da "ritornello".

---

### C — Confidence

Confidenze aggregate, coerenza interna, avvisi.

| Campo | Tipo | Range | Descrizione |
|-------|------|-------|-------------|
| `field_confidence` | dict | — | Confidenza per: rhythm, melody, harmony, motif, form (0–1 ciascuno) |
| `overall_confidence` | float | 0–1 | Media delle confidenze |
| `melody_harmony_agreement` | float | 0–1 | Quanta energia melodica cade nella scala stimata. <0.5 = forte disaccordo |
| `warnings` | list | — | Avvisi automatici (bassa confidenza, detuning, ambiguita...) |
| `notes` | list | — | Note da tutti i moduli |
| `disclaimer` | string | — | Disclaimer legale |

#### Come leggere le confidenze

| Valore | Significato |
|--------|-------------|
| **0.8–1.0** | Alta — risultato affidabile |
| **0.5–0.8** | Media — plausibile, interpretare con cautela |
| **0.3–0.5** | Bassa — incerto, alternative valide |
| **0.0–0.3** | Molto bassa — inaffidabile, segnalato con warning |

---

## Multi-Pass Analysis

Il segnale viene analizzato da 6 viste diverse:

| Pass | Segnale | Usato per | Descrizione |
|------|---------|-----------|-------------|
| A | Mono mix | Rhythm, baseline | Segnale originale in mono |
| B | Armonico (HPSS) | Melody, Harmony | Componente tonale |
| C | Percussivo (HPSS) | Rhythm | Componente percussiva |
| D | Low band (<250 Hz) | Bass | Frequenze basse |
| E | Mid+High (>250 Hz) | Melody | Voce e strumenti melodici |
| F | Onset-enhanced | Rhythm | Mono * envelope onset |

Ogni modulo usa i pass piu rilevanti con pesi diversi — non e una media cieca.

---

## Feature invarianti — guida per il confronto

Se il tuo obiettivo e confrontare due JSON per trovare somiglianze tra arrangiamenti diversi dello stesso brano, usa queste feature:

| Feature | Dove | Cosa cattura | Resistente a |
|---------|------|-------------|-------------|
| `interval_histogram` | M | Distribuzione dei salti melodici | Trasposizione, tempo, timbro |
| `contour_bigrams` | M | Forma del contorno melodico | Trasposizione, tempo, timbro |
| `pitch_class_profile_relative` | M | Note melodiche relative alla key | Trasposizione |
| `pc_transition_matrix` | M | Quali note seguono quali | Tempo, timbro |
| `chroma_profile_relative` | H | Energia armonica relativa alla key | Trasposizione |
| `harmonic_emphasis_relative` | H | Emphasis relativa alla key | Trasposizione |
| `relative_root_functions` | H | Progressione come gradi (I-IV-V) | Trasposizione |
| `relative_chord_functions` | H | Accordi come gradi (Imin7-IV-V7) | Trasposizione |
| `harmonic_rhythm_per_beat` | H | Cambi armonici per beat | Tempo |

Per confrontare, calcola la **cosine similarity** tra i vettori numerici (interval_histogram, chroma_profile_relative, etc.) e il **match ratio** tra le sequenze (relative_root_functions).

---

## Limitazioni

- Lavora **solo su audio mixato finale** — nessuna separazione di sorgenti
- Key detection euristico (Krumhansl-Kessler + Temperley), non ML
- Estrazione melodica da mix completo = intrinsecamente rumorosa
- Segmentazione strutturale, non semantica (no etichette "strofa"/"ritornello")
- Audio breve (<30s) = risultati meno affidabili
- Confidenze auto-valutate, non validate su ground truth
- Brani con forte distorsione possono confondere il key detection
- Power chords senza terza → mode_ambiguity = high (corretto)

---

## Disclaimer

> This output is a structural similarity aid derived from final mixed audio only. It is not a legal proof of plagiarism or authorship.

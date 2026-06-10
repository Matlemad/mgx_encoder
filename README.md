# MGX Lyrics Companion

Songwriting assistant che combina:
- **MGX audio genome analysis** — analisi strutturale del mix (DSP locale)
- **Cyanite enrichment** — mood, genre, energy, valence (mock, API ready)
- **Lyrics editor** — stats strutturali del testo
- **TACT-style text mining** — frequenze, n-grammi, co-occorrenze, KWIC
- **Contextual Palette** — 10 moduli di analisi contestuale attivati dalla selezione del testo
- **Musixmatch corpus exploration** — associazioni lessicali dal corpus (mock, API ready)
- **Inspiration engine** — direzioni creative dall'incrocio di tutti i dati

Tutto gira **in locale**. Nessuna API cloud necessaria. I provider esterni sono mockati con dati realistici e attivabili aggiungendo le API key.

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

### 5. Usa l'app

L'app ti guida in 3 step:

1. **Step 1 — Analyze Demo**: carica il tuo demo audio e clicca "Analyze Demo"
2. **Step 2 — Text & Mining**: incolla il testo del brano e clicca "Run Text Mining"
3. **Step 3 — Inspiration Studio**: seleziona porzioni di testo e usa la Contextual Palette per esplorare rime, riscritture, emozioni, cliche, immagini, e direzioni creative

Alla fine, vai su **Export** per scaricare tutti i file.

### 6. Dove trovo i file di output?

```
mgx_encoder/
  outputs/
    mgx_output.json       ← genoma MGX-v1
    mgx_report.md         ← report leggibile
    lyrics_mining.json    ← text mining
    full_project.json     ← tutto insieme
    plots/                ← grafici debug (se abilitati)
```

### 7. Sessioni successive

```bash
cd mgx/mgx_encoder
source .venv/bin/activate
streamlit run app.py
```

---

## Struttura del progetto

```
mgx_encoder/
  app.py                        ← UI Streamlit (flow guidato a 3 step)
  requirements.txt
  .env.example                  ← template per API key
  src/
    __init__.py
    audio_loader.py             ← caricamento file audio
    youtube_loader.py           ← download YouTube + cookie
    preprocessing.py            ← HPSS, band splits, tuning, multi-chroma
    multipass.py                ← 6 pass di analisi del segnale
    rhythm.py                   ← R: tempo, groove, swing
    melody.py                   ← M: pitch, intervalli, feature invarianti
    harmony.py                  ← H: key, modo, accordi, feature invarianti
    motif.py                    ← X: ripetizioni, auto-similarita
    form.py                     ← F: segmentazione in sezioni
    confidence.py               ← C: confidenze, coerenza, warning
    report.py                   ← generazione report Markdown
    lyrics_editor.py            ← analisi strutturale del testo
    text_mining.py              ← TACT-style: frequenze, n-grammi, KWIC
    inspiration_engine.py       ← sintesi creativa da tutti i dati
    utils.py                    ← helper
    providers/
      base.py                   ← interfacce astratte
      mock_musixmatch.py        ← dati mock corpus
      mock_cyanite.py           ← dati mock audio enrichment
      musixmatch.py             ← stub per API reale
      cyanite.py                ← stub per API reale
    contextual_palette/
      selection_analyzer.py     ← classifica tipo di selezione
      palette_registry.py       ← protocollo moduli
      runner.py                 ← esegue moduli per selezione
      llm_provider.py           ← mock LLM (futuro: OpenAI/Claude)
      modules/
        lexical_constellation.py
        rhyme_explorer.py
        metric_rewrite.py
        emotional_reading.py
        corpus_insights.py
        cliche_detector.py
        imagery_analyzer.py
        narrative_function.py
        repetition_radar.py
        inspiration_directions.py
  outputs/
  temp/
  examples/
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

## Flow esperienziale

L'app guida l'utente in un percorso a 3 step:

### Step 1 — Analyze Demo
Upload del file audio (WAV/MP3/FLAC) o link YouTube. Il sistema:
- Estrae il genoma musicale MGX-v1 (R, M, H, X, F, C)
- Arricchisce con dati Cyanite (mock): mood, genre, energy, valence, instrumentation
- Mostra un riepilogo: BPM, key, confidence, mood

### Step 2 — Text & Mining
Incolla il testo del brano (lo stesso cantato sul demo). Il sistema:
- Conta righe, strofe, parole, righe ripetute
- Esegue text mining TACT-style: frequenze, bigrammi, co-occorrenze
- Offre ricerca KWIC (keyword-in-context)

### Step 3 — Inspiration Studio
Il cuore dell'esperienza. Due colonne:
- **Sinistra**: il testo del brano
- **Destra**: la **Contextual Palette**

L'utente seleziona una porzione di testo e la incolla nel campo di selezione. Il sistema classifica automaticamente il tipo di selezione e attiva i moduli pertinenti.

Prima di analizzare, l'utente puo scegliere artisti di riferimento (o "All") e caricare dati corpus mock da Musixmatch.

### Export
Download di tutti gli output: MGX JSON, Mining JSON, Full Project JSON.

---

## Contextual Palette

La palette e un pannello contestuale che si attiva sulla selezione del testo. Classifica automaticamente il tipo di selezione e mostra solo i moduli rilevanti.

### Tipi di selezione

| Tipo | Esempio | Riconoscimento |
|------|---------|----------------|
| `WORD` | "mare" | 1 parola |
| `PHRASE` | "broken heart in the night" | 2+ parole su una riga |
| `STANZA` | 3+ righe | Blocco multi-riga |
| `CHORUS` | Strofa con "chorus"/"ritornello" | Keyword nel testo |
| `FULL_TEXT` | Tutto il testo | Match con i lyrics completi |

### I 10 moduli

| # | Modulo | Scopo | Tipi supportati |
|---|--------|-------|-----------------|
| 1 | **Lexical Constellation** | Espansione semantica: connessioni locali + corpus | WORD, PHRASE |
| 2 | **Rhyme Explorer** | Rime perfette, quasi-rime, assonanze, consonanze (IT+EN) | WORD, PHRASE |
| 3 | **Metric-Aware Rewrite** | Riscritture con 6 stili conservando la metrica | PHRASE, STANZA |
| 4 | **Emotional Reading** | Emozione testo vs musica + alignment score | PHRASE, STANZA, FULL |
| 5 | **Corpus Insights** | Associazioni dal corpus, direzioni meno esplorate (mock) | WORD, PHRASE, STANZA |
| 6 | **Cliche Detector** | Score cliche (0-100) + alternative originali | PHRASE, STANZA |
| 7 | **Imagery Analyzer** | Radar sensoriale: visual, auditory, tactile, spatial, body | PHRASE, STANZA, FULL |
| 8 | **Narrative Function** | Ruolo narrativo della strofa (observation, conflict, desire...) | STANZA, CHORUS |
| 9 | **Repetition Radar** | Parole/simboli ripetuti, campi dominanti | STANZA, FULL |
| 10 | **Inspiration Directions** | Territori inesplorati, opportunita simboliche, prompt creativi | STANZA, FULL |

### Stili di riscrittura (modulo 3)

| Stile | Approccio |
|-------|-----------|
| Conservative | Sinonimo diretto, struttura identica |
| Poetic | Vocabolario piu evocativo |
| Symbolic | Immagine al posto dell'astrazione |
| Concrete | Oggetto fisico al posto del concetto |
| Minimal | Riduzione, sottrazione |
| Narrative | Aggiunta di contesto narrativo |

### Architettura palette

```
src/contextual_palette/
  selection_analyzer.py     ← classifica WORD/PHRASE/STANZA/CHORUS/FULL_TEXT
  palette_registry.py       ← protocollo PaletteModule, registry
  runner.py                 ← esegue moduli, cross-module context
  llm_provider.py           ← MockLLMProvider (futuro: OpenAI, Claude)
  modules/
    lexical_constellation.py
    rhyme_explorer.py
    metric_rewrite.py
    emotional_reading.py
    corpus_insights.py
    cliche_detector.py
    imagery_analyzer.py
    narrative_function.py
    repetition_radar.py
    inspiration_directions.py
```

Ogni modulo espone: `id`, `title`, `supported_types`, `run(text, context)`.
Aggiungere un nuovo modulo = creare un file e importarlo in `runner.py`.

---

## Moduli di supporto

### Lyrics Editor (`src/lyrics_editor.py`)

- Normalizzazione testo
- Split in stanze (blank lines)
- Conteggio righe, parole, strofe
- Righe ripetute, parole frequenti
- Estrazione terminazioni di riga (placeholder rime)

### Text Mining (`src/text_mining.py`)

- Tokenizzazione + rimozione stopwords (EN + IT)
- Frequenza parole, bigrammi, trigrammi
- Co-occorrenze (finestra scorrevole, top 100)
- Concordanza KWIC

### Inspiration Engine (`src/inspiration_engine.py`)

- Campi lessicali dominanti dal mining
- Allineamento musica/testo (incrocia MGX + Cyanite con le emozioni del testo)
- Insight corpus (da Musixmatch mock)
- Suggerimenti di scrittura copyright-safe

---

## Provider adapters (`src/providers/`)

| File | Stato | Descrizione |
|------|-------|-------------|
| `base.py` | Implementato | Interfacce astratte `LyricsCorpusProvider`, `MusicAnalysisProvider` |
| `mock_musixmatch.py` | Implementato | Dati finti: temi, artisti correlati, associazioni, usage patterns |
| `mock_cyanite.py` | Implementato | Dati finti: mood, genre, energy, valence, instrumentation, tags |
| `musixmatch.py` | Stub | Legge `MUSIXMATCH_API_KEY`, raise se assente |
| `cyanite.py` | Stub | Legge `CYANITE_API_KEY`, raise se assente |

### LLM Provider (`src/contextual_palette/llm_provider.py`)

| Provider | Stato |
|----------|-------|
| `MockLLMProvider` | Implementato — risposte euristiche |
| `OpenAIProvider` | Futuro |
| `ClaudeProvider` | Futuro |

### Configurazione API

```bash
cp .env.example .env
```

```
MUSIXMATCH_API_KEY=
CYANITE_API_KEY=
PROVIDER_MODE=mock
```

Con `PROVIDER_MODE=mock` (default) tutti i provider sono mock. Aggiungi le API key per attivare quelli reali.

---

## File di output

| File | Contenuto |
|------|-----------|
| `outputs/mgx_output.json` | Genoma MGX-v1 |
| `outputs/mgx_report.md` | Report MGX leggibile |
| `outputs/lyrics_mining.json` | Risultato text mining |
| `outputs/full_project.json` | Tutto: MGX + lyrics + mining + cyanite + musixmatch + palette |
| `outputs/plots/` | Grafici debug (se abilitati) |

---

## Copyright safety

Il sistema **non genera mai**:
- Testi completi di altri artisti
- Imitazioni dirette ("scrivi come Artista X")
- Frasi coperte da copyright

Genera solo:
- Pattern lessicali astratti
- Cluster tematici
- Territori semantici
- Suggerimenti strutturali
- Prompt creativi (direzioni, non testi)
- Insight a livello di corpus

L'autore resta il songwriter. Il sistema e un microscopio e un assistente creativo.

---

## Limitazioni

**Audio genome:**
- Solo audio mixato finale — no stem separation
- Key detection euristico (Krumhansl-Kessler + Temperley), non ML
- Estrazione melodica da mix = rumorosa
- Segmentazione strutturale, non semantica
- Audio breve (<30s) = meno affidabile

**Lyrics / Mining:**
- Sillabe e rime = euristico basico
- Stopwords solo EN e IT
- Nessun NLP avanzato (no POS, no NER)

**Contextual Palette:**
- Rhyme bank limitato (euristico, non dizionario completo)
- Metric rewrite basato su sinonimi locali (futuro: LLM)
- Cliche detector copre i pattern piu comuni, non esaustivo
- Imagery analyzer basato su keyword, non su comprensione semantica profonda

**Provider:**
- Musixmatch e Cyanite sono mock
- LLM provider e mock (futuro: OpenAI/Claude)

---

## Disclaimer

> This output is a structural similarity aid derived from final mixed audio only. It is not a legal proof of plagiarism or authorship.

> The system never generates, displays, or suggests copyrighted lyrics from other artists.

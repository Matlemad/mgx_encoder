# MGX Librettist

**Melody-aware AI lyrics companion for songwriters.**

MGX Librettist **non è un generatore di canzoni**: è un **layer di intelligenza melody-aware per il testo**. Aiuta il songwriter a scrivere parole che si incastrano con la melodia, il mood, la struttura, i riferimenti e la direzione emotiva del brano caricato. Il cuore dell'esperienza è un **editor reattivo**: selezioni una riga o un blocco, il pannello a destra fa l'**audit automatico** (perché quella riga funziona o no) e proponi un **rephrase** controllato sulla metrica — l'AUTORE resta il songwriter. Combina:

- **MGX audio genome analysis** — analisi strutturale del mix (DSP locale)
- **MIDI analysis** — analisi opzionale di topline vocale e backing (slot sillabici, cadenze, pitch-class profile)
- **Cyanite enrichment** — genere, mood, energy, valence, arousal, strumentazione, BPM, key (API GraphQL reale, con fallback mock)
- **Lyrics Prompter** — due modalità: testo già scritto (struttura + prosodia + mining) o solo un tema (**Writing Brief AI**, con fallback euristico)
- **Reference Profile** — astrazione copyright-safe di artisti/canzoni di riferimento (Musixmatch)
- **Reactive Lyrics Editor + Line/Block Audit** — clicchi una riga/blocco e il pannello mostra automaticamente 8 punteggi (Metric Fit, Stress Alignment, Singability, Mood, Rhyme, Cliché Risk, Imagery, Reference Alignment), una diagnosi e un'azione consigliata
- **Rephrase on melody** — controlli semplici (mood, struttura rime, artista reference da Musixmatch) e un bottone Rephrase che propone un'alternativa sulla metrica (OpenAI solo al click); **Apply** sostituisce solo la riga/blocco selezionato
- **Metric Draft Scaffold** — strumento secondario per impostare un draft strutturato sulla metrica del MIDI, con validazione sillabica
- **Indicatori di progresso** — ogni tab mostra una spunta verde (✅) al completamento dello step

Tutto gira **in locale**. L'app è pienamente usabile offline: i provider esterni (Musixmatch, Cyanite) e l'LLM (OpenAI) hanno fallback mock/euristici e si attivano aggiungendo le API key in `.env`.

### Regola di sicurezza copyright

Il sistema **non** imita artisti viventi o defunti e **non** riproduce testi protetti. I riferimenti vengono usati solo per estrarre pattern astratti e copyright-safe: temi, campi lessicali, densità di immagini, tendenze di lunghezza dei versi, stance narrativa, temperatura emotiva, tendenze strutturali, tendenze ritmico-foniche, territori simbolici. **L'autore resta il songwriter.**

---

## Quick Start (run-through completo)

### 1. Prerequisiti

- **Python 3.11+**
- **ffmpeg** (consigliato per la decodifica/conversione audio di MP3/FLAC)
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

L'app è organizzata in **5 tab**:

1. **Demo Uploader**: carica il demo audio (richiesto) e, opzionalmente, MIDI vocale + MIDI backing + metadata manuali. Genera la *Song Genome Summary*.
2. **Lyrics Prompter**: scegli la modalità — **A** (ho già il testo: struttura, prosodia, text mining) o **B** (ho solo un tema: genera un *Writing Brief*, non testi completi).
3. **References**: inserisci artisti/canzoni/tag di riferimento. Genera un *Reference Profile* copyright-safe (solo pattern astratti).
4. **Writing Studio**: editor reattivo a sinistra, **Line/Block Audit + Rephrase** a destra, riepilogo del brano in alto. **Clicca** una riga (o "Select block" su una strofa/ritornello): il pannello fa l'audit automatico, poi puoi fare **Rephrase** e **Apply**. In fondo c'è il **Metric Draft Scaffold** per impostare un draft sulla metrica.
5. **Export**: scarica `full_project.json`, il report Markdown e i singoli JSON.

> MIDI opzionale: se non carichi un MIDI vocale, i moduli metrici useranno stime euristiche da BPM e lunghezza dei versi.

### 6. Dove trovo i file di output?

```
mgx_encoder/
  outputs/
    mgx_output.json         ← genoma MGX-v1
    mgx_report.md           ← report MGX leggibile
    lyrics_mining.json      ← text mining
    full_project.json       ← stato di progetto unificato (tutto)
    librettist_report.md    ← report Librettist leggibile
    plots/                  ← grafici debug (se abilitati)
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
  app.py                        ← UI Streamlit (5 tab: Demo, Lyrics, References, Studio, Export)
  requirements.txt
  .env.example                  ← template per API key
  src/
    __init__.py
    audio_loader.py             ← caricamento file audio
    preprocessing.py            ← HPSS, band splits, tuning, multi-chroma
    multipass.py                ← 6 pass di analisi del segnale
    rhythm.py                   ← R: tempo, groove, swing
    melody.py                   ← M: pitch, intervalli, feature invarianti
    harmony.py                  ← H: key, modo, accordi, feature invarianti
    motif.py                    ← X: ripetizioni, auto-similarita
    form.py                     ← F: segmentazione in sezioni
    confidence.py               ← C: confidenze, coerenza, warning
    report.py                   ← generazione report MGX Markdown
    midi_analyzer.py            ← analisi MIDI vocale/backing (mido)
    lyrics_editor.py            ← struttura del testo + prosodia/sillabe
    text_mining.py              ← TACT-style: frequenze, n-grammi, KWIC
    writing_brief.py            ← Writing Brief da un tema (Mode B, AI + fallback euristico)
    reference_profile.py        ← Reference Profile copyright-safe
    librettist_report.py        ← Song Genome Summary + report Librettist
    draft_composer.py           ← Draft Composer: generazione testi AI melody-aware
    utils.py                    ← helper
    providers/
      base.py                   ← interfacce astratte
      factory.py                ← selezione real/mock + fallback (carica .env)
      mock_musixmatch.py        ← dati mock corpus
      mock_cyanite.py           ← dati mock audio enrichment
      musixmatch.py             ← API Musixmatch reale (Analysis API)
      cyanite.py                ← API Cyanite reale (GraphQL)
    contextual_palette/
      selection_analyzer.py     ← classifica tipo di selezione
      audit.py                  ← Line/Block Audit (8 score deterministici + diagnosi)
      rephrase_selection.py     ← Rephrase on-demand (OpenAI + fallback euristico)
      palette_registry.py       ← protocollo moduli
      runner.py                 ← esegue moduli per selezione (motore interno audit)
      llm_provider.py           ← provider LLM (OpenAI live + fallback mock)
      modules/
        lexical_constellation.py
        rhyme_explorer.py
        metric_rewrite.py
        metric_fit.py
        stress_alignment.py
        hook_strength.py
        singability_check.py
        emotional_reading.py
        corpus_insights.py
        cliche_detector.py
        imagery_analyzer.py
        narrative_function.py
        repetition_radar.py
        title_finder.py
        inspiration_directions.py
  outputs/
  temp/
  examples/
```

---

## Input audio

L'app accetta **solo file audio caricati**: `WAV`, `MP3`, `FLAC`. (Il download da YouTube è stato rimosso dal prodotto.)

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
| `source` | string | `"file"` (sempre, l'app accetta solo upload) |
| `filename` | string | Nome del file analizzato |
| `title` | string / null | Titolo del brano (metadata manuale) |
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

L'app guida l'utente in 5 tab:

### 1 — Demo Uploader
Upload del **file audio** (WAV/MP3/FLAC), più MIDI opzionali e metadata manuali. Il sistema:
- Estrae il genoma musicale MGX-v1 (R, M, H, X, F, C)
- Analizza MIDI vocale (slot sillabici, frasi, cadenza) e backing (pitch-class profile, root) se forniti
- Arricchisce con **Cyanite** (analisi audio reale via GraphQL quando `CYANITE_MODE=graphql` + API key; altrimenti mock): genere/sottogeneri, mood, energy, valence, arousal, strumentazione, BPM, key, time signature. Se la chiamata live fallisce, **ricade automaticamente sul mock** con un avviso.
- Mostra la **Song Genome Summary** unificata: BPM/Key confrontati **MGX vs Cyanite vs scelto**, time signature, mood/energy/valence/arousal, genere/sottogenere, strumentazione, sezioni/forma (MGX), contorno melodico, warning e note di confidenza. La risposta GraphQL raw resta solo in un expander di debug.
- Se carichi un **MIDI vocale**, mostra la **Vocal Melody Map**: numero di note, durata, range melodico, durata media nota, numero di frasi, slot sillabici suggeriti, posizioni forti, profilo di cadenza, warning. Questa mappa abilita la modalità **melody-aware** per Metric Fit e Stress Alignment. Senza MIDI vocale, questi moduli funzionano comunque in **modalità euristica** (stime da BPM e lunghezza dei versi).

### 2 — Lyrics Prompter
Due modalità:
- **Mode A — ho già il testo**: struttura, prosodia per riga (sillabe, ending, stress hint, rime), text mining TACT-style (frequenze, bigrammi, co-occorrenze, KWIC)
- **Mode B — ho solo un tema**: genera un **Writing Brief** (tema, POV, temperatura emotiva, scene, campi lessicali, immagini promettenti/da evitare, titoli, concept di ritornello, archi narrativi). **Non** genera testi completi.

### 3 — References
Inserisci artisti, canzoni e tag di riferimento (+ eventuali "avoid"). Genera un **Reference Profile — copyright-safe abstraction**: solo pattern astratti (temi comuni, mood dominanti, generi/territori stilistici, entità/territori simbolici, stance narrativa, densità di immagini, tendenze di verso/ritornello, vincoli creativi, territori da evitare). Mai testi.

**Musixmatch API — uso e visibilità**
- In alto trovi un **box di stato del provider**: provider mode (`real`/`mock`), stato Musixmatch (`live` / `mock` / chiave mancante), esito dell'ultima chiamata e l'etichetta di sicurezza *"Abstract descriptors only — no lyrics stored"*.
- Quando inserisci artisti reali e Musixmatch è `live`, il profilo viene àncorato al vero catalogo degli artisti (Analysis API → temi/mood/entità/generi aggregati) e compare il badge **"✅ Grounded in Musixmatch API"**.
- Se la chiamata live fallisce, l'app fa **fallback automatico al mock** e mostra *"Using mock fallback because: <reason>"*.
- Ogni profilo registra la **provenienza**: `source` (`musixmatch_live` | `musixmatch_mock_fallback` | `musixmatch_mock`), `provider_status`, `copyright_safe`, `stored_content_policy: abstract_descriptors_only_no_lyrics`.
- Un **debug expander sanitizzato** mostra solo informazioni astratte: qualsiasi campo che possa contenere testo letterale (lyrics, snippet, quote…) viene rimosso prima di visualizzazione ed export tramite `strip_literal_text`.
- L'app **non memorizza né mostra mai testi** restituiti da Musixmatch: solo descrittori astratti.

Il Reference Profile alimenta **Corpus Insights** e **Inspiration Directions** nella Writing Studio, che dichiarano esplicitamente se gli spunti sono *grounded in Musixmatch live*, basati su *mock profile* o su *euristiche locali generiche*.

Una callout **"Suggested references demo"** guida i giudici: 1) aggiungi 2–3 artisti, 2) genera il profilo, 3) vai in Writing Studio, 4) seleziona una strofa, 5) lancia Corpus Insights o Inspiration Directions.

### 4 — Writing Studio (reactive lyric editor)
Il cuore dell'esperienza. In alto il riepilogo del brano e il box di contesto reference; sotto, due colonne:
- **Sinistra — Lyrics editor reattivo**: un `text_area` editabile (persistente) **più** una lista cliccabile di righe e blocchi. Clicca **"Select block"** su una strofa/ritornello, oppure una **singola riga**, per selezionarla. La riga selezionata è evidenziata (●).
- **Destra — Line/Block Audit**: appena selezioni qualcosa, il pannello si aggiorna **automaticamente** (nessun bottone "run").

Interazione principale: **Select → Audit → Rephrase → Apply.**

**Line/Block Audit** mostra:
- un blurb **"perché questa riga/blocco funziona o no"**;
- 8 punteggi (0–100): **Metric Fit, Stress Alignment, Singability, Mood Alignment, Rhyme Structure, Cliché Risk, Imagery Strength, Reference Alignment**;
- la metrica melodica (mode melody-aware/heuristic, sillabe stimate, range target);
- una **diagnosi** (cosa funziona / cosa no / azione consigliata);
- l'origine del reference (Musixmatch live / mock fallback / nessun profilo).

L'audit è **deterministico e veloce** (riusa la logica dei moduli esistenti: metric_fit, stress_alignment, singability_check, emotional_reading, cliche_detector, imagery_analyzer, rhyme_explorer) e **non** chiama OpenAI. Tutto il contesto è alimentato da: **song genome summary**, MGX, Cyanite, MIDI vocale/backing, prosodia, text mining, reference profile e writing brief.

**Rephrase controls** (solo questi): un **Mood slider** (darker / balanced / brighter, default inferito dal mood del brano), un **Rhyme structure slider** (AABB / ABAB / ABBA / loose-slant), uno slider **"Stick to melody metric"** (loose / balanced / tight) e un **selettore artista reference** popolato da `reference_profile.artists` (Musixmatch). L'artista influenza il rephrase **solo come direzione astratta** (temi, mood, densità di immagini, stance) — mai imitazione né citazione.

> **Target per-riga**: il rephrase calcola un target di sillabe **per ciascuna riga** della selezione (dalle frasi del MIDI vocale, o ripartendo il range del blocco quando il MIDI non c'è) e lo passa a OpenAI riga per riga, con l'istruzione esplicita di **riscrivere le parole** (comprimere/espandere) per centrare il target — **non** di limitarsi a ri-spezzare il testo originale. Lo slider *tight* alza la priorità metrica (e la temperatura) per forzare una vera parafrasi sulla metrica.

- **Rephrase**: chiama OpenAI **solo al click**, riscrive **solo** la riga/blocco selezionato rispettando metrica/mood/rime, e mostra una spiegazione + un check metrico. Con LLM non disponibile/quota esaurita → **fallback euristico** (nessun crash, warning chiaro).
- **Apply**: sostituisce **solo** la riga/blocco selezionato (per **indice di riga**, quindi nessuna ambiguità con occorrenze ripetute), aggiorna il testo, ri-esegue prosodia/text mining se attivi e mostra "Applied to lyrics editor." Il draft dell'utente non viene mai sovrascritto per intero.

> Nota tecnica: `st.text_area` non espone la selezione live in Streamlit. Usiamo quindi un modello **click-to-select** riga/blocco, che per l'Apply è anche più robusto (sostituzione per indice). La UX resta reattiva: niente copia/incolla manuale.

#### Metric Draft Scaffold — draft sulla melodia (strumento secondario, copyright-safe)
Sotto l'editor reattivo c'è il **Metric Draft Scaffold** (ex Draft Composer): non è un generatore di canzoni, ma uno strumento per **impostare un draft strutturato sulla metrica del MIDI** quando parti da zero o vuoi riscrivere un'intera sezione. Combina **tutto** il contesto raccolto prima:
- **genoma musicale** (MGX + Cyanite): bpm, key, mode, mood, energy, genere;
- **metrica della melodia** dal MIDI vocale: numero di frasi e **target di sillabe per riga** (in ordine), cadenza, range melodico;
- **intento creativo**: il *Writing Brief* (Mode B) **oppure** le lyrics esistenti (Mode A) da riscrivere/continuare;
- **Reference Profile** Musixmatch (solo pattern astratti, mai testi da copiare).

Comportamento:
- Se non ci sono lyrics ma esiste un Writing Brief (Mode B) → pulsante **"Draft on melody"**.
- Se ci sono lyrics (Mode A) → **"Rewrite draft on melody"**.
- Il draft è **strutturato** (title + sezioni verse/chorus/bridge) e passa una **validazione metrica**: ogni riga del verse viene confrontata con i target di sillabe del MIDI (±1). Se troppe righe sbagliano, parte un **re-pass automatico "tighten to metric"**.
- Puoi **rigenerare tutto**, **rigenerare una singola sezione**, e poi **"Use this draft in the editor"** per portarlo nell'editor: a quel punto lo rifinisci riga per riga con il Line/Block Audit + Rephrase.
- **Copyright safe**: il system prompt vieta di riprodurre testi esistenti; i riferimenti sono solo descrittori astratti; l'autore resti tu.

Configurazione LLM (in `.env`):
```
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
```
Se la chiave manca o l'SDK non è installato, il Draft Composer usa un **generatore euristico di fallback** (placeholder marcati `[draft]`) così il flusso resta dimostrabile offline. Richiede `pip install openai` (già in `requirements.txt`).

#### Come le metriche vengono servite a OpenAI
Le quattro fonti (Cyanite, MGX, text mining, Musixmatch) **non** vengono passate grezze: sono ridotte a descrittori astratti e assemblate in un *brief* testuale strutturato (`build_composition_brief` → `_user_prompt` in `src/draft_composer.py`). Ci sono due punti di chiamata all'LLM:

1. **Writing Brief AI** (Mode B): riceve il tuo tema + un mini-contesto musicale (mood da Cyanite, mode/bpm da MGX) + la **direzione astratta del Reference Profile** Musixmatch (temi/mood/stance).
2. **Draft Composer** (Writing Studio): riceve l'intero brief assemblato.

Mappa fonte → cosa arriva al modello (Draft Composer):

| Fonte | Descrittori serviti | Sezione del prompt |
|------|---------------------|--------------------|
| **MGX** (DSP locale) | `bpm`, `key`, `mode`, `time_signature`, `form_sections` | `MUSICAL CONTEXT` |
| **Cyanite** | `mood`/`moods`, `energy`, `valence`, `arousal`, `genres`/`subgenres`, `instrumentation` (e `bpm`/`key` se MGX manca) | `MUSICAL CONTEXT` |
| **MIDI vocale** | target di sillabe per riga (ordinati), n° frasi, `cadence`, range melodico | `MELODY METRIC` (vincolo più stringente) |
| **Text mining** | top words, bigrammi, co-occorrenze | `LYRIC VOCABULARY` |
| **Musixmatch** (Reference Profile) | `common_themes`, `dominant_moods`, `narrative_stance`, `imagery_density` — solo astratti | `REFERENCE DIRECTION` (ispirazione, non imitazione) |
| **Writing Brief** | tema, temperatura, POV, scene, immagini, titoli, concept chorus | `CREATIVE INTENT` |
| **Lyrics (Mode A)** | il tuo testo esistente (solo in *rewrite*) | `EXISTING DRAFT` |

Dopo la generazione, le sillabe di ogni riga del verse vengono **ricontate localmente** e confrontate con i target del MIDI; se troppe righe sforano (±1) parte un **re-pass automatico "tighten to metric"** che rimanda a OpenAI solo le righe fuori metrica. **Copyright safe**: il system prompt vieta di riprodurre testi esistenti e i riferimenti restano descrittori astratti.

### 5 — Export
Download di tutti gli output: Full Project JSON, MGX JSON, Lyrics Mining JSON e il **Librettist Report** in Markdown. Il `full_project.json` include anche `analysis.generated_draft` (con `source`, `model`, `copyright_safe`, `metric_report`) e `analysis.composition_brief`.

---

## Contextual Palette (motore dell'audit)

I moduli della palette restano il **motore interno** del Line/Block Audit: `build_selection_audit` (`src/contextual_palette/audit.py`) richiama la loro logica e la riduce a 8 punteggi deterministici 0–100 + diagnosi. Il rephrase on-demand vive in `src/contextual_palette/rephrase_selection.py` (OpenAI solo al click, con fallback euristico). Di seguito i tipi di selezione e i singoli moduli riusati.

### Tipi di selezione

| Tipo | Esempio | Riconoscimento |
|------|---------|----------------|
| `WORD` | "mare" | 1 parola |
| `PHRASE` | "broken heart in the night" | 2+ parole su una riga |
| `STANZA` | 3+ righe | Blocco multi-riga |
| `CHORUS` | Strofa con "chorus"/"ritornello" | Keyword nel testo |
| `FULL_TEXT` | Tutto il testo | Match con i lyrics completi |

### I 15 moduli

| # | Modulo | Scopo | Tipi supportati |
|---|--------|-------|-----------------|
| 1 | **Lexical Constellation** | Espansione semantica: connessioni locali + corpus | WORD, PHRASE |
| 2 | **Rhyme Explorer** | Rime perfette, quasi-rime, assonanze, consonanze (IT+EN) | WORD, PHRASE |
| 3 | **Metric-Aware Rewrite** | Riscritture multi-stile conservando metrica/accenti/ultima parola | PHRASE, STANZA |
| 4 | **Metric Fit** | Sillabe del testo vs slot melodici. `mode: melody-aware` con MIDI vocale, `mode: heuristic` senza. Espone range sillabico target, diagnosi e problemi | PHRASE, STANZA, CHORUS |
| 5 | **Stress Alignment** | Parole forti su posizioni metriche/melodiche forti. `mode: melody-aware` con MIDI vocale (posizioni forti reali), altrimenti `heuristic` | PHRASE, CHORUS |
| 6 | **Hook Strength** | Forza del ritornello/hook + candidati titolo + singability | CHORUS, PHRASE |
| 7 | **Singability Check** | Righe difficili da cantare (cluster consonantici, plosive, vocali) | PHRASE, CHORUS, STANZA |
| 8 | **Emotional Reading** | Emozione testo vs musica + alignment + opzioni creative | PHRASE, STANZA, FULL |
| 9 | **Corpus Insights** | Associazioni astratte da corpus + reference profile (mock) | WORD, PHRASE, STANZA |
| 10 | **Cliche Detector** | Score cliche (0-100) + alternative originali | PHRASE, STANZA |
| 11 | **Imagery Analyzer** | Radar sensoriale: visual, auditory, tactile, spatial, body | PHRASE, STANZA, FULL |
| 12 | **Narrative Function** | Ruolo narrativo della strofa (observation, conflict, desire...) | STANZA, CHORUS |
| 13 | **Repetition Radar** | Parole/simboli ripetuti, campi dominanti | STANZA, FULL |
| 14 | **Title Finder** | Titoli ricavati dal testo dell'autore (mai dai riferimenti) | STANZA, CHORUS, FULL |
| 15 | **Inspiration Directions** | Direzioni creative dall'incrocio di MGX/Cyanite/MIDI/reference/brief | STANZA, FULL |

### Stili di riscrittura (Metric-Aware Rewrite)

`conservative`, `poetic`, `symbolic`, `concrete`, `minimal`, `narrative`, `ironic`, `darker`, `simpler`, `more_singable`.

Controlli `preserve`: `syllable_count`, `main_accents`, `last_word`, `rhyme`, `meaning`, `dominant_image`, `emotional_tone`. Quando è presente **Metric Fit**, le sue **target sillabe** e i flag `preserve_last_word` / `preserve_rhyme` vengono passati automaticamente al rewrite: le alternative cercano di rispettare il numero di sillabe target, l'ultima parola (se richiesto), la rima (se richiesta) e mantenere significato/immagine dominante/tono emotivo.

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
    metric_fit.py
    stress_alignment.py
    hook_strength.py
    singability_check.py
    emotional_reading.py
    corpus_insights.py
    cliche_detector.py
    imagery_analyzer.py
    narrative_function.py
    repetition_radar.py
    title_finder.py
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

### MIDI Analyzer (`src/midi_analyzer.py`)

- `analyze_vocal_midi(path)` → eventi nota, frasi, range melodico, slot sillabici suggeriti, posizioni forti, profilo di cadenza. Alimenta la **Vocal Melody Map** in Tab 1 e abilita la modalità **melody-aware** di Metric Fit e Stress Alignment.
- `analyze_backing_midi(path)` → pitch-class profile, density profile, root accordali probabili
- Basato su `mido` (puro Python). Fail-soft: se `mido` manca o il file è corrotto, restituisce un dict con `warnings` senza rompere l'app. Senza MIDI vocale, i moduli melody-aware ripiegano sulla modalità euristica (BPM + lunghezza versi).

### Writing Brief (`src/writing_brief.py`)

- `generate_writing_brief(theme_prompt, language, mgx_summary, cyanite)` → brief strutturato (tema, POV, temperatura, scene, campi lessicali, immagini, titoli, ritornelli, archi narrativi)
- Template-based in mock mode. **Non** genera testi completi

### Reference Profile (`src/reference_profile.py`)

- `build_reference_profile(artists, provider, ...)` → pattern astratti copyright-safe (stance, densità immagini, stile verso/ritornello, registro simbolico, vincoli, avoid)
- Usa il provider Musixmatch (mock) solo per associazioni a livello di corpus

### Text Mining (`src/text_mining.py`)

- Tokenizzazione + rimozione stopwords (EN + IT)
- Frequenza parole, bigrammi, trigrammi
- Co-occorrenze (finestra scorrevole, top 100)
- Concordanza KWIC

### Draft Composer (`src/draft_composer.py`)

- `build_composition_brief(...)` → impacchetta genoma musicale, metrica MIDI, intento creativo, reference astratti **e segnali del text mining** (top words/bigrams) in un brief copyright-safe
- `compose_draft(provider, brief, ...)` → genera un draft strutturato via LLM, valida la metrica riga-per-riga e applica un re-pass "tighten to metric"; fallback euristico offline
- `regenerate_section(...)` → rigenera una singola sezione (verse/chorus/bridge)
- `validate_metric(...)` → confronta le sillabe generate con i target del MIDI vocale

### Draft / Brief AI (`src/contextual_palette/llm_provider.py`)

- `OpenAILLMProvider` (live) + `MockLLMProvider` (fallback), selezionati da `LLM_PROVIDER`/`OPENAI_API_KEY`
- Alimenta sia il **Draft Composer** sia il **Writing Brief AI** della Mode B
- Mai riproduce testi esistenti: copyright safety nei system prompt

---

## Provider adapters (`src/providers/`)

| File | Stato | Descrizione |
|------|-------|-------------|
| `base.py` | Implementato | Interfacce astratte `LyricsCorpusProvider`, `MusicAnalysisProvider` |
| `factory.py` | Implementato | Sceglie provider reale/mock in base a `PROVIDER_MODE` + chiavi, con fallback |
| `mock_musixmatch.py` | Implementato | Dati finti: temi, artisti correlati, associazioni, usage patterns |
| `mock_cyanite.py` | Implementato | Dati finti: mood, genre, energy, valence, instrumentation, tags |
| `musixmatch.py` | **Implementato (live)** | API Musixmatch reale via **Analysis API** — solo pattern astratti (moods/themes/entities), mai testi |
| `cyanite.py` | **Implementato (live)** | API Cyanite reale via **GraphQL** — test credenziali + analisi audio (upload → analisi → descrittori astratti) |

### Musixmatch (live)

Il provider reale usa principalmente `track.lyrics.analysis.search` (Analysis API), che restituisce dati astratti a livello di corpus:

- `search_by_theme(themes)` → temi/mood/generi co-occorrenti reali per ciascun seed
- `artist_analysis_profile(artist)` → analizza i brani reali (top tracks) dell'artista citato e aggrega temi/mood/entità/generi. **Questo àncora il Reference Profile al vero catalogo degli artisti di riferimento**, non a pattern generici, restando astratto e copyright-safe
- `lexical_associations(word)` → temi ed entità che co-occorrono con la parola
- `usage_patterns(word)` → pattern astratti (mood dominanti, generi tipici, temi correlati)
- `related_artists(artist)` → euristica per genere (Musixmatch non ha un endpoint "related" diretto)

Quando inserisci artisti nella tab **References**, il profilo viene marcato come *grounded in real catalog* e mostra, per ciascun artista, i temi/mood/generi/entità ricavati dai suoi brani reali — sempre come descrittori astratti, mai testi.

**Copyright safety:** il provider scarta deliberatamente qualsiasi frammento letterale di testo (es. `themes[].quotes`). Espone solo descrittori astratti. Autenticazione via parametro `apikey` su `https://api.musixmatch.com/ws/1.1/`.

Se la chiamata live fallisce (rete, chiave non valida, limiti di piano), l'app ricade automaticamente sul provider mock con un avviso.

### Cyanite (live, GraphQL)

Provider audio reale via API **GraphQL** (`https://api.cyanite.ai/graphql`), autenticazione `Authorization: Bearer <CYANITE_API_KEY>`. Si attiva con `CYANITE_MODE=graphql`.

Funzioni principali in `src/providers/cyanite.py`:

- `cyanite_graphql_request(query, variables)` → POST GraphQL riutilizzabile, con gestione di errori di rete, HTTP, `401/403` e array `errors` GraphQL.
- `test_cyanite_credentials()` → test leggero (`query { ping }`); non solleva eccezioni, ritorna `{ok, mode, api_url, message, raw}`.
- `analyze_audio_file(path)` → flusso completo: `fileUploadRequest` → PUT dei byte audio → `libraryTrackCreate` (auto-enqueue di `AudioAnalysisV7`) → polling di `libraryTrack(id)` → estrazione dei **descrittori astratti**.

I descrittori restituiti (`normalize_analysis_result`) sono copyright-safe: genere/sottogeneri, mood (`moodTags`/`moodAdvancedTags`), movimento, carattere, strumenti, voce, `energyLevel`, `valence`, `arousal`, `keyPrediction {value, confidence}`, `bpmPrediction {value, confidence}`, `timeSignature`, era musicale, una caption. Nessun testo, nessun audio salvato.

**Integrazione nel flusso principale (Tab 1):** quando clicchi **Analyze Demo**, dopo l'analisi locale MGX l'app esegue automaticamente l'analisi Cyanite reale se `CYANITE_MODE=graphql` e `CYANITE_API_KEY` è presente. In caso di errore (rete, timeout, stato `Failed`) **ricade sul mock** mostrando un avviso con la causa. Il risultato finisce in `analysis.cyanite`, la sorgente in `analysis.cyanite_source` (`cyanite_live` / `cyanite_mock_fallback` / `cyanite_mock`), e i descrittori confluiscono nella Song Genome Summary.

Resta inoltre disponibile la tab **5 · Export → Provider debug** con due controlli di test:
- **Test Cyanite credentials** → verifica connettività (`ping`).
- **Run Cyanite analysis (real)** → analizza l'audio del demo (o un file caricato) e mostra i descrittori normalizzati + la risposta raw.

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
PROVIDER_MODE=real
MUSIXMATCH_API_KEY=la_tua_chiave
CYANITE_API_KEY=il_tuo_access_token
CYANITE_API_URL=https://api.cyanite.ai/graphql
CYANITE_MODE=graphql
CYANITE_WEBHOOK_SECRET=il_tuo_webhook_secret
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
ANTHROPIC_API_KEY=
```

- `PROVIDER_MODE=mock` → tutti i provider sono mock, app pienamente usabile offline.
- `PROVIDER_MODE=real` → per ogni provider, usa l'API reale se la relativa chiave è presente, altrimenti ricade sul mock.
- `LLM_PROVIDER=openai` + `OPENAI_API_KEY` → abilita il **Writing Brief AI** e il **Draft Composer** live; senza chiave (o senza `pip install openai`) si usano i fallback euristici. Richiede crediti attivi sull'account OpenAI.

Il file `.env` è già in `.gitignore`: **non committare mai le chiavi**. Le variabili vengono caricate automaticamente con `python-dotenv`. Lo stato dei provider (live/mock) è mostrato in cima all'app.

---

## Cyanite Webhook Setup

Cyanite notifica via webhook quando l'analisi audio cambia stato (es. `finished` / `failed`). È disponibile un endpoint serverless minimale, pronto per il deploy su Vercel:

```
api/cyanite/webhook.py        ← funzione Python serverless (dentro al repo mgx_encoder)
.vercelignore                 ← esclude l'app Streamlit dal deploy Vercel
```

URL finale dopo il deploy:

```
https://<vercel-app-domain>/api/cyanite/webhook
```

L'endpoint accetta `POST` (eventi Cyanite), espone un healthcheck `GET`, verifica la firma `Signature` (**HMAC-SHA512** del raw body) se `CYANITE_WEBHOOK_SECRET` è impostato, logga l'evento e risponde **200** rapidamente (Cyanite annulla la richiesta dopo ~3s). Non scarica ancora i risultati dell'analisi.

### Variabili d'ambiente

```
CYANITE_WEBHOOK_SECRET=
CYANITE_API_KEY=
CYANITE_API_URL=https://api.cyanite.ai/graphql
```

- Se `CYANITE_WEBHOOK_SECRET` è assente, l'endpoint accetta comunque l'evento ma logga un avviso (gli eventi di test della web-app Cyanite non includono la firma).
- `CYANITE_API_KEY` non è ancora usata dal webhook (servirà al prossimo step di integrazione).

### Deploy su Vercel

1. Il repo GitHub deployato è `mgx_encoder`, quindi lascia la **Root Directory = `.` (root del repo)**: è la cartella che contiene sia `app.py` sia `api/`. Vercel rileva automaticamente `api/**/*.py` come funzioni Python (l'endpoint usa solo la stdlib).
   - Il file `.vercelignore` esclude dal deploy `app.py`, `src/` e `requirements.txt` (Streamlit non gira su Vercel). Questo evita l'errore *"Found app.py but it does not export a top-level app/application/handler"* e impedisce l'installazione di dipendenze pesanti (librosa, ecc.). **Non** impostare la Root Directory su una sottocartella.
2. Copia l'URL deployato: `https://<domain>/api/cyanite/webhook`
3. Invia questo URL a Cyanite per ottenere le credenziali API (access token + webhook secret).
4. Aggiungi `CYANITE_API_KEY` e `CYANITE_WEBHOOK_SECRET` ottenuti nelle **Environment Variables** di Vercel.
5. **Redeploy** dopo aver impostato le variabili d'ambiente.
6. Testa l'endpoint:

```bash
curl -X GET https://<domain>/api/cyanite/webhook

curl -X POST https://<domain>/api/cyanite/webhook \
  -H "Content-Type: application/json" \
  -d '{"version":"2","resource":{"type":"LibraryTrack","id":"test"},"event":{"type":"AudioAnalysisV7","status":"finished"}}'
```

### Test locale

```bash
python api/cyanite/webhook.py     # serve su http://localhost:8000

curl http://localhost:8000/api/cyanite/webhook
curl -X POST http://localhost:8000/api/cyanite/webhook \
  -H "Content-Type: application/json" \
  -d '{"version":"2","resource":{"type":"LibraryTrack","id":"test"},"event":{"type":"AudioAnalysisV7","status":"finished"}}'
```

In locale (non su Vercel) gli eventi ricevuti vengono accodati in `outputs/cyanite_webhook_events.jsonl`. Su Vercel la scrittura su filesystem viene saltata (FS effimero/read-only).

> Nota: questo è solo l'endpoint webhook (riceve gli eventi). Il flusso reale di upload/analisi e il fetch dei risultati sono già implementati lato app in `src/providers/cyanite.py` (polling di `libraryTrack`). Collegare il webhook in modo che, all'evento `finished`, recuperi automaticamente i risultati è il prossimo step.

---

## File di output

| File | Contenuto |
|------|-----------|
| `outputs/mgx_output.json` | Genoma MGX-v1 |
| `outputs/mgx_report.md` | Report MGX leggibile |
| `outputs/lyrics_mining.json` | Risultato text mining |
| `outputs/full_project.json` | Stato di progetto unificato: project_meta, inputs, analysis (mgx, cyanite, cyanite_source, song_genome_summary, vocal/backing MIDI, lyrics, prosodia, mining, writing brief, reference profile, generated_draft, composition_brief), writing_studio (selection_audit copyright-safe), exports |
| `outputs/librettist_report.md` | Report Librettist leggibile (Song Genome, Lyrics, Writing Brief, Reference Profile, Line/Block Audit, Warnings, Copyright) |
| `outputs/plots/` | Grafici debug (se abilitati) |

---

## Data model — `full_project.json`

Lo stato di progetto unificato esportato dall'app:

```json
{
  "project_meta": { "title": "", "language": "", "created_at": "", "provider_mode": "mock" },
  "inputs": {
    "audio_file": "", "vocal_midi_file": "", "backing_midi_file": "",
    "reference_artists": [], "reference_songs": [], "avoid_references": []
  },
  "analysis": {
    "mgx": {}, "cyanite": {},
    "cyanite_source": "cyanite_live | cyanite_mock_fallback | cyanite_mock",
    "song_genome_summary": {},
    "vocal_midi": {}, "backing_midi": {},
    "lyrics_structure": {}, "lyrics_prosody": {}, "text_mining": {},
    "writing_brief": {}, "reference_profile": {}
  },
  "writing_studio": {
    "selected_text": "", "selection_type": "LINE | BLOCK | STANZA | CHORUS | FULL_TEXT",
    "selection_line_range": [0, 0],
    "selection_audit": { "scores": {}, "diagnosis": {}, "metric": {}, "reference": {} },
    "copyright_safe": true, "stored_content_policy": "abstract_descriptors_only_no_lyrics"
  },
  "exports": { "mgx_output": "outputs/mgx_output.json", "lyrics_mining": "outputs/lyrics_mining.json", "full_project": "outputs/full_project.json" }
}
```

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

**MIDI:**
- Parsing euristico via `mido` — nessuna quantizzazione musicale avanzata
- Le posizioni forti/cadenze sono stime, non analisi metrica formale

**Lyrics / Mining:**
- Sillabe e rime = euristico basico (IT + EN)
- Stopwords solo EN e IT
- Nessun NLP avanzato (no POS, no NER)

**Line/Block Audit & Contextual Palette:**
- I punteggi 0–100 dell'audit sono **stime euristiche deterministiche**, non misure assolute
- Selezione via **click-to-select** riga/blocco (Streamlit non espone la selezione testuale live)
- Rhyme bank limitato (euristico, non dizionario completo)
- Cliche detector copre i pattern piu comuni, non esaustivo
- Imagery analyzer basato su keyword, non su comprensione semantica profonda

**Provider:**
- Musixmatch: **integrazione reale** via Analysis API (con `PROVIDER_MODE=real` + chiave); fallback mock automatico
- Cyanite: **integrazione reale** via GraphQL (con `CYANITE_MODE=graphql` + access token) — integrata nel **flusso principale** (Tab 1) con fallback mock automatico, oltre al pannello debug
- LLM: **OpenAI live** (`LLM_PROVIDER=openai` + `OPENAI_API_KEY`) per Writing Brief AI, Rephrase on melody e Metric Draft Scaffold; fallback euristico offline
- `related_artists` di Musixmatch è euristico per genere (l'API non espone un endpoint "related")

---

## Disclaimer

> This output is a structural similarity aid derived from final mixed audio only. It is not a legal proof of plagiarism or authorship.

> The system never generates, displays, or suggests copyrighted lyrics from other artists.

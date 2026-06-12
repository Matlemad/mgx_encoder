"""MIDI analysis for MGX Librettist.

Lightweight, heuristic MIDI parsing using `mido` (pure-Python). Designed to
fail softly: if `mido` is missing or a file cannot be parsed, the analyzer
returns a JSON-compatible dict with `warnings` instead of raising.

Two entry points:
- ``analyze_vocal_midi``   -> melodic topline analysis (syllable slots, phrases)
- ``analyze_backing_midi`` -> harmonic/backing analysis (pitch-class profile)
"""
from __future__ import annotations

from typing import Any

try:  # mido is optional; the app must keep running without it
    import mido  # type: ignore

    _MIDO_AVAILABLE = True
except Exception:  # pragma: no cover - import guard
    mido = None  # type: ignore
    _MIDO_AVAILABLE = False

_NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def _pitch_name(pitch: int) -> str:
    octave = pitch // 12 - 1
    return f"{_NOTE_NAMES[pitch % 12]}{octave}"


def _empty_vocal(warnings: list[str]) -> dict[str, Any]:
    return {
        "type": "vocal_melody",
        "n_notes": 0,
        "duration_sec": 0.0,
        "note_events": [],
        "phrase_estimates": [],
        "melodic_range": {},
        "average_note_duration": 0.0,
        "suggested_syllable_slots": 0,
        "strong_positions": [],
        "cadence_profile": "",
        "warnings": warnings,
    }


def _empty_backing(warnings: list[str]) -> dict[str, Any]:
    return {
        "type": "backing",
        "n_tracks": 0,
        "duration_sec": 0.0,
        "pitch_class_profile": [],
        "density_profile": [],
        "possible_chord_roots": [],
        "warnings": warnings,
    }


def _extract_note_events(midi) -> tuple[list[dict[str, Any]], float, float]:
    """Return (note_events sorted by start, duration_sec, ticks_per_beat-derived spb).

    Each event: {start, end, duration, pitch, velocity}. Times in seconds.
    """
    tempo = 500000  # default 120 BPM (microseconds per beat)
    tpb = midi.ticks_per_beat or 480
    events: list[dict[str, Any]] = []
    active: dict[int, tuple[float, int]] = {}

    abs_ticks = 0
    abs_seconds = 0.0
    # Merge all tracks into a single timeline of absolute seconds.
    for msg in mido.merge_tracks(midi.tracks):
        delta_ticks = msg.time
        abs_ticks += delta_ticks
        abs_seconds += mido.tick2second(delta_ticks, tpb, tempo)
        if msg.type == "set_tempo":
            tempo = msg.tempo
        elif msg.type == "note_on" and msg.velocity > 0:
            active[msg.note] = (abs_seconds, msg.velocity)
        elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
            start_vel = active.pop(msg.note, None)
            if start_vel is not None:
                start, vel = start_vel
                events.append(
                    {
                        "start": round(start, 4),
                        "end": round(abs_seconds, 4),
                        "duration": round(abs_seconds - start, 4),
                        "pitch": msg.note,
                        "pitch_name": _pitch_name(msg.note),
                        "velocity": vel,
                        "beat_position_estimate": None,
                    }
                )

    events.sort(key=lambda e: e["start"])
    duration = max((e["end"] for e in events), default=0.0)
    spb = tempo / 1_000_000.0
    return events, round(duration, 3), spb


def _estimate_phrases(events: list[dict[str, Any]], gap_factor: float = 1.8) -> list[dict[str, Any]]:
    """Group notes into phrases separated by unusually long rests."""
    if not events:
        return []
    gaps = []
    for prev, cur in zip(events, events[1:]):
        gaps.append(max(0.0, cur["start"] - prev["end"]))
    if gaps:
        sorted_gaps = sorted(gaps)
        median = sorted_gaps[len(sorted_gaps) // 2]
    else:
        median = 0.0
    threshold = max(0.4, median * gap_factor)

    phrases = []
    current = [events[0]]
    for prev, cur in zip(events, events[1:]):
        gap = cur["start"] - prev["end"]
        if gap > threshold:
            phrases.append(current)
            current = [cur]
        else:
            current.append(cur)
    phrases.append(current)

    return [
        {
            "index": i,
            "start": ph[0]["start"],
            "end": ph[-1]["end"],
            "n_notes": len(ph),
            "syllable_slots": len(ph),
        }
        for i, ph in enumerate(phrases)
    ]


def _cadence_profile(events: list[dict[str, Any]]) -> str:
    """Heuristic: descending/ascending/static based on last few notes."""
    if len(events) < 3:
        return "insufficient_data"
    tail = [e["pitch"] for e in events[-4:]]
    delta = tail[-1] - tail[0]
    if delta <= -2:
        return "descending (resolved/closing)"
    if delta >= 2:
        return "ascending (open/unresolved)"
    return "static (flat ending)"


def _strong_positions(events: list[dict[str, Any]], spb: float) -> list[float]:
    """Note starts that land near beat boundaries (heuristic strong beats)."""
    if spb <= 0:
        return []
    strong = []
    for e in events:
        beat_pos = e["start"] / spb
        frac = beat_pos - int(beat_pos)
        if frac < 0.12 or frac > 0.88:
            strong.append(round(e["start"], 3))
    return strong[:200]


def analyze_vocal_midi(path: str) -> dict[str, Any]:
    """Analyze a vocal/topline MIDI file into a syllable-aware summary."""
    if not _MIDO_AVAILABLE:
        return _empty_vocal(["mido not installed: run `pip install mido` to enable MIDI analysis."])
    try:
        midi = mido.MidiFile(path)
    except Exception as exc:  # noqa: BLE001
        return _empty_vocal([f"Could not parse vocal MIDI: {exc}"])

    events, duration, spb = _extract_note_events(midi)
    if not events:
        return _empty_vocal(["No note events found in vocal MIDI."])

    pitches = [e["pitch"] for e in events]
    durations = [e["duration"] for e in events]
    phrases = _estimate_phrases(events)
    avg_dur = round(sum(durations) / len(durations), 4) if durations else 0.0

    warnings: list[str] = []
    if len(events) > 5000:
        warnings.append("Very dense MIDI: this may be a backing track rather than a vocal line.")

    return {
        "type": "vocal_melody",
        "n_notes": len(events),
        "duration_sec": duration,
        "note_events": events[:1000],
        "phrase_estimates": phrases,
        "melodic_range": {
            "min_pitch": min(pitches),
            "max_pitch": max(pitches),
            "min_pitch_name": _pitch_name(min(pitches)),
            "max_pitch_name": _pitch_name(max(pitches)),
            "range_semitones": max(pitches) - min(pitches),
        },
        "average_note_duration": avg_dur,
        "suggested_syllable_slots": len(events),
        "strong_positions": _strong_positions(events, spb),
        "cadence_profile": _cadence_profile(events),
        "warnings": warnings,
    }


def analyze_backing_midi(path: str) -> dict[str, Any]:
    """Analyze a backing/harmony MIDI file into a pitch-class profile summary."""
    if not _MIDO_AVAILABLE:
        return _empty_backing(["mido not installed: run `pip install mido` to enable MIDI analysis."])
    try:
        midi = mido.MidiFile(path)
    except Exception as exc:  # noqa: BLE001
        return _empty_backing([f"Could not parse backing MIDI: {exc}"])

    events, duration, _spb = _extract_note_events(midi)
    if not events:
        return _empty_backing(["No note events found in backing MIDI."])

    pc_profile = [0.0] * 12
    for e in events:
        pc_profile[e["pitch"] % 12] += e["duration"]
    total = sum(pc_profile) or 1.0
    pc_norm = [round(v / total, 4) for v in pc_profile]

    # Density profile: notes per ~2-second window.
    window = 2.0
    n_windows = max(1, int(duration / window) + 1)
    density = [0] * n_windows
    for e in events:
        idx = min(n_windows - 1, int(e["start"] / window))
        density[idx] += 1

    ranked = sorted(range(12), key=lambda i: pc_norm[i], reverse=True)
    possible_roots = [_NOTE_NAMES[i] for i in ranked[:4] if pc_norm[i] > 0.0]

    return {
        "type": "backing",
        "n_tracks": len(midi.tracks),
        "duration_sec": duration,
        "pitch_class_profile": pc_norm,
        "density_profile": density,
        "possible_chord_roots": possible_roots,
        "warnings": [],
    }

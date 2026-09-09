"""
Сборка пака переговоров по рации и фонового эфира.

Выход: <out>/RussianRadio/{Male1,Male2,Female1,Female2,Chatter}/<id>_<n>.wav
плюс manifest.json с полной раскладкой (реплика, эмоция, роль, длительность).

Имена файлов совместимы с загрузчиком RussianRadioManager.GetOrLoadClips():
он ищет "<messageId>_*.wav", а при отсутствии — "<messageId>.wav".
Дополнительно раскладываются алиасы id, встречающиеся в разных сборках игры.
"""

from __future__ import annotations

import os
import time

from . import dsp
from .casting import RADIO_CAST, alt_of
from .emotions import get as get_emotion
from .parallel import default_jobs, get_backend, run_tasks
from .render import render_line
from .scripts_radio import ALIASES, CHATTER, SCRIPTS

ROLES = ("Male1", "Male2", "Female1", "Female2")


def _seed(*parts) -> int:
    h = 1469598103934665603
    for p in parts:
        for b in str(p).encode("utf-8"):
            h = ((h ^ b) * 1099511628211) & 0xFFFFFFFFFFFFFFFF
    return h & 0x7FFFFFFF


def _worker(task: dict) -> dict:
    """Синтез + обработка + запись одной реплики (выполняется в пуле процессов)."""
    tts = get_backend(task["backend"])
    emotion = get_emotion(task["emotion"])

    if task["kind"] == "chatter":
        profile = RADIO_CAST["Chatter"] if task["index"] % 2 == 1 else alt_of("Chatter")
        mode = "chatter"
    else:
        role = task["role"]
        profile = RADIO_CAST[role] if task["index"] % 2 == 1 else alt_of(role)
        mode = "radio"

    raw = tts.synth(task["text"], profile.tts_voice, rate=profile.rate,
                    pitch_semitones=profile.pitch_semitones,
                    style=emotion.style, style_degree=emotion.style_degree)
    clip = render_line(raw, profile, task["emotion"], task["seed"], mode=mode)

    written = []
    for path in task["paths"]:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if task["overwrite"] or not os.path.exists(path):
            dsp.write_wav(path, clip)
        written.append(path)

    return {
        "kind": task["kind"],
        "category": task["category"],
        "role": task["role"],
        "actor": profile.key,
        "index": task["index"],
        "text": task["text"],
        "emotion": task["emotion"],
        "duration": round(dsp.duration(clip), 3),
        "files": written,
        "label": f"{task['role']}/{task['category']}_{task['index']} "
                 f"({task['emotion']}, {dsp.duration(clip):.2f}с)",
    }


def build_radio(out_root: str, backend_name: str, only_role: str | None = None,
                only_category: str | None = None, limit: int | None = None,
                overwrite: bool = True, jobs: int | None = None,
                progress=print) -> dict:
    """Сгенерировать все реплики экипажей и фоновый эфир."""
    radio_root = os.path.join(out_root, "RussianRadio")
    jobs = jobs or default_jobs()

    tasks: list[dict] = []

    for category, per_role in SCRIPTS.items():
        if only_category and category != only_category:
            continue
        for role in ROLES:
            if only_role and only_role != role:
                continue
            for idx, (text, emotion) in enumerate(per_role.get(role) or [], start=1):
                role_dir = os.path.join(radio_root, role)
                paths = [os.path.join(role_dir, f"{alias}_{idx}.wav")
                         for alias in ALIASES.get(category, (category,))]
                tasks.append({
                    "kind": "radio", "category": category, "role": role,
                    "index": idx, "text": text, "emotion": emotion,
                    "paths": paths, "overwrite": overwrite,
                    "backend": backend_name,
                    "seed": _seed(category, role, idx, text),
                })

    if (not only_role or only_role == "Chatter") and (not only_category or only_category == "chatter"):
        chatter_dir = os.path.join(radio_root, "Chatter")
        for idx, (text, emotion) in enumerate(CHATTER, start=1):
            tasks.append({
                "kind": "chatter", "category": "chatter", "role": "Chatter",
                "index": idx, "text": text, "emotion": emotion,
                "paths": [os.path.join(chatter_dir, f"chatter_{idx}.wav")],
                "overwrite": overwrite, "backend": backend_name,
                "seed": _seed("chatter", idx, text),
            })

    if limit:
        tasks = tasks[:limit]

    progress(f"[Рация] К синтезу: {len(tasks)} реплик, потоков: {jobs}")
    t0 = time.time()
    results = run_tasks(_worker, tasks, jobs, progress)
    results = [r for r in results if r]

    for r in results:
        r.pop("label", None)
        r["files"] = [os.path.relpath(p, out_root) for p in r["files"]]

    return {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "backend": backend_name,
        "sample_rate": dsp.SR,
        "format": "WAV 16-bit PCM stereo 44100 Hz",
        "roles": {k: v.title for k, v in RADIO_CAST.items()},
        "count": len(results),
        "elapsed_sec": round(time.time() - t0, 1),
        "entries": results,
    }

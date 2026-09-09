"""
Параллельное выполнение задач синтеза.

DSP-обработка одной реплики занимает ~1-2 с, а реплик в паке больше шестисот,
поэтому сборка распараллеливается по процессам (GIL обойдён). Бэкенд TTS
создаётся лениво в каждом рабочем процессе — так сетевые сессии не разделяются
между процессами и не конфликтуют.
"""

from __future__ import annotations

import os
from concurrent.futures import ProcessPoolExecutor, as_completed

_BACKEND = None
_BACKEND_NAME = None


def get_backend(name: str):
    """Ленивая инициализация TTS-бэкенда внутри рабочего процесса."""
    global _BACKEND, _BACKEND_NAME
    if _BACKEND is None or _BACKEND_NAME != name:
        from .tts import select_backend
        _BACKEND = select_backend(name, verbose=False)
        _BACKEND_NAME = name
    return _BACKEND


def default_jobs() -> int:
    try:
        return max(1, min(8, (os.cpu_count() or 2)))
    except Exception:
        return 2


def run_tasks(worker, tasks: list, jobs: int, progress=print):
    """
    Выполнить задачи пулом процессов, сохраняя порядок результатов.
    При jobs <= 1 (или недоступном пуле) выполняется последовательно.
    """
    results: list = [None] * len(tasks)
    if jobs <= 1 or len(tasks) <= 1:
        for i, t in enumerate(tasks):
            results[i] = worker(t)
            _report(progress, i + 1, len(tasks), results[i])
        return results

    try:
        with ProcessPoolExecutor(max_workers=jobs) as pool:
            futures = {pool.submit(worker, t): i for i, t in enumerate(tasks)}
            done = 0
            for fut in as_completed(futures):
                i = futures[fut]
                results[i] = fut.result()
                done += 1
                _report(progress, done, len(tasks), results[i])
        return results
    except Exception as ex:
        progress(f"[!] Параллельный режим недоступен ({ex}), "
                 f"переключаюсь на последовательный.")
        for i, t in enumerate(tasks):
            if results[i] is None:
                results[i] = worker(t)
                _report(progress, i + 1, len(tasks), results[i])
        return results


def _report(progress, done: int, total: int, result) -> None:
    if not progress:
        return
    label = ""
    if isinstance(result, dict):
        label = result.get("label") or ""
    progress(f"  [{done}/{total}] {label}")

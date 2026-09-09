"""
Проверка качества и целостности собранного пака.

Проверяется не только «файл существует», но и то, что важно на слух:
  * формат (44.1 кГц, 16 бит, стерео) — иначе движок мода не загрузит клип;
  * отсутствие клиппинга и «мёртвых» (тихих/пустых) файлов;
  * разброс громкости между репликами (скачки уровня в эфире режут ухо);
  * адекватная длительность (обрубленные или зависшие клипы);
  * покрытие: все ли роли и категории озвучены, нет ли дыр в раскладке.
"""

from __future__ import annotations

import json
import math
import os
import wave

from . import dsp

ROLES = ("Male1", "Male2", "Female1", "Female2", "Chatter")


def _scan_wav(path: str) -> dict | None:
    try:
        with wave.open(path, "rb") as w:
            ch, sw, sr, n = (w.getnchannels(), w.getsampwidth(),
                             w.getframerate(), w.getnframes())
            frames = w.readframes(min(n, sr * 30))
    except Exception:
        return None

    import array
    if sw != 2:
        return {"path": path, "channels": ch, "rate": sr, "bits": sw * 8,
                "dur": n / max(sr, 1), "peak": 0.0, "rms_db": -120.0,
                "clipped": 0}

    data = array.array("h")
    data.frombytes(frames)
    if not len(data):
        return {"path": path, "channels": ch, "rate": sr, "bits": 16,
                "dur": 0.0, "peak": 0.0, "rms_db": -120.0, "clipped": 0}

    peak = 0
    acc = 0.0
    clipped = 0
    for s in data:
        a = abs(s)
        if a > peak:
            peak = a
        if a >= 32700:
            clipped += 1
        acc += float(s) * s
    rms = math.sqrt(acc / len(data)) / 32768.0
    return {
        "path": path, "channels": ch, "rate": sr, "bits": sw * 8,
        "dur": n / max(sr, 1), "peak": peak / 32768.0,
        "rms_db": 20 * math.log10(max(rms, 1e-9)), "clipped": clipped,
    }


def verify_pack(out_root: str, game_dir: str | None = None) -> bool:
    print("=" * 62)
    print(" ПРОВЕРКА РУССКОГО ЗВУКОВОГО ПАКА 112 OPERATOR")
    print("=" * 62)

    problems: list[str] = []
    warnings: list[str] = []

    radio_root = os.path.join(out_root, "RussianRadio")
    calls_root = os.path.join(out_root, "RussianCalls")

    # --- 1. Рация
    print("\n1. Переговоры по рации")
    all_stats = []
    if not os.path.isdir(radio_root):
        problems.append(f"Отсутствует каталог рации: {radio_root}")
        print("   [!] Каталог не найден")
    else:
        for role in ROLES:
            d = os.path.join(radio_root, role)
            if not os.path.isdir(d):
                # Chatter — необязательный фоновый эфир; остальные роли обязательны
                if role == "Chatter":
                    warnings.append("Нет папки роли: Chatter (фоновый эфир не собран)")
                    print(f"   [~] {role}: папка отсутствует")
                else:
                    problems.append(f"Нет папки роли: {role}")
                    print(f"   [!] {role}: папка отсутствует")
                continue
            files = sorted(f for f in os.listdir(d) if f.endswith(".wav"))
            stats = [s for s in (_scan_wav(os.path.join(d, f)) for f in files) if s]
            all_stats.extend(stats)
            if not files:
                problems.append(f"Роль {role} не содержит файлов")
            durs = [s["dur"] for s in stats] or [0]
            print(f"   {role}: {len(files)} файлов, "
                  f"длительность {min(durs):.2f}–{max(durs):.2f} с")

    # --- 2. Звонки
    print("\n2. Экстренные вызовы 112")
    if not os.path.isdir(calls_root):
        warnings.append("Каталог звонков отсутствует (нужны исходники игры)")
        print("   [~] Не собрано (требуются StreamingAssets игры)")
    else:
        call_dirs = sorted(d for d in os.listdir(calls_root)
                           if os.path.isdir(os.path.join(calls_root, d)))
        total = 0
        for cd in call_dirs:
            p = os.path.join(calls_root, cd)
            fs = [f for f in os.listdir(p) if f.endswith(".wav")]
            total += len(fs)
            for f in fs[:400]:
                s = _scan_wav(os.path.join(p, f))
                if s:
                    all_stats.append(s)
        print(f"   Вызовов: {len(call_dirs)}, реплик: {total}")

    # --- 3. Технические характеристики
    print("\n3. Технический контроль")
    if not all_stats:
        problems.append("Не найдено ни одного WAV-файла")
    else:
        bad_fmt = [s for s in all_stats if s["rate"] != 44100 or s["bits"] != 16
                   or s["channels"] != 2]
        clipped = [s for s in all_stats if s["clipped"] > 40]
        silent = [s for s in all_stats if s["rms_db"] < -60.0 and s["dur"] > 0.4]
        tiny = [s for s in all_stats if s["dur"] < 0.25]
        huge = [s for s in all_stats if s["dur"] > 25.0]

        levels = [s["rms_db"] for s in all_stats if s["rms_db"] > -60]
        spread = (max(levels) - min(levels)) if levels else 0.0
        avg = sum(levels) / len(levels) if levels else -120

        print(f"   Всего файлов: {len(all_stats)}")
        print(f"   Средний уровень: {avg:.1f} dBFS, разброс: {spread:.1f} дБ")
        print(f"   Формат 44.1/16/стерео: {len(all_stats) - len(bad_fmt)}/{len(all_stats)}")

        if bad_fmt:
            problems.append(f"Неверный формат у {len(bad_fmt)} файлов "
                            f"(пример: {os.path.basename(bad_fmt[0]['path'])})")
        if clipped:
            problems.append(f"Клиппинг в {len(clipped)} файлах "
                            f"(пример: {os.path.basename(clipped[0]['path'])})")
        if silent:
            problems.append(f"Пустые/тихие клипы: {len(silent)} "
                            f"(пример: {os.path.basename(silent[0]['path'])})")
        if tiny:
            warnings.append(f"Очень короткие клипы (<0.25 с): {len(tiny)}")
        if huge:
            warnings.append(f"Очень длинные клипы (>25 с): {len(huge)}")
        if spread > 14.0:
            warnings.append(f"Большой разброс громкости: {spread:.1f} дБ "
                            "— в эфире будут скачки уровня")

    # --- 4. Манифесты
    print("\n4. Манифесты")
    for name in ("russian_radio_manifest.json", "russian_calls_manifest.json"):
        p = os.path.join(out_root, name)
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                m = json.load(f)
            print(f"   {name}: {m.get('count', '?')} записей, "
                  f"движок TTS: {m.get('backend', '?')}")
            if m.get("backend") == "stub":
                warnings.append("Пак собран процедурным стендом (stub) — "
                                "это не релизное качество речи, "
                                "пересоберите с --backend edge/piper/silero")
        else:
            warnings.append(f"Нет манифеста {name}")

    # --- 5. Интеграция с игрой
    if game_dir:
        print("\n5. Интеграция с игрой")
        gd = os.path.join(game_dir, "Operator 112_Data")
        dll = os.path.join(gd, "Managed", "RussianRadioMod.dll")
        print(f"   RussianRadioMod.dll: {'установлен' if os.path.exists(dll) else 'НЕ установлен'}")
        for name in ("ScriptingAssemblies.json", "RuntimeInitializeOnLoads.json"):
            p = os.path.join(gd, name)
            ok = False
            if os.path.exists(p):
                with open(p, encoding="utf-8") as f:
                    ok = "RussianRadioMod" in f.read()
            print(f"   {name}: {'мод зарегистрирован' if ok else 'запись отсутствует'}")

    # --- Итог
    print("\n" + "=" * 62)
    for w in warnings:
        print(f" [~] {w}")
    for p in problems:
        print(f" [!] {p}")
    if not problems:
        print(" РЕЗУЛЬТАТ: пак корректен и готов к установке.")
    else:
        print(f" РЕЗУЛЬТАТ: обнаружено проблем — {len(problems)}.")
    print("=" * 62)
    return not problems

"""
Командный интерфейс сборки русской озвучки.

Примеры:
    # Всё сразу прямо в установленную игру
    python3 -m voicepack all --game "/путь/к/112 Operator"

    # Только рация, в локальную папку build/
    python3 -m voicepack radio --out build

    # Демо-нарезка: по одной реплике на роль, чтобы послушать качество
    python3 -m voicepack demo --out build/demo

    # Проверить, что получилось
    python3 -m voicepack verify --out build
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time

from . import dsp
from .parallel import default_jobs
from .tts import select_backend


DEFAULT_GAME_DIRS = [
    os.path.expanduser("~/.steam/steam/steamapps/common/112 Operator"),
    os.path.expanduser("~/.local/share/Steam/steamapps/common/112 Operator"),
    os.path.expanduser("~/.var/app/com.valvesoftware.Steam/data/Steam/steamapps/common/112 Operator"),
    os.path.expanduser("~/Library/Application Support/Steam/steamapps/common/112 Operator"),
    "C:/Program Files (x86)/Steam/steamapps/common/112 Operator",
    "/home/astra/vint2/gamez/steamapps/common/112 Operator",
]


def find_game(explicit: str | None) -> str | None:
    cands = ([explicit] if explicit else []) + list(DEFAULT_GAME_DIRS)
    for vdf in (
        os.path.expanduser("~/.steam/steam/steamapps/libraryfolders.vdf"),
        os.path.expanduser("~/.local/share/Steam/steamapps/libraryfolders.vdf"),
        os.path.expanduser("~/.var/app/com.valvesoftware.Steam/data/Steam/steamapps/libraryfolders.vdf"),
    ):
        if os.path.isfile(vdf):
            try:
                with open(vdf, "r", encoding="utf-8", errors="ignore") as f:
                    for m in re.finditer(r'"path"\s+"([^"]+)"', f.read()):
                        cands.append(os.path.join(m.group(1), "steamapps", "common", "112 Operator"))
            except Exception:
                pass
    for c in cands:
        if c and os.path.isdir(os.path.join(c, "Operator 112_Data")):
            return c
    return None


def streaming_assets_of(game_dir: str) -> str:
    return os.path.join(game_dir, "Operator 112_Data", "StreamingAssets")


def resolve_out(args) -> str:
    if args.out:
        return os.path.abspath(args.out)
    game = find_game(args.game)
    if game:
        return os.path.join(streaming_assets_of(game), "Audio")
    return os.path.abspath("build")


def save_manifest(out_root: str, name: str, data: dict) -> str:
    os.makedirs(out_root, exist_ok=True)
    path = os.path.join(out_root, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


# ---------------------------------------------------------------------------
# Команды
# ---------------------------------------------------------------------------

def cmd_radio(args):
    from .build_radio import build_radio

    out_root = resolve_out(args)
    backend = select_backend(args.backend).name
    print(f"[Рация] Каталог сборки: {out_root}")
    manifest = build_radio(out_root, backend, only_role=args.role,
                           only_category=args.category, limit=args.limit,
                           overwrite=not args.keep, jobs=args.jobs)
    p = save_manifest(out_root, "russian_radio_manifest.json", manifest)
    print(f"[Рация] Готово: {manifest['count']} реплик за {manifest['elapsed_sec']} с")
    print(f"[Рация] Манифест: {p}")
    return 0


def cmd_calls(args):
    from .build_calls import build_calls

    game = find_game(args.game)
    if not game and not args.streaming_assets:
        print("Ошибка: не найдена установленная игра. Укажите --game "
              "\"/путь/к/112 Operator\" или --streaming-assets.", file=sys.stderr)
        return 2
    sa = args.streaming_assets or streaming_assets_of(game)
    out_root = resolve_out(args)
    backend = select_backend(args.backend).name

    print(f"[Звонки] StreamingAssets: {sa}")
    print(f"[Звонки] Каталог сборки: {out_root}")
    manifest = build_calls(out_root, backend, sa, only_calls=args.call,
                           limit=args.limit, operator_voice=args.operator_voice,
                           overwrite=not args.keep, jobs=args.jobs)
    p = save_manifest(out_root, "russian_calls_manifest.json", manifest)
    print(f"[Звонки] Готово: {manifest['count']} реплик за {manifest['elapsed_sec']} с")
    print(f"[Звонки] Манифест: {p}")
    return 0


def cmd_all(args):
    rc = cmd_radio(args)
    if rc:
        return rc
    game = find_game(args.game)
    if not game and not args.streaming_assets:
        print("[Звонки] Пропущено: игра не найдена (нужны исходные тексты и XML).")
        return 0
    return cmd_calls(args)


def cmd_demo(args):
    """Короткая демо-нарезка: по одной яркой реплике каждой роли и эмоции."""
    from .build_radio import _seed
    from .casting import RADIO_CAST, caller_profile, OPERATOR_PROFILE
    from .render import render_line
    from .scripts_radio import SCRIPTS

    out_root = resolve_out(args)
    demo_dir = os.path.join(out_root, "Demo")
    os.makedirs(demo_dir, exist_ok=True)
    tts = select_backend(args.backend)

    picks = [
        ("Male1", "go", 0), ("Male1", "officerDown", 0),
        ("Male2", "underfire", 0), ("Male2", "chaseStarted", 0),
        ("Female1", "callAllUnits", 0), ("Female2", "officerDown", 0),
        ("Female2", "attacked", 0), ("Male2", "whyWeCameHere", 0),
    ]
    made = []
    for role, cat, i in picks:
        lines = SCRIPTS.get(cat, {}).get(role)
        if not lines:
            continue
        text, emotion = lines[i]
        profile = RADIO_CAST[role]
        raw = tts.synth(text, profile.tts_voice, rate=profile.rate,
                        pitch_semitones=profile.pitch_semitones)
        clip = render_line(raw, profile, emotion, _seed(cat, role, i), mode="radio")
        path = os.path.join(demo_dir, f"radio_{role}_{cat}.wav")
        dsp.write_wav(path, clip)
        made.append(path)
        print(f"  {os.path.basename(path)}  ({emotion}, {dsp.duration(clip):.2f}с)")

    # Демо звонка: оператор + звонящая в панике
    op_text = "Служба сто двенадцать, оператор Никитин. Что у вас случилось?"
    raw = tts.synth(op_text, OPERATOR_PROFILE.tts_voice, rate=1.0)
    clip = render_line(raw, OPERATOR_PROFILE, "calm", 1, mode="headset")
    dsp.write_wav(os.path.join(demo_dir, "call_operator.wav"), clip)
    print(f"  call_operator.wav ({dsp.duration(clip):.2f}с)")

    caller_text = ("Пожалуйста, помогите! Тут авария, машина перевернулась, "
                   "внутри человек, он не отвечает!")
    cp = caller_profile("FEMALE", 0)
    raw = tts.synth(caller_text, cp.tts_voice, rate=cp.rate,
                    pitch_semitones=cp.pitch_semitones)
    clip = render_line(raw, cp, "panic", 2, mode="phone", ambience="street")
    dsp.write_wav(os.path.join(demo_dir, "call_caller_panic.wav"), clip)
    print(f"  call_caller_panic.wav ({dsp.duration(clip):.2f}с)")

    print(f"\n[Демо] Файлы: {demo_dir}")
    return 0


def cmd_verify(args):
    from .verify import verify_pack
    out_root = resolve_out(args)
    ok = verify_pack(out_root, game_dir=find_game(args.game))
    return 0 if ok else 1


def cmd_install(args):
    from .install import install_pack
    game = find_game(args.game)
    if not game:
        print("Ошибка: не найдена установленная игра. Укажите --game.", file=sys.stderr)
        return 2
    src = os.path.abspath(args.out or "build")
    return 0 if install_pack(src, game) else 1


# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="voicepack",
        description="Кинематографическая русская озвучка для 112 Operator",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("--out", help="Каталог сборки (по умолчанию — в игру, "
                                      "иначе ./build)")
        sp.add_argument("--game", help="Путь к каталогу игры '112 Operator'")
        sp.add_argument("--streaming-assets", help="Прямой путь к StreamingAssets")
        sp.add_argument("--backend", default="auto",
                        choices=("auto", "edge", "piper", "silero", "espeak", "stub"),
                        help="Движок синтеза речи")
        sp.add_argument("--limit", type=int, help="Ограничить число реплик (отладка)")
        sp.add_argument("--keep", action="store_true",
                        help="Не перезаписывать уже существующие файлы")
        sp.add_argument("--operator-voice", default="male", choices=("male", "female"),
                        help="Пол оператора 112")
        sp.add_argument("--jobs", type=int, default=default_jobs(),
                        help=f"Число параллельных процессов "
                             f"(по умолчанию {default_jobs()})")

    sp = sub.add_parser("radio", help="Собрать переговоры по рации и фоновый эфир")
    common(sp)
    sp.add_argument("--role", choices=("Male1", "Male2", "Female1", "Female2", "Chatter"))
    sp.add_argument("--category", help="Только одна категория реплик")
    sp.set_defaults(func=cmd_radio)

    sp = sub.add_parser("calls", help="Собрать озвучку вызовов 112")
    common(sp)
    sp.add_argument("--call", action="append", help="Только указанные id вызовов")
    sp.set_defaults(func=cmd_calls)

    sp = sub.add_parser("all", help="Собрать всё: рацию и звонки")
    common(sp)
    sp.add_argument("--role", default=None, help=argparse.SUPPRESS)
    sp.add_argument("--category", default=None, help=argparse.SUPPRESS)
    sp.add_argument("--call", action="append", help=argparse.SUPPRESS)
    sp.set_defaults(func=cmd_all)

    sp = sub.add_parser("demo", help="Короткая демо-нарезка для прослушивания")
    common(sp)
    sp.set_defaults(func=cmd_demo)

    sp = sub.add_parser("verify", help="Проверить целостность и качество пака")
    common(sp)
    sp.set_defaults(func=cmd_verify)

    sp = sub.add_parser("install", help="Установить собранный пак в игру")
    common(sp)
    sp.set_defaults(func=cmd_install)

    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

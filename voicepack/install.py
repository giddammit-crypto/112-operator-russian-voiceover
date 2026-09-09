"""
Установка собранного пака в игру и регистрация мода в движке Unity.

Все изменяемые файлы игры бэкапятся один раз в *.original — установку
всегда можно откатить (см. uninstall_pack).
"""

from __future__ import annotations

import json
import os
import shutil


MOD_ENTRY = {
    "assemblyName": "RussianRadioMod",
    "nameSpace": "RussianRadioMod",
    "className": "RussianRadioManager",
    "methodName": "OnGameStart",
    "loadTypes": 1,
    "isUnityClass": False,
}


def _backup_once(path: str) -> None:
    bak = path + ".original"
    if os.path.exists(path) and not os.path.exists(bak):
        shutil.copyfile(path, bak)
        print(f"   Резервная копия: {os.path.basename(bak)}")


def copy_audio(src_root: str, game_dir: str) -> int:
    """Скопировать RussianRadio/ и RussianCalls/ в StreamingAssets/Audio."""
    dst_root = os.path.join(game_dir, "Operator 112_Data", "StreamingAssets", "Audio")
    copied = 0
    for sub in ("RussianRadio", "RussianCalls"):
        s = os.path.join(src_root, sub)
        if not os.path.isdir(s):
            continue
        d = os.path.join(dst_root, sub)
        for root, _dirs, files in os.walk(s):
            rel = os.path.relpath(root, s)
            target = os.path.join(d, rel) if rel != "." else d
            os.makedirs(target, exist_ok=True)
            for f in files:
                if f.endswith(".wav"):
                    shutil.copyfile(os.path.join(root, f), os.path.join(target, f))
                    copied += 1
        print(f"   {sub}: скопировано в {d}")
    return copied


def register_assembly(game_dir: str, dll_path: str | None = None) -> bool:
    """Прописать сборку мода в ScriptingAssemblies и RuntimeInitializeOnLoads."""
    gd = os.path.join(game_dir, "Operator 112_Data")
    managed = os.path.join(gd, "Managed")

    if dll_path and os.path.isfile(dll_path):
        os.makedirs(managed, exist_ok=True)
        shutil.copyfile(dll_path, os.path.join(managed, "RussianRadioMod.dll"))
        print("   RussianRadioMod.dll установлен в Managed/")

    sa = os.path.join(gd, "ScriptingAssemblies.json")
    if os.path.exists(sa):
        _backup_once(sa)
        with open(sa, encoding="utf-8") as f:
            data = json.load(f)
        if "RussianRadioMod.dll" not in data.get("names", []):
            data["names"].append("RussianRadioMod.dll")
            data.setdefault("types", []).append(16)
            with open(sa, "w", encoding="utf-8") as f:
                json.dump(data, f, separators=(",", ":"))
            print("   Сборка добавлена в ScriptingAssemblies.json")
        else:
            print("   ScriptingAssemblies.json: запись уже есть")

    rt = os.path.join(gd, "RuntimeInitializeOnLoads.json")
    if os.path.exists(rt):
        _backup_once(rt)
        with open(rt, encoding="utf-8") as f:
            data = json.load(f)
        root = data.setdefault("root", [])
        if not any(x.get("assemblyName") == "RussianRadioMod" for x in root):
            root.append(dict(MOD_ENTRY))
            with open(rt, "w", encoding="utf-8") as f:
                json.dump(data, f, separators=(",", ":"))
            print("   Точка входа добавлена в RuntimeInitializeOnLoads.json")
        else:
            print("   RuntimeInitializeOnLoads.json: запись уже есть")
    return True


def install_mod_profile(repo_root: str, game_dir: str) -> None:
    """Скопировать профиль мода, чтобы он появился в меню «Моды»."""
    src = os.path.join(repo_root, "MyMods", "RussianRadioVoiceover")
    if not os.path.isdir(src):
        return
    targets = [
        os.path.join(game_dir, "MyMods", "RussianRadioVoiceover"),
        os.path.join(game_dir, "..", "..", "compatdata", "793460", "pfx", "drive_c",
                     "users", "steamuser", "AppData", "LocalLow", "JutsuGames",
                     "112 Operator", "MyMods", "RussianRadioVoiceover"),
        os.path.expanduser("~/AppData/LocalLow/JutsuGames/112 Operator/MyMods/"
                           "RussianRadioVoiceover"),
    ]
    for t in targets:
        parent = os.path.dirname(os.path.abspath(t))
        if not os.path.isdir(os.path.dirname(parent)):
            continue
        try:
            os.makedirs(t, exist_ok=True)
            for f in os.listdir(src):
                sp = os.path.join(src, f)
                if os.path.isfile(sp):
                    shutil.copyfile(sp, os.path.join(t, f))
            print(f"   Профиль мода: {os.path.abspath(t)}")
        except OSError:
            continue


def install_pack(src_root: str, game_dir: str, dll_path: str | None = None) -> bool:
    print("=" * 62)
    print(" УСТАНОВКА РУССКОЙ ОЗВУЧКИ В 112 OPERATOR")
    print("=" * 62)
    print(f" Игра: {game_dir}")
    print(f" Пак:  {src_root}\n")

    if not os.path.isdir(os.path.join(game_dir, "Operator 112_Data")):
        print(" [!] Это не каталог игры 112 Operator.")
        return False

    print("1. Копирование аудио")
    n = copy_audio(src_root, game_dir)
    print(f"   Всего файлов: {n}")

    print("\n2. Регистрация сборки мода")
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if dll_path is None:
        cand = os.path.join(repo_root, "RussianRadioMod", "bin", "Release",
                            "netstandard2.1", "RussianRadioMod.dll")
        dll_path = cand if os.path.isfile(cand) else None
    if dll_path is None:
        print("   [~] DLL не собрана — соберите: "
              "dotnet build RussianRadioMod/RussianRadioMod.csproj -c Release")
    register_assembly(game_dir, dll_path)

    print("\n3. Профиль мода для меню «Моды»")
    install_mod_profile(repo_root, game_dir)

    print("\n" + "=" * 62)
    print(" Установка завершена. Запустите игру и включите мод")
    print(" «Russian Radio Voiceover» в меню «Моды».")
    print("=" * 62)
    return True


def uninstall_pack(game_dir: str) -> bool:
    """Откат: восстановить *.original и удалить аудио мода."""
    gd = os.path.join(game_dir, "Operator 112_Data")
    for name in ("ScriptingAssemblies.json", "RuntimeInitializeOnLoads.json"):
        p = os.path.join(gd, name)
        bak = p + ".original"
        if os.path.exists(bak):
            shutil.copyfile(bak, p)
            print(f" Восстановлен {name}")
    dll = os.path.join(gd, "Managed", "RussianRadioMod.dll")
    if os.path.exists(dll):
        os.remove(dll)
        print(" Удалён RussianRadioMod.dll")
    for sub in ("RussianRadio", "RussianCalls"):
        d = os.path.join(gd, "StreamingAssets", "Audio", sub)
        if os.path.isdir(d):
            shutil.rmtree(d)
            print(f" Удалён каталог {sub}")
    return True

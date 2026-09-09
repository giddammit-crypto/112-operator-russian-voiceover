import json
import os
import shutil

game_data = "/home/astra/vint2/gamez/steamapps/common/112 Operator/Operator 112_Data"
mod_dll_src = "/home/astra/.gemini/antigravity/scratch/operator112_russian_voice_mod/RussianRadioMod/bin/Release/netstandard2.1/RussianRadioMod.dll"
mod_dll_dst = os.path.join(game_data, "Managed", "RussianRadioMod.dll")

# 1. Copy DLL
shutil.copyfile(mod_dll_src, mod_dll_dst)
print(f"Copied {mod_dll_dst} ({os.path.getsize(mod_dll_dst)} bytes)")

# 2. Update ScriptingAssemblies.json
sa_path = os.path.join(game_data, "ScriptingAssemblies.json")
sa_bak = sa_path + ".original"
if not os.path.exists(sa_bak):
    shutil.copyfile(sa_path, sa_bak)
    print("Backed up ScriptingAssemblies.json")

with open(sa_path, "r", encoding="utf-8") as f:
    sa_data = json.load(f)

if "RussianRadioMod.dll" not in sa_data["names"]:
    sa_data["names"].append("RussianRadioMod.dll")
    sa_data["types"].append(16)
    with open(sa_path, "w", encoding="utf-8") as f:
        json.dump(sa_data, f, separators=(',', ':'))
    print("Added RussianRadioMod.dll to ScriptingAssemblies.json")
else:
    print("RussianRadioMod.dll already in ScriptingAssemblies.json")

# 3. Update RuntimeInitializeOnLoads.json
rt_path = os.path.join(game_data, "RuntimeInitializeOnLoads.json")
rt_bak = rt_path + ".original"
if not os.path.exists(rt_bak):
    shutil.copyfile(rt_path, rt_bak)
    print("Backed up RuntimeInitializeOnLoads.json")

with open(rt_path, "r", encoding="utf-8") as f:
    rt_data = json.load(f)

has_entry = any(x.get("assemblyName") == "RussianRadioMod" for x in rt_data["root"])
if not has_entry:
    rt_data["root"].append({
        "assemblyName": "RussianRadioMod",
        "nameSpace": "RussianRadioMod",
        "className": "RussianRadioManager",
        "methodName": "OnGameStart",
        "loadTypes": 1,
        "isUnityClass": False
    })
    with open(rt_path, "w", encoding="utf-8") as f:
        json.dump(rt_data, f, separators=(',', ':'))
    print("Added RussianRadioManager.OnGameStart to RuntimeInitializeOnLoads.json")
else:
    print("RuntimeInitializeOnLoads entry already exists")

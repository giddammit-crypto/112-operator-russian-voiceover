import os
import sys
import wave
import json

GAME_DATA = "/home/astra/vint2/gamez/steamapps/common/112 Operator/Operator 112_Data"
STREAMING_ASSETS = os.path.join(GAME_DATA, "StreamingAssets")
RADIO_DIR = os.path.join(STREAMING_ASSETS, "Audio", "RussianRadio")
CALLS_DIR = os.path.join(STREAMING_ASSETS, "Audio", "RussianCalls")

print("=== VERIFYING RUSSIAN VOICE MOD (RADIO & CALLS) ===\n")

# 1. Radio Files Verification
print("1. Checking Radio Files:")
radio_folders = ["Male1", "Male2", "Female1", "Female2", "Chatter"]
total_radio_files = 0
for rf in radio_folders:
    dir_path = os.path.join(RADIO_DIR, rf)
    if os.path.exists(dir_path):
        files = [f for f in os.listdir(dir_path) if f.endswith(".wav")]
        print(f"   - {rf}: {len(files)} wav files")
        total_radio_files += len(files)
        # Check first file
        if files:
            sample_f = os.path.join(dir_path, files[0])
            with wave.open(sample_f, 'rb') as w:
                print(f"     Sample ({files[0]}): {w.getnchannels()} ch, {w.getframerate()} Hz, {w.getsampwidth()*8} bit, {w.getnframes()/w.getframerate():.2f}s")
    else:
        print(f"   [!] Missing folder: {rf}")

print(f"Total Radio Files: {total_radio_files}\n")

# 2. Calls Files Verification
print("2. Checking Emergency Calls:")
if os.path.exists(CALLS_DIR):
    call_dirs = [d for d in os.listdir(CALLS_DIR) if os.path.isdir(os.path.join(CALLS_DIR, d))]
    total_call_files = 0
    for cd in call_dirs:
        c_path = os.path.join(CALLS_DIR, cd)
        w_files = [f for f in os.listdir(c_path) if f.endswith(".wav")]
        total_call_files += len(w_files)
    print(f"   - Generated calls count: {len(call_dirs)} distinct calls")
    print(f"   - Total dialogue audio clips: {total_call_files} wav files")
    
    # Check sample call
    if "c_car_crash" in call_dirs:
        crash_path = os.path.join(CALLS_DIR, "c_car_crash")
        crash_files = [f for f in os.listdir(crash_path) if f.endswith(".wav")]
        print(f"   - c_car_crash: {len(crash_files)} lines (Operator & Caller)")
        with wave.open(os.path.join(crash_path, "1.wav"), 'rb') as w:
            print(f"     Operator (1.wav): {w.getnchannels()} ch, {w.getframerate()} Hz, {w.getsampwidth()*8} bit, {w.getnframes()/w.getframerate():.2f}s")
        with wave.open(os.path.join(crash_path, "2.wav"), 'rb') as w:
            print(f"     Caller (2.wav): {w.getnchannels()} ch, {w.getframerate()} Hz, {w.getsampwidth()*8} bit, {w.getnframes()/w.getframerate():.2f}s")
else:
    print("   [!] Calls directory not found!")

# 3. DLL and IL Hook Verification
print("\n3. Checking Engine Integration:")
mod_dll = os.path.join(GAME_DATA, "Managed", "RussianRadioMod.dll")
print(f"   - RussianRadioMod.dll exists: {os.path.exists(mod_dll)} ({os.path.getsize(mod_dll)} bytes)")

sa_path = os.path.join(GAME_DATA, "ScriptingAssemblies.json")
with open(sa_path, "r", encoding="utf-8") as f:
    sa_data = json.load(f)
print(f"   - In ScriptingAssemblies.json: {'RussianRadioMod.dll' in sa_data.get('names', [])}")

rt_path = os.path.join(GAME_DATA, "RuntimeInitializeOnLoads.json")
with open(rt_path, "r", encoding="utf-8") as f:
    rt_data = json.load(f)
has_rt = any(x.get("assemblyName") == "RussianRadioMod" for x in rt_data.get("root", []))
print(f"   - In RuntimeInitializeOnLoads.json: {has_rt}")

# 4. In-Game Mod Directory
print("\n4. Checking In-Game Mod UI Visibility:")
mod_paths = [
    "/home/astra/vint2/gamez/steamapps/compatdata/793460/pfx/drive_c/users/steamuser/AppData/LocalLow/JutsuGames/112 Operator/MyMods/RussianRadioVoiceover",
    os.path.join(GAME_DATA, "..", "MyMods", "RussianRadioVoiceover")
]
for mp in mod_paths:
    cfg = os.path.join(mp, "config.json")
    img = os.path.join(mp, "preview.png")
    print(f"   - Mod at '{os.path.basename(os.path.dirname(mp))}/{os.path.basename(mp)}':")
    print(f"     config.json: {os.path.exists(cfg)}, preview.png: {os.path.exists(img)}")

print("\n=== VERIFICATION COMPLETE! ===")

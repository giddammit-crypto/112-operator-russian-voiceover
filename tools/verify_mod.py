import os
import struct

game_dir = "/home/astra/vint2/gamez/steamapps/common/112 Operator"
game_data = os.path.join(game_dir, "Operator 112_Data")
audio_dir = os.path.join(game_data, "StreamingAssets", "Audio", "RussianRadio")
managed_dir = os.path.join(game_data, "Managed")

print("=== VERIFYING RUSSIAN RADIO MOD ===")

# 1. Check Mod DLLs
mod_dll = os.path.join(managed_dir, "RussianRadioMod.dll")
main_dll = os.path.join(managed_dir, "Main.dll")
main_bak = os.path.join(managed_dir, "Main.dll.original")

assert os.path.exists(mod_dll), "RussianRadioMod.dll missing!"
assert os.path.exists(main_dll), "Main.dll missing!"
assert os.path.exists(main_bak), "Main.dll.original missing!"
print(f"[OK] Assemblies exist: RussianRadioMod.dll ({os.path.getsize(mod_dll)} bytes), Main.dll backup intact.")

# 2. Check JSON configs
rt_json = os.path.join(game_data, "RuntimeInitializeOnLoads.json")
sa_json = os.path.join(game_data, "ScriptingAssemblies.json")
with open(rt_json, "r", encoding="utf-8") as f:
    rt_content = f.read()
    assert "RussianRadioMod" in rt_content, "RussianRadioMod not in RuntimeInitializeOnLoads.json"
with open(sa_json, "r", encoding="utf-8") as f:
    sa_content = f.read()
    assert "RussianRadioMod.dll" in sa_content, "RussianRadioMod.dll not in ScriptingAssemblies.json"
print("[OK] Unity engine JSON manifests correctly configured.")

# 3. Check and validate all WAV files
folders = ["Male1", "Male2", "Female1", "Female2", "Chatter"]
total_checked = 0
total_duration = 0.0

for folder in folders:
    fpath = os.path.join(audio_dir, folder)
    assert os.path.exists(fpath), f"Folder missing: {folder}"
    wav_files = [f for f in os.listdir(fpath) if f.endswith(".wav")]
    print(f"[INFO] Folder {folder}: {len(wav_files)} WAV files found.")
    assert len(wav_files) > 0, f"No files in {folder}!"
    
    for w in wav_files:
        full_p = os.path.join(fpath, w)
        with open(full_p, "rb") as f:
            header = f.read(44)
            riff = header[:4]
            wave = header[8:12]
            fmt = header[12:16]
            assert riff == b"RIFF", f"Not a RIFF: {w}"
            assert wave == b"WAVE", f"Not a WAVE: {w}"
            assert fmt == b"fmt ", f"Not a fmt: {w}"
            audio_format, channels, sample_rate, byte_rate, block_align, bits = struct.unpack("<HHIIHH", header[20:36])
            assert audio_format == 1, f"Not PCM: {w}"
            assert channels == 2, f"Not stereo: {w}"
            assert sample_rate == 44100, f"Not 44.1kHz: {w}"
            assert bits == 16, f"Not 16-bit: {w}"
            size = os.path.getsize(full_p)
            dur = (size - 44) / (sample_rate * channels * 2)
            total_duration += dur
            total_checked += 1

print(f"\n[SUCCESS] ALL {total_checked} Russian audio tracks verified!")
print(f"Total audio runtime: {total_duration / 60:.1f} minutes of voice acting.")
print("=== MOD VERIFICATION PASSED 100% ===")

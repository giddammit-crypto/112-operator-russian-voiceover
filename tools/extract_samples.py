import os
import UnityPy

game_assets = "/home/astra/vint2/gamez/steamapps/common/112 Operator/Operator 112_Data/sharedassets2.assets"
out_dir = "/home/astra/.gemini/antigravity/scratch/operator112_russian_voice_mod/extracted_samples"
os.makedirs(out_dir, exist_ok=True)

env = UnityPy.load(game_assets)
saved = 0
for obj in env.objects:
    if obj.type.name == "AudioClip":
        clip = obj.read()
        name = getattr(clip, "m_Name", "")
        if any(k in name for k in ["go_1", "underfire_1", "wtf_1", "stuck_1", "officerdown_1", "chatter_1"]):
            samples = clip.samples
            for fname, data in samples.items():
                target_path = os.path.join(out_dir, f"{name}_{obj.path_id}.wav")
                with open(target_path, "wb") as f:
                    f.write(data)
                print(f"Saved: {target_path} ({len(data)} bytes)")
                saved += 1
                if saved >= 10:
                    break
        if saved >= 10:
            break

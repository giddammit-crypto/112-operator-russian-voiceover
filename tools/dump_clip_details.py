import UnityPy

path = "/home/astra/vint2/gamez/steamapps/common/112 Operator/Operator 112_Data/sharedassets2.assets"
env = UnityPy.load(path)

clips_info = []
for obj in env.objects:
    if obj.type.name == "AudioClip":
        clip = obj.read()
        name = getattr(clip, "m_Name", "")
        duration = getattr(clip, "m_Length", 0)
        freq = getattr(clip, "m_Frequency", 0)
        channels = getattr(clip, "m_Channels", 0)
        clips_info.append({
            "path_id": obj.path_id,
            "name": name,
            "duration": round(duration, 2),
            "freq": freq,
            "channels": channels
        })

print(f"Total clips found: {len(clips_info)}")
# Let's save as json for our analysis
import json
with open("/home/astra/.gemini/antigravity/scratch/operator112_russian_voice_mod/clips_sharedassets2.json", "w", encoding="utf-8") as f:
    json.dump(clips_info, f, indent=2, ensure_ascii=False)

print("Saved clips_sharedassets2.json")

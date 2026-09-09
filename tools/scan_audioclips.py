import os
import UnityPy

game_data = "/home/astra/vint2/gamez/steamapps/common/112 Operator/Operator 112_Data"

for target in ["sharedassets0.assets", "sharedassets2.assets", "resources.assets"]:
    path = os.path.join(game_data, target)
    if not os.path.exists(path):
        continue
    env = UnityPy.load(path)
    names = []
    for obj in env.objects:
        if obj.type.name == "AudioClip":
            try:
                data = obj.read()
                name = getattr(data, "m_Name", getattr(data, "name", str(data)))
                names.append(name)
            except Exception as e:
                names.append(f"err: {e}")
    print(f"\n=== {target} ({len(names)} clips) ===")
    # Print sample and search for chatter / radio / dialogue
    radio_clips = [n for n in names if any(k in n.lower() for k in ["radio", "chat", "male", "female", "police", "medic", "fire", "unit", "call", "c_"])]
    print(f"Radio/dialogue-related clips: {len(radio_clips)}")
    for n in sorted(radio_clips)[:40]:
        print(f"  {n}")
    if len(radio_clips) > 40:
        print(f"  ... and {len(radio_clips)-40} more")

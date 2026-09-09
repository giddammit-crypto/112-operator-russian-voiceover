import struct
import UnityPy

game_assets = "/home/astra/vint2/gamez/steamapps/common/112 Operator/Operator 112_Data/sharedassets2.assets"
env = UnityPy.load(game_assets)

# Build map of path_id -> name for AudioClips
clip_names = {}
for obj in env.objects:
    if obj.type.name == "AudioClip":
        c = obj.read()
        clip_names[obj.path_id] = getattr(c, "m_Name", "")

print(f"Total clip_names mapped: {len(clip_names)}")

# Find all MonoBehaviours and check if any reference these path_ids
for obj in env.objects:
    if obj.type.name == "MonoBehaviour":
        raw = obj.get_raw_data()
        # Search for path_ids in the raw data (as 64-bit little-endian ints)
        found = []
        for i in range(0, len(raw) - 7, 4):
            val = struct.unpack("<q", raw[i:i+8])[0]
            if val in clip_names:
                found.append((val, clip_names[val]))
        if len(found) > 10:
            print(f"MonoBehaviour path_id={obj.path_id} references {len(found)} clips!")
            print("  First 10 referenced clips:")
            for pid, cname in found[:10]:
                print(f"    {pid} -> {cname}")

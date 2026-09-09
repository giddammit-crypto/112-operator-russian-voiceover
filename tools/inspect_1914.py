import struct
import UnityPy

game_assets = "/home/astra/vint2/gamez/steamapps/common/112 Operator/Operator 112_Data/sharedassets2.assets"
env = UnityPy.load(game_assets)

clip_names = {}
for obj in env.objects:
    if obj.type.name == "AudioClip":
        c = obj.read()
        clip_names[obj.path_id] = getattr(c, "m_Name", "")

for obj in env.objects:
    if obj.path_id == 1914:
        raw = obj.get_raw_data()
        print(f"RadioMessageLibrary raw length: {len(raw)} bytes")
        
        # Let's inspect strings inside raw data
        strings = []
        cur = []
        for b in raw:
            if 32 <= b <= 126:
                cur.append(chr(b))
            else:
                if len(cur) >= 3:
                    strings.append("".join(cur))
                cur = []
        print("Strings found in MonoBehaviour 1914:", strings[:40])

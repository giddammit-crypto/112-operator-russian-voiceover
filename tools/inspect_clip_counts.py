import UnityPy
from collections import Counter

path = "/home/astra/vint2/gamez/steamapps/common/112 Operator/Operator 112_Data/sharedassets2.assets"
env = UnityPy.load(path)

clips = []
for obj in env.objects:
    if obj.type.name == "AudioClip":
        data = obj.read()
        name = getattr(data, "m_Name", "")
        clips.append((name, obj.path_id))

print(f"Total AudioClips in sharedassets2: {len(clips)}")
counts = Counter([c[0] for c in clips])
print("\nUnique names and their counts:")
for name, cnt in sorted(counts.items()):
    print(f"  {name}: {cnt} instances")

import UnityPy

path = "/home/astra/vint2/gamez/steamapps/common/112 Operator/Operator 112_Data/sharedassets2.assets"
env = UnityPy.load(path)

rvoice_clips = []
other_clips = []

for obj in env.objects:
    if obj.type.name == "AudioClip":
        data = obj.read()
        name = getattr(data, "m_Name", "")
        if "rvoice" in name.lower() or "radio" in name.lower() or "chatter" in name.lower():
            rvoice_clips.append(name)
        else:
            other_clips.append(name)

print(f"Total rvoice clips: {len(rvoice_clips)}")
for n in sorted(set(rvoice_clips)):
    print(n)

print(f"\nOther clips in sharedassets2: {len(other_clips)}")
for n in sorted(set(other_clips))[:30]:
    print(n)

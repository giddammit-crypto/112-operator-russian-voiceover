import UnityPy

env = UnityPy.load('/home/astra/vint2/gamez/steamapps/common/112 Operator/Operator 112_Data/sharedassets2.assets')
clips = []
for obj in env.objects:
    if obj.type.name == 'AudioClip':
        clip = obj.read()
        res = clip.m_Resource
        clips.append({
            'path_id': obj.path_id,
            'name': clip.m_Name,
            'offset': res.m_Offset,
            'size': res.m_Size,
            'channels': clip.m_Channels,
            'frequency': clip.m_Frequency,
            'length': clip.m_Length,
            'format': clip.m_CompressionFormat
        })

# Sort by offset
clips.sort(key=lambda x: x['offset'])

print(f"Total clips: {len(clips)}")
print(f"First clip: {clips[0]}")
print(f"Last clip: {clips[-1]}")
print(f"Total size spanned: {clips[-1]['offset'] + clips[-1]['size']} bytes")

# Check if offsets are contiguous
gaps = 0
for i in range(len(clips) - 1):
    curr_end = clips[i]['offset'] + clips[i]['size']
    next_start = clips[i+1]['offset']
    if curr_end != next_start:
        gaps += 1

print(f"Gaps between clips: {gaps}")

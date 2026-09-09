import struct
import json
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

offset = 0
file_id, go_pid = struct.unpack_from("<iq", raw, offset)
offset += 12
m_enabled = raw[offset]
offset += 4 # byte + 3 padding
script_fid, script_pid = struct.unpack_from("<iq", raw, offset)
offset += 12
name_len = struct.unpack_from("<I", raw, offset)[0]
offset += 4
m_name = raw[offset:offset+name_len].decode("latin1")
offset += name_len
if offset % 4 != 0:
    offset += (4 - (offset % 4))

print(f"Header: name='{m_name}', offset={offset}")

num_messages = struct.unpack_from("<I", raw, offset)[0]
offset += 4
print(f"num_messages = {num_messages}")

def read_string(data, off):
    slen = struct.unpack_from("<I", data, off)[0]
    off += 4
    s = data[off:off+slen].decode("utf-8", errors="replace")
    off += slen
    if off % 4 != 0:
        off += (4 - (off % 4))
    return s, off

def read_pptr_array(data, off):
    count = struct.unpack_from("<I", data, off)[0]
    off += 4
    pptrs = []
    for _ in range(count):
        fid, pid = struct.unpack_from("<iq", data, off)
        off += 12
        pptrs.append(pid)
    return pptrs, off

messages = []
for idx in range(num_messages):
    tooltip_stay = raw[offset] != 0
    offset += 1
    tell_disp = raw[offset] != 0
    offset += 1
    ed_fix = raw[offset] != 0
    offset += 1
    offset += 1 # padding to 4 bytes
    
    t_start, t_end = struct.unpack_from("<ii", raw, offset)
    offset += 8
    
    msg_id, offset = read_string(raw, offset)
    
    use_voice = raw[offset] != 0
    offset += 1
    offset += 3 # pad
    
    male1, offset = read_pptr_array(raw, offset)
    male2, offset = read_pptr_array(raw, offset)
    female1, offset = read_pptr_array(raw, offset)
    female2, offset = read_pptr_array(raw, offset)
    
    use_tooltip = raw[offset] != 0
    offset += 1
    use_radio_bar = raw[offset] != 0
    offset += 1
    offset += 2 # pad to 4
    
    messages.append({
        "id": msg_id,
        "use_voice": use_voice,
        "male1": [(p, clip_names.get(p, f"pid_{p}")) for p in male1],
        "male2": [(p, clip_names.get(p, f"pid_{p}")) for p in male2],
        "female1": [(p, clip_names.get(p, f"pid_{p}")) for p in female1],
        "female2": [(p, clip_names.get(p, f"pid_{p}")) for p in female2],
    })

print(f"Successfully parsed {len(messages)} messages!")
with open("/home/astra/.gemini/antigravity/scratch/operator112_russian_voice_mod/parsed_radio_messages.json", "w", encoding="utf-8") as f:
    json.dump(messages, f, indent=2, ensure_ascii=False)

for m in messages:
    print(f"[{m['id']}] useVoice={m['use_voice']}")
    print(f"  Male1   ({len(m['male1'])}): {[x[1] for x in m['male1']]}")
    print(f"  Male2   ({len(m['male2'])}): {[x[1] for x in m['male2']]}")
    print(f"  Female1 ({len(m['female1'])}): {[x[1] for x in m['female1']]}")
    print(f"  Female2 ({len(m['female2'])}): {[x[1] for x in m['female2']]}")

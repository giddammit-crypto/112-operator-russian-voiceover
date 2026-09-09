import os
import re
import sys
import glob
import asyncio
import subprocess
import xml.etree.ElementTree as ET
import edge_tts

GAME_ROOT = "/home/astra/vint2/gamez/steamapps/common/112 Operator"
STREAMING_ASSETS = os.path.join(GAME_ROOT, "Operator 112_Data", "StreamingAssets")
LANG_PATH = os.path.join(STREAMING_ASSETS, "Languages", "ru-RU.txt")
CALLS_DIR = os.path.join(STREAMING_ASSETS, "Calls")
CALLS_911_DIR = os.path.join(STREAMING_ASSETS, "Calls_911")
DEST_DIR = os.path.join(STREAMING_ASSETS, "Audio", "RussianCalls")
TEMP_DIR = "/home/astra/.gemini/antigravity/scratch/operator112_russian_voice_mod/temp_call_mp3"

os.makedirs(DEST_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

# 1. Parse ru-RU.txt for all dialogue lines
print("Parsing ru-RU.txt...")
dialog_texts = {}
pattern = re.compile(r'\"(incident\.[^\"\:]+\.dialog\.[^\"\:]+)\"\s*:\s*\"(.*)\"')

with open(LANG_PATH, "r", encoding="utf-8") as f:
    for line in f:
        m = pattern.search(line)
        if m:
            key = m.group(1)
            val = m.group(2)
            if val.endswith('",') or val.endswith('"'):
                val = val.rstrip(',').rstrip('"')
            # Handle unescaped quotes or standard backslashes
            val = val.replace('\\"', '"').replace('\\n', ' ')
            dialog_texts[key] = val

print(f"Loaded {len(dialog_texts)} localized dialog lines.")

# 2. Parse all XMLs to collect metadata (operator, emotions, sex)
print("Scanning Call XMLs...")
xml_files = glob.glob(os.path.join(CALLS_DIR, "**/*.xml"), recursive=True) + glob.glob(os.path.join(CALLS_911_DIR, "**/*.xml"), recursive=True)

calls_meta = {}

for fpath in xml_files:
    try:
        tree = ET.parse(fpath)
        root = tree.getroot()
        incident = root.find("incident")
        if incident is None:
            continue
        call_id = incident.get("id", os.path.splitext(os.path.basename(fpath))[0])
        
        # Determine default sex of the call caller
        default_sex = "MALE"
        for p in root.iter():
            props = p.get("properties", "")
            if "sex=FEMALE" in props:
                default_sex = "FEMALE"
                break
            elif "sex=MALE" in props:
                default_sex = "MALE"
                break

        options = {}
        for opt in root.iter("dialogOption"):
            opt_id = opt.get("id")
            if not opt_id:
                continue
            op_tag = (opt.get("operator") or "").lower().strip()
            is_op = "operator" in op_tag or "dispatcher" in op_tag
            em = (opt.get("emotions") or "").lower().strip()
            texten = opt.get("texten", "")
            options[opt_id] = {
                "is_operator": is_op,
                "emotions": em,
                "texten": texten,
                "sex": default_sex
            }

        calls_meta[call_id] = {
            "default_sex": default_sex,
            "options": options,
            "file": fpath
        }
    except Exception as ex:
        pass

print(f"Parsed metadata for {len(calls_meta)} calls.")

def clean_dialog_text(raw_text, is_operator=False):
    t = raw_text
    if is_operator:
        m = re.match(r'^\{[^}]+\}\s*(.*)$', t)
        if m and m.group(1).strip():
            t = m.group(1).strip()
        else:
            t = re.sub(r'[\{\}]', '', t)
    # Remove typewriter timing tags like [[0.3]]
    t = re.sub(r'\[\[[\d\.]+\]\]', '', t)
    # Natural Russian address replacement
    t = t.replace('[[ADDRESS]]', 'улица Ленина')
    t = t.replace('[[DISTRICT]]', 'в нашем районе')
    t = re.sub(r'[\{\}]', '', t)
    # Clean ellipses and extra whitespace
    t = re.sub(r'\.{2,}', '... ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t

def get_voice_params(is_operator, sex, emotions):
    if is_operator:
        # Crisp, calm, professional dispatcher
        return {
            "voice": "ru-RU-DmitryNeural",
            "pitch": "-3Hz",
            "rate": "+4%",
            "dsp": "operator"
        }

    is_female = (sex == "FEMALE")
    voice = "ru-RU-SvetlanaNeural" if is_female else "ru-RU-DmitryNeural"
    em = emotions.lower()

    if any(w in em for w in ["shout", "scream", "panic", "fright", "terror", "scared"]):
        rate = "+20%" if is_female else "+22%"
        pitch = "+14Hz" if is_female else "+16Hz"
    elif any(w in em for w in ["cry", "sobbing", "pain", "helpless", "desperate", "moan", "weep"]):
        rate = "-6%" if is_female else "-4%"
        pitch = "+8Hz" if is_female else "+10Hz"
    elif any(w in em for w in ["angr", "irritat", "furious", "mad", "aggressive"]):
        rate = "+14%" if is_female else "+12%"
        pitch = "+5Hz" if is_female else "+7Hz"
    elif any(w in em for w in ["whisper", "quiet", "distance", "breath"]):
        rate = "-8%" if is_female else "-10%"
        pitch = "-4Hz" if is_female else "-6Hz"
    elif any(w in em for w in ["slur", "drunk", "dazed", "weak", "dying"]):
        rate = "-12%" if is_female else "-15%"
        pitch = "-8Hz" if is_female else "-10Hz"
    elif any(w in em for w in ["nervous", "worried", "anxious", "hurried", "confused", "unsure"]):
        rate = "+12%" if is_female else "+14%"
        pitch = "+6Hz" if is_female else "+8Hz"
    else:
        # Normal telephone caller
        rate = "+5%" if is_female else "+4%"
        pitch = "+2Hz" if is_female else "+1Hz"

    return {
        "voice": voice,
        "pitch": pitch,
        "rate": rate,
        "dsp": "caller"
    }

SEMAPHORE = asyncio.Semaphore(8)

async def synthesize_option(call_id, opt_id, meta, text):
    out_dir = os.path.join(DEST_DIR, call_id)
    os.makedirs(out_dir, exist_ok=True)
    out_wav = os.path.join(out_dir, f"{opt_id}.wav")

    # Skip if already generated
    if os.path.exists(out_wav) and os.path.getsize(out_wav) > 1000:
        return True

    is_op = meta.get("is_operator", False)
    clean_text = clean_dialog_text(text, is_op)
    
    has_letters = bool(re.search(r'[a-zA-Zа-яА-Я0-9]', clean_text))
    if not has_letters:
        # Generate 1.2s silence for pauses / silence / hangup
        cmd_silence = [
            "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-t", "1.2", "-ar", "44100", "-ac", "2", out_wav
        ]
        res = subprocess.run(cmd_silence, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return res.returncode == 0

    vparams = get_voice_params(is_op, meta.get("sex", "MALE"), meta.get("emotions", ""))

    temp_mp3 = os.path.join(TEMP_DIR, f"{call_id}_{opt_id}.mp3")

    async with SEMAPHORE:
        try:
            comm = edge_tts.Communicate(clean_text, vparams["voice"], rate=vparams["rate"], pitch=vparams["pitch"])
            await comm.save(temp_mp3)

            # DSP filter
            if vparams["dsp"] == "operator":
                # Clean headset dispatch filter
                dsp_filter = (
                    "highpass=f=120,lowpass=f=7500,equalizer=f=3000:t=q:w=1.5:g=2,"
                    "acompressor=threshold=-16dB:ratio=4:attack=5:release=50,volume=1.6,aresample=44100"
                )
            else:
                # Realistic telephone line filter with bandpass and soft clipping
                dsp_filter = (
                    "highpass=f=350,lowpass=f=3400,equalizer=f=1000:t=q:w=1.0:g=4,"
                    "equalizer=f=2500:t=q:w=1.5:g=3,asoftclip=type=atan,volume=2.2,aresample=44100"
                )

            cmd = [
                "ffmpeg", "-y", "-i", temp_mp3,
                "-af", dsp_filter,
                "-ac", "2", "-ar", "44100",
                out_wav
            ]
            res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return res.returncode == 0
        except Exception as ex:
            print(f"Error on {call_id}/{opt_id}: {ex}")
            return False
        finally:
            if os.path.exists(temp_mp3):
                os.remove(temp_mp3)

async def main():
    # Build list of all available dialogue lines
    tasks = []
    
    # Check if specific calls were requested as CLI arguments
    target_calls = sys.argv[1:] if len(sys.argv) > 1 else None

    total_matched = 0
    for call_id, cm in calls_meta.items():
        if target_calls and call_id not in target_calls:
            continue
        for opt_id, om in cm["options"].items():
            key = f"incident.{call_id}.dialog.{opt_id}"
            if key in dialog_texts:
                text = dialog_texts[key]
                tasks.append((call_id, opt_id, om, text))
                total_matched += 1

    print(f"Found {total_matched} dialogue lines ready to synthesize.")

    batch_size = 50
    total = len(tasks)
    success = 0

    for i in range(0, total, batch_size):
        batch = tasks[i:i+batch_size]
        sub_tasks = [synthesize_option(c, o, m, t) for c, o, m, t in batch]
        results = await asyncio.gather(*sub_tasks)
        success += sum(1 for r in results if r)
        print(f"Progress: {min(i+batch_size, total)}/{total} lines processed ({success} successful)")

    print(f"=== FINISHED SYNTHESIS! Total: {success}/{total} audio files created. ===")

if __name__ == "__main__":
    asyncio.run(main())

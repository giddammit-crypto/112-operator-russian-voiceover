import json
import re

ru_path = "/home/astra/vint2/gamez/steamapps/common/112 Operator/Operator 112_Data/StreamingAssets/Languages/ru-RU.txt"
en_path = "/home/astra/vint2/gamez/steamapps/common/112 Operator/Operator 112_Data/StreamingAssets/Languages/en-US.txt"

def load_kv(path):
    kv = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith('"text.radio.'):
                # parse JSON-like key: value
                parts = line.split('": "', 1)
                if len(parts) == 2:
                    k = parts[0].strip('"\t ')
                    v = parts[1].rstrip('",')
                    kv[k] = v
    return kv

ru_radio = load_kv(ru_path)
en_radio = load_kv(en_path)

print(f"Radio lines in en-US: {len(en_radio)}")
print(f"Radio lines in ru-RU: {len(ru_radio)}")

# Print full table
print("\nSample mapping (Key | EN | RU):")
for k in sorted(en_radio.keys()):
    print(f"{k} =>\n  EN: {en_radio.get(k)}\n  RU: {ru_radio.get(k, '<missing>')}")

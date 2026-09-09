import UnityPy

path = "/home/astra/vint2/gamez/steamapps/common/112 Operator/Operator 112_Data/sharedassets2.assets"
env = UnityPy.load(path)

print("Searching MonoBehaviours in sharedassets2...")
for obj in env.objects:
    if obj.type.name == "MonoBehaviour":
        try:
            data = obj.read()
            m_name = getattr(data, "m_Name", "")
            # check script
            script = getattr(data, "m_Script", None)
            script_name = ""
            if script:
                sdata = script.read()
                script_name = getattr(sdata, "m_Name", getattr(sdata, "m_ClassName", ""))
            
            if any(k in f"{m_name} {script_name}".lower() for k in ["radio", "voice", "audio", "message"]):
                print(f"MonoBehaviour path_id={obj.path_id} name='{m_name}' script='{script_name}'")
                # print some raw data or type tree
                raw = data.to_dict()
                print("  Keys:", list(raw.keys())[:15])
                if "radioMessages" in raw:
                    print("  radioMessages count:", len(raw["radioMessages"]))
                    for m in raw["radioMessages"][:5]:
                        print("   Sample msg:", m)
                if "dispatcherRadioMessages" in raw:
                    print("  dispatcherRadioMessages count:", len(raw["dispatcherRadioMessages"]))
        except Exception as e:
            pass

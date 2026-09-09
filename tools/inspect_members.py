import dnfile

pe = dnfile.dnPE("/home/astra/vint2/gamez/steamapps/common/112 Operator/Operator 112_Data/Managed/Main.dll")
typedef = pe.net.mdtables.TypeDef

target_names = [
    "RadioMessageLibrary",
    "RadioMessageDispatcher",
    "RadioMessage",
    "RadioChatter",
    "AudioClipLoader",
    "CallWindow"
]

print("Scanning classes...")
for row in typedef.rows:
    tname = str(row.TypeName)
    if tname in target_names:
        print(f"\n==================== {row.TypeNamespace}.{tname} ====================")
        
        print("--- FIELDS ---")
        for f in getattr(row, "FieldList", []):
            try:
                print(f"  {f.row.Name}")
            except Exception as e:
                print(f"  field err: {e}")
            
        print("--- METHODS ---")
        for m in getattr(row, "MethodList", []):
            try:
                print(f"  {m.row.Name}")
            except Exception as e:
                print(f"  method err: {e}")

import dnfile

pe = dnfile.dnPE("/home/astra/vint2/gamez/steamapps/common/112 Operator/Operator 112_Data/Managed/Main.dll")

tables = pe.net.mdtables
if hasattr(tables, "tables"):
    table_dict = tables.tables
else:
    table_dict = {t.name: t for t in tables.tables_list} if hasattr(tables, "tables_list") else {}

typedef_table = getattr(tables, "TypeDef", None) or table_dict.get("TypeDef")

print("Found TypeDef table:", typedef_table is not None)
if typedef_table:
    for row in typedef_table.rows:
        tname = str(row.TypeName)
        tns = str(row.TypeNamespace)
        full = f"{tns}.{tname}" if tns else tname
        if any(w in full.lower() for w in ["radio", "chatter", "audioclip", "voice", "callwindow", "sound"]):
            print(f"- {full}")

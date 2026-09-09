import dnfile
from dncil.cil.body import CilMethodBody

pe = dnfile.dnPE("/home/astra/vint2/gamez/steamapps/common/112 Operator/Operator 112_Data/Managed/Main.dll")

def disasm(m_row):
    rva = m_row.Rva
    if not rva:
        return []
    try:
        body = CilMethodBody(pe, rva)
        lines = []
        for ins in body.instructions:
            lines.append(f"    IL_{ins.offset:04x}: {ins.opcode.name} {ins.operand if ins.operand is not None else ''}")
        return lines
    except Exception as e:
        return [f"    <error: {e}>"]

for row in pe.net.mdtables.TypeDef.rows:
    tname = str(row.TypeName)
    if tname in ["RadioMessageLibrary", "RadioChatter", "RadioMessage"]:
        print(f"\n==================== {row.TypeNamespace}.{tname} ====================")
        for m in getattr(row, "MethodList", []):
            m_row = m.row
            print(f"\n  Method {m_row.Name}:")
            for l in disasm(m_row)[:40]:
                print(l)

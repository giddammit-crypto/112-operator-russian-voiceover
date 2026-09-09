import dnfile
from dnfile.enums import OpCodes

pe = dnfile.dnPE("/home/astra/vint2/gamez/steamapps/common/112 Operator/Operator 112_Data/Managed/Main.dll")

typedef = pe.net.mdtables.TypeDef

def disassemble_method(method_row):
    rva = method_row.RVA
    if rva == 0:
        return "No body"
    # read bytes from RVA
    offset = pe.get_offset_from_rva(rva)
    # read method header
    first_byte = pe.get_data(rva, 1)[0]
    # Check if tiny header (0x02 mask) or fat header
    if (first_byte & 0x03) == 0x02:
        code_size = first_byte >> 2
        header_size = 1
    else:
        header = pe.get_data(rva, 12)
        code_size = int.from_bytes(header[4:8], "little")
        header_size = (header[1] >> 4) * 4
    code = pe.get_data(rva + header_size, code_size)
    return f"CodeSize: {code_size} bytes, Hex: {code[:40].hex()}..."

for row in typedef.rows:
    tname = str(row.TypeName)
    if tname in ["RadioMessageLibrary", "RadioMessage"]:
        print(f"\nType: {row.TypeNamespace}.{tname}")
        for m in getattr(row, "MethodList", []):
            try:
                m_row = m.row
                print(f"  Method: {m_row.Name} ({disassemble_method(m_row)})")
            except Exception as e:
                print(f"  Err: {e}")

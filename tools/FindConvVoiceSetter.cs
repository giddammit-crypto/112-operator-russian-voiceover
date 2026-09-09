using System;
using System.IO;
using System.Linq;
using Mono.Cecil;
using Mono.Cecil.Cil;

class FindConvVoiceSetter
{
    static void Main(string[] args)
    {
        string gameData = "/home/astra/vint2/gamez/steamapps/common/112 Operator/Operator 112_Data/Managed";
        string mainDll = Path.Combine(gameData, "Main.dll.original");
        if (!File.Exists(mainDll)) mainDll = Path.Combine(gameData, "Main.dll");

        var resolver = new DefaultAssemblyResolver();
        resolver.AddSearchDirectory(gameData);

        using var asm = AssemblyDefinition.ReadAssembly(mainDll, new ReaderParameters { AssemblyResolver = resolver });
        foreach (var t in asm.MainModule.Types)
        {
            foreach (var m in t.Methods)
            {
                if (!m.HasBody) continue;
                foreach (var ins in m.Body.Instructions)
                {
                    if (ins.Operand is FieldReference fr && fr.DeclaringType.Name == "ConversationElement" &&
                        (fr.Name == "voice" || fr.Name == "audioResponse"))
                    {
                        if (ins.OpCode == OpCodes.Stfld)
                        {
                            Console.WriteLine($"Setter in {t.FullName}::{m.Name} -> {fr.Name}");
                        }
                    }
                }
            }
        }
    }
}

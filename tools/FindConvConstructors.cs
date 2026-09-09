using System;
using System.IO;
using System.Linq;
using Mono.Cecil;
using Mono.Cecil.Cil;

class FindConvConstructors
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
                    if (ins.Operand is MethodReference mr && mr.DeclaringType.Name == "Conversation" && mr.Name == ".ctor")
                    {
                        Console.WriteLine($"Conversation constructor in {t.FullName}::{m.Name}");
                    }
                    if (ins.Operand is FieldReference fr && fr.DeclaringType.Name == "Conversation" && fr.Name == "loadedFromPath" && ins.OpCode == OpCodes.Stfld)
                    {
                        Console.WriteLine($"Conversation.loadedFromPath set in {t.FullName}::{m.Name}");
                    }
                }
            }
        }
    }
}

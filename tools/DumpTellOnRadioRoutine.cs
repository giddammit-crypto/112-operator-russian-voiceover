using System;
using System.IO;
using System.Linq;
using Mono.Cecil;
using Mono.Cecil.Cil;

class DumpTellOnRadioRoutine
{
    static void Main(string[] args)
    {
        string gameData = "/home/astra/vint2/gamez/steamapps/common/112 Operator/Operator 112_Data/Managed";
        string mainDll = Path.Combine(gameData, "Main.dll.original");
        if (!File.Exists(mainDll)) mainDll = Path.Combine(gameData, "Main.dll");

        var resolver = new DefaultAssemblyResolver();
        resolver.AddSearchDirectory(gameData);

        using var asm = AssemblyDefinition.ReadAssembly(mainDll, new ReaderParameters { AssemblyResolver = resolver });
        var t = asm.MainModule.GetType("com.jutsugames.operator112.units.Unit");

        foreach (var m in t.Methods.Where(m => m.Name.Contains("TellOnRadio")))
        {
            Console.WriteLine($"\n--- METHOD: {m.Name} ---");
            if (m.HasBody)
            {
                foreach (var ins in m.Body.Instructions)
                {
                    if (ins.OpCode == OpCodes.Ldstr || ins.OpCode == OpCodes.Call || ins.OpCode == OpCodes.Callvirt || ins.OpCode == OpCodes.Ldfld)
                    {
                        Console.WriteLine($"  IL_{ins.Offset:X4}: {ins.OpCode} {ins.Operand}");
                    }
                }
            }
        }
    }
}

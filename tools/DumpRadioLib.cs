using System;
using System.IO;
using System.Linq;
using Mono.Cecil;
using Mono.Cecil.Cil;

class DumpRadioLib
{
    static void Main(string[] args)
    {
        string gameData = "/home/astra/vint2/gamez/steamapps/common/112 Operator/Operator 112_Data/Managed";
        string mainDll = Path.Combine(gameData, "Main.dll.original");
        if (!File.Exists(mainDll)) mainDll = Path.Combine(gameData, "Main.dll");

        var resolver = new DefaultAssemblyResolver();
        resolver.AddSearchDirectory(gameData);

        using var asm = AssemblyDefinition.ReadAssembly(mainDll, new ReaderParameters { AssemblyResolver = resolver });
        var t = asm.MainModule.GetType("com.jutsugames.operator112.UI.ingame.RadioMessageLibrary");

        Console.WriteLine($"TYPE: {t.FullName} (Base: {t.BaseType})");
        foreach (var f in t.Fields)
        {
            Console.WriteLine($"  Field: {f.FieldType} {f.Name} (static: {f.IsStatic})");
        }
        foreach (var m in t.Methods)
        {
            Console.WriteLine($"\n--- METHOD: {m.Name} (static: {m.IsStatic}) ---");
            if (m.HasBody)
            {
                foreach (var ins in m.Body.Instructions)
                {
                    Console.WriteLine($"  IL_{ins.Offset:X4}: {ins.OpCode} {ins.Operand}");
                }
            }
        }
    }
}

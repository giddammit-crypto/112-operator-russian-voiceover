using System;
using System.IO;
using System.Linq;
using Mono.Cecil;
using Mono.Cecil.Cil;

class DumpModsLoader
{
    static void Main(string[] args)
    {
        string gameData = "/home/astra/vint2/gamez/steamapps/common/112 Operator/Operator 112_Data/Managed";
        string mainDll = Path.Combine(gameData, "Main.dll.original");
        if (!File.Exists(mainDll)) mainDll = Path.Combine(gameData, "Main.dll");

        var resolver = new DefaultAssemblyResolver();
        resolver.AddSearchDirectory(gameData);

        using var asm = AssemblyDefinition.ReadAssembly(mainDll, new ReaderParameters { AssemblyResolver = resolver });
        var t = asm.MainModule.GetType("com.jutsugames.utilities.workshop.mods.ModsLoader");
        Console.WriteLine($"TYPE: {t.FullName}");

        foreach (var m in t.Methods)
        {
            Console.WriteLine($"\n--- METHOD: {m.Name} ---");
            if (m.HasBody)
            {
                foreach (var ins in m.Body.Instructions)
                {
                    Console.WriteLine($"  IL_{ins.Offset:X4}: {ins.OpCode} {ins.Operand}");
                }
            }
        }

        var modConfig = asm.MainModule.GetType("com.jutsugames.utilities.workshop.ModConfig");
        Console.WriteLine($"\nTYPE: {modConfig.FullName}");
        foreach (var f in modConfig.Fields)
        {
            Console.WriteLine($"  Field: {f.FieldType} {f.Name}");
        }
        foreach (var p in modConfig.Properties)
        {
            Console.WriteLine($"  Prop: {p.PropertyType} {p.Name}");
        }

        var modType = asm.MainModule.GetType("com.jutsugames.utilities.workshop.mods.ModType");
        Console.WriteLine($"\nTYPE: {modType.FullName}");
        foreach (var f in modType.Fields)
        {
            Console.WriteLine($"  Enum value: {f.Name} = {f.Constant}");
        }
    }
}

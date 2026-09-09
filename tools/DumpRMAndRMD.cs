using System;
using System.IO;
using System.Linq;
using Mono.Cecil;

class DumpRMAndRMD
{
    static void Main(string[] args)
    {
        string gameData = "/home/astra/vint2/gamez/steamapps/common/112 Operator/Operator 112_Data/Managed";
        string mainDll = Path.Combine(gameData, "Main.dll.original");
        if (!File.Exists(mainDll)) mainDll = Path.Combine(gameData, "Main.dll");

        var resolver = new DefaultAssemblyResolver();
        resolver.AddSearchDirectory(gameData);

        using var asm = AssemblyDefinition.ReadAssembly(mainDll, new ReaderParameters { AssemblyResolver = resolver });
        
        var t1 = asm.MainModule.GetType("com.jutsugames.operator112.UI.ingame.RadioMessage");
        Console.WriteLine($"TYPE: {t1.FullName}");
        foreach (var f in t1.Fields)
        {
            Console.WriteLine($"  Field: {f.FieldType} {f.Name}");
        }

        var t2 = asm.MainModule.GetType("com.jutsugames.operator112.UI.ingame.RadioMessageDispatcher");
        Console.WriteLine($"\nTYPE: {t2.FullName} (Base: {t2.BaseType})");
        foreach (var f in t2.Fields)
        {
            Console.WriteLine($"  Field: {f.FieldType} {f.Name}");
        }
    }
}

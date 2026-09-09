using System;
using System.IO;
using System.Linq;
using Mono.Cecil;

class DumpSOLib
{
    static void Main(string[] args)
    {
        string gameData = "/home/astra/vint2/gamez/steamapps/common/112 Operator/Operator 112_Data/Managed";
        string mainDll = Path.Combine(gameData, "Main.dll.original");
        if (!File.Exists(mainDll)) mainDll = Path.Combine(gameData, "Main.dll");

        var resolver = new DefaultAssemblyResolver();
        resolver.AddSearchDirectory(gameData);

        using var asm = AssemblyDefinition.ReadAssembly(mainDll, new ReaderParameters { AssemblyResolver = resolver });
        var t = asm.MainModule.GetType("com.jutsugames.operator112.gamelogic.ScriptableObjectLibrary");

        Console.WriteLine($"TYPE: {t.FullName} (Base: {t.BaseType})");
        foreach (var f in t.Fields)
        {
            Console.WriteLine($"  Field: {f.FieldType} {f.Name} (static: {f.IsStatic})");
        }
        foreach (var p in t.Properties)
        {
            Console.WriteLine($"  Prop: {p.PropertyType} {p.Name}");
        }
        foreach (var m in t.Methods)
        {
            Console.WriteLine($"  Method: {m.ReturnType} {m.Name}");
        }
    }
}

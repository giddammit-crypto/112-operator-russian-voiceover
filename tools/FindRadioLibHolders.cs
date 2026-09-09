using System;
using System.IO;
using System.Linq;
using Mono.Cecil;

class FindRadioLibHolders
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
            foreach (var f in t.Fields)
            {
                if (f.FieldType.FullName.Contains("RadioMessageLibrary"))
                {
                    Console.WriteLine($"Field in {t.FullName} -> {f.FieldType} {f.Name} (static: {f.IsStatic})");
                }
            }
            foreach (var p in t.Properties)
            {
                if (p.PropertyType.FullName.Contains("RadioMessageLibrary"))
                {
                    Console.WriteLine($"Prop in {t.FullName} -> {p.PropertyType} {p.Name}");
                }
            }
        }
    }
}

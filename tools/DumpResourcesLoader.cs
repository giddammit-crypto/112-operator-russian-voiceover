using System;
using System.IO;
using System.Linq;
using Mono.Cecil;
using Mono.Cecil.Cil;

class DumpResourcesLoader
{
    static void Main(string[] args)
    {
        string gameData = "/home/astra/vint2/gamez/steamapps/common/112 Operator/Operator 112_Data/Managed";
        string mainDll = Path.Combine(gameData, "Main.dll.original");
        if (!File.Exists(mainDll)) mainDll = Path.Combine(gameData, "Main.dll");

        var resolver = new DefaultAssemblyResolver();
        resolver.AddSearchDirectory(gameData);

        using var asm = AssemblyDefinition.ReadAssembly(mainDll, new ReaderParameters { AssemblyResolver = resolver });
        var t = asm.MainModule.GetType("com.jutsugames.utilities.ResourcesLoader");
        if (t == null)
        {
            var libDll = Path.Combine(gameData, "Libraries.dll");
            using var asmLib = AssemblyDefinition.ReadAssembly(libDll, new ReaderParameters { AssemblyResolver = resolver });
            t = asmLib.MainModule.GetType("com.jutsugames.utilities.ResourcesLoader");
        }

        Console.WriteLine($"TYPE: {t.FullName}");
        foreach (var m in t.Methods)
        {
            if (m.Name.Contains("Dialog") || m.Name.Contains("Call") || m.Name.Contains("Audio"))
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
        }
    }
}

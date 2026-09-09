using System;
using System.IO;
using System.Linq;
using Mono.Cecil;

class FindCallAudioClasses
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
            if (t.Name.IndexOf("Dialog", StringComparison.OrdinalIgnoreCase) >= 0 ||
                t.Name.IndexOf("Call", StringComparison.OrdinalIgnoreCase) >= 0)
            {
                Console.WriteLine($"TYPE: {t.FullName}");
                foreach (var m in t.Methods)
                {
                    if (m.Name.IndexOf("Audio", StringComparison.OrdinalIgnoreCase) >= 0 ||
                        m.Name.IndexOf("Play", StringComparison.OrdinalIgnoreCase) >= 0 ||
                        m.Name.IndexOf("Voice", StringComparison.OrdinalIgnoreCase) >= 0 ||
                        m.Name.IndexOf("Sound", StringComparison.OrdinalIgnoreCase) >= 0)
                    {
                        Console.WriteLine($"  Method: {m.Name}");
                    }
                }
            }
        }
    }
}

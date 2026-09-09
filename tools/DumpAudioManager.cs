using System;
using System.IO;
using System.Linq;
using Mono.Cecil;

class DumpAudioManager
{
    static void Main(string[] args)
    {
        string gameData = "/home/astra/vint2/gamez/steamapps/common/112 Operator/Operator 112_Data/Managed";
        string mainDll = Path.Combine(gameData, "Main.dll.original");
        if (!File.Exists(mainDll)) mainDll = Path.Combine(gameData, "Main.dll");

        var resolver = new DefaultAssemblyResolver();
        resolver.AddSearchDirectory(gameData);

        using var asm = AssemblyDefinition.ReadAssembly(mainDll, new ReaderParameters { AssemblyResolver = resolver });
        
        var t1 = asm.MainModule.GetType("com.jutsugames.operator112.gamelogic.audio.AudioManager");
        Console.WriteLine($"TYPE: {t1.FullName} (Base: {t1.BaseType})");
        foreach (var f in t1.Fields)
        {
            Console.WriteLine($"  Field: {f.FieldType} {f.Name} (static: {f.IsStatic})");
        }
    }
}

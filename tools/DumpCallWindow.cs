using System;
using System.IO;
using System.Linq;
using Mono.Cecil;
using Mono.Cecil.Cil;

class DumpCallWindow
{
    static void Main(string[] args)
    {
        string gameData = "/home/astra/vint2/gamez/steamapps/common/112 Operator/Operator 112_Data/Managed";
        string mainDll = Path.Combine(gameData, "Main.dll.original");
        if (!File.Exists(mainDll)) mainDll = Path.Combine(gameData, "Main.dll");

        var resolver = new DefaultAssemblyResolver();
        resolver.AddSearchDirectory(gameData);

        using var asm = AssemblyDefinition.ReadAssembly(mainDll, new ReaderParameters { AssemblyResolver = resolver });
        var cw = asm.MainModule.GetType("com.jutsugames.operator112.gamelogic.calls.CallWindow");
        Console.WriteLine($"TYPE: {cw.FullName}");
        foreach (var f in cw.Fields)
        {
            Console.WriteLine($"  Field: {f.FieldType} {f.Name}");
        }
        foreach (var m in cw.Methods)
        {
            if (m.Name == "SetDialogueAudio" || m.Name.Contains("Audio") || m.Name.Contains("Dialogue") || m.Name == "PlayDialogueAudio")
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

        var opt = asm.MainModule.GetType("com.jutsugames.operator112.gamelogic.calls.DialogueOption");
        Console.WriteLine($"\nTYPE: {opt.FullName}");
        foreach (var f in opt.Fields)
        {
            Console.WriteLine($"  Field: {f.FieldType} {f.Name}");
        }
        foreach (var p in opt.Properties)
        {
            Console.WriteLine($"  Prop: {p.PropertyType} {p.Name}");
        }
    }
}

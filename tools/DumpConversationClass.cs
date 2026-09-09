using System;
using System.IO;
using System.Linq;
using Mono.Cecil;
using Mono.Cecil.Cil;

class DumpConversationClass
{
    static void Main(string[] args)
    {
        string gameData = "/home/astra/vint2/gamez/steamapps/common/112 Operator/Operator 112_Data/Managed";
        string mainDll = Path.Combine(gameData, "Main.dll.original");
        if (!File.Exists(mainDll)) mainDll = Path.Combine(gameData, "Main.dll");

        var resolver = new DefaultAssemblyResolver();
        resolver.AddSearchDirectory(gameData);

        using var asm = AssemblyDefinition.ReadAssembly(mainDll, new ReaderParameters { AssemblyResolver = resolver });
        var t = asm.MainModule.GetType("com.jutsugames.operator112.gamelogic.calls.Conversation");

        Console.WriteLine($"TYPE: {t.FullName}");
        foreach (var f in t.Fields)
        {
            Console.WriteLine($"  Field: {f.FieldType} {f.Name}");
        }
        foreach (var m in t.Methods)
        {
            Console.WriteLine($"  Method: {m.Name}");
            if (m.IsConstructor && m.HasBody)
            {
                foreach (var ins in m.Body.Instructions)
                {
                    if (ins.OpCode == OpCodes.Ldstr || ins.OpCode == OpCodes.Call || ins.OpCode == OpCodes.Stfld)
                        Console.WriteLine($"    {ins.OpCode} {ins.Operand}");
                }
            }
        }
    }
}

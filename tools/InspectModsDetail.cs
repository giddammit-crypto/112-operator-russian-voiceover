using System;
using System.IO;
using System.Linq;
using Mono.Cecil;
using Mono.Cecil.Cil;

class InspectModsDetail
{
    static void Main(string[] args)
    {
        string gameData = "/home/astra/vint2/gamez/steamapps/common/112 Operator/Operator 112_Data/Managed";
        string mainDll = Path.Combine(gameData, "Main.dll.original");
        if (!File.Exists(mainDll)) mainDll = Path.Combine(gameData, "Main.dll");

        var resolver = new DefaultAssemblyResolver();
        resolver.AddSearchDirectory(gameData);

        using var asm = AssemblyDefinition.ReadAssembly(mainDll, new ReaderParameters { AssemblyResolver = resolver });
        var targetTypeNames = new[]
        {
            "com.jutsugames.utilities.workshop.ModConfig",
            "com.jutsugames.utilities.workshop.ModConfigMeta",
            "com.jutsugames.utilities.workshop.mods.ModType",
            "com.jutsugames.utilities.workshop.mods.ModsLoader",
            "com.jutsugames.utilities.workshop.mods.InstalledModsPanel",
            "com.jutsugames.utilities.workshop.ModsList"
        };

        foreach (var typeName in targetTypeNames)
        {
            var t = asm.MainModule.GetType(typeName);
            if (t == null) continue;

            Console.WriteLine($"\n========================================================");
            Console.WriteLine($"TYPE: {t.FullName}");
            Console.WriteLine($"========================================================");
            
            Console.WriteLine("--- FIELDS ---");
            foreach (var f in t.Fields)
            {
                Console.WriteLine($"  {f.FieldType.FullName} {f.Name} (const: {f.Constant})");
            }

            Console.WriteLine("--- PROPERTIES ---");
            foreach (var p in t.Properties)
            {
                Console.WriteLine($"  {p.PropertyType.FullName} {p.Name}");
            }

            Console.WriteLine("--- METHODS ---");
            foreach (var m in t.Methods)
            {
                Console.WriteLine($"\n  METHOD: {m.ReturnType.FullName} {m.Name}({string.Join(", ", m.Parameters.Select(p => p.ParameterType.Name + " " + p.Name))})");
                if (m.HasBody)
                {
                    foreach (var ins in m.Body.Instructions)
                    {
                        if (ins.OpCode == OpCodes.Ldstr || ins.OpCode == OpCodes.Call || ins.OpCode == OpCodes.Callvirt || ins.OpCode == OpCodes.Ldfld || ins.OpCode == OpCodes.Stfld)
                        {
                            Console.WriteLine($"    {ins.OpCode} {ins.Operand}");
                        }
                    }
                }
            }
        }
    }
}

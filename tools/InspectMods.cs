using System;
using System.IO;
using System.Linq;
using Mono.Cecil;
using Mono.Cecil.Cil;

class InspectMods
{
    static void Main(string[] args)
    {
        string gameData = "/home/astra/vint2/gamez/steamapps/common/112 Operator/Operator 112_Data/Managed";
        string mainDll = Path.Combine(gameData, "Main.dll.original");
        if (!File.Exists(mainDll)) mainDll = Path.Combine(gameData, "Main.dll");

        var resolver = new DefaultAssemblyResolver();
        resolver.AddSearchDirectory(gameData);

        using (var asm = AssemblyDefinition.ReadAssembly(mainDll, new ReaderParameters { AssemblyResolver = resolver }))
        {
            var types = asm.MainModule.Types
                .SelectMany(GetAllTypes)
                .Where(t => t.FullName.StartsWith("com.jutsugames") && 
                            (t.FullName.IndexOf("Mod", StringComparison.OrdinalIgnoreCase) >= 0 ||
                             t.FullName.IndexOf("Workshop", StringComparison.OrdinalIgnoreCase) >= 0))
                .ToList();

            Console.WriteLine($"Found {types.Count} types in com.jutsugames related to Mod/Workshop:");
            foreach (var t in types)
            {
                Console.WriteLine($"\n=== TYPE: {t.FullName} ===");
                foreach (var f in t.Fields)
                {
                    Console.WriteLine($"  Field: {f.FieldType.Name} {f.Name} = {f.Constant}");
                }
                foreach (var m in t.Methods)
                {
                    Console.WriteLine($"  Method: {m.ReturnType.Name} {m.Name}({string.Join(", ", m.Parameters.Select(pr => pr.ParameterType.Name + " " + pr.Name))})");
                    if (m.HasBody)
                    {
                        var ldstrs = m.Body.Instructions
                            .Where(i => i.OpCode == OpCodes.Ldstr)
                            .Select(i => (string)i.Operand)
                            .Distinct()
                            .ToList();
                        if (ldstrs.Count > 0)
                        {
                            Console.WriteLine($"    Strings: {string.Join(" | ", ldstrs.Select(s => $"\"{s}\""))}");
                        }
                    }
                }
            }
        }
    }

    static System.Collections.Generic.IEnumerable<TypeDefinition> GetAllTypes(TypeDefinition type)
    {
        yield return type;
        foreach (var nested in type.NestedTypes)
        {
            foreach (var t in GetAllTypes(nested))
                yield return t;
        }
    }
}

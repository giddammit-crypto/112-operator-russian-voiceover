using System;
using System.IO;
using System.Linq;
using Mono.Cecil;

class FindModsLoader
{
    static void Main(string[] args)
    {
        string gameData = "/home/astra/vint2/gamez/steamapps/common/112 Operator/Operator 112_Data/Managed";
        var resolver = new DefaultAssemblyResolver();
        resolver.AddSearchDirectory(gameData);

        foreach (var dll in Directory.GetFiles(gameData, "*.dll"))
        {
            try
            {
                using var asm = AssemblyDefinition.ReadAssembly(dll, new ReaderParameters { AssemblyResolver = resolver });
                foreach (var t in asm.MainModule.Types.SelectMany(GetAllTypes))
                {
                    if (t.Name.IndexOf("Mod", StringComparison.OrdinalIgnoreCase) >= 0 &&
                        !t.Name.Contains("Modifier") && !t.Name.Contains("Module"))
                    {
                        Console.WriteLine($"Assembly: {Path.GetFileName(dll)} -> {t.FullName}");
                    }
                }
            }
            catch { }
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

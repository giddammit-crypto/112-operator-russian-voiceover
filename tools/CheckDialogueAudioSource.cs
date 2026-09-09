using System;
using System.IO;
using System.Linq;
using Mono.Cecil;

class CheckDialogueAudioSource
{
    static void Main(string[] args)
    {
        string gameData = "/home/astra/vint2/gamez/steamapps/common/112 Operator/Operator 112_Data/Managed";
        string mainDll = Path.Combine(gameData, "Main.dll.original");
        if (!File.Exists(mainDll)) mainDll = Path.Combine(gameData, "Main.dll");

        var resolver = new DefaultAssemblyResolver();
        resolver.AddSearchDirectory(gameData);

        using var asm = AssemblyDefinition.ReadAssembly(mainDll, new ReaderParameters { AssemblyResolver = resolver });
        var t = asm.MainModule.GetType("com.jutsugames.operator112.gamelogic.calls.CallWindow");

        var f = t.Fields.FirstOrDefault(f => f.Name == "dialogueAudioSource");
        if (f != null)
        {
            Console.WriteLine($"dialogueAudioSource visibility: isPublic={f.IsPublic}, isFamily={f.IsFamily}, isPrivate={f.IsPrivate}");
        }

        var convField = t.Fields.FirstOrDefault(f => f.Name == "currentConv");
        if (convField != null)
        {
            Console.WriteLine($"currentConv visibility: isPublic={convField.IsPublic}, isPrivate={convField.IsPrivate}");
        }
    }
}

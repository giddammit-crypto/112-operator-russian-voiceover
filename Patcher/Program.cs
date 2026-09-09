using System;
using System.IO;
using System.Linq;
using Mono.Cecil;
using Mono.Cecil.Cil;

class Program
{
    static void Main(string[] args)
    {
        string gameData = "/home/astra/vint2/gamez/steamapps/common/112 Operator/Operator 112_Data/Managed";
        string mainDll = Path.Combine(gameData, "Main.dll");
        string mainBak = mainDll + ".original";
        string modDll = Path.Combine(gameData, "RussianRadioMod.dll");

        if (!File.Exists(mainDll))
        {
            Console.WriteLine("Main.dll not found: " + mainDll);
            return;
        }

        if (!File.Exists(mainBak))
        {
            File.Copy(mainDll, mainBak);
            Console.WriteLine("Backed up Main.dll -> Main.dll.original");
        }

        var resolver = new DefaultAssemblyResolver();
        resolver.AddSearchDirectory(gameData);

        var readerParams = new ReaderParameters 
        { 
            ReadWrite = true, 
            AssemblyResolver = resolver 
        };

        using (var asmMain = AssemblyDefinition.ReadAssembly(mainDll, readerParams))
        using (var asmMod = AssemblyDefinition.ReadAssembly(modDll, new ReaderParameters { AssemblyResolver = resolver }))
        {
            var appInitType = asmMain.MainModule.GetType("com.jutsugames.operator112.AppInit");
            if (appInitType == null)
            {
                Console.WriteLine("AppInit type not found!");
                return;
            }

            var targetMethod = appInitType.Methods.FirstOrDefault(m => m.Name == "OnBeforeSceneLoadRuntimeMethod");
            if (targetMethod == null)
            {
                Console.WriteLine("OnBeforeSceneLoadRuntimeMethod not found!");
                return;
            }

            var modManagerType = asmMod.MainModule.GetType("RussianRadioMod.RussianRadioManager");
            var modInitMethod = modManagerType.Methods.FirstOrDefault(m => m.Name == "OnGameStart");
            if (modInitMethod == null)
            {
                Console.WriteLine("RussianRadioManager.OnGameStart not found!");
                return;
            }

            var importedInit = asmMain.MainModule.ImportReference(modInitMethod);

            // Check if AppInit already injected
            bool alreadyInjectedInit = targetMethod.Body.Instructions.Any(ins => 
                ins.OpCode == OpCodes.Call && ins.Operand is MethodReference mr && mr.Name == "OnGameStart");

            if (!alreadyInjectedInit)
            {
                var il = targetMethod.Body.GetILProcessor();
                var firstIns = targetMethod.Body.Instructions[0];
                var callIns = il.Create(OpCodes.Call, importedInit);
                il.InsertBefore(firstIns, callIns);
                Console.WriteLine("Injected call to RussianRadioManager.OnGameStart()");
            }
            else
            {
                Console.WriteLine("AppInit hook already present");
            }

            // Hook CallWindow.SetDialogueAudio
            var callWinType = asmMain.MainModule.GetType("com.jutsugames.operator112.gamelogic.calls.CallWindow");
            if (callWinType == null)
            {
                Console.WriteLine("CallWindow type not found!");
                return;
            }

            var setAudioMethod = callWinType.Methods.FirstOrDefault(m => m.Name == "SetDialogueAudio" && m.Parameters.Count == 2);
            if (setAudioMethod == null)
            {
                Console.WriteLine("SetDialogueAudio method not found!");
                return;
            }

            var modCallMethod = modManagerType.Methods.FirstOrDefault(m => m.Name == "OnSetDialogueAudio");
            if (modCallMethod == null)
            {
                Console.WriteLine("RussianRadioManager.OnSetDialogueAudio not found!");
                return;
            }

            var importedCallHook = asmMain.MainModule.ImportReference(modCallMethod);

            bool alreadyInjectedCall = setAudioMethod.Body.Instructions.Any(ins => 
                ins.OpCode == OpCodes.Call && ins.Operand is MethodReference mr && mr.Name == "OnSetDialogueAudio");

            if (!alreadyInjectedCall)
            {
                var il = setAudioMethod.Body.GetILProcessor();
                var firstIns = setAudioMethod.Body.Instructions[0];

                // Inject:
                // ldarg.0 (this / CallWindow)
                // ldarg.1 (ConversationElement)
                // call RussianRadioManager.OnSetDialogueAudio(CallWindow, ConversationElement)
                var ldarg0 = il.Create(OpCodes.Ldarg_0);
                var ldarg1 = il.Create(OpCodes.Ldarg_1);
                var callHook = il.Create(OpCodes.Call, importedCallHook);

                il.InsertBefore(firstIns, ldarg0);
                il.InsertBefore(firstIns, ldarg1);
                il.InsertBefore(firstIns, callHook);
                Console.WriteLine("Injected call to RussianRadioManager.OnSetDialogueAudio() into CallWindow.SetDialogueAudio()");
            }
            else
            {
                Console.WriteLine("CallWindow.SetDialogueAudio hook already present");
            }

            asmMain.Write();
            Console.WriteLine("Successfully wrote patched Main.dll!");
        }
    }
}

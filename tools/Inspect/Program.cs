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
        string mainDll = Path.Combine(gameData, "Main.dll.original");
        if (!File.Exists(mainDll)) mainDll = Path.Combine(gameData, "Main.dll");

        var resolver = new DefaultAssemblyResolver();
        resolver.AddSearchDirectory(gameData);
        var readerParams = new ReaderParameters { AssemblyResolver = resolver };

        using (var asm = AssemblyDefinition.ReadAssembly(mainDll, readerParams))
        {
            var callWin = asm.MainModule.GetType("com.jutsugames.operator112.gamelogic.calls.CallWindow");
            Console.WriteLine("=== CallWindow Fields ===");
            foreach (var f in callWin.Fields)
            {
                Console.WriteLine($"{f.FieldType.Name} {f.Name}");
            }

            Console.WriteLine("\n=== CallWindow Methods ===");
            foreach (var m in callWin.Methods)
            {
                string pars = string.Join(", ", m.Parameters.Select(p => $"{p.ParameterType.Name} {p.Name}"));
                Console.WriteLine($"{m.ReturnType.Name} {m.Name}({pars})");
            }

            var convElem = asm.MainModule.GetType("com.jutsugames.operator112.gamelogic.calls.ConversationElement");
            Console.WriteLine("\n=== ConversationElement Fields ===");
            foreach (var f in convElem.Fields)
            {
                Console.WriteLine($"{f.FieldType.Name} {f.Name}");
            }

            var conv = asm.MainModule.GetType("com.jutsugames.operator112.gamelogic.calls.Conversation");
            Console.WriteLine("\n=== Conversation Fields ===");
            foreach (var f in conv.Fields)
            {
                Console.WriteLine($"{f.FieldType.Name} {f.Name}");
            }

            var setDiag = callWin.Methods.FirstOrDefault(m => m.Name == "SetDialogueAudio");
            if (setDiag != null)
            {
                Console.WriteLine("\n=== IL of SetDialogueAudio ===");
                foreach (var ins in setDiag.Body.Instructions)
                {
                    Console.WriteLine($"  {ins.Offset:x4}: {ins.OpCode} {ins.Operand}");
                }
            }

            var printCaller = callWin.Methods.FirstOrDefault(m => m.Name == "PrintCaller");
            if (printCaller != null)
            {
                Console.WriteLine("\n=== IL of PrintCaller ===");
                foreach (var ins in printCaller.Body.Instructions)
                {
                    Console.WriteLine($"  {ins.Offset:x4}: {ins.OpCode} {ins.Operand}");
                }
            }

            var printOp = callWin.Methods.FirstOrDefault(m => m.Name == "PrintOperator");
            if (printOp != null)
            {
                Console.WriteLine("\n=== IL of PrintOperator ===");
                foreach (var ins in printOp.Body.Instructions)
                {
                    Console.WriteLine($"  {ins.Offset:x4}: {ins.OpCode} {ins.Operand}");
                }
            }
            var printText = callWin.Methods.FirstOrDefault(m => m.Name == "PrintText");
            if (printText != null)
            {
                Console.WriteLine("\n=== IL of PrintText ===");
                foreach (var ins in printText.Body.Instructions)
                {
                    Console.WriteLine($"  {ins.Offset:x4}: {ins.OpCode} {ins.Operand}");
                }
            }
        }
    }
}

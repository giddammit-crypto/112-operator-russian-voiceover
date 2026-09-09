using System;
using System.IO;
using System.Collections.Generic;

class TestCreateModConfig
{
    static void Main(string[] args)
    {
        string pfxMods = "/home/astra/vint2/gamez/steamapps/compatdata/793460/pfx/drive_c/users/steamuser/AppData/LocalLow/JutsuGames/112 Operator/MyMods";
        string modDir = Path.Combine(pfxMods, "RussianRadioVoiceover");
        Directory.CreateDirectory(modDir);
        Directory.CreateDirectory(Path.Combine(modDir, "LANGUAGES"));

        // Standard JSON format for ModConfig
        string json = @"
{
  ""title"": ""Russian Radio Voiceover (Русская озвучка)"",
  ""desc"": ""Качественная русская озвучка переговоров по рации (мужские и женские голоса, эмоции, фоновый радиоэфир)."",
  ""language"": ""ru"",
  ""visibility"": ""public"",
  ""order"": 1,
  ""modTypes"": [
    ""LANGUAGES""
  ]
}";
        File.WriteAllText(Path.Combine(modDir, "config.json"), json.Trim());
        Console.WriteLine("Created config.json in " + modDir);
    }
}

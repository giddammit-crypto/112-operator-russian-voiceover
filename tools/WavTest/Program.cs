using System;
using System.IO;

class Program
{
    static void Main(string[] args)
    {
        string path = "/home/astra/.gemini/antigravity/scratch/operator112_russian_voice_mod/test_caller.wav";
        if (!File.Exists(path))
        {
            Console.WriteLine("File not found: " + path);
            return;
        }

        byte[] wavBytes = File.ReadAllBytes(path);
        using (var ms = new MemoryStream(wavBytes))
        using (var reader = new BinaryReader(ms))
        {
            string riff = new string(reader.ReadChars(4));
            uint riffSize = reader.ReadUInt32();
            string wave = new string(reader.ReadChars(4));
            if (riff != "RIFF" || wave != "WAVE")
            {
                Console.WriteLine("Invalid WAV header");
                return;
            }

            short format = 0;
            short channels = 0;
            int sampleRate = 0;
            short bitsPerSample = 0;
            byte[] dataBytes = null;

            while (ms.Position < ms.Length)
            {
                string chunkId = new string(reader.ReadChars(4));
                uint chunkSize = reader.ReadUInt32();

                if (chunkId == "fmt ")
                {
                    format = reader.ReadInt16();
                    channels = reader.ReadInt16();
                    sampleRate = reader.ReadInt32();
                    int byteRate = reader.ReadInt32();
                    short blockAlign = reader.ReadInt16();
                    bitsPerSample = reader.ReadInt16();
                    if (chunkSize > 16)
                    {
                        reader.ReadBytes((int)(chunkSize - 16));
                    }
                }
                else if (chunkId == "data")
                {
                    dataBytes = reader.ReadBytes((int)chunkSize);
                    break;
                }
                else
                {
                    reader.ReadBytes((int)chunkSize);
                }
            }

            Console.WriteLine($"WAV parsed: Format={format}, Channels={channels}, Rate={sampleRate}, Bits={bitsPerSample}, DataBytes={dataBytes?.Length}");
            
            // Convert to float array (interleaved if stereo)
            int sampleCount = dataBytes.Length / (bitsPerSample / 8);
            float[] samples = new float[sampleCount];
            for (int i = 0; i < sampleCount; i++)
            {
                short val = BitConverter.ToInt16(dataBytes, i * 2);
                samples[i] = val / 32768f;
            }
            Console.WriteLine($"Successfully extracted {samples.Length} float samples! Duration: {(float)samples.Length / channels / sampleRate:F2}s");
        }
    }
}

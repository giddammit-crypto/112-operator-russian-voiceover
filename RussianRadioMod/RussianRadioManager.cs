using System;
using System.IO;
using System.Collections.Generic;
using System.Reflection;
using UnityEngine;
using UnityEngine.SceneManagement;
using com.jutsugames.operator112.UI.ingame;
using com.jutsugames.operator112.gamelogic;
using com.jutsugames.operator112.gamelogic.audio;
using com.jutsugames.operator112.gamelogic.calls;

namespace RussianRadioMod
{
    public class RussianRadioManager : MonoBehaviour
    {
        private static bool isInitialized = false;
        private static string baseDir;
        private static string callsBaseDir;
        private static readonly Dictionary<string, AudioClip[]> male1Cache = new Dictionary<string, AudioClip[]>(StringComparer.OrdinalIgnoreCase);
        private static readonly Dictionary<string, AudioClip[]> male2Cache = new Dictionary<string, AudioClip[]>(StringComparer.OrdinalIgnoreCase);
        private static readonly Dictionary<string, AudioClip[]> female1Cache = new Dictionary<string, AudioClip[]>(StringComparer.OrdinalIgnoreCase);
        private static readonly Dictionary<string, AudioClip[]> female2Cache = new Dictionary<string, AudioClip[]>(StringComparer.OrdinalIgnoreCase);
        private static readonly Dictionary<string, AudioClip> callsCache = new Dictionary<string, AudioClip>(StringComparer.OrdinalIgnoreCase);
        private static AudioClip[] chatterCache = null;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]
        public static void OnGameStart()
        {
            try
            {
                if (isInitialized) return;

                string[] candidatePaths = new string[]
                {
                    Path.Combine(Application.streamingAssetsPath, "Audio", "RussianRadio"),
                    Application.streamingAssetsPath.Replace('\\', '/') + "/Audio/RussianRadio",
                    Path.Combine(Application.dataPath, "StreamingAssets", "Audio", "RussianRadio"),
                    Path.Combine(Directory.GetCurrentDirectory(), "Operator 112_Data", "StreamingAssets", "Audio", "RussianRadio")
                };

                foreach (var p in candidatePaths)
                {
                    if (Directory.Exists(p))
                    {
                        baseDir = p;
                        break;
                    }
                }

                if (string.IsNullOrEmpty(baseDir))
                {
                    baseDir = Path.Combine(Application.streamingAssetsPath, "Audio", "RussianRadio");
                }

                Debug.Log("[RussianRadioMod] Selected baseDir: " + baseDir);
                if (!Directory.Exists(baseDir))
                {
                    Debug.LogWarning("[RussianRadioMod] Base directory not found on disk: " + baseDir);
                }

                string[] candidateCallPaths = new string[]
                {
                    Path.Combine(Application.streamingAssetsPath, "Audio", "RussianCalls"),
                    Application.streamingAssetsPath.Replace('\\', '/') + "/Audio/RussianCalls",
                    Path.Combine(Application.dataPath, "StreamingAssets", "Audio", "RussianCalls"),
                    Path.Combine(Directory.GetCurrentDirectory(), "Operator 112_Data", "StreamingAssets", "Audio", "RussianCalls")
                };

                foreach (var p in candidateCallPaths)
                {
                    if (Directory.Exists(p))
                    {
                        callsBaseDir = p;
                        break;
                    }
                }

                if (string.IsNullOrEmpty(callsBaseDir))
                {
                    callsBaseDir = Path.Combine(Application.streamingAssetsPath, "Audio", "RussianCalls");
                }

                Debug.Log("[RussianRadioMod] Selected callsBaseDir: " + callsBaseDir);

                GameObject go = new GameObject("RussianRadioManager");
                DontDestroyOnLoad(go);
                go.AddComponent<RussianRadioManager>();
                isInitialized = true;
                Debug.Log("[RussianRadioMod] Manager successfully instantiated and hooked!");
            }
            catch (Exception ex)
            {
                Debug.LogError("[RussianRadioMod] Exception during OnGameStart: " + ex);
            }
        }

        private void Awake()
        {
            SceneManager.sceneLoaded += OnSceneLoaded;
        }

        private void OnDestroy()
        {
            SceneManager.sceneLoaded -= OnSceneLoaded;
        }

        private void OnSceneLoaded(Scene scene, LoadSceneMode mode)
        {
            Debug.Log("[RussianRadioMod] Scene loaded: " + scene.name + ", attempting to patch radio libraries...");
            ApplyPatches();
        }

        private void Update()
        {
            // Check regularly to catch dynamically loaded libraries or singletons
            if (Time.frameCount % 60 == 0)
            {
                ApplyPatches();
            }
        }

        public static void ApplyPatches()
        {
            try
            {
                if (!Directory.Exists(baseDir)) return;

                // 1. Patch ScriptableObjectLibrary instance if available
                try
                {
                    if (ScriptableObjectLibrary.instance != null && ScriptableObjectLibrary.instance.radioMessageLibrary != null)
                    {
                        PatchRadioLibrary(ScriptableObjectLibrary.instance.radioMessageLibrary);
                    }
                }
                catch (Exception ex)
                {
                    Debug.LogWarning("[RussianRadioMod] Note while checking ScriptableObjectLibrary: " + ex.Message);
                }

                // 2. Patch all RadioMessageLibrary ScriptableObjects loaded in memory
                try
                {
                    RadioMessageLibrary[] libs = Resources.FindObjectsOfTypeAll<RadioMessageLibrary>();
                    if (libs != null && libs.Length > 0)
                    {
                        foreach (var lib in libs)
                        {
                            PatchRadioLibrary(lib);
                        }
                    }
                }
                catch (Exception ex)
                {
                    Debug.LogWarning("[RussianRadioMod] Note while finding RadioMessageLibrary: " + ex.Message);
                }

                // 3. Patch RadioChatter via AudioManager singleton
                try
                {
                    if (AudioManager.instance != null && AudioManager.instance.radioChatter != null)
                    {
                        PatchRadioChatter(AudioManager.instance.radioChatter);
                    }
                }
                catch (Exception ex)
                {
                    Debug.LogWarning("[RussianRadioMod] Note while checking AudioManager: " + ex.Message);
                }
            }
            catch (Exception ex)
            {
                Debug.LogError("[RussianRadioMod] Error in ApplyPatches: " + ex);
            }
        }

        private static void PatchRadioLibrary(RadioMessageLibrary lib)
        {
            if (lib == null) return;

            // Patch standard unit radio messages
            if (lib.radioMessages != null && lib.radioMessages.Count > 0)
            {
                int patchedCount = 0;
                for (int i = 0; i < lib.radioMessages.Count; i++)
                {
                    RadioMessage msg = lib.radioMessages[i];
                    if (msg == null || string.IsNullOrEmpty(msg.id)) continue;

                    // Skip if already patched
                    if (msg.audioMale != null && msg.audioMale.Length > 0 && msg.audioMale[0] != null && msg.audioMale[0].name.StartsWith("ru_"))
                    {
                        continue;
                    }

                    string id = msg.id;
                    AudioClip[] m1 = GetOrLoadClips("Male1", id, male1Cache);
                    if (m1 != null && m1.Length > 0) msg.audioMale = m1;

                    AudioClip[] m2 = GetOrLoadClips("Male2", id, male2Cache);
                    if (m2 != null && m2.Length > 0) msg.secondAudioMale = m2;

                    AudioClip[] f1 = GetOrLoadClips("Female1", id, female1Cache);
                    if (f1 != null && f1.Length > 0) msg.audioFemale = f1;

                    AudioClip[] f2 = GetOrLoadClips("Female2", id, female2Cache);
                    if (f2 != null && f2.Length > 0) msg.secondAudioFemale = f2;

                    msg.useVoice = true;
                    patchedCount++;
                }

                if (patchedCount > 0)
                {
                    Debug.Log($"[RussianRadioMod] Successfully injected Russian voiceovers into {patchedCount} radio messages in library '{lib.name}'!");
                }
            }

            // Patch dispatcher radio messages
            if (lib.dispatcherRadioMessages != null && lib.dispatcherRadioMessages.Count > 0)
            {
                int patchedDispatcherCount = 0;
                for (int i = 0; i < lib.dispatcherRadioMessages.Count; i++)
                {
                    RadioMessageDispatcher msg = lib.dispatcherRadioMessages[i];
                    if (msg == null || string.IsNullOrEmpty(msg.id)) continue;

                    if (msg.audioMale != null && msg.audioMale.Length > 0 && msg.audioMale[0] != null && msg.audioMale[0].name.StartsWith("ru_"))
                    {
                        continue;
                    }

                    string id = msg.id;
                    AudioClip[] m1 = GetOrLoadClips("Male1", id, male1Cache);
                    if (m1 != null && m1.Length > 0) msg.audioMale = m1;

                    AudioClip[] m2 = GetOrLoadClips("Male2", id, male2Cache);
                    if (m2 != null && m2.Length > 0) msg.secondAudioMale = m2;

                    AudioClip[] f1 = GetOrLoadClips("Female1", id, female1Cache);
                    if (f1 != null && f1.Length > 0) msg.audioFemale = f1;

                    AudioClip[] f2 = GetOrLoadClips("Female2", id, female2Cache);
                    if (f2 != null && f2.Length > 0) msg.secondAudioFemale = f2;

                    msg.useVoice = true;
                    patchedDispatcherCount++;
                }

                if (patchedDispatcherCount > 0)
                {
                    Debug.Log($"[RussianRadioMod] Successfully injected Russian voiceovers into {patchedDispatcherCount} dispatcher messages in library '{lib.name}'!");
                }
            }
        }

        private static void PatchRadioChatter(RadioChatter rc)
        {
            if (rc == null) return;

            FieldInfo chatterField = typeof(RadioChatter).GetField("chatter", BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
            if (chatterField == null) return;

            AudioClip[] existing = chatterField.GetValue(rc) as AudioClip[];
            if (existing != null && existing.Length > 0 && existing[0] != null && existing[0].name.StartsWith("ru_"))
            {
                return; // Already patched
            }

            if (chatterCache == null)
            {
                string chatterDir = Path.Combine(baseDir, "Chatter");
                if (Directory.Exists(chatterDir))
                {
                    string[] wavFiles = Directory.GetFiles(chatterDir, "*.wav");
                    List<AudioClip> clips = new List<AudioClip>();
                    foreach (var f in wavFiles)
                    {
                        AudioClip c = LoadWav(f, "ru_chatter_" + Path.GetFileNameWithoutExtension(f));
                        if (c != null) clips.Add(c);
                    }
                    chatterCache = clips.ToArray();
                }
            }

            if (chatterCache != null && chatterCache.Length > 0)
            {
                chatterField.SetValue(rc, chatterCache);
                Debug.Log($"[RussianRadioMod] Injected {chatterCache.Length} Russian background chatter tracks into RadioChatter!");
            }
        }

        private static AudioClip[] GetOrLoadClips(string folderName, string messageId, Dictionary<string, AudioClip[]> cache)
        {
            // Кэш хранит и отрицательный результат (null): без этого движок
            // сканировал бы диск заново для каждого несуществующего id
            // при каждом вызове ApplyPatches (раз в 60 кадров).
            if (cache.TryGetValue(messageId, out var existing))
            {
                return existing;
            }

            string folder = Path.Combine(baseDir, folderName);
            if (!Directory.Exists(folder))
            {
                cache[messageId] = null;
                return null;
            }

            string[] files = Directory.GetFiles(folder, messageId + "_*.wav");
            if (files.Length == 0)
            {
                files = Directory.GetFiles(folder, messageId + ".wav");
            }

            if (files.Length == 0)
            {
                // Запасной путь: сопоставление без учёта регистра —
                // разные сборки игры пишут id то camelCase, то в нижнем регистре.
                List<string> matches = new List<string>();
                foreach (var f in Directory.GetFiles(folder, "*.wav"))
                {
                    string stem = Path.GetFileNameWithoutExtension(f);
                    int underscore = stem.LastIndexOf('_');
                    string baseName = underscore > 0 ? stem.Substring(0, underscore) : stem;
                    if (string.Equals(baseName, messageId, StringComparison.OrdinalIgnoreCase) ||
                        string.Equals(stem, messageId, StringComparison.OrdinalIgnoreCase))
                    {
                        matches.Add(f);
                    }
                }
                files = matches.ToArray();
            }

            if (files.Length == 0)
            {
                cache[messageId] = null;
                return null;
            }

            // Стабильный порядок дублей: _1, _2, _10 (а не лексикографически).
            Array.Sort(files, CompareByTrailingIndex);

            List<AudioClip> clips = new List<AudioClip>();
            for (int i = 0; i < files.Length; i++)
            {
                string clipName = $"ru_{folderName}_{messageId}_{i + 1}";
                AudioClip c = LoadWav(files[i], clipName);
                if (c != null) clips.Add(c);
            }

            AudioClip[] res = clips.Count > 0 ? clips.ToArray() : null;
            cache[messageId] = res;
            return res;
        }

        private static int CompareByTrailingIndex(string a, string b)
        {
            int ia = TrailingIndexOf(a);
            int ib = TrailingIndexOf(b);
            if (ia != ib) return ia.CompareTo(ib);
            return string.Compare(a, b, StringComparison.OrdinalIgnoreCase);
        }

        private static int TrailingIndexOf(string path)
        {
            string stem = Path.GetFileNameWithoutExtension(path);
            int u = stem.LastIndexOf('_');
            if (u >= 0 && u < stem.Length - 1 && int.TryParse(stem.Substring(u + 1), out int n))
            {
                return n;
            }
            return 0;
        }

        public static void OnSetDialogueAudio(CallWindow window, ConversationElement ce)
        {
            try
            {
                if (ce == null || ce.conversation == null) return;
                string callId = ce.conversation.id;
                string optId = ce.id;
                if (string.IsNullOrEmpty(callId) || string.IsNullOrEmpty(optId)) return;

                AudioClip clip = GetOrLoadCallClip(callId, optId);
                if (clip != null)
                {
                    ce.voice = clip;
                    ce.audioResponse = null;
                    if (window != null && window.dialogueAudioSource != null)
                    {
                        window.dialogueAudioSource.clip = clip;
                    }
                    Debug.Log($"[RussianRadioMod] Injected Russian dialogue audio for call '{callId}', option '{optId}' (duration: {clip.length:F2}s)");
                }
            }
            catch (Exception ex)
            {
                Debug.LogError("[RussianRadioMod] Exception in OnSetDialogueAudio: " + ex);
            }
        }

        public static AudioClip GetOrLoadCallClip(string callId, string optionId)
        {
            string key = $"{callId}/{optionId}";
            if (callsCache.TryGetValue(key, out var cached))
            {
                return cached;
            }

            if (string.IsNullOrEmpty(callsBaseDir) || !Directory.Exists(callsBaseDir))
            {
                return null;
            }

            string file = Path.Combine(callsBaseDir, callId, optionId + ".wav");
            if (!File.Exists(file))
            {
                // Отрицательный результат тоже кэшируем: диалоговое окно
                // дёргает этот метод на каждую реплику, а без озвучки
                // остаются только вызовы вне русской локализации.
                callsCache[key] = null;
                return null;
            }

            string clipName = $"ru_call_{callId}_{optionId}";
            AudioClip clip = LoadWav(file, clipName);
            if (clip != null)
            {
                callsCache[key] = clip;
            }
            return clip;
        }

        public static AudioClip LoadWav(string filePath, string clipName)
        {
            try
            {
                byte[] wavBytes = File.ReadAllBytes(filePath);
                using (var ms = new MemoryStream(wavBytes))
                using (var reader = new BinaryReader(ms))
                {
                    string riff = new string(reader.ReadChars(4));
                    uint riffSize = reader.ReadUInt32();
                    string wave = new string(reader.ReadChars(4));
                    if (riff != "RIFF" || wave != "WAVE") return null;

                    short format = 0;
                    short channels = 0;
                    int sampleRate = 0;
                    short bitsPerSample = 0;
                    byte[] dataBytes = null;

                    while (ms.Position < ms.Length - 8)
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
                            if (chunkSize > 16) reader.ReadBytes((int)(chunkSize - 16));
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

                    if (format != 1 || channels == 0 || sampleRate == 0 || bitsPerSample != 16 || dataBytes == null)
                    {
                        return null;
                    }

                    int sampleCount = dataBytes.Length / 2;
                    float[] samples = new float[sampleCount];
                    for (int i = 0; i < sampleCount; i++)
                    {
                        short val = BitConverter.ToInt16(dataBytes, i * 2);
                        samples[i] = val / 32768f;
                    }

                    int totalFrames = sampleCount / channels;
                    AudioClip clip = AudioClip.Create(clipName, totalFrames, (int)channels, sampleRate, false);
                    clip.SetData(samples, 0);
                    return clip;
                }
            }
            catch (Exception ex)
            {
                Debug.LogError($"[RussianRadioMod] Failed to load WAV: {filePath} error: {ex.Message}");
                return null;
            }
        }
    }
}

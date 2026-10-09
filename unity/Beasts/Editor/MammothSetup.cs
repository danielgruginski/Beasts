using System;
using System.IO;
using System.Text;
using UnityEditor;
using UnityEngine;
using static Beasts.EditorTools.BeastSetupUtil;
using Object = UnityEngine.Object;

namespace Beasts.EditorTools
{
    /// <summary>
    /// Builds the woolly mammoth from the files exported by Blender (Assets/Beasts/Models, Textures):
    ///   Mammoth.fbx            Generic rig, avatar from this model, Motion = root-motion node, sockets kept (Head,
    ///                          Mouth, Back (a rider or howdah on the hump), Trunk (its tip), TuskL/R (the tips))
    ///   Anims/Mammoth@*.fbx    one clip each, avatar copied from Mammoth.fbx; loop flags, root motion and animation
    ///                          events (OnBeastEvent: Bite on the TuskSwipe's hook and the Stomp's slam, Roar on the
    ///                          Trumpet, Dead) from Anims/mammoth_clips.json
    ///   Materials              M_Mammoth (reddish brown), M_Mammoth_Dark (near black); smoothness from the alpha
    ///   Prefabs/Mammoth        Animator + BeastAppearance (coat, size) + BeastEvents
    ///   Animation/MammothAnims clip pools for BeastRandomAnimator (Sleep leads into Wake)
    /// then the test scene (BeastsTestScene). Runs once by itself the first time the files are imported; afterwards
    /// Tools > Beasts > Rebuild Mammoth. A report and renders go to Logs/MammothSetup.
    /// </summary>
    [InitializeOnLoad]
    public static class MammothSetup
    {
        const string ModelPath = Models + "/Mammoth.fbx";
        public const string PrefabPath = Prefabs + "/Mammoth.prefab";
        public const string SetPath = SetDir + "/MammothAnims.asset";

        static PoolDef[] Pools() => new[]
        {
            new PoolDef("Idle", 2f, "Idle") { h0 = 3f, h1 = 6 },
            new PoolDef("Graze", 1.2f, "Graze") { h0 = 4f, h1 = 8 },
            new PoolDef("Walk", 2f, "Walk") { moves = true, h0 = 3, h1 = 6 },
            new PoolDef("Run", 0.6f, "Run") { moves = true, h0 = 1.5f, h1 = 3 },
            new PoolDef("Charge", 0.4f, "Charge") { moves = true, h0 = 1.2f, h1 = 2f, next = "Idle" },
            new PoolDef("Trumpet", 0.4f, "Trumpet") { next = "Idle" },
            new PoolDef("TuskSwipe", 1.0f, "TuskSwipe") { next = "Idle" },
            new PoolDef("Stomp", 0.5f, "Stomp") { next = "Idle" },
            new PoolDef("Sleep", 0.3f, "Sleep") { h0 = 4f, h1 = 7f, next = "Wake" },
            new PoolDef("Wake", 0f, "Wake") { next = "Idle" },
            new PoolDef("Hit", 0.4f, "Hit") { next = "Idle" },
            new PoolDef("Death", 0.15f, "Death") { after = 2.5f, next = "Wake" },
        };

        static MammothSetup() => EditorApplication.delayCall += () => AutoBuild(20);

        static void AutoBuild(int retries)
        {
            if (!File.Exists(ModelPath) || File.Exists(PrefabPath)) return;
            bool ready = AssetImporter.GetAtPath(ModelPath) is ModelImporter &&
                         AssetDatabase.LoadAssetAtPath<Texture2D>(Textures + "/T_Mammoth.png") != null &&
                         !EditorApplication.isCompiling && !EditorApplication.isUpdating;
            if (ready) Build();
            else if (retries > 0) EditorApplication.delayCall += () => AutoBuild(retries - 1);
        }

        [MenuItem("Tools/Beasts/Rebuild Mammoth")]
        public static void Build() => Run(true);

        /// <summary>scenes: also rebuild the test scene and the renders.</summary>
        public static void Run(bool scenes)
        {
            var dir = OutDir("MammothSetup");
            Directory.CreateDirectory(dir);
            var log = new StringBuilder();
            Application.LogCallback onLog = (c, s, t) => { if (t != LogType.Log) log.AppendLine($"[{t}] {c}"); };
            Application.logMessageReceived += onLog;
            try
            {
                EnsureFolders();
                foreach (var t in new[] { "T_Mammoth", "T_Mammoth_Dark" }) ConfigureSmoothnessTexture($"{Textures}/{t}.png");
                var brown = MakeLit("M_Mammoth", Textures + "/T_Mammoth.png", Color.white);
                var dark = MakeLit("M_Mammoth_Dark", Textures + "/T_Mammoth_Dark.png", Color.white);

                var (avatar, motionPath, model) = ConfigureModel(ModelPath, new[] { ("M_Mammoth", brown) }, log);
                var clips = ConfigureClips("Mammoth", Anims + "/mammoth_clips.json", avatar, motionPath, EventFunction, log);
                MakeSet("MammothAnims", Pools(), clips, log);

                var go = NewCreature(model, avatar, "Mammoth");
                var look = go.GetComponent<BeastAppearance>() ?? go.AddComponent<BeastAppearance>();
                look.skins = new[] { brown, brown, dark };     // listed more often = more likely
                look.scale = new Vector2(0.92f, 1.06f);
                if (go.GetComponent<BeastEvents>() == null) go.AddComponent<BeastEvents>();
                var prefab = PrefabUtility.SaveAsPrefabAsset(go, PrefabPath);
                Object.DestroyImmediate(go);
                log.AppendLine("  prefab: " + PrefabPath);

                if (scenes)
                {
                    BeastsTestScene.Build(log);
                    BeastsTestScene.RenderLineup(prefab, clips, new (string, float)[]
                    {
                        ("Idle", 1f), ("Walk", 0.4f), ("Charge", 0.2f), ("Trumpet", 0.8f), ("TuskSwipe", 0.55f),
                        ("Stomp", 0.85f), ("Graze", 2.2f), ("Sleep", 1f), ("Death", 2.5f),
                    }, dir, 4.6f, 1.6f, log);
                }
                AssetDatabase.SaveAssets();
                log.AppendLine("OK");
            }
            catch (Exception e)
            {
                log.AppendLine("EXCEPTION " + e);
            }
            finally
            {
                Application.logMessageReceived -= onLog;
                File.WriteAllText(Path.Combine(dir, "setup_report.txt"), log.ToString());
                Debug.Log("Mammoth setup finished: " + Path.Combine(dir, "setup_report.txt"));
            }
        }
    }
}

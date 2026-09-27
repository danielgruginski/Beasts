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
    /// Builds the wolf from the files exported by Blender (Assets/Beasts/Models, Textures):
    ///   Wolf.fbx            Generic rig, avatar from this model, Motion = root-motion node, sockets kept
    ///   Anims/Wolf@*.fbx    one clip each, avatar copied from Wolf.fbx; loop flags, root motion and animation events
    ///                       (OnBeastEvent: Bite, Howl, Dead) from Anims/wolf_clips.json
    ///   Materials           M_Wolf (grey), M_Wolf_Black, M_Wolf_White, M_Wolf_Brown (grey coat, tinted);
    ///                       smoothness from the texture's alpha
    ///   Prefabs/Wolf        Animator + BeastAppearance (coat, size) + BeastEvents
    ///   Animation/WolfAnims clip pools for BeastRandomAnimator
    /// then the test scene (BeastsTestScene). Runs once by itself the first time the files are imported; afterwards
    /// Tools > Beasts > Rebuild Wolf. A report and renders go to Logs/WolfSetup.
    /// </summary>
    [InitializeOnLoad]
    public static class WolfSetup
    {
        const string ModelPath = Models + "/Wolf.fbx";
        public const string PrefabPath = Prefabs + "/Wolf.prefab";
        public const string SetPath = SetDir + "/WolfAnims.asset";

        static PoolDef[] Pools() => new[]
        {
            new PoolDef("Idle", 2f, "Idle", "IdlePant") { h0 = 3, h1 = 6 },
            new PoolDef("Walk", 2.2f, "Walk") { moves = true, h0 = 3, h1 = 6 },
            new PoolDef("Trot", 1.6f, "Trot") { moves = true, h0 = 2, h1 = 5 },
            new PoolDef("Run", 0.7f, "Run") { moves = true, h0 = 1.5f, h1 = 3 },
            new PoolDef("Threat", 0.8f, "Threat") { next = "Bite" },
            new PoolDef("Bite", 1.2f, "Bite") { next = "Idle" },
            new PoolDef("Lunge", 0.8f, "Lunge") { next = "Idle" },
            new PoolDef("Howl", 0.5f, "Howl") { next = "Idle" },
            new PoolDef("Hit", 0.5f, "Hit") { next = "Idle" },
            new PoolDef("Death", 0.25f, "Death") { after = 2f, next = "GetUp" },
            new PoolDef("GetUp", 0f, "GetUp") { next = "Idle" },
        };

        static WolfSetup() => EditorApplication.delayCall += () => AutoBuild(20);

        static void AutoBuild(int retries)
        {
            if (!File.Exists(ModelPath) || File.Exists(PrefabPath)) return;
            bool ready = AssetImporter.GetAtPath(ModelPath) is ModelImporter &&
                         AssetDatabase.LoadAssetAtPath<Texture2D>(Textures + "/T_Wolf.png") != null &&
                         !EditorApplication.isCompiling && !EditorApplication.isUpdating;
            if (ready) Build();
            else if (retries > 0) EditorApplication.delayCall += () => AutoBuild(retries - 1);
        }

        [MenuItem("Tools/Beasts/Rebuild Wolf")]
        public static void Build() => Run(true);

        /// <summary>scenes: also rebuild the test scene and the renders.</summary>
        public static void Run(bool scenes)
        {
            var dir = OutDir("WolfSetup");
            Directory.CreateDirectory(dir);
            var log = new StringBuilder();
            Application.LogCallback onLog = (c, s, t) => { if (t != LogType.Log) log.AppendLine($"[{t}] {c}"); };
            Application.logMessageReceived += onLog;
            try
            {
                EnsureFolders();
                foreach (var t in new[] { "T_Wolf", "T_Wolf_Black", "T_Wolf_White" }) ConfigureSmoothnessTexture($"{Textures}/{t}.png");
                var grey = MakeLit("M_Wolf", Textures + "/T_Wolf.png", Color.white);
                var black = MakeLit("M_Wolf_Black", Textures + "/T_Wolf_Black.png", Color.white);
                var white = MakeLit("M_Wolf_White", Textures + "/T_Wolf_White.png", Color.white);
                var brown = MakeLit("M_Wolf_Brown", Textures + "/T_Wolf.png", new Color(1f, 0.86f, 0.70f));

                var (avatar, motionPath, model) = ConfigureModel(ModelPath, new[] { ("M_Wolf", grey) }, log);
                var clips = ConfigureClips("Wolf", Anims + "/wolf_clips.json", avatar, motionPath, EventFunction, log);
                MakeSet("WolfAnims", Pools(), clips, log);

                var go = NewCreature(model, avatar, "Wolf");
                var look = go.GetComponent<BeastAppearance>() ?? go.AddComponent<BeastAppearance>();
                look.skins = new[] { grey, grey, grey, brown, black, white };     // listed more often = more likely
                look.scale = new Vector2(0.92f, 1.1f);
                if (go.GetComponent<BeastEvents>() == null) go.AddComponent<BeastEvents>();
                var prefab = PrefabUtility.SaveAsPrefabAsset(go, PrefabPath);
                Object.DestroyImmediate(go);
                log.AppendLine("  prefab: " + PrefabPath);

                if (scenes)
                {
                    BeastsTestScene.Build(log);
                    BeastsTestScene.RenderLineup(prefab, clips, new (string, float)[]
                    {
                        ("Idle", 1f), ("Walk", 0.25f), ("Trot", 0.2f), ("Run", 0.15f), ("Bite", 0.4f), ("Lunge", 0.65f),
                        ("Howl", 1.5f), ("Death", 2.1f),
                    }, dir, 2.2f, 0.5f, log);
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
                Debug.Log("Wolf setup finished: " + Path.Combine(dir, "setup_report.txt"));
            }
        }
    }
}

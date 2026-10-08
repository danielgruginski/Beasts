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
    /// Builds the cave bear from the files exported by Blender (Assets/Beasts/Models, Textures):
    ///   Bear.fbx             Generic rig, avatar from this model, Motion = root-motion node, sockets kept (Head, Mouth,
    ///                        Back, PawL/R)
    ///   Anims/Bear@*.fbx     one clip each, avatar copied from Bear.fbx; loop flags, root motion and animation events
    ///                        (OnBeastEvent: Bite on the Swipe's rake, the Bite, the Slam's crash and the Hug's crush;
    ///                        Roar; Dead) from Anims/bear_clips.json
    ///   Materials            M_Bear (dark brown), M_Bear_Old (greyer, more scars); smoothness from the texture's alpha
    ///   Prefabs/Bear         Animator + BeastAppearance (coat, size) + BeastEvents
    ///   Animation/BearAnims  clip pools for BeastRandomAnimator (Sleep leads into Wake)
    /// then the test scene (BeastsTestScene). Runs once by itself the first time the files are imported; afterwards
    /// Tools > Beasts > Rebuild Bear. A report and renders go to Logs/BearSetup.
    /// </summary>
    [InitializeOnLoad]
    public static class BearSetup
    {
        const string ModelPath = Models + "/Bear.fbx";
        public const string PrefabPath = Prefabs + "/Bear.prefab";
        public const string SetPath = SetDir + "/BearAnims.asset";

        static PoolDef[] Pools() => new[]
        {
            new PoolDef("Idle", 2f, "Idle") { h0 = 2.5f, h1 = 5 },
            new PoolDef("Walk", 2f, "Walk") { moves = true, h0 = 3, h1 = 6 },
            new PoolDef("Run", 0.8f, "Run") { moves = true, h0 = 1.5f, h1 = 3 },
            new PoolDef("Swipe", 1.2f, "Swipe") { next = "Idle" },
            new PoolDef("Bite", 0.8f, "Bite") { next = "Idle" },
            new PoolDef("Slam", 0.5f, "Slam") { next = "Idle" },
            new PoolDef("Hug", 0.4f, "Hug") { next = "Idle" },
            new PoolDef("Rear", 0.4f, "Rear") { next = "Idle" },
            new PoolDef("Roar", 0.4f, "Roar") { next = "Idle" },
            new PoolDef("Sleep", 0.3f, "Sleep") { h0 = 4f, h1 = 7f, next = "Wake" },
            new PoolDef("Wake", 0f, "Wake") { next = "Idle" },
            new PoolDef("Hit", 0.4f, "Hit") { next = "Idle" },
            new PoolDef("Death", 0.15f, "Death") { after = 2.5f, next = "Wake" },
        };

        static BearSetup() => EditorApplication.delayCall += () => AutoBuild(20);

        static void AutoBuild(int retries)
        {
            if (!File.Exists(ModelPath) || File.Exists(PrefabPath)) return;
            bool ready = AssetImporter.GetAtPath(ModelPath) is ModelImporter &&
                         AssetDatabase.LoadAssetAtPath<Texture2D>(Textures + "/T_Bear.png") != null &&
                         !EditorApplication.isCompiling && !EditorApplication.isUpdating;
            if (ready) Build();
            else if (retries > 0) EditorApplication.delayCall += () => AutoBuild(retries - 1);
        }

        [MenuItem("Tools/Beasts/Rebuild Bear")]
        public static void Build() => Run(true);

        /// <summary>scenes: also rebuild the test scene and the renders.</summary>
        public static void Run(bool scenes)
        {
            var dir = OutDir("BearSetup");
            Directory.CreateDirectory(dir);
            var log = new StringBuilder();
            Application.LogCallback onLog = (c, s, t) => { if (t != LogType.Log) log.AppendLine($"[{t}] {c}"); };
            Application.logMessageReceived += onLog;
            try
            {
                EnsureFolders();
                foreach (var t in new[] { "T_Bear", "T_Bear_Old" }) ConfigureSmoothnessTexture($"{Textures}/{t}.png");
                var brown = MakeLit("M_Bear", Textures + "/T_Bear.png", Color.white);
                var old = MakeLit("M_Bear_Old", Textures + "/T_Bear_Old.png", Color.white);

                var (avatar, motionPath, model) = ConfigureModel(ModelPath, new[] { ("M_Bear", brown) }, log);
                var clips = ConfigureClips("Bear", Anims + "/bear_clips.json", avatar, motionPath, EventFunction, log);
                MakeSet("BearAnims", Pools(), clips, log);

                var go = NewCreature(model, avatar, "Bear");
                var look = go.GetComponent<BeastAppearance>() ?? go.AddComponent<BeastAppearance>();
                look.skins = new[] { brown, brown, old };      // listed more often = more likely
                look.scale = new Vector2(0.92f, 1.08f);
                if (go.GetComponent<BeastEvents>() == null) go.AddComponent<BeastEvents>();
                var prefab = PrefabUtility.SaveAsPrefabAsset(go, PrefabPath);
                Object.DestroyImmediate(go);
                log.AppendLine("  prefab: " + PrefabPath);

                if (scenes)
                {
                    BeastsTestScene.Build(log);
                    BeastsTestScene.RenderLineup(prefab, clips, new (string, float)[]
                    {
                        ("Idle", 1f), ("Walk", 0.3f), ("Run", 0.2f), ("Swipe", 0.45f), ("Bite", 0.45f), ("Slam", 0.55f),
                        ("Hug", 0.75f), ("Rear", 1.35f), ("Sleep", 1f), ("Death", 2f),
                    }, dir, 3.2f, 1.0f, log);
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
                Debug.Log("Bear setup finished: " + Path.Combine(dir, "setup_report.txt"));
            }
        }
    }
}

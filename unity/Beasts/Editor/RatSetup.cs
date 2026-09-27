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
    /// Builds the giant rat from the files exported by Blender (Assets/Beasts/Models, Textures):
    ///   Rat.fbx             Generic rig, avatar from this model, Motion = root-motion node, sockets kept
    ///   Anims/Rat@*.fbx     one clip each, avatar copied from Rat.fbx; loop flags, root motion and animation events
    ///                       (OnBeastEvent: Bite, Dead) from Anims/rat_clips.json
    ///   Materials           M_Rat (brown), M_Rat_Black, M_Rat_Plague; smoothness from the texture's alpha
    ///   Prefabs/Rat         Animator + BeastAppearance (coat, size) + BeastEvents
    ///   Animation/RatAnims  clip pools for BeastRandomAnimator
    /// then the test scene (BeastsTestScene). Runs once by itself the first time the files are imported; afterwards
    /// Tools > Beasts > Rebuild Rat. A report and renders go to Logs/RatSetup.
    /// </summary>
    [InitializeOnLoad]
    public static class RatSetup
    {
        const string ModelPath = Models + "/Rat.fbx";
        public const string PrefabPath = Prefabs + "/Rat.prefab";
        public const string SetPath = SetDir + "/RatAnims.asset";

        static PoolDef[] Pools() => new[]
        {
            new PoolDef("Idle", 2f, "Idle") { h0 = 2, h1 = 5 },
            new PoolDef("Rear", 0.8f, "Rear") { next = "Idle" },
            new PoolDef("Walk", 2.2f, "Walk") { moves = true, h0 = 2, h1 = 5 },
            new PoolDef("Run", 1.0f, "Run") { moves = true, h0 = 1.5f, h1 = 3 },
            new PoolDef("Threat", 0.7f, "Threat") { next = "Bite" },
            new PoolDef("Bite", 1.2f, "Bite") { next = "Idle" },
            new PoolDef("Lunge", 0.8f, "Lunge") { next = "Idle" },
            new PoolDef("Hit", 0.5f, "Hit") { next = "Idle" },
            new PoolDef("Death", 0.25f, "Death") { after = 2f, next = "GetUp" },
            new PoolDef("GetUp", 0f, "GetUp") { next = "Idle" },
        };

        static RatSetup() => EditorApplication.delayCall += () => AutoBuild(20);

        static void AutoBuild(int retries)
        {
            if (!File.Exists(ModelPath) || File.Exists(PrefabPath)) return;
            bool ready = AssetImporter.GetAtPath(ModelPath) is ModelImporter &&
                         AssetDatabase.LoadAssetAtPath<Texture2D>(Textures + "/T_Rat.png") != null &&
                         !EditorApplication.isCompiling && !EditorApplication.isUpdating;
            if (ready) Build();
            else if (retries > 0) EditorApplication.delayCall += () => AutoBuild(retries - 1);
        }

        [MenuItem("Tools/Beasts/Rebuild Rat")]
        public static void Build() => Run(true);

        /// <summary>scenes: also rebuild the test scene and the renders.</summary>
        public static void Run(bool scenes)
        {
            var dir = OutDir("RatSetup");
            Directory.CreateDirectory(dir);
            var log = new StringBuilder();
            Application.LogCallback onLog = (c, s, t) => { if (t != LogType.Log) log.AppendLine($"[{t}] {c}"); };
            Application.logMessageReceived += onLog;
            try
            {
                EnsureFolders();
                foreach (var t in new[] { "T_Rat", "T_Rat_Black", "T_Rat_Plague" }) ConfigureSmoothnessTexture($"{Textures}/{t}.png");
                var brown = MakeLit("M_Rat", Textures + "/T_Rat.png", Color.white);
                var black = MakeLit("M_Rat_Black", Textures + "/T_Rat_Black.png", Color.white);
                var plague = MakeLit("M_Rat_Plague", Textures + "/T_Rat_Plague.png", Color.white);

                var (avatar, motionPath, model) = ConfigureModel(ModelPath, new[] { ("M_Rat", brown) }, log);
                var clips = ConfigureClips("Rat", Anims + "/rat_clips.json", avatar, motionPath, EventFunction, log);
                MakeSet("RatAnims", Pools(), clips, log);

                var go = NewCreature(model, avatar, "Rat");
                var look = go.GetComponent<BeastAppearance>() ?? go.AddComponent<BeastAppearance>();
                look.skins = new[] { brown, brown, brown, black, plague };     // listed more often = more likely
                look.scale = new Vector2(0.85f, 1.15f);
                if (go.GetComponent<BeastEvents>() == null) go.AddComponent<BeastEvents>();
                var prefab = PrefabUtility.SaveAsPrefabAsset(go, PrefabPath);
                Object.DestroyImmediate(go);
                log.AppendLine("  prefab: " + PrefabPath);

                if (scenes)
                {
                    BeastsTestScene.Build(log);
                    BeastsTestScene.RenderLineup(prefab, clips, new (string, float)[]
                    {
                        ("Idle", 1f), ("Rear", 1.2f), ("Walk", 0.2f), ("Run", 0.15f), ("Bite", 0.35f), ("Lunge", 0.55f),
                        ("Threat", 1f), ("Death", 1.8f),
                    }, dir, 1.4f, 0.25f, log);
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
                Debug.Log("Rat setup finished: " + Path.Combine(dir, "setup_report.txt"));
            }
        }
    }
}

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
    /// Builds the red deer stag from the files exported by Blender (Assets/Beasts/Models, Textures):
    ///   Deer.fbx               Generic rig, avatar from this model, Motion = root-motion node, sockets kept (Head,
    ///                          Mouth, Back, AntlerL/R)
    ///   Anims/Deer@*.fbx       one clip each, avatar copied from Deer.fbx; loop flags, root motion and animation events
    ///                          (OnBeastEvent: Bite on the Attack's antler hook, Dead) from Anims/deer_clips.json
    ///   Materials              M_Deer (grey-brown, russet back); smoothness from the alpha
    ///   Prefabs/Deer           Animator + BeastAppearance (coat, size) + BeastEvents
    ///   Animation/DeerAnims    clip pools for BeastRandomAnimator (Alert after grazing; Sleep leads into Wake)
    /// then the test scene (BeastsTestScene). Runs once by itself the first time the files are imported; afterwards
    /// Tools > Beasts > Rebuild Deer. A report and renders go to Logs/DeerSetup.
    /// </summary>
    [InitializeOnLoad]
    public static class DeerSetup
    {
        const string ModelPath = Models + "/Deer.fbx";
        public const string PrefabPath = Prefabs + "/Deer.prefab";
        public const string SetPath = SetDir + "/DeerAnims.asset";

        static PoolDef[] Pools() => new[]
        {
            new PoolDef("Idle", 1.5f, "Idle") { h0 = 3f, h1 = 6 },
            new PoolDef("Graze", 2f, "Graze") { h0 = 4f, h1 = 9, next = "Alert" },
            new PoolDef("Alert", 0.5f, "Alert") { h0 = 1.5f, h1 = 2.5f, next = "Idle" },
            new PoolDef("Walk", 2f, "Walk") { moves = true, h0 = 3, h1 = 6 },
            new PoolDef("Trot", 0.8f, "Trot") { moves = true, h0 = 2, h1 = 4 },
            new PoolDef("Run", 0.5f, "Run") { moves = true, h0 = 1.2f, h1 = 2.5f },
            new PoolDef("Attack", 0.3f, "Attack") { next = "Idle" },
            new PoolDef("Sleep", 0.3f, "Sleep") { h0 = 4f, h1 = 7f, next = "Wake" },
            new PoolDef("Wake", 0f, "Wake") { next = "Idle" },
            new PoolDef("Hit", 0.3f, "Hit") { next = "Idle" },
            new PoolDef("Death", 0.15f, "Death") { after = 2.5f, next = "Wake" },
        };

        static DeerSetup() => EditorApplication.delayCall += () => AutoBuild(20);

        static void AutoBuild(int retries)
        {
            if (!File.Exists(ModelPath) || File.Exists(PrefabPath)) return;
            bool ready = AssetImporter.GetAtPath(ModelPath) is ModelImporter &&
                         AssetDatabase.LoadAssetAtPath<Texture2D>(Textures + "/T_Deer.png") != null &&
                         !EditorApplication.isCompiling && !EditorApplication.isUpdating && !EditorApplication.isPlaying;
            if (ready) Build();
            else if (retries > 0) EditorApplication.delayCall += () => AutoBuild(retries - 1);
        }

        [MenuItem("Tools/Beasts/Rebuild Deer")]
        public static void Build() => Run(true);

        /// <summary>scenes: also rebuild the test scene and the renders.</summary>
        public static void Run(bool scenes)
        {
            var dir = OutDir("DeerSetup");
            Directory.CreateDirectory(dir);
            var log = new StringBuilder();
            Application.LogCallback onLog = (c, s, t) => { if (t != LogType.Log) log.AppendLine($"[{t}] {c}"); };
            Application.logMessageReceived += onLog;
            try
            {
                EnsureFolders();
                ConfigureSmoothnessTexture($"{Textures}/T_Deer.png");
                var coat = MakeLit("M_Deer", Textures + "/T_Deer.png", Color.white);

                var (avatar, motionPath, model) = ConfigureModel(ModelPath, new[] { ("M_Deer", coat) }, log);
                var clips = ConfigureClips("Deer", Anims + "/deer_clips.json", avatar, motionPath, EventFunction, log);
                MakeSet("DeerAnims", Pools(), clips, log);

                var go = NewCreature(model, avatar, "Deer");
                var look = go.GetComponent<BeastAppearance>() ?? go.AddComponent<BeastAppearance>();
                look.skins = new[] { coat };
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
                        ("Idle", 1f), ("Graze", 2.2f), ("Alert", 1.2f), ("Walk", 0.5f), ("Trot", 0.3f), ("Run", 0.2f),
                        ("Attack", 0.5f), ("Sleep", 1f), ("Death", 2.2f),
                    }, dir, 3.4f, 1.3f, log);
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
                Debug.Log("Deer setup finished: " + Path.Combine(dir, "setup_report.txt"));
            }
        }
    }
}

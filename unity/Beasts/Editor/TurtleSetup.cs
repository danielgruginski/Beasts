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
    /// Builds the giant turtle (2026-10-23) from the files exported by Blender (Assets/Beasts/Models, Textures):
    ///   Turtle.fbx            Generic rig, avatar from this model, Motion = root-motion node, sockets kept (Socket_Head,
    ///                         Socket_Mouth, Socket_Back on the shell's top); one skinned mesh, TurtleBody (skin and shell)
    ///   Anims/Turtle@*.fbx    seven clips (Idle, Walk, Bite, Withdraw, Emerge, Hit, Death), avatar copied from
    ///                         Turtle.fbx; loop flags, root motion (Walk) and animation events (OnBeastEvent: Bite, Dead)
    ///                         from Anims/turtle_clips.json
    ///   Materials             M_Turtle; smoothness from the texture's alpha
    ///   Prefabs/Turtle        Animator + BeastAppearance (size) + BeastEvents
    ///   Animation/TurtleAnims clip pools for BeastRandomAnimator (Withdraw holds, then Emerge)
    /// No scene is touched (the game side is to come). Runs once by itself the first time the files are imported;
    /// afterwards Tools > Beasts > Rebuild Turtle. A report and renders (in a preview scene) go to Logs/TurtleSetup.
    /// </summary>
    [InitializeOnLoad]
    public static class TurtleSetup
    {
        const string ModelPath = Models + "/Turtle.fbx";
        public const string PrefabPath = Prefabs + "/Turtle.prefab";
        public const string SetPath = SetDir + "/TurtleAnims.asset";

        static PoolDef[] Pools() => new[]
        {
            new PoolDef("Idle", 2.5f, "Idle") { h0 = 4, h1 = 8 },
            new PoolDef("Walk", 2f, "Walk") { moves = true, h0 = 4, h1 = 8 },
            new PoolDef("Bite", 0.8f, "Bite") { next = "Idle" },
            new PoolDef("Withdraw", 0.5f, "Withdraw") { after = 3f, next = "Emerge" },
            new PoolDef("Emerge", 0f, "Emerge") { next = "Idle" },
            new PoolDef("Hit", 0.4f, "Hit") { next = "Idle" },
            new PoolDef("Death", 0.15f, "Death") { after = 2.5f, next = "Idle" },
        };

        static TurtleSetup() => EditorApplication.delayCall += () => AutoBuild(20);

        static void AutoBuild(int retries)
        {
            if (!File.Exists(ModelPath) || File.Exists(PrefabPath)) return;
            bool ready = AssetImporter.GetAtPath(ModelPath) is ModelImporter &&
                         AssetDatabase.LoadAssetAtPath<Texture2D>(Textures + "/T_Turtle.png") != null &&
                         !EditorApplication.isCompiling && !EditorApplication.isUpdating &&
                         !EditorApplication.isPlayingOrWillChangePlaymode;
            if (ready) Build();
            else if (retries > 0) EditorApplication.delayCall += () => AutoBuild(retries - 1);
        }

        [MenuItem("Tools/Beasts/Rebuild Turtle")]
        public static void Build() => Run(true);

        /// <summary>renders: also the lineup renders (a preview scene; the open scenes are never touched).</summary>
        public static void Run(bool renders)
        {
            var dir = OutDir("TurtleSetup");
            Directory.CreateDirectory(dir);
            var log = new StringBuilder();
            Application.LogCallback onLog = (c, s, t) => { if (t != LogType.Log) log.AppendLine($"[{t}] {c}"); };
            Application.logMessageReceived += onLog;
            try
            {
                EnsureFolders();
                ConfigureSmoothnessTexture(Textures + "/T_Turtle.png");
                var hide = MakeLit("M_Turtle", Textures + "/T_Turtle.png", Color.white);

                var (avatar, motionPath, model) = ConfigureModel(ModelPath, new[] { ("M_Turtle", hide) }, log);
                var clips = ConfigureClips("Turtle", Anims + "/turtle_clips.json", avatar, motionPath, EventFunction, log);
                MakeSet("TurtleAnims", Pools(), clips, log);

                var go = NewCreature(model, avatar, "Turtle");
                var look = go.GetComponent<BeastAppearance>() ?? go.AddComponent<BeastAppearance>();
                look.skins = new[] { hide };
                look.scale = new Vector2(0.9f, 1.1f);
                if (go.GetComponent<BeastEvents>() == null) go.AddComponent<BeastEvents>();
                var prefab = PrefabUtility.SaveAsPrefabAsset(go, PrefabPath);
                Object.DestroyImmediate(go);
                log.AppendLine("  prefab: " + PrefabPath);

                if (renders)
                {
                    BeastsTestScene.RenderLineup(prefab, clips, new (string, float)[]
                    {
                        ("Idle", 2.8f), ("Walk", 0.4f), ("Bite", 0.53f), ("Withdraw", 1.2f), ("Emerge", 0.6f),
                        ("Hit", 0.1f), ("Death", 2.5f),
                    }, dir, 4.2f, 0.7f, log, 1.8f);
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
                Debug.Log("Turtle setup finished: " + Path.Combine(dir, "setup_report.txt"));
            }
        }
    }
}

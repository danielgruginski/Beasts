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
    /// Builds the zombie wolf (2026-10-23) from the files exported by Blender (Assets/Beasts/Models, Textures):
    ///   ZombieWolf.fbx           Generic rig, avatar from this model, Motion = root-motion node, sockets kept. It is the
    ///                            wolf's skeleton under the same node name (WolfRig), so the wolf's clips bind to it too
    ///   Anims/ZombieWolf@*.fbx   the wolf's twelve clips keyed on it, avatar copied from ZombieWolf.fbx; loop flags,
    ///                            root motion and animation events (OnBeastEvent: Bite, Howl, Dead) from
    ///                            Anims/zombiewolf_clips.json
    ///   Materials                M_ZombieWolf (grey), M_ZombieWolf_Dark, M_ZombieWolf_Pale; smoothness from the
    ///                            textures' alpha
    ///   Prefabs/ZombieWolf       Animator + BeastAppearance (coat, size) + BeastEvents
    ///   Animation/ZombieWolfAnims  clip pools for BeastRandomAnimator (the wolf's)
    /// No scene is touched: it is not added to Beasts_Test (the game side is to come). Runs once by itself the first time
    /// the files are imported; afterwards Tools > Beasts > Rebuild Zombie Wolf. A report and renders (in a preview scene)
    /// go to Logs/ZombieWolfSetup.
    /// </summary>
    [InitializeOnLoad]
    public static class ZombieWolfSetup
    {
        const string ModelPath = Models + "/ZombieWolf.fbx";
        public const string PrefabPath = Prefabs + "/ZombieWolf.prefab";
        public const string SetPath = SetDir + "/ZombieWolfAnims.asset";

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

        static ZombieWolfSetup() => EditorApplication.delayCall += () => AutoBuild(20);

        static void AutoBuild(int retries)
        {
            if (!File.Exists(ModelPath) || File.Exists(PrefabPath)) return;
            bool ready = AssetImporter.GetAtPath(ModelPath) is ModelImporter &&
                         AssetDatabase.LoadAssetAtPath<Texture2D>(Textures + "/T_ZombieWolf.png") != null &&
                         !EditorApplication.isCompiling && !EditorApplication.isUpdating;
            if (ready) Build();
            else if (retries > 0) EditorApplication.delayCall += () => AutoBuild(retries - 1);
        }

        [MenuItem("Tools/Beasts/Rebuild Zombie Wolf")]
        public static void Build() => Run(true);

        /// <summary>renders: also the lineup renders (a preview scene; the open scenes are never touched).</summary>
        public static void Run(bool renders)
        {
            var dir = OutDir("ZombieWolfSetup");
            Directory.CreateDirectory(dir);
            var log = new StringBuilder();
            Application.LogCallback onLog = (c, s, t) => { if (t != LogType.Log) log.AppendLine($"[{t}] {c}"); };
            Application.logMessageReceived += onLog;
            try
            {
                EnsureFolders();
                foreach (var t in new[] { "T_ZombieWolf", "T_ZombieWolf_Dark", "T_ZombieWolf_Pale" })
                    ConfigureSmoothnessTexture($"{Textures}/{t}.png");
                var grey = MakeLit("M_ZombieWolf", Textures + "/T_ZombieWolf.png", Color.white);
                var dark = MakeLit("M_ZombieWolf_Dark", Textures + "/T_ZombieWolf_Dark.png", Color.white);
                var pale = MakeLit("M_ZombieWolf_Pale", Textures + "/T_ZombieWolf_Pale.png", Color.white);

                var (avatar, motionPath, model) = ConfigureModel(ModelPath, new[] { ("M_ZombieWolf", grey) }, log);
                var clips = ConfigureClips("ZombieWolf", Anims + "/zombiewolf_clips.json", avatar, motionPath, EventFunction, log);
                MakeSet("ZombieWolfAnims", Pools(), clips, log);

                var go = NewCreature(model, avatar, "ZombieWolf");
                var look = go.GetComponent<BeastAppearance>() ?? go.AddComponent<BeastAppearance>();
                look.skins = new[] { grey, grey, grey, dark, pale };          // listed more often = more likely
                look.scale = new Vector2(0.94f, 1.06f);
                if (go.GetComponent<BeastEvents>() == null) go.AddComponent<BeastEvents>();
                var prefab = PrefabUtility.SaveAsPrefabAsset(go, PrefabPath);
                Object.DestroyImmediate(go);
                log.AppendLine("  prefab: " + PrefabPath);

                if (renders)
                {
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
                Debug.Log("Zombie wolf setup finished: " + Path.Combine(dir, "setup_report.txt"));
            }
        }
    }
}

using System;
using System.IO;
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEngine;
using static Beasts.EditorTools.BeastSetupUtil;
using Object = UnityEngine.Object;

namespace Beasts.EditorTools
{
    /// <summary>
    /// Builds the dragon (2026-10-18) from the files exported by Blender (Assets/Beasts/Models, Textures):
    ///   Dragon.fbx          Generic rig, avatar from this model, Motion = root-motion node, Socket_Mouth kept (the fire);
    ///                       two skinned meshes: DragonBody (~32k tris) and DragonWingMembrane
    ///   Anims/Dragon@*.fbx  14 clips, avatar copied from Dragon.fbx; loop flags, root motion and animation events
    ///                       (OnBeastEvent: Bite, Fire, FireEnd, Roar, Dead, TakeOff, Land) from Anims/dragon_clips.json;
    ///                       Takeoff and Land keep their root motion's height (7 m up, 7 m down), so the dragon flies
    ///   Materials           M_Dragon (the first preset), M_Dragon_Ash, M_Dragon_Bronze and the wings' M_DragonWing* (drawn
    ///                       from both sides); smoothness from the textures' alpha, normal maps T_Dragon_Normal (scales) and
    ///                       T_DragonWing_Normal; imported at <see cref="TexSize"/> (painted at 4096)
    ///   Prefabs/Dragon      Animator + BeastAppearance (hide and matching wings, size) + BeastEvents + BeastBreath (fire
    ///                       from the mouth between the Fire clip's events)
    ///   Animation/DragonAnims clip pools for BeastRandomAnimator; "Flight" is Takeoff, Fly, Glide, Fly, Land in a row
    /// then the dragons' test scene (DragonsTestScene). Runs once by itself the first time the files are imported;
    /// afterwards Tools > Beasts > Rebuild Dragon. A report and renders go to Logs/DragonSetup.
    /// </summary>
    [InitializeOnLoad]
    public static class DragonSetup
    {
        const string ModelPath = Models + "/Dragon.fbx";
        public const string PrefabPath = Prefabs + "/Dragon.prefab";
        public const string SetPath = SetDir + "/DragonAnims.asset";
        public const int TexSize = 2048;
        static readonly string[] Presets = { "", "_Ash", "_Bronze" };
        static readonly string[] Climbing = { "Takeoff", "Land" };

        static PoolDef[] Pools() => new[]
        {
            new PoolDef("Idle", 2f, "Idle") { h0 = 4, h1 = 8 },
            new PoolDef("Walk", 1.6f, "Walk") { moves = true, h0 = 4, h1 = 8 },
            new PoolDef("Run", 0.5f, "Run") { moves = true, h0 = 2, h1 = 4 },
            new PoolDef("Bite", 0.8f, "Bite") { next = "Idle" },
            new PoolDef("Claw", 0.7f, "Claw") { next = "Idle" },
            new PoolDef("TailSweep", 0.5f, "TailSweep") { next = "Idle" },
            new PoolDef("Fire", 0.9f, "Fire") { next = "Idle" },
            new PoolDef("Roar", 0.5f, "Roar") { next = "Idle" },
            new PoolDef("Hit", 0.3f, "Hit") { next = "Idle" },
            new PoolDef("Death", 0.12f, "Death") { after = 2.5f, next = "Idle" },
            new PoolDef("Flight", 1.0f, "Takeoff", "Fly", "Glide", "Fly", "Land")
                { sequence = true, moves = true, vertical = true, h0 = 3, h1 = 6, next = "Idle" },
        };

        static DragonSetup() => EditorApplication.delayCall += () => AutoBuild(20);

        static void AutoBuild(int retries)
        {
            if (!File.Exists(ModelPath) || File.Exists(PrefabPath)) return;
            bool ready = AssetImporter.GetAtPath(ModelPath) is ModelImporter &&
                         AssetDatabase.LoadAssetAtPath<Texture2D>(Textures + "/T_Dragon.png") != null &&
                         !EditorApplication.isCompiling && !EditorApplication.isUpdating &&
                         !EditorApplication.isPlayingOrWillChangePlaymode;
            if (ready) Build();
            else if (retries > 0) EditorApplication.delayCall += () => AutoBuild(retries - 1);
        }

        [MenuItem("Tools/Beasts/Rebuild Dragon")]
        public static void Build() => Run(true);

        static SkinnedMeshRenderer Part(GameObject go, string name) =>
            go.GetComponentsInChildren<SkinnedMeshRenderer>(true).FirstOrDefault(r => r.name == name);

        /// <summary>scenes: also rebuild the test scene and the renders.</summary>
        public static void Run(bool scenes)
        {
            var dir = OutDir("DragonSetup");
            Directory.CreateDirectory(dir);
            var log = new StringBuilder();
            Application.LogCallback onLog = (c, s, t) => { if (t != LogType.Log) log.AppendLine($"[{t}] {c}"); };
            Application.logMessageReceived += onLog;
            try
            {
                EnsureFolders();
                var hides = new Material[Presets.Length];
                var wings = new Material[Presets.Length];
                for (int i = 0; i < Presets.Length; i++)
                {
                    string p = Presets[i];
                    ConfigureSmoothnessTexture($"{Textures}/T_Dragon{p}.png", TexSize);
                    ConfigureSmoothnessTexture($"{Textures}/T_DragonWing{p}.png", TexSize);
                    hides[i] = MakeLit("M_Dragon" + p, $"{Textures}/T_Dragon{p}.png", Color.white);
                    wings[i] = MakeLit("M_DragonWing" + p, $"{Textures}/T_DragonWing{p}.png", Color.white);
                    AddNormalMap(hides[i], Textures + "/T_Dragon_Normal.png", 1f, TexSize);
                    AddNormalMap(wings[i], Textures + "/T_DragonWing_Normal.png", 0.8f, TexSize);
                    MakeTwoSided(wings[i]);
                }

                var (avatar, motionPath, model) = ConfigureModel(ModelPath, new[] { ("M_Dragon", hides[0]), ("M_DragonWing", wings[0]) }, log);
                var clips = ConfigureClips("Dragon", Anims + "/dragon_clips.json", avatar, motionPath, EventFunction, log, Climbing);
                MakeSet("DragonAnims", Pools(), clips, log);

                var go = NewCreature(model, avatar, "Dragon");
                var body = Part(go, "DragonBody");
                var wing = Part(go, "DragonWingMembrane");
                var look = go.GetComponent<BeastAppearance>() ?? go.AddComponent<BeastAppearance>();
                look.target = body;
                look.skins = hides;
                look.pairedTarget = wing;
                look.pairedSkins = wings;
                look.scale = new Vector2(0.92f, 1.08f);
                if (go.GetComponent<BeastEvents>() == null) go.AddComponent<BeastEvents>();
                var breath = go.GetComponent<BeastBreath>() ?? go.AddComponent<BeastBreath>();
                breath.mouth = go.GetComponentsInChildren<Transform>(true).FirstOrDefault(t => t.name == "Socket_Mouth");
                log.AppendLine($"  Dragon.prefab: body={body != null} wing={wing != null} mouth={breath.mouth != null}");
                var prefab = PrefabUtility.SaveAsPrefabAsset(go, PrefabPath);
                Object.DestroyImmediate(go);

                if (scenes)
                {
                    DragonsTestScene.Build(log);
                    var poses = new (string, float)[]
                    {
                        ("Idle", 1f), ("Walk", 0.3f), ("Bite", 0.6f), ("Claw", 0.5f), ("Fire", 1.3f), ("Roar", 1.1f),
                        ("Takeoff", 0.9f), ("Fly", 0.3f), ("Glide", 1f), ("Death", 2.9f),
                    };
                    BeastsTestScene.RenderLineup(prefab, clips, poses, dir, 15f, 2.5f, log, 3f);
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
                Debug.Log("Dragon setup finished: " + Path.Combine(dir, "setup_report.txt"));
            }
        }
    }
}

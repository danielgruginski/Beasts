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
    /// Builds the hydra (2026-10-18) from the files exported by Blender (Assets/Beasts/Models, Textures):
    ///   Hydra.fbx           Generic rig, avatar from this model, Motion = root-motion node; two skinned meshes: HydraBody
    ///                       (~40k tris, three necks and heads) and HydraFins (back and tail fins, gill fans, toe webs)
    ///   Anims/Hydra@*.fbx   9 clips, avatar copied from Hydra.fbx; loop flags, root motion and animation events
    ///                       (OnBeastEvent: Bite, Bite2, Bite3, Roar, Dead) from Anims/hydra_clips.json
    ///   Materials           M_Hydra (sea green), M_Hydra_Swamp, M_Hydra_Abyss and the fins' M_HydraFins* (drawn from both
    ///                       sides); smoothness from the textures' alpha, normal maps T_Hydra_Normal and T_HydraFins_Normal
    ///   Prefabs/Hydra       Animator + BeastAppearance (hide and matching fins, size) + BeastEvents
    ///   Animation/HydraAnims clip pools for BeastRandomAnimator
    /// then the dragons' test scene (DragonsTestScene). Runs once by itself the first time the files are imported;
    /// afterwards Tools > Beasts > Rebuild Hydra. A report and renders go to Logs/HydraSetup.
    /// </summary>
    [InitializeOnLoad]
    public static class HydraSetup
    {
        const string ModelPath = Models + "/Hydra.fbx";
        public const string PrefabPath = Prefabs + "/Hydra.prefab";
        public const string SetPath = SetDir + "/HydraAnims.asset";
        public const int TexSize = 2048;
        static readonly string[] Presets = { "", "_Swamp", "_Abyss" };

        static PoolDef[] Pools() => new[]
        {
            new PoolDef("Idle", 2f, "Idle") { h0 = 4, h1 = 8 },
            new PoolDef("Walk", 2f, "Walk") { moves = true, h0 = 4, h1 = 8 },
            new PoolDef("Run", 0.6f, "Run") { moves = true, h0 = 2, h1 = 4 },
            new PoolDef("Bite", 1f, "Bite") { next = "Idle" },
            new PoolDef("TripleBite", 0.8f, "TripleBite") { next = "Idle" },
            new PoolDef("TailSweep", 0.5f, "TailSweep") { next = "Idle" },
            new PoolDef("Roar", 0.5f, "Roar") { next = "Idle" },
            new PoolDef("Hit", 0.3f, "Hit") { next = "Idle" },
            new PoolDef("Death", 0.12f, "Death") { after = 2.5f, next = "Idle" },
        };

        static HydraSetup() => EditorApplication.delayCall += () => AutoBuild(20);

        static void AutoBuild(int retries)
        {
            if (!File.Exists(ModelPath) || File.Exists(PrefabPath)) return;
            bool ready = AssetImporter.GetAtPath(ModelPath) is ModelImporter &&
                         AssetDatabase.LoadAssetAtPath<Texture2D>(Textures + "/T_Hydra.png") != null &&
                         !EditorApplication.isCompiling && !EditorApplication.isUpdating &&
                         !EditorApplication.isPlayingOrWillChangePlaymode;
            if (ready) Build();
            else if (retries > 0) EditorApplication.delayCall += () => AutoBuild(retries - 1);
        }

        [MenuItem("Tools/Beasts/Rebuild Hydra")]
        public static void Build() => Run(true);

        static SkinnedMeshRenderer Part(GameObject go, string name) =>
            go.GetComponentsInChildren<SkinnedMeshRenderer>(true).FirstOrDefault(r => r.name == name);

        /// <summary>scenes: also rebuild the test scene and the renders.</summary>
        public static void Run(bool scenes)
        {
            var dir = OutDir("HydraSetup");
            Directory.CreateDirectory(dir);
            var log = new StringBuilder();
            Application.LogCallback onLog = (c, s, t) => { if (t != LogType.Log) log.AppendLine($"[{t}] {c}"); };
            Application.logMessageReceived += onLog;
            try
            {
                EnsureFolders();
                var hides = new Material[Presets.Length];
                var fins = new Material[Presets.Length];
                for (int i = 0; i < Presets.Length; i++)
                {
                    string p = Presets[i];
                    ConfigureSmoothnessTexture($"{Textures}/T_Hydra{p}.png", TexSize);
                    ConfigureSmoothnessTexture($"{Textures}/T_HydraFins{p}.png", TexSize / 2);
                    hides[i] = MakeLit("M_Hydra" + p, $"{Textures}/T_Hydra{p}.png", Color.white);
                    fins[i] = MakeLit("M_HydraFins" + p, $"{Textures}/T_HydraFins{p}.png", Color.white);
                    AddNormalMap(hides[i], Textures + "/T_Hydra_Normal.png", 1f, TexSize);
                    AddNormalMap(fins[i], Textures + "/T_HydraFins_Normal.png", 0.8f, TexSize / 2);
                    MakeTwoSided(fins[i]);
                }

                var (avatar, motionPath, model) = ConfigureModel(ModelPath, new[] { ("M_Hydra", hides[0]), ("M_HydraFins", fins[0]) }, log);
                var clips = ConfigureClips("Hydra", Anims + "/hydra_clips.json", avatar, motionPath, EventFunction, log);
                MakeSet("HydraAnims", Pools(), clips, log);

                var go = NewCreature(model, avatar, "Hydra");
                var body = Part(go, "HydraBody");
                var fin = Part(go, "HydraFins");
                var look = go.GetComponent<BeastAppearance>() ?? go.AddComponent<BeastAppearance>();
                look.target = body;
                look.skins = hides;
                look.pairedTarget = fin;
                look.pairedSkins = fins;
                look.scale = new Vector2(0.92f, 1.08f);
                if (go.GetComponent<BeastEvents>() == null) go.AddComponent<BeastEvents>();
                log.AppendLine($"  Hydra.prefab: body={body != null} fins={fin != null}");
                var prefab = PrefabUtility.SaveAsPrefabAsset(go, PrefabPath);
                Object.DestroyImmediate(go);

                if (scenes)
                {
                    DragonsTestScene.Build(log);
                    var poses = new (string, float)[]
                    {
                        ("Idle", 1f), ("Walk", 0.3f), ("Run", 0.2f), ("Bite", 0.6f), ("TripleBite", 1.2f), ("TailSweep", 0.8f),
                        ("Roar", 1.0f), ("Hit", 0.1f), ("Death", 2.9f),
                    };
                    BeastsTestScene.RenderLineup(prefab, clips, poses, dir, 11f, 1.8f, log, 2.5f);
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
                Debug.Log("Hydra setup finished: " + Path.Combine(dir, "setup_report.txt"));
            }
        }
    }
}

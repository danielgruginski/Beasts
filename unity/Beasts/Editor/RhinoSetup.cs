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
    /// Builds the woolly rhino (the woods' boss) from the files exported by Blender (Assets/Beasts/Models, Textures):
    ///   Rhino.fbx             Generic rig, avatar from this model, Motion = root-motion node, sockets kept; two skinned
    ///                         meshes: RhinoBody and Spear (the snapped boar spear in its left shoulder, on the Chest bone:
    ///                         hide it once the corpse is looted)
    ///   Anims/Rhino@*.fbx     one clip each, avatar copied from Rhino.fbx; loop flags, root motion and animation events
    ///                         (OnBeastEvent: Bite on the Gore's toss and the Stamp's slam, Roar, Dead) from
    ///                         Anims/rhino_clips.json
    ///   Materials             M_Rhino; smoothness from the texture's alpha
    ///   Prefabs/Rhino         Animator + BeastEvents (a one-off boss: no random looks)
    ///   Animation/RhinoAnims  clip pools for BeastRandomAnimator (Paw leads into Charge, Sleep into Wake)
    /// then the test scene (BeastsTestScene). Runs once by itself the first time the files are imported; afterwards
    /// Tools > Beasts > Rebuild Rhino. A report and renders go to Logs/RhinoSetup.
    /// </summary>
    [InitializeOnLoad]
    public static class RhinoSetup
    {
        const string ModelPath = Models + "/Rhino.fbx";
        public const string PrefabPath = Prefabs + "/Rhino.prefab";
        public const string SetPath = SetDir + "/RhinoAnims.asset";

        static PoolDef[] Pools() => new[]
        {
            new PoolDef("Idle", 2f, "Idle") { h0 = 2.5f, h1 = 5 },
            new PoolDef("Walk", 2f, "Walk") { moves = true, h0 = 3, h1 = 6 },
            new PoolDef("Run", 0.8f, "Run") { moves = true, h0 = 1.5f, h1 = 3 },
            new PoolDef("Paw", 0.8f, "Paw") { h0 = 1.2f, h1 = 1.2f, next = "Charge" },
            new PoolDef("Charge", 0f, "Charge") { moves = true, h0 = 1.0f, h1 = 1.6f, next = "Idle" },
            new PoolDef("Gore", 1.2f, "Gore") { next = "Idle" },
            new PoolDef("Stamp", 0.5f, "Stamp") { next = "Idle" },
            new PoolDef("Roar", 0.4f, "Roar") { next = "Idle" },
            new PoolDef("Daze", 0.3f, "Daze") { h0 = 2f, h1 = 4f, next = "Idle" },
            new PoolDef("Sleep", 0.3f, "Sleep") { h0 = 4f, h1 = 7f, next = "Wake" },
            new PoolDef("Wake", 0f, "Wake") { next = "Idle" },
            new PoolDef("Hit", 0.4f, "Hit") { next = "Idle" },
            new PoolDef("Death", 0.15f, "Death") { after = 2.5f, next = "Wake" },
        };

        static RhinoSetup() => EditorApplication.delayCall += () => AutoBuild(20);

        static void AutoBuild(int retries)
        {
            if (!File.Exists(ModelPath) || File.Exists(PrefabPath)) return;
            bool ready = AssetImporter.GetAtPath(ModelPath) is ModelImporter &&
                         AssetDatabase.LoadAssetAtPath<Texture2D>(Textures + "/T_Rhino.png") != null &&
                         !EditorApplication.isCompiling && !EditorApplication.isUpdating;
            if (ready) Build();
            else if (retries > 0) EditorApplication.delayCall += () => AutoBuild(retries - 1);
        }

        [MenuItem("Tools/Beasts/Rebuild Rhino")]
        public static void Build() => Run(true);

        /// <summary>scenes: also rebuild the test scene and the renders.</summary>
        public static void Run(bool scenes)
        {
            var dir = OutDir("RhinoSetup");
            Directory.CreateDirectory(dir);
            var log = new StringBuilder();
            Application.LogCallback onLog = (c, s, t) => { if (t != LogType.Log) log.AppendLine($"[{t}] {c}"); };
            Application.logMessageReceived += onLog;
            try
            {
                EnsureFolders();
                ConfigureSmoothnessTexture(Textures + "/T_Rhino.png");
                var mat = MakeLit("M_Rhino", Textures + "/T_Rhino.png", Color.white);

                var (avatar, motionPath, model) = ConfigureModel(ModelPath, new[] { ("M_Rhino", mat) }, log);
                var spear = model.GetComponentsInChildren<SkinnedMeshRenderer>(true).FirstOrDefault(r => r.name == "Spear");
                log.AppendLine($"  spear: {(spear != null ? $"{spear.sharedMesh.triangles.Length / 3} tris, root bone {spear.rootBone?.name}" : "MISSING")}");
                var clips = ConfigureClips("Rhino", Anims + "/rhino_clips.json", avatar, motionPath, EventFunction, log);
                MakeSet("RhinoAnims", Pools(), clips, log);

                var go = NewCreature(model, avatar, "Rhino");
                if (go.GetComponent<BeastEvents>() == null) go.AddComponent<BeastEvents>();
                var prefab = PrefabUtility.SaveAsPrefabAsset(go, PrefabPath);
                Object.DestroyImmediate(go);
                log.AppendLine("  prefab: " + PrefabPath);

                if (scenes)
                {
                    BeastsTestScene.Build(log);
                    BeastsTestScene.RenderLineup(prefab, clips, new (string, float)[]
                    {
                        ("Idle", 1f), ("Paw", 0.15f), ("Charge", 0.12f), ("Gore", 0.45f), ("Stamp", 0.85f), ("Roar", 0.8f),
                        ("Daze", 0.6f), ("Sleep", 1f), ("Death", 2f),
                    }, dir, 3.6f, 0.8f, log);
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
                Debug.Log("Rhino setup finished: " + Path.Combine(dir, "setup_report.txt"));
            }
        }
    }
}

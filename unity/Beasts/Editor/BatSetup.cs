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
    /// Builds the giant bat (2026-10-23) from the files exported by Blender (Assets/Beasts/Models, Textures):
    ///   Bat.fbx            Generic rig, avatar from this model, Motion = root-motion node, sockets kept; two skinned
    ///                      meshes on one texture: BatBody (fur, arms, fingers, legs, head) and BatWing (the membranes).
    ///                      The bind pose flies: the body hangs 1.6 m over the GameObject, so the game moves it on the
    ///                      ground like the other beasts
    ///   Anims/Bat@*.fbx    seven clips (Idle, Hover, Fly, Dive, Screech, Hit, Death), avatar copied from Bat.fbx; loop
    ///                      flags, root motion (Fly) and animation events (OnBeastEvent: Bite, Screech, Dead) from
    ///                      Anims/bat_clips.json
    ///   Materials          M_Bat and M_BatWing (the same T_Bat); smoothness from the texture's alpha. BatWing has two
    ///                      layers (2026-10-23): the membrane's faces plus a flipped copy for the underside, so M_BatWing
    ///                      culls back faces like any opaque material (URP Lit drawn from both sides, _Cull 0, lit the
    ///                      underside with the upper side's normals: bright from below)
    ///   Prefabs/Bat        Animator + BeastAppearance (size) + BeastEvents
    ///   Animation/BatAnims clip pools for BeastRandomAnimator
    /// No scene is touched (the game side is to come). Runs once by itself the first time the files are imported;
    /// afterwards Tools > Beasts > Rebuild Bat. A report and renders (in a preview scene) go to Logs/BatSetup.
    /// </summary>
    [InitializeOnLoad]
    public static class BatSetup
    {
        const string ModelPath = Models + "/Bat.fbx";
        public const string PrefabPath = Prefabs + "/Bat.prefab";
        public const string SetPath = SetDir + "/BatAnims.asset";

        static PoolDef[] Pools() => new[]
        {
            new PoolDef("Idle", 2f, "Idle", "Hover") { h0 = 3, h1 = 6 },
            new PoolDef("Fly", 2f, "Fly") { moves = true, h0 = 3, h1 = 6 },
            new PoolDef("Screech", 0.5f, "Screech") { next = "Dive" },
            new PoolDef("Dive", 1.2f, "Dive") { next = "Idle" },
            new PoolDef("Hit", 0.4f, "Hit") { next = "Idle" },
            new PoolDef("Death", 0.2f, "Death") { after = 2.5f, next = "Idle" },
        };

        static BatSetup() => EditorApplication.delayCall += () => AutoBuild(20);

        static void AutoBuild(int retries)
        {
            if (!File.Exists(ModelPath) || File.Exists(PrefabPath)) return;
            bool ready = AssetImporter.GetAtPath(ModelPath) is ModelImporter &&
                         AssetDatabase.LoadAssetAtPath<Texture2D>(Textures + "/T_Bat.png") != null &&
                         !EditorApplication.isCompiling && !EditorApplication.isUpdating &&
                         !EditorApplication.isPlayingOrWillChangePlaymode;
            if (ready) Build();
            else if (retries > 0) EditorApplication.delayCall += () => AutoBuild(retries - 1);
        }

        [MenuItem("Tools/Beasts/Rebuild Bat")]
        public static void Build() => Run(true);

        static SkinnedMeshRenderer Part(GameObject go, string name) =>
            go.GetComponentsInChildren<SkinnedMeshRenderer>(true).FirstOrDefault(r => r.name == name);

        /// <summary>renders: also the lineup renders (a preview scene; the open scenes are never touched).</summary>
        public static void Run(bool renders)
        {
            var dir = OutDir("BatSetup");
            Directory.CreateDirectory(dir);
            var log = new StringBuilder();
            Application.LogCallback onLog = (c, s, t) => { if (t != LogType.Log) log.AppendLine($"[{t}] {c}"); };
            Application.logMessageReceived += onLog;
            try
            {
                EnsureFolders();
                ConfigureSmoothnessTexture(Textures + "/T_Bat.png");
                var hide = MakeLit("M_Bat", Textures + "/T_Bat.png", Color.white);
                var wingMat = MakeLit("M_BatWing", Textures + "/T_Bat.png", Color.white);
                if (wingMat.HasProperty("_Cull")) wingMat.SetFloat("_Cull", 2f);   // back faces culled: the underside is
                wingMat.doubleSidedGI = false;                                       // a layer of its own in the mesh

                var (avatar, motionPath, model) = ConfigureModel(ModelPath, new[] { ("M_Bat", hide), ("M_BatWing", wingMat) }, log);
                var clips = ConfigureClips("Bat", Anims + "/bat_clips.json", avatar, motionPath, EventFunction, log);
                MakeSet("BatAnims", Pools(), clips, log);

                var go = NewCreature(model, avatar, "Bat");
                var body = Part(go, "BatBody");
                var wing = Part(go, "BatWing");
                foreach (var r in new[] { body, wing })                  // the wings reach 1.5 m out and swing 1 m down
                    if (r != null) r.localBounds = new Bounds(r.localBounds.center, r.localBounds.size + Vector3.one * 1.2f);
                var look = go.GetComponent<BeastAppearance>() ?? go.AddComponent<BeastAppearance>();
                look.target = body;
                look.skins = new[] { hide };
                look.scale = new Vector2(0.92f, 1.08f);
                if (go.GetComponent<BeastEvents>() == null) go.AddComponent<BeastEvents>();
                log.AppendLine($"  Bat.prefab: body={body != null} wing={wing != null}" +
                               (wing != null ? $" wing tris={wing.sharedMesh.triangles.Length / 3} (two layers: 1920)" : ""));
                var prefab = PrefabUtility.SaveAsPrefabAsset(go, PrefabPath);
                Object.DestroyImmediate(go);
                log.AppendLine("  prefab: " + PrefabPath);

                if (renders)
                {
                    BeastsTestScene.RenderLineup(prefab, clips, new (string, float)[]
                    {
                        ("Idle", 0.3f), ("Hover", 0.5f), ("Fly", 0.1f), ("Fly", 0.4f), ("Dive", 0.73f), ("Screech", 1.0f),
                        ("Hit", 0.1f), ("Death", 1.9f),
                    }, dir, 3.4f, 1.1f, log, 1.6f);
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
                Debug.Log("Bat setup finished: " + Path.Combine(dir, "setup_report.txt"));
            }
        }
    }
}

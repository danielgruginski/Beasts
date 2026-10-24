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
    /// Builds the golden eagle (2026-10-24) from the files exported by Blender (Assets/Beasts/Models, Textures):
    ///   Eagle.fbx           Generic rig, avatar from this model, Motion = root-motion node, sockets kept (Socket_Head,
    ///                       Socket_Mouth, Socket_Grip on the right foot); one skinned mesh, EagleBody (body, beak, feet and
    ///                       the feather cards, each card with an underside of its own)
    ///   Anims/Eagle@*.fbx   ten clips (Idle, Walk, TakeOff, Fly, Glide, Dive, Land, Screech, Hit, Death), avatar copied
    ///                       from Eagle.fbx; loop flags, root motion (Walk, TakeOff, Fly, Glide, Dive, Land: horizontal only)
    ///                       and animation events (OnBeastEvent: Strike, Screech, Dead) from Anims/eagle_clips.json
    ///   Materials           M_Eagle (golden, T_Eagle) and M_Eagle_Bald (T_Eagle_Bald); smoothness from the textures'
    ///                       alpha; back faces culled (_Cull 2): every card that can be seen from below has a flipped copy
    ///                       of its own, so each side is lit with its own normal (URP Lit drawn from both sides lights the
    ///                       underside with the top's normal: the bat's lesson)
    ///   Prefabs/Eagle       Animator + BeastAppearance (golden or bald, size) + BeastEvents; the mesh's bounds ride on
    ///                       Hips (the clips fly the body 1.5-2.3 m over the GameObject)
    ///   Animation/EagleAnims clip pools for BeastRandomAnimator: on the ground Idle, Walk, Screech, Hit, Death and TakeOff;
    ///                       TakeOff leads to Flight (Fly, Glide, Fly, Dive, Fly, Glide in a row), Flight to Land, Land to Idle
    /// The skeleton carries the height, as the bat's does: the GameObject stays on the ground while the eagle flies 1.5 m
    /// over it (TakeOff rises, Land comes down, Dive stoops to the ground), so no pool needs `vertical` and the game moves
    /// it like any ground creature. No scene is touched. Runs once by itself the first time the files are imported;
    /// afterwards Tools > Beasts > Rebuild Eagle. A report and renders (in a preview scene) go to Logs/EagleSetup.
    /// </summary>
    [InitializeOnLoad]
    public static class EagleSetup
    {
        const string ModelPath = Models + "/Eagle.fbx";
        public const string PrefabPath = Prefabs + "/Eagle.prefab";
        public const string SetPath = SetDir + "/EagleAnims.asset";

        static PoolDef[] Pools() => new[]
        {
            new PoolDef("Idle", 2f, "Idle") { h0 = 4, h1 = 8 },
            new PoolDef("Walk", 0.8f, "Walk") { moves = true, h0 = 2, h1 = 5 },
            new PoolDef("Screech", 0.4f, "Screech") { next = "Idle" },
            new PoolDef("Hit", 0.3f, "Hit") { next = "Idle" },
            new PoolDef("Death", 0.1f, "Death") { after = 2.5f, next = "Idle" },
            new PoolDef("TakeOff", 0.9f, "TakeOff") { next = "Flight" },
            new PoolDef("Flight", 0f, "Fly", "Glide", "Fly", "Dive", "Fly", "Glide")
                { sequence = true, moves = true, h0 = 2, h1 = 4, next = "Land" },
            new PoolDef("Land", 0f, "Land") { next = "Idle" },
        };

        static EagleSetup() => EditorApplication.delayCall += () => AutoBuild(20);

        static void AutoBuild(int retries)
        {
            if (!File.Exists(ModelPath) || File.Exists(PrefabPath)) return;
            bool ready = AssetImporter.GetAtPath(ModelPath) is ModelImporter &&
                         AssetDatabase.LoadAssetAtPath<Texture2D>(Textures + "/T_Eagle.png") != null &&
                         AssetDatabase.LoadAssetAtPath<Texture2D>(Textures + "/T_Eagle_Bald.png") != null &&
                         !EditorApplication.isCompiling && !EditorApplication.isUpdating &&
                         !EditorApplication.isPlayingOrWillChangePlaymode;
            if (ready) Build();
            else if (retries > 0) EditorApplication.delayCall += () => AutoBuild(retries - 1);
        }

        [MenuItem("Tools/Beasts/Rebuild Eagle")]
        public static void Build() => Run(true);

        static Material Skin(string name, string tex)
        {
            ConfigureSmoothnessTexture($"{Textures}/{tex}.png");
            var mat = MakeLit(name, $"{Textures}/{tex}.png", Color.white);
            if (mat.HasProperty("_Cull")) mat.SetFloat("_Cull", 2f);     // back faces culled: the undersides are faces
            mat.doubleSidedGI = false;                                    // of their own in the mesh
            EditorUtility.SetDirty(mat);
            return mat;
        }

        /// <summary>renders: also the lineup renders (a preview scene; the open scenes are never touched).</summary>
        public static void Run(bool renders)
        {
            var dir = OutDir("EagleSetup");
            Directory.CreateDirectory(dir);
            var log = new StringBuilder();
            Application.LogCallback onLog = (c, s, t) => { if (t != LogType.Log) log.AppendLine($"[{t}] {c}"); };
            Application.logMessageReceived += onLog;
            try
            {
                EnsureFolders();
                var golden = Skin("M_Eagle", "T_Eagle");
                var bald = Skin("M_Eagle_Bald", "T_Eagle_Bald");

                var (avatar, motionPath, model) = ConfigureModel(ModelPath, new[] { ("M_Eagle", golden) }, log);
                var clips = ConfigureClips("Eagle", Anims + "/eagle_clips.json", avatar, motionPath, EventFunction, log);
                MakeSet("EagleAnims", Pools(), clips, log);

                var go = NewCreature(model, avatar, "Eagle");
                var body = go.GetComponentsInChildren<SkinnedMeshRenderer>(true).FirstOrDefault(r => r.name == "EagleBody");
                var hips = go.GetComponentsInChildren<Transform>(true).FirstOrDefault(t => t.name == "Hips");
                if (body != null && hips != null)
                {
                    // the bounds ride on the trunk, which flies up to 2.3 m over the GameObject: a 2.6 m cube round the
                    // hips holds the 2.03 m span in any pose (the wing tip is at most 1.05 m from the hips)
                    body.rootBone = hips;
                    body.localBounds = new Bounds(Vector3.zero, Vector3.one * 2.6f);
                }
                var look = go.GetComponent<BeastAppearance>() ?? go.AddComponent<BeastAppearance>();
                look.target = body;
                look.skins = new[] { golden, bald };
                look.scale = new Vector2(0.92f, 1.08f);
                if (go.GetComponent<BeastEvents>() == null) go.AddComponent<BeastEvents>();
                log.AppendLine($"  Eagle.prefab: body={body != null} rootBone={(body != null && body.rootBone != null ? body.rootBone.name : "-")}" +
                               (body != null ? $" tris={body.sharedMesh.triangles.Length / 3} (5356)" : "") +
                               $" sockets={string.Join(",", go.GetComponentsInChildren<Transform>(true).Where(t => t.name.StartsWith("Socket_")).Select(t => t.name))}");
                var prefab = PrefabUtility.SaveAsPrefabAsset(go, PrefabPath);
                Object.DestroyImmediate(go);
                log.AppendLine("  prefab: " + PrefabPath);

                if (renders)
                {
                    BeastsTestScene.RenderLineup(prefab, clips, new (string, float)[]
                    {
                        ("Idle", 1f), ("Walk", 0.3f), ("Screech", 0.8f), ("TakeOff", 0.6f), ("Fly", 0.1f), ("Glide", 1f),
                        ("Dive", 1.27f), ("Land", 1.4f), ("Death", 2.4f),
                    }, dir, 2.4f, 0.9f, log, 1.4f);
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
                Debug.Log("Eagle setup finished: " + Path.Combine(dir, "setup_report.txt"));
            }
        }
    }
}

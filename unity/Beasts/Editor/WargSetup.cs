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
    /// Builds the warg (2026-10-12) from the files exported by Blender (Assets/Beasts/Models, Textures):
    ///   Warg.fbx            Generic rig, avatar from this model, Motion = root-motion node, sockets kept (Socket_Saddle:
    ///                       the rider's seat); three skinned meshes: WargBody, WargTack (saddle, straps, bridle, reins),
    ///                       WargMask (the goblins' bone war-mask)
    ///   Anims/Warg@*.fbx    one clip each, avatar copied from Warg.fbx; loop flags, root motion and animation events
    ///                       (OnBeastEvent: Bite, Howl, Dead) from Anims/warg_clips.json
    ///   Materials           M_Warg (dark brown-grey), M_Warg_Ash, M_Warg_Black, M_WargTack; smoothness from the
    ///                       textures' alpha, normal maps T_Warg_Normal (fur clumps, strands down the locks) and
    ///                       T_WargTack_Normal
    ///   Prefabs/Warg        wild: Animator + BeastAppearance (coat on WargBody, size) + BeastEvents + WargTack (off)
    ///   Prefabs/WargRidden  the same, saddled and masked, for the goblins' mounts
    ///   Animation/WargAnims clip pools for BeastRandomAnimator
    /// then the test scene (BeastsTestScene). Runs once by itself the first time the files are imported; afterwards
    /// Tools > Beasts > Rebuild Warg. A report and renders go to Logs/WargSetup.
    /// </summary>
    [InitializeOnLoad]
    public static class WargSetup
    {
        const string ModelPath = Models + "/Warg.fbx";
        public const string PrefabPath = Prefabs + "/Warg.prefab";
        public const string RiddenPrefabPath = Prefabs + "/WargRidden.prefab";
        public const string SetPath = SetDir + "/WargAnims.asset";

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

        static WargSetup() => EditorApplication.delayCall += () => AutoBuild(20);

        static void AutoBuild(int retries)
        {
            if (!File.Exists(ModelPath) || File.Exists(PrefabPath)) return;
            bool ready = AssetImporter.GetAtPath(ModelPath) is ModelImporter &&
                         AssetDatabase.LoadAssetAtPath<Texture2D>(Textures + "/T_Warg.png") != null &&
                         !EditorApplication.isCompiling && !EditorApplication.isUpdating;
            if (ready) Build();
            else if (retries > 0) EditorApplication.delayCall += () => AutoBuild(retries - 1);
        }

        [MenuItem("Tools/Beasts/Rebuild Warg")]
        public static void Build() => Run(true);

        static SkinnedMeshRenderer Part(GameObject go, string name) =>
            go.GetComponentsInChildren<SkinnedMeshRenderer>(true).FirstOrDefault(r => r.name == name);

        /// <summary>scenes: also rebuild the test scene and the renders.</summary>
        public static void Run(bool scenes)
        {
            var dir = OutDir("WargSetup");
            Directory.CreateDirectory(dir);
            var log = new StringBuilder();
            Application.LogCallback onLog = (c, s, t) => { if (t != LogType.Log) log.AppendLine($"[{t}] {c}"); };
            Application.logMessageReceived += onLog;
            try
            {
                EnsureFolders();
                foreach (var t in new[] { "T_Warg", "T_Warg_Ash", "T_Warg_Black", "T_WargTack" })
                    ConfigureSmoothnessTexture($"{Textures}/{t}.png");
                var dark = MakeLit("M_Warg", Textures + "/T_Warg.png", Color.white);
                var ash = MakeLit("M_Warg_Ash", Textures + "/T_Warg_Ash.png", Color.white);
                var black = MakeLit("M_Warg_Black", Textures + "/T_Warg_Black.png", Color.white);
                var tack = MakeLit("M_WargTack", Textures + "/T_WargTack.png", Color.white);
                foreach (var m in new[] { dark, ash, black }) AddNormalMap(m, Textures + "/T_Warg_Normal.png");
                AddNormalMap(tack, Textures + "/T_WargTack_Normal.png", 0.8f);

                var (avatar, motionPath, model) = ConfigureModel(ModelPath, new[] { ("M_Warg", dark), ("M_WargTack", tack) }, log);
                var clips = ConfigureClips("Warg", Anims + "/warg_clips.json", avatar, motionPath, EventFunction, log);
                MakeSet("WargAnims", Pools(), clips, log);

                GameObject wild = null, ridden = null;
                foreach (var (path, saddled) in new[] { (PrefabPath, false), (RiddenPrefabPath, true) })
                {
                    var go = NewCreature(model, avatar, saddled ? "WargRidden" : "Warg");
                    var body = Part(go, "WargBody");
                    var look = go.GetComponent<BeastAppearance>() ?? go.AddComponent<BeastAppearance>();
                    look.target = body;
                    look.skins = new[] { dark, dark, dark, ash, black };          // listed more often = more likely
                    look.scale = new Vector2(0.94f, 1.08f);
                    if (go.GetComponent<BeastEvents>() == null) go.AddComponent<BeastEvents>();
                    var gear = go.GetComponent<WargTack>() ?? go.AddComponent<WargTack>();
                    gear.tackRenderer = Part(go, "WargTack");
                    gear.maskRenderer = Part(go, "WargMask");
                    gear.saddled = gear.masked = saddled;
                    gear.Apply();
                    log.AppendLine($"  {Path.GetFileName(path)}: body={body != null} tack={gear.tackRenderer != null} " +
                                   $"mask={gear.maskRenderer != null} saddled={saddled}");
                    var prefab = PrefabUtility.SaveAsPrefabAsset(go, path);
                    Object.DestroyImmediate(go);
                    if (saddled) ridden = prefab; else wild = prefab;
                }

                if (scenes)
                {
                    BeastsTestScene.Build(log);
                    var poses = new (string, float)[]
                    {
                        ("Idle", 1f), ("Walk", 0.25f), ("Trot", 0.2f), ("Run", 0.15f), ("Bite", 0.42f), ("Lunge", 0.7f),
                        ("Howl", 1.5f), ("Death", 2.1f),
                    };
                    BeastsTestScene.RenderLineup(ridden, clips, poses, dir, 3.0f, 0.7f, log);
                    var wildDir = Path.Combine(dir, "wild");
                    Directory.CreateDirectory(wildDir);
                    BeastsTestScene.RenderLineup(wild, clips, poses, wildDir, 3.0f, 0.7f, log);
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
                Debug.Log("Warg setup finished: " + Path.Combine(dir, "setup_report.txt"));
            }
        }
    }
}

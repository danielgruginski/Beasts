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
    /// Builds the leech (2026-10-23) from the files exported by Blender (Assets/Beasts/Models, Textures):
    ///   Leech.fbx            Generic rig (a chain: Sucker, Body1-10, Head, and a Swell bone on each body bone whose
    ///                        uniform scale swells that segment), avatar from this model, Motion = root-motion node,
    ///                        sockets Socket_Mouth and Socket_Rear; one skinned mesh, LeechBody
    ///   Anims/Leech@*.fbx    five clips (Idle, Crawl, Lunge, Hit, Death), avatar copied from Leech.fbx; loop flags, root
    ///                        motion (Crawl) and animation events (OnBeastEvent: Bite, Drain, Drain2, Dead) from
    ///                        Anims/leech_clips.json
    ///   Materials            M_Leech (wet: smoothness from the texture's alpha)
    ///   Prefabs/Leech        Animator + BeastAppearance (size) + BeastEvents
    ///   Animation/LeechAnims clip pools for BeastRandomAnimator
    /// No scene is touched (the game side is to come). Runs once by itself the first time the files are imported;
    /// afterwards Tools > Beasts > Rebuild Leech. A report and renders (in a preview scene) go to Logs/LeechSetup.
    /// </summary>
    [InitializeOnLoad]
    public static class LeechSetup
    {
        const string ModelPath = Models + "/Leech.fbx";
        public const string PrefabPath = Prefabs + "/Leech.prefab";
        public const string SetPath = SetDir + "/LeechAnims.asset";

        static PoolDef[] Pools() => new[]
        {
            new PoolDef("Idle", 2f, "Idle") { h0 = 3, h1 = 6 },
            new PoolDef("Crawl", 2.2f, "Crawl") { moves = true, h0 = 4, h1 = 8 },
            new PoolDef("Lunge", 0.9f, "Lunge") { next = "Idle" },
            new PoolDef("Hit", 0.4f, "Hit") { next = "Idle" },
            new PoolDef("Death", 0.2f, "Death") { after = 2.5f, next = "Idle" },
        };

        static LeechSetup() => EditorApplication.delayCall += () => AutoBuild(20);

        static void AutoBuild(int retries)
        {
            if (!File.Exists(ModelPath) || File.Exists(PrefabPath)) return;
            bool ready = AssetImporter.GetAtPath(ModelPath) is ModelImporter &&
                         AssetDatabase.LoadAssetAtPath<Texture2D>(Textures + "/T_Leech.png") != null &&
                         !EditorApplication.isCompiling && !EditorApplication.isUpdating &&
                         !EditorApplication.isPlayingOrWillChangePlaymode;
            if (ready) Build();
            else if (retries > 0) EditorApplication.delayCall += () => AutoBuild(retries - 1);
        }

        [MenuItem("Tools/Beasts/Rebuild Leech")]
        public static void Build() => Run(true);

        /// <summary>renders: also the lineup renders (a preview scene; the open scenes are never touched).</summary>
        public static void Run(bool renders)
        {
            var dir = OutDir("LeechSetup");
            Directory.CreateDirectory(dir);
            var log = new StringBuilder();
            Application.LogCallback onLog = (c, s, t) => { if (t != LogType.Log) log.AppendLine($"[{t}] {c}"); };
            Application.logMessageReceived += onLog;
            try
            {
                EnsureFolders();
                ConfigureSmoothnessTexture(Textures + "/T_Leech.png");
                var skin = MakeLit("M_Leech", Textures + "/T_Leech.png", Color.white);

                var (avatar, motionPath, model) = ConfigureModel(ModelPath, new[] { ("M_Leech", skin) }, log);
                var clips = ConfigureClips("Leech", Anims + "/leech_clips.json", avatar, motionPath, EventFunction, log);
                MakeSet("LeechAnims", Pools(), clips, log);

                var go = NewCreature(model, avatar, "Leech");
                var smr = go.GetComponentInChildren<SkinnedMeshRenderer>();
                if (smr != null)                           // the crawl arches it 0.5 m up, the lunge reaches 0.4 m out
                    smr.localBounds = new Bounds(smr.localBounds.center, smr.localBounds.size + Vector3.one * 1.0f);
                var look = go.GetComponent<BeastAppearance>() ?? go.AddComponent<BeastAppearance>();
                look.skins = new[] { skin };
                look.scale = new Vector2(0.85f, 1.15f);
                if (go.GetComponent<BeastEvents>() == null) go.AddComponent<BeastEvents>();
                var prefab = PrefabUtility.SaveAsPrefabAsset(go, PrefabPath);
                Object.DestroyImmediate(go);
                log.AppendLine("  prefab: " + PrefabPath);

                if (renders)
                {
                    BeastsTestScene.RenderLineup(prefab, clips, new (string, float)[]
                    {
                        ("Idle", 0.7f), ("Crawl", 0.8f), ("Crawl", 1.4f), ("Lunge", 0.4f), ("Lunge", 1.0f),
                        ("Hit", 0.1f), ("Death", 2.0f),
                    }, dir, 2.4f, 0.3f, log, 1.0f);
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
                Debug.Log("Leech setup finished: " + Path.Combine(dir, "setup_report.txt"));
            }
        }
    }
}

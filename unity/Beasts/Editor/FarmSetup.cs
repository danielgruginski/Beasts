using System;
using System.Collections.Generic;
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
    /// Builds the farm animals (goat, sheep, cow, horse, pig, chicken) from the files exported by Blender
    /// (Assets/Beasts/Models, Textures), each the way <see cref="DeerSetup"/> builds the deer:
    ///   &lt;Name&gt;.fbx             Generic rig, avatar from this model, Motion = root-motion node, sockets kept
    ///   Anims/&lt;Name&gt;@*.fbx      one clip each; loop flags, root motion and events (Bite on the goat's butt, Dead) from
    ///                          Anims/&lt;name&gt;_clips.json
    ///   Materials              M_&lt;Name&gt; and one per extra coat (M_Goat_White ...); smoothness from the alpha; a
    ///                          normal map T_&lt;Name&gt;_Normal on every coat when there is one (the horse)
    ///   Prefabs/&lt;Name&gt;        Animator + BeastAppearance (coats, size) + BeastEvents
    ///   Animation/&lt;Name&gt;Anims clip pools for BeastRandomAnimator (mostly grazing; Alert after grazing; Sleep -> Wake)
    /// Only the animals whose model is imported are built. Then the test scene (<see cref="FarmTestScene"/>) and
    /// renders. Runs once by itself when a model arrives without a prefab; afterwards Tools > Beasts > Rebuild Farm
    /// Animals. A report and renders go to Logs/FarmSetup.
    /// </summary>
    [InitializeOnLoad]
    public static class FarmSetup
    {
        public class Animal
        {
            public string name;
            public string[] coats;          // texture suffixes after T_<name>: "" (the first coat), "_White" ...
            public Vector2 scale = new Vector2(0.92f, 1.08f);
            public float spacing = 2f, lookHeight = 0.6f, camScale = 0.6f;
            public bool attack;
            public string ModelPath => $"{Models}/{name}.fbx";
            public string PrefabPath => $"{Prefabs}/{name}.prefab";
            public string SetPath => $"{SetDir}/{name}Anims.asset";
        }

        public static readonly Animal[] All =
        {
            new Animal { name = "Goat", coats = new[] { "", "_White", "_Pied" }, spacing = 1.6f, lookHeight = 0.45f,
                         camScale = 0.5f, attack = true },
            new Animal { name = "Sheep", coats = new[] { "", "_Black", "_Grey" }, spacing = 1.6f, lookHeight = 0.45f,
                         camScale = 0.5f },
            new Animal { name = "Cow", coats = new[] { "", "_Red", "_Pied" }, spacing = 3f, lookHeight = 0.8f,
                         camScale = 0.8f },
            new Animal { name = "Horse", coats = new[] { "", "_Chestnut", "_Grey", "_Black" }, spacing = 3.2f,
                         lookHeight = 1f, camScale = 0.9f },
            new Animal { name = "Pig", coats = new[] { "", "_Saddleback", "_Black", "_Brown" }, spacing = 1.8f, lookHeight = 0.4f,
                         camScale = 0.5f },
            new Animal { name = "Chicken", coats = new[] { "", "_White", "_Black" }, scale = new Vector2(0.9f, 1.1f),
                         spacing = 0.6f, lookHeight = 0.2f, camScale = 0.25f },
        };

        public static Animal Get(string name) => All.First(a => a.name == name);

        static PoolDef[] Pools(Animal a)
        {
            if (a.name == "Chicken")
                return new[]
                {
                    new PoolDef("Idle", 1.5f, "Idle") { h0 = 2f, h1 = 5 },
                    new PoolDef("Peck", 3f, "Peck") { h0 = 3f, h1 = 7, next = "Alert" },
                    new PoolDef("Scratch", 1f, "Scratch") { h0 = 2f, h1 = 4 },
                    new PoolDef("Alert", 0.5f, "Alert") { h0 = 1f, h1 = 2f, next = "Idle" },
                    new PoolDef("Call", 0.3f, "Call") { next = "Idle" },
                    new PoolDef("Walk", 2f, "Walk") { moves = true, h0 = 2, h1 = 5 },
                    new PoolDef("Run", 0.4f, "Run") { moves = true, h0 = 1f, h1 = 2f },
                    new PoolDef("Flap", 0.2f, "Flap") { next = "Idle" },
                    new PoolDef("Sleep", 0.3f, "Sleep") { h0 = 4f, h1 = 7f, next = "Wake" },
                    new PoolDef("Wake", 0f, "Wake") { next = "Idle" },
                    new PoolDef("Hit", 0.2f, "Hit") { next = "Idle" },
                    new PoolDef("Death", 0.1f, "Death") { after = 2.5f, next = "Wake" },
                };
            var pools = new List<PoolDef>
            {
                new PoolDef("Idle", 1.5f, "Idle") { h0 = 3f, h1 = 6 },
                new PoolDef("Graze", 3f, "Graze") { h0 = 5f, h1 = 10, next = "Alert" },
                new PoolDef("Alert", 0.4f, "Alert") { h0 = 1.5f, h1 = 2.5f, next = "Idle" },
                new PoolDef("Call", 0.3f, "Call") { next = "Idle" },
                new PoolDef("Walk", 2f, "Walk") { moves = true, h0 = 3, h1 = 6 },
                new PoolDef("Trot", 0.5f, "Trot") { moves = true, h0 = 2, h1 = 4 },
                new PoolDef("Run", 0.25f, "Run") { moves = true, h0 = 1.2f, h1 = 2.5f },
                new PoolDef("Sleep", 0.3f, "Sleep") { h0 = 4f, h1 = 7f, next = "Wake" },
                new PoolDef("Wake", 0f, "Wake") { next = "Idle" },
                new PoolDef("Hit", 0.2f, "Hit") { next = "Idle" },
                new PoolDef("Death", 0.1f, "Death") { after = 2.5f, next = "Wake" },
            };
            if (a.attack) pools.Add(new PoolDef("Attack", 0.2f, "Attack") { next = "Idle" });
            return pools.ToArray();
        }

        static (string clip, float t)[] Lineup(Animal a) => a.name == "Chicken"
            ? new[] { ("Idle", 1f), ("Peck", 0.6f), ("Scratch", 0.4f), ("Walk", 0.3f), ("Run", 0.2f), ("Flap", 0.4f),
                      ("Sleep", 1f), ("Death", 1.2f) }
            : new[] { ("Idle", 1f), ("Graze", 2f), ("Alert", 1f), ("Call", 0.5f), ("Walk", 0.4f), ("Trot", 0.25f),
                      ("Run", 0.2f), ("Sleep", 1f), ("Death", 2f) };

        static FarmSetup() => EditorApplication.delayCall += () => AutoBuild(20);

        static void AutoBuild(int retries)
        {
            if (!All.Any(a => File.Exists(a.ModelPath) && !File.Exists(a.PrefabPath))) return;
            bool ready = !EditorApplication.isCompiling && !EditorApplication.isUpdating && !EditorApplication.isPlaying &&
                         All.Where(a => File.Exists(a.ModelPath)).All(a => AssetImporter.GetAtPath(a.ModelPath) is ModelImporter);
            if (ready) Build();
            else if (retries > 0) EditorApplication.delayCall += () => AutoBuild(retries - 1);
        }

        [MenuItem("Tools/Beasts/Rebuild Farm Animals")]
        public static void Build() => Run(true);

        /// <summary>scenes: also rebuild the test scene and the renders. only: the animals to build (null = all
        /// that are imported).</summary>
        public static void Run(bool scenes, params string[] only)
        {
            var dir = OutDir("FarmSetup");
            Directory.CreateDirectory(dir);
            var log = new StringBuilder();
            Application.LogCallback onLog = (c, s, t) => { if (t != LogType.Log) log.AppendLine($"[{t}] {c}"); };
            Application.logMessageReceived += onLog;
            try
            {
                EnsureFolders();
                var built = new List<(Animal a, GameObject prefab, Dictionary<string, AnimationClip> clips)>();
                foreach (var a in All)
                {
                    if (!File.Exists(a.ModelPath) || (only != null && only.Length > 0 && !only.Contains(a.name))) continue;
                    var skins = new List<Material>();
                    var normal = $"{Textures}/T_{a.name}_Normal.png";      // one relief for all coats (the horse)
                    foreach (var c in a.coats)
                    {
                        var tex = $"{Textures}/T_{a.name}{c}.png";
                        if (!File.Exists(tex)) continue;
                        ConfigureSmoothnessTexture(tex);
                        var mat = MakeLit($"M_{a.name}{c}", tex, Color.white);
                        if (File.Exists(normal)) AddNormalMap(mat, normal);
                        skins.Add(mat);
                    }
                    var (avatar, motionPath, model) = ConfigureModel(a.ModelPath, new[] { ($"M_{a.name}", skins[0]) }, log);
                    var clips = ConfigureClips(a.name, $"{Anims}/{a.name.ToLowerInvariant()}_clips.json", avatar,
                                               motionPath, EventFunction, log);
                    MakeSet($"{a.name}Anims", Pools(a), clips, log);
                    var go = NewCreature(model, avatar, a.name);
                    var look = go.GetComponent<BeastAppearance>() ?? go.AddComponent<BeastAppearance>();
                    look.skins = skins.ToArray();
                    look.scale = a.scale;
                    if (go.GetComponent<BeastEvents>() == null) go.AddComponent<BeastEvents>();
                    var prefab = PrefabUtility.SaveAsPrefabAsset(go, a.PrefabPath);
                    Object.DestroyImmediate(go);
                    log.AppendLine($"  prefab: {a.PrefabPath} ({skins.Count} coats)");
                    built.Add((a, prefab, clips));
                }
                if (scenes && built.Count > 0)
                {
                    FarmTestScene.Build(log);
                    foreach (var (a, prefab, clips) in built)
                    {
                        var sub = Path.Combine(dir, a.name);
                        Directory.CreateDirectory(sub);
                        BeastsTestScene.RenderLineup(prefab, clips, Lineup(a).Where(p => clips.ContainsKey(p.clip)).ToArray(),
                                                     sub, a.spacing, a.lookHeight, log, a.camScale);
                    }
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
                Debug.Log("Farm setup finished: " + Path.Combine(dir, "setup_report.txt"));
            }
        }
    }
}

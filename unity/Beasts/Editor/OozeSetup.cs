using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Animations;
using UnityEngine.Playables;
using UnityEngine.Rendering;
using UnityEngine.SceneManagement;
using static Beasts.EditorTools.BeastSetupUtil;
using Object = UnityEngine.Object;

namespace Beasts.EditorTools
{
    /// <summary>
    /// Builds the dungeon ooze from the files exported by Blender (Assets/Beasts/Models, Textures, Shaders):
    ///   Ooze.fbx               Generic rig, avatar from this model, Motion = root-motion node, sockets kept (Gut,
    ///                          Mouth, Spit); two skinned meshes: OozeBody (the jelly) and OozeContents (the remains)
    ///   Anims/Ooze@*.fbx       one clip each, avatar copied from Ooze.fbx; loop flags, root motion and animation events
    ///                          (OnBeastEvent: Hit, Grab, Engulf, Spit, Dead, Risen) from Anims/ooze_clips.json
    ///   Materials              M_Ooze (Beasts/OozeJelly: see-through, opacity from T_Ooze's alpha), M_OozeContents
    ///                          (URP Lit, smoothness from the alpha)
    ///   Prefabs/Ooze           Animator + BeastAppearance (size only) + BeastEvents
    ///   Animation/OozeAnims    clip pools for BeastRandomAnimator (Puddle leads into Rise, Death too)
    /// then the test scene (BeastsTestScene). Runs once by itself the first time the files are imported; afterwards
    /// Tools > Beasts > Rebuild Ooze. A report, renders and a root-motion trace go to Logs/OozeSetup. Nothing here
    /// changes the scenes open in the editor: the test scene is built beside them, the renders use a preview scene.
    /// </summary>
    [InitializeOnLoad]
    public static class OozeSetup
    {
        const string ModelPath = Models + "/Ooze.fbx";
        public const string PrefabPath = Prefabs + "/Ooze.prefab";
        public const string SetPath = SetDir + "/OozeAnims.asset";
        const string JellyShader = "Beasts/OozeJelly";
        const float BoundsPad = 0.8f;        // the pods reach this far past the bind pose (Grab, Lash)

        static PoolDef[] Pools() => new[]
        {
            new PoolDef("Idle", 1.5f, "Idle") { h0 = 3f, h1 = 6 },
            new PoolDef("Crawl", 2.5f, "Crawl") { moves = true, h0 = 4, h1 = 8 },
            new PoolDef("Lash", 0.4f, "Lash") { next = "Idle" },
            new PoolDef("Grab", 0.4f, "Grab") { next = "Idle" },
            new PoolDef("Spit", 0.3f, "Spit") { next = "Idle" },
            new PoolDef("Engulf", 0.3f, "Engulf") { next = "Idle" },
            new PoolDef("Hit", 0.3f, "Hit") { next = "Idle" },
            new PoolDef("Puddle", 0.4f, "Puddle") { h0 = 4f, h1 = 8f, next = "Rise" },
            new PoolDef("Rise", 0f, "Rise") { next = "Idle" },
            new PoolDef("Death", 0.15f, "Death") { after = 2.5f, next = "Rise" },
        };

        static OozeSetup() => EditorApplication.delayCall += () => AutoBuild(20);

        static void AutoBuild(int retries)
        {
            if (!File.Exists(ModelPath) || File.Exists(PrefabPath)) return;
            bool ready = AssetImporter.GetAtPath(ModelPath) is ModelImporter &&
                         AssetDatabase.LoadAssetAtPath<Texture2D>(Textures + "/T_Ooze.png") != null &&
                         Shader.Find(JellyShader) != null &&
                         !EditorApplication.isCompiling && !EditorApplication.isUpdating && !EditorApplication.isPlaying;
            if (ready) Build();
            else if (retries > 0) EditorApplication.delayCall += () => AutoBuild(retries - 1);
        }

        [MenuItem("Tools/Beasts/Rebuild Ooze")]
        public static void Build() => Run(true);

        /// <summary>scenes: also rebuild the test scene, the renders and the root-motion trace.</summary>
        public static void Run(bool scenes)
        {
            var dir = OutDir("OozeSetup");
            Directory.CreateDirectory(dir);
            var log = new StringBuilder();
            Application.LogCallback onLog = (c, s, t) => { if (t != LogType.Log) log.AppendLine($"[{t}] {c}"); };
            Application.logMessageReceived += onLog;
            try
            {
                EnsureFolders();
                var jelly = MakeJelly("M_Ooze", Textures + "/T_Ooze.png", log);
                ConfigureSmoothnessTexture($"{Textures}/T_OozeContents.png");
                var remains = MakeLit("M_OozeContents", Textures + "/T_OozeContents.png", Color.white);

                var (avatar, motionPath, model) = ConfigureModel(ModelPath,
                    new[] { ("M_Ooze", jelly), ("M_OozeContents", remains) }, log);
                foreach (var smr in model.GetComponentsInChildren<SkinnedMeshRenderer>(true))
                    log.AppendLine($"  mesh {smr.name}: tris={smr.sharedMesh.triangles.Length / 3} bones={smr.bones.Length} " +
                                   $"material={(smr.sharedMaterial != null ? smr.sharedMaterial.name + " (" + smr.sharedMaterial.shader.name + ")" : "null")}");
                var clips = ConfigureClips("Ooze", Anims + "/ooze_clips.json", avatar, motionPath, EventFunction, log);
                MakeSet("OozeAnims", Pools(), clips, log);

                var go = NewCreature(model, avatar, "Ooze");
                foreach (var smr in go.GetComponentsInChildren<SkinnedMeshRenderer>(true))
                {
                    var b = smr.localBounds;
                    b.Expand(BoundsPad * 2f);
                    smr.localBounds = b;
                    smr.shadowCastingMode = ShadowCastingMode.On;      // the jelly's caster is dithered by its opacity
                }
                var look = go.GetComponent<BeastAppearance>() ?? go.AddComponent<BeastAppearance>();
                look.skins = new Material[0];                          // one jelly; two meshes, so no skin swap
                look.scale = new Vector2(0.85f, 1.15f);
                if (go.GetComponent<BeastEvents>() == null) go.AddComponent<BeastEvents>();
                var prefab = PrefabUtility.SaveAsPrefabAsset(go, PrefabPath);
                Object.DestroyImmediate(go);
                log.AppendLine("  prefab: " + PrefabPath);

                if (scenes)
                {
                    BeastsTestScene.Build(log);
                    RenderPreview(prefab, clips, new (string, float)[]
                    {
                        ("Idle", 1f), ("Crawl", 0.5f), ("Lash", 0.67f), ("Grab", 0.6f), ("Engulf", 1.15f),
                        ("Spit", 0.7f), ("Death", 2.3f), ("Rise", 0.75f),
                    }, dir, 3.6f, 0.6f, log);
                    if (clips.TryGetValue("Crawl", out var crawl)) TraceRootMotion(prefab, crawl, 3, log);
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
                Debug.Log("Ooze setup finished: " + Path.Combine(dir, "setup_report.txt"));
            }
        }

        /// <summary>The jelly: Beasts/OozeJelly with T_Ooze (RGB colour, A opacity). Falls back to URP Lit
        /// transparent if the shader is missing.</summary>
        static Material MakeJelly(string name, string texPath, StringBuilder log)
        {
            if (AssetImporter.GetAtPath(texPath) is TextureImporter ti)
            {
                ti.maxTextureSize = 1024;
                ti.sRGBTexture = true;
                ti.mipmapEnabled = true;
                ti.alphaSource = TextureImporterAlphaSource.FromInput;
                ti.alphaIsTransparency = true;
                ti.textureCompression = TextureImporterCompression.CompressedHQ;
                ti.SaveAndReimport();
            }
            var shader = Shader.Find(JellyShader);
            if (shader == null)
            {
                log.AppendLine($"  {JellyShader} not found: URP Lit transparent instead");
                return MakeTransparentLit(name, texPath, Color.white, 0.9f);
            }
            var path = $"{Materials}/{name}.mat";
            var mat = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (mat == null)
            {
                mat = new Material(shader) { name = name };
                AssetDatabase.CreateAsset(mat, path);
            }
            mat.shader = shader;
            var tex = AssetDatabase.LoadAssetAtPath<Texture2D>(texPath);
            mat.SetTexture("_BaseMap", tex);
            mat.mainTexture = tex;
            mat.SetColor("_BaseColor", Color.white);
            mat.renderQueue = (int)RenderQueue.Transparent;
            EditorUtility.SetDirty(mat);
            return mat;
        }

        /// <summary>Verification renders in a preview scene (the open scenes are not touched): the ooze posed from its
        /// clips in a row, a goblin for scale; lineup, close-up and the colony camera.</summary>
        static void RenderPreview(GameObject prefab, Dictionary<string, AnimationClip> clips, (string clip, float t)[] poses,
                                  string dir, float spacing, float lookHeight, StringBuilder log)
        {
            var scene = EditorSceneManager.NewPreviewScene();
            var made = new List<Camera>();
            bool async = ShaderUtil.allowAsyncCompilation;
            ShaderUtil.allowAsyncCompilation = false;      // the first render after the install skipped the jelly: its
            try                                            // variants were still compiling
            {
                var floor = GameObject.CreatePrimitive(PrimitiveType.Plane);
                SceneManager.MoveGameObjectToScene(floor, scene);
                floor.transform.localScale = new Vector3(5, 1, 3);
                var gm = AssetDatabase.LoadAssetAtPath<Material>(Scenes + "/M_BeastGround.mat");
                if (gm != null) floor.GetComponent<Renderer>().sharedMaterial = gm;
                var sun = new GameObject("Sun").AddComponent<Light>();
                SceneManager.MoveGameObjectToScene(sun.gameObject, scene);
                sun.type = LightType.Directional;
                sun.intensity = 1.6f;
                sun.shadows = LightShadows.Soft;
                sun.transform.rotation = Quaternion.Euler(50, 200, 0);
                float x0 = -(poses.Length - 1) * 0.5f * spacing;
                for (int i = 0; i < poses.Length; i++)
                {
                    var go = (GameObject)PrefabUtility.InstantiatePrefab(prefab, scene);
                    go.transform.SetPositionAndRotation(new Vector3(x0 + i * spacing, 0, 0), Quaternion.Euler(0, 200f, 0));
                    if (clips.TryGetValue(poses[i].clip, out var c)) c.SampleAnimation(go, Mathf.Min(poses[i].t, c.length));
                    foreach (var smr in go.GetComponentsInChildren<SkinnedMeshRenderer>()) smr.forceMatrixRecalculationPerRender = true;
                }
                var gob = AssetDatabase.LoadAssetAtPath<GameObject>("Assets/Goblins/Prefabs/Goblin_Spearman.prefab");
                if (gob != null)
                {
                    var g = (GameObject)PrefabUtility.InstantiatePrefab(gob, scene);
                    g.transform.SetPositionAndRotation(new Vector3(x0 - 2.6f, 0, 0.8f), Quaternion.Euler(0, 180f, 0));
                }
                Camera Cam(string n, Vector3 pos, Vector3 target, float fov)
                {
                    var cam = MakeCamera(n, pos, target, fov);
                    SceneManager.MoveGameObjectToScene(cam.gameObject, scene);
                    cam.scene = scene;
                    made.Add(cam);
                    return cam;
                }
                float w = poses.Length * spacing;
                Render(Cam("CAM_Lineup", new Vector3(0, 3.5f + lookHeight, -w * 0.62f), new Vector3(0, lookHeight, 0), 45), dir, "lineup.png", 1800, 800);
                Render(Cam("CAM_Close", new Vector3(x0 + 2.0f, 1.6f + lookHeight, -4.6f), new Vector3(x0, lookHeight, 0), 40), dir, "close.png", 1200, 900);
                Render(Cam("CAM_Colony", new Vector3(0, 40 * Mathf.Sin(50 * Mathf.Deg2Rad), -40 * Mathf.Cos(50 * Mathf.Deg2Rad)),
                           new Vector3(0, 0.5f, 0), 30), dir, "lineup_colony_40m.png", 1600, 900);
                log.AppendLine("  renders: " + dir);
            }
            finally
            {
                ShaderUtil.allowAsyncCompilation = async;
                EditorSceneManager.ClosePreviewScene(scene);
            }
        }

        /// <summary>Root motion over a few loops of a moving clip, played through a manual PlayableGraph on a copy in a
        /// preview scene: the travel per loop, and the Body's offset from the GameObject at each loop's start (it must
        /// stay put, or the clip snaps when it loops).</summary>
        static void TraceRootMotion(GameObject prefab, AnimationClip clip, int loops, StringBuilder log)
        {
            var scene = EditorSceneManager.NewPreviewScene();
            var graph = PlayableGraph.Create("OozeTrace");
            try
            {
                var go = (GameObject)PrefabUtility.InstantiatePrefab(prefab, scene);
                go.transform.SetPositionAndRotation(Vector3.zero, Quaternion.identity);
                var anim = go.GetComponent<Animator>();
                anim.applyRootMotion = true;
                anim.cullingMode = AnimatorCullingMode.AlwaysAnimate;
                var body = go.GetComponentsInChildren<Transform>(true).First(t => t.name == "Body");
                graph.SetTimeUpdateMode(DirectorUpdateMode.Manual);
                var output = AnimationPlayableOutput.Create(graph, "Animation", anim);
                output.SetSourcePlayable(AnimationClipPlayable.Create(graph, clip));
                graph.Play();
                const float dt = 1f / 30f;
                int perLoop = Mathf.RoundToInt(clip.length / dt);
                var starts = new List<Vector3>();
                var offsets = new List<Vector3>();
                graph.Evaluate(0);
                for (int f = 0; f <= perLoop * loops; f++)
                {
                    if (f % perLoop == 0)
                    {
                        starts.Add(go.transform.position);
                        offsets.Add(go.transform.InverseTransformPoint(body.position));
                    }
                    graph.Evaluate(dt);
                }
                var travel = Enumerable.Range(1, starts.Count - 1).Select(i => (starts[i] - starts[i - 1]).magnitude);
                log.AppendLine($"  root motion {clip.name}: per loop {string.Join(", ", travel.Select(d => d.ToString("0.000")))} m, " +
                               $"Body offset at loop starts {string.Join(" ", offsets.Select(o => o.ToString("F3")))}, " +
                               $"heading {go.transform.forward:F2}");
            }
            finally
            {
                if (graph.IsValid()) graph.Destroy();
                EditorSceneManager.ClosePreviewScene(scene);
            }
        }
    }
}

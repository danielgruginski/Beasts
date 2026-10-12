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
    /// Builds the dungeon oozes from the files exported by Blender (Assets/Beasts/Models, Textures, Shaders):
    ///   Ooze.fbx               Generic rig, avatar from this model, Motion = root-motion node, sockets kept (Gut,
    ///                          Mouth, Spit); two skinned meshes: OozeBody (the jelly) and OozeContents (the remains)
    ///   Anims/Ooze@*.fbx       one clip each, avatar copied from Ooze.fbx; loop flags, root motion and animation events
    ///                          (OnBeastEvent: Hit, Hurt, Grab, Engulf, Spit, Dead, Risen, Split) from ooze_clips.json
    ///   Materials              M_Ooze (Beasts/OozeJelly: T_Ooze's masks coloured by OozeLook's preset, per renderer),
    ///                          M_OozeContents (URP Lit, smoothness from the alpha), and the effects' M_OozeTrail,
    ///                          M_OozeDrop, M_OozePuddle (URP Particles/Lit) and M_OozeGlob (the jelly on a flat mask)
    ///   Textures/FX            the effects' small textures, drawn here (drop, splat, trail, flat mask); Models/
    ///                          OozeGlob.asset, the glob's sphere
    ///   Prefabs/Ooze           Animator + OozeLook (random colour, size 0.9-1.1) + BeastEvents + OozeFx
    ///   Prefabs/GiantOoze      the same at 1.6x (life-size remains inside) + OozeSplit: Split makes two Oozes at 0.79x
    ///   Prefabs/SmallOoze      the same at 0.5-0.6x, only bones, coins and the vacuoles inside
    ///   Animation/OozeAnims, GiantOozeAnims   clip pools for BeastRandomAnimator (the giant's has Split)
    /// then the test scene (BeastsTestScene). Runs once by itself the first time the files are imported; afterwards
    /// Tools > Beasts > Rebuild Ooze. A report, renders and a root-motion trace go to Logs/OozeSetup. Nothing here
    /// changes the scenes open in the editor: the test scene is built beside them, the renders use a preview scene.
    /// </summary>
    [InitializeOnLoad]
    public static class OozeSetup
    {
        const string ModelPath = Models + "/Ooze.fbx";
        public const string PrefabPath = Prefabs + "/Ooze.prefab";
        public const string GiantPrefabPath = Prefabs + "/GiantOoze.prefab";
        public const string SmallPrefabPath = Prefabs + "/SmallOoze.prefab";
        public const string SetPath = SetDir + "/OozeAnims.asset";
        public const string GiantSetPath = SetDir + "/GiantOozeAnims.asset";
        const string JellyShader = "Beasts/OozeJelly";
        const string FxDir = Textures + "/FX";
        const float BoundsPad = 0.8f;        // the pods reach this far past the bind pose (Grab, Lash)
        const float GiantSize = 1.6f, ChildScale = 0.79f, SplitAt = 58f / 30f;
        static readonly string[] AllPresets = OozeLook.Presets.Select(p => p.name).ToArray();

        static PoolDef[] Pools(bool giant)
        {
            var p = new List<PoolDef>
            {
                new PoolDef("Idle", 1.5f, "Idle") { h0 = 3f, h1 = 6 },
                new PoolDef("Crawl", 2.5f, "Crawl") { moves = true, h0 = 4, h1 = 8 },
                new PoolDef("Lash", 0.4f, "Lash") { next = "Idle" },
                new PoolDef("Grab", 0.4f, "Grab") { next = "Idle" },
                new PoolDef("Spit", 0.4f, "Spit") { next = "Idle" },
                new PoolDef("Engulf", 0.3f, "Engulf") { next = "Idle" },
                new PoolDef("Hit", 0.3f, "Hit") { next = "Idle" },
                new PoolDef("Puddle", 0.4f, "Puddle") { h0 = 4f, h1 = 8f, next = "Rise" },
                new PoolDef("Rise", 0f, "Rise") { next = "Idle" },
                new PoolDef("Death", 0.15f, "Death") { after = 2.5f, next = "Rise" },
                new PoolDef("Reform", 0f, "Reform") { next = "Idle" },
            };
            if (giant) p.Add(new PoolDef("Split", 0.35f, "Split") { next = "Idle" });
            return p.ToArray();
        }

        static OozeSetup() => EditorApplication.delayCall += () => AutoBuild(20);

        static void AutoBuild(int retries)
        {
            if (!File.Exists(ModelPath) || File.Exists(GiantPrefabPath)) return;
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
                EnsureFolder(FxDir);
                var jelly = MakeJelly("M_Ooze", Textures + "/T_Ooze.png", log);
                ConfigureSmoothnessTexture($"{Textures}/T_OozeContents.png");
                var remains = MakeLit("M_OozeContents", Textures + "/T_OozeContents.png", Color.white);
                var fx = MakeFx(log);

                var (avatar, motionPath, model) = ConfigureModel(ModelPath,
                    new[] { ("M_Ooze", jelly), ("M_OozeContents", remains) }, log);
                foreach (var smr in model.GetComponentsInChildren<SkinnedMeshRenderer>(true))
                    log.AppendLine($"  mesh {smr.name}: tris={smr.sharedMesh.triangles.Length / 3} bones={smr.bones.Length} " +
                                   $"material={(smr.sharedMaterial != null ? smr.sharedMaterial.name + " (" + smr.sharedMaterial.shader.name + ")" : "null")}");
                var clips = ConfigureClips("Ooze", Anims + "/ooze_clips.json", avatar, motionPath, EventFunction, log);
                var set = MakeSet("OozeAnims", Pools(false), clips, log);
                MakeSet("GiantOozeAnims", Pools(true), clips, log);
                var (left, right) = RemainsBySide(model);
                log.AppendLine($"  remains left: {string.Join(" ", left)}; right: {string.Join(" ", right)}");

                var ooze = SavePrefab(model, avatar, "Ooze", PrefabPath, fx, look =>
                {
                    look.preset = "";
                    look.randomFrom = new[] { "Green", "Green", "Grey", "Ochre", "Crimson", "Black" };
                    look.scale = new Vector2(0.9f, 1.1f);
                }, null, log);
                var giant = SavePrefab(model, avatar, "GiantOoze", GiantPrefabPath, fx, look =>
                {
                    look.preset = "";
                    look.randomFrom = new[] { "Green", "Black" };
                    look.scale = new Vector2(GiantSize, GiantSize);
                }, go =>
                {
                    var split = go.AddComponent<OozeSplit>();
                    split.childPrefab = AssetDatabase.LoadAssetAtPath<GameObject>(PrefabPath);
                    split.childScale = ChildScale;
                    split.childSet = set;
                    split.leftRemains = left;
                    split.rightRemains = right;
                }, log);
                SavePrefab(model, avatar, "SmallOoze", SmallPrefabPath, fx, look =>
                {
                    look.preset = "";
                    look.randomFrom = new[] { "Green", "Grey", "Ochre" };
                    look.scale = new Vector2(0.5f, 0.6f);
                    look.hidden = new[] { "Skull", "Helm", "Sword" };       // it has only eaten rats
                }, null, log);

                if (scenes)
                {
                    BeastsTestScene.Build(log);
                    RenderPreview(ooze, giant, clips, dir, log);
                    if (clips.TryGetValue("Crawl", out var crawl)) TraceRootMotion(ooze, crawl, 3, log);
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

        struct Fx { public Material trail, drop, puddle, glob; public Mesh globMesh; }

        static GameObject SavePrefab(GameObject model, Avatar avatar, string name, string path, Fx fx,
                                     Action<OozeLook> setLook, Action<GameObject> extra, StringBuilder log)
        {
            var go = NewCreature(model, avatar, name);
            foreach (var smr in go.GetComponentsInChildren<SkinnedMeshRenderer>(true))
            {
                var b = smr.localBounds;
                b.Expand(BoundsPad * 2f);
                smr.localBounds = b;
                smr.shadowCastingMode = ShadowCastingMode.On;          // the jelly's caster is dithered by its opacity
            }
            if (go.GetComponent<BeastEvents>() == null) go.AddComponent<BeastEvents>();
            var look = go.AddComponent<OozeLook>();
            setLook(look);
            var f = go.AddComponent<OozeFx>();
            f.trailMaterial = fx.trail;
            f.dropMaterial = fx.drop;
            f.puddleMaterial = fx.puddle;
            f.globMaterial = fx.glob;
            f.globMesh = fx.globMesh;
            extra?.Invoke(go);
            var prefab = PrefabUtility.SaveAsPrefabAsset(go, path);
            Object.DestroyImmediate(go);
            log.AppendLine("  prefab: " + path);
            return prefab;
        }

        /// <summary>Which content bones sit on the left half's side (with HalfL) and which on the right, in the bind pose.</summary>
        static (string[] left, string[] right) RemainsBySide(GameObject model)
        {
            var t = model.GetComponentsInChildren<Transform>(true).ToDictionary(x => x.name);
            float side = Mathf.Sign(model.transform.InverseTransformPoint(t["HalfL"].position).x);
            var left = new List<string>();
            var right = new List<string>();
            foreach (var n in OozeLook.Remains)
            {
                if (!t.TryGetValue(n, out var b)) continue;
                float x = model.transform.InverseTransformPoint(b.position).x;
                (Mathf.Sign(x) == side || Mathf.Abs(x) < 1e-4f ? left : right).Add(n);
            }
            return (left.ToArray(), right.ToArray());
        }

        // ------------------------------------------------------------------------------------------- materials
        /// <summary>The jelly: Beasts/OozeJelly with T_Ooze (linear masks), the green preset by default. Falls back to
        /// URP Lit transparent if the shader is missing.</summary>
        static Material MakeJelly(string name, string texPath, StringBuilder log)
        {
            if (AssetImporter.GetAtPath(texPath) is TextureImporter ti)
            {
                ti.maxTextureSize = 1024;
                ti.sRGBTexture = false;                                 // masks, not colour
                ti.mipmapEnabled = true;
                ti.alphaSource = TextureImporterAlphaSource.FromInput;
                ti.alphaIsTransparency = false;
                ti.textureCompression = TextureImporterCompression.CompressedHQ;
                ti.SaveAndReimport();
            }
            var shader = Shader.Find(JellyShader);
            if (shader == null)
            {
                log.AppendLine($"  {JellyShader} not found: URP Lit transparent instead");
                return MakeTransparentLit(name, texPath, Color.white, 0.9f);
            }
            var mat = JellyMaterial(name, shader, AssetDatabase.LoadAssetAtPath<Texture2D>(texPath));
            return mat;
        }

        static Material JellyMaterial(string name, Shader shader, Texture2D masks)
        {
            var path = $"{Materials}/{name}.mat";
            var mat = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (mat == null)
            {
                mat = new Material(shader) { name = name };
                AssetDatabase.CreateAsset(mat, path);
            }
            mat.shader = shader;
            mat.SetTexture("_BaseMap", masks);
            var p = OozeLook.Find("Green");
            mat.SetColor("_ThinColor", p.thin);
            mat.SetColor("_MidColor", p.mid);
            mat.SetColor("_CoreColor", p.core);
            mat.SetColor("_CreviceColor", p.crevice);
            mat.SetFloat("_Opacity", p.opacity);
            mat.renderQueue = (int)RenderQueue.Transparent;
            EditorUtility.SetDirty(mat);
            return mat;
        }

        static Fx MakeFx(StringBuilder log)
        {
            var drop = SaveTexture("T_OozeDrop", 64, 64, (u, v) =>
            {
                float r = Mathf.Sqrt((u - 0.5f) * (u - 0.5f) + (v - 0.5f) * (v - 0.5f)) * 2f;
                float a = 1f - Smooth(0.72f, 1f, r);
                float hl = Mathf.Exp(-((u - 0.36f) * (u - 0.36f) + (v - 0.64f) * (v - 0.64f)) / 0.006f);
                float c = 0.82f + 0.18f * (1 - r) + 0.6f * hl;
                return new Color(c, c, c, a);
            }, true);
            var splat = SaveTexture("T_OozeSplat", 128, 128, (u, v) =>
            {
                float x = u - 0.5f, y = v - 0.5f;
                float ang = Mathf.Atan2(y, x);
                float rim = 0.36f + 0.05f * Mathf.Sin(ang * 5f + 0.7f) + 0.035f * Mathf.Sin(ang * 11f + 2.1f);
                float r = Mathf.Sqrt(x * x + y * y);
                float a = 1f - Smooth(rim - 0.05f, rim + 0.01f, r);
                for (int k = 0; k < 7; k++)                                // droplets thrown round it
                {
                    float da = k * 0.9f + 0.4f, dr = 0.42f + 0.03f * (k % 3);
                    float dx = x - Mathf.Cos(da) * dr, dy = y - Mathf.Sin(da) * dr;
                    a = Mathf.Max(a, 1f - Smooth(0.018f, 0.032f, Mathf.Sqrt(dx * dx + dy * dy)));
                }
                float c = 0.85f + 0.15f * Smooth(rim, 0f, r);
                return new Color(c, c, c, a * 0.95f);
            }, true);
            var trailTex = SaveTexture("T_OozeTrail", 64, 32, (u, v) =>
            {
                float w = 0.42f + 0.05f * Mathf.Sin(u * 18.8f) + 0.03f * Mathf.Sin(u * 43f + 1.3f);
                float a = 1f - Smooth(w - 0.12f, w, Mathf.Abs(v - 0.5f));
                return new Color(1, 1, 1, a);
            }, true);
            var flat = SaveTexture("T_OozeFlat", 8, 8, (u, v) => new Color(0.55f, 1f, 0.5f, 0.42f), false);

            var trail = ParticleMat("M_OozeTrail", trailTex, 0.95f);
            var dropM = ParticleMat("M_OozeDrop", drop, 0.9f);
            var puddle = ParticleMat("M_OozePuddle", splat, 0.95f);
            Material glob = null;
            var shader = Shader.Find(JellyShader);
            if (shader != null) glob = JellyMaterial("M_OozeGlob", shader, flat);
            var meshPath = Models + "/OozeGlob.asset";
            var mesh = AssetDatabase.LoadAssetAtPath<Mesh>(meshPath);
            if (mesh == null)
            {
                mesh = SphereMesh(14, 10);
                AssetDatabase.CreateAsset(mesh, meshPath);
            }
            log.AppendLine($"  fx: {trail?.name}, {dropM?.name}, {puddle?.name}, {glob?.name}, {mesh.name} ({mesh.triangles.Length / 3} tris)");
            return new Fx { trail = trail, drop = dropM, puddle = puddle, glob = glob, globMesh = mesh };
        }

        /// <summary>GLSL's smoothstep (Mathf.SmoothStep is an interpolation between its first two arguments: used as
        /// this, it left the drop, splat and trail textures nearly opaque everywhere).</summary>
        static float Smooth(float e0, float e1, float x)
        {
            float t = Mathf.Clamp01((x - e0) / (e1 - e0));
            return t * t * (3 - 2 * t);
        }

        static Texture2D SaveTexture(string name, int w, int h, Func<float, float, Color> f, bool srgb)
        {
            var tex = new Texture2D(w, h, TextureFormat.RGBA32, false, !srgb);
            for (int y = 0; y < h; y++)
                for (int x = 0; x < w; x++)
                    tex.SetPixel(x, y, f((x + 0.5f) / w, (y + 0.5f) / h));
            tex.Apply();
            var path = $"{FxDir}/{name}.png";
            File.WriteAllBytes(Path.GetFullPath(path), tex.EncodeToPNG());
            Object.DestroyImmediate(tex);
            AssetDatabase.ImportAsset(path);
            if (AssetImporter.GetAtPath(path) is TextureImporter ti)
            {
                ti.sRGBTexture = srgb;
                ti.alphaSource = TextureImporterAlphaSource.FromInput;
                ti.alphaIsTransparency = srgb;
                ti.mipmapEnabled = true;
                ti.wrapMode = TextureWrapMode.Clamp;
                ti.textureCompression = TextureImporterCompression.Uncompressed;
                ti.SaveAndReimport();
            }
            return AssetDatabase.LoadAssetAtPath<Texture2D>(path);
        }

        /// <summary>URP Particles/Lit, alpha blended, both faces, glossy: the wet effects (vertex colour tints them).</summary>
        static Material ParticleMat(string name, Texture2D tex, float smoothness)
        {
            var shader = Shader.Find("Universal Render Pipeline/Particles/Lit");
            if (shader == null) return null;
            var path = $"{Materials}/{name}.mat";
            var mat = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (mat == null)
            {
                mat = new Material(shader) { name = name };
                AssetDatabase.CreateAsset(mat, path);
            }
            mat.shader = shader;
            mat.SetTexture("_BaseMap", tex);
            mat.mainTexture = tex;
            mat.SetColor("_BaseColor", Color.white);
            mat.SetFloat("_Surface", 1f);
            mat.SetFloat("_Blend", 0f);
            mat.SetFloat("_BlendModePreserveSpecular", 0f);           // URP's default keeps reflections at full strength
            mat.DisableKeyword("_ALPHAPREMULTIPLY_ON");               // where the texture is clear: whole quads showed
            mat.SetFloat("_Cull", 0f);
            mat.SetFloat("_SrcBlend", (float)BlendMode.SrcAlpha);
            mat.SetFloat("_DstBlend", (float)BlendMode.OneMinusSrcAlpha);
            mat.SetFloat("_ZWrite", 0f);
            if (mat.HasProperty("_Smoothness")) mat.SetFloat("_Smoothness", smoothness);
            mat.EnableKeyword("_SURFACE_TYPE_TRANSPARENT");
            mat.SetOverrideTag("RenderType", "Transparent");
            mat.renderQueue = (int)RenderQueue.Transparent;
            EditorUtility.SetDirty(mat);
            return mat;
        }

        static Mesh SphereMesh(int seg, int rings)
        {
            var v = new List<Vector3>();
            var n = new List<Vector3>();
            var uv = new List<Vector2>();
            var tri = new List<int>();
            for (int i = 0; i <= rings; i++)
            {
                float th = Mathf.PI * i / rings;
                for (int j = 0; j <= seg; j++)
                {
                    float ph = 2 * Mathf.PI * j / seg;
                    var p = new Vector3(Mathf.Sin(th) * Mathf.Cos(ph), Mathf.Cos(th), Mathf.Sin(th) * Mathf.Sin(ph));
                    v.Add(p * 0.5f);
                    n.Add(p);
                    uv.Add(new Vector2((float)j / seg, 1f - (float)i / rings));
                }
            }
            for (int i = 0; i < rings; i++)
                for (int j = 0; j < seg; j++)
                {
                    int a = i * (seg + 1) + j, b = a + seg + 1;
                    tri.AddRange(new[] { a, a + 1, b, a + 1, b + 1, b });
                }
            var m = new Mesh { name = "OozeGlob" };
            m.SetVertices(v);
            m.SetNormals(n);
            m.SetUVs(0, uv);
            m.SetTriangles(tri, 0);
            m.RecalculateBounds();
            return m;
        }

        // ------------------------------------------------------------------------------------------- renders
        /// <summary>Verification renders in a preview scene (the open scenes are not touched), shaders compiled
        /// synchronously (the first render after an import otherwise skips the jelly):
        ///   lineup.png        the clips posed in a row, a goblin for scale
        ///   presets.png       the colour presets side by side, with a giant and a small one
        ///   split.png         the giant splitting: the strand just before the snap, then the two halves (Reform's
        ///                     first frame) where OozeSplit puts them, from the same camera
        ///   close.png, lineup_colony_40m.png
        /// </summary>
        static void RenderPreview(GameObject ooze, GameObject giant, Dictionary<string, AnimationClip> clips, string dir,
                                  StringBuilder log)
        {
            bool async = ShaderUtil.allowAsyncCompilation;
            ShaderUtil.allowAsyncCompilation = false;
            try
            {
                var poses = new (string, float)[]
                {
                    ("Idle", 1f), ("Crawl", 0.5f), ("Lash", 0.67f), ("Grab", 0.6f), ("Engulf", 1.15f),
                    ("Spit", 0.7f), ("Death", 2.3f), ("Rise", 0.75f),
                };
                float spacing = 3.6f, x0 = -(poses.Length - 1) * 0.5f * spacing, w = poses.Length * spacing;
                Stage(s =>
                {
                    for (int i = 0; i < poses.Length; i++)
                        Pose(s, ooze, clips, poses[i].Item1, poses[i].Item2, new Vector3(x0 + i * spacing, 0, 0), "Green", 1f);
                    Goblin(s, new Vector3(x0 - 2.6f, 0, 0.8f));
                    Shoot(s, "CAM_Lineup", new Vector3(0, 4.1f, -w * 0.62f), new Vector3(0, 0.6f, 0), 45, dir, "lineup.png", 1800, 800);
                    Shoot(s, "CAM_Close", new Vector3(x0 + 2.0f, 2.2f, -4.6f), new Vector3(x0, 0.6f, 0), 40, dir, "close.png", 1200, 900);
                    Shoot(s, "CAM_Colony", new Vector3(0, 40 * Mathf.Sin(50 * Mathf.Deg2Rad), -40 * Mathf.Cos(50 * Mathf.Deg2Rad)),
                          new Vector3(0, 0.5f, 0), 30, dir, "lineup_colony_40m.png", 1600, 900);
                });
                Stage(s =>
                {
                    var names = AllPresets;
                    for (int i = 0; i < names.Length; i++)
                        Pose(s, ooze, clips, "Idle", 1f, new Vector3((i - (names.Length - 1) * 0.5f) * 3.4f, 0, 0), names[i], 1f);
                    Pose(s, giant, clips, "Idle", 1f, new Vector3(-2.5f, 0, 5.5f), "Black", GiantSize);
                    var small = AssetDatabase.LoadAssetAtPath<GameObject>(SmallPrefabPath);
                    Pose(s, small, clips, "Idle", 1f, new Vector3(4.2f, 0, 4.5f), "Grey", 0.55f, new[] { "Skull", "Helm", "Sword" });
                    Goblin(s, new Vector3(1.2f, 0, 4.2f));
                    Shoot(s, "CAM_Presets", new Vector3(0, 7.5f, -13.5f), new Vector3(0, 0.6f, 2.2f), 42, dir, "presets.png", 1800, 900);
                });
                Stage(s =>
                {
                    var g = Pose(s, giant, clips, "Split", SplitAt - 0.01f, new Vector3(-3.6f, 0, 0), "Green", GiantSize);
                    var split = giant.GetComponent<OozeSplit>();
                    var halves = g.GetComponentsInChildren<Transform>().Where(t => t.name == "HalfL" || t.name == "HalfR").ToArray();
                    foreach (var h in halves)
                    {
                        var at = h.position + new Vector3(7.2f, 0, 0);
                        at.y = 0;
                        bool isLeft = h.name == "HalfL";
                        Pose(s, ooze, clips, "Reform", 0f, at, "Green", GiantSize * ChildScale,
                             isLeft ? split.rightRemains : split.leftRemains, Quaternion.Euler(0, 200f + (isLeft ? 25 : -25), 0));
                    }
                    Shoot(s, "CAM_Split", new Vector3(0, 8.5f, -9.5f), new Vector3(0, 0.6f, 0), 48, dir, "split.png", 1800, 900);
                });
                log.AppendLine("  renders: " + dir);
            }
            finally
            {
                ShaderUtil.allowAsyncCompilation = async;
            }
        }

        static void Stage(Action<Scene> fill)
        {
            var scene = EditorSceneManager.NewPreviewScene();
            try
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
                fill(scene);
            }
            finally
            {
                EditorSceneManager.ClosePreviewScene(scene);
            }
        }

        static GameObject Pose(Scene s, GameObject prefab, Dictionary<string, AnimationClip> clips, string clip, float t,
                               Vector3 at, string preset, float size, string[] hidden = null, Quaternion? rot = null)
        {
            var go = (GameObject)PrefabUtility.InstantiatePrefab(prefab, s);
            go.transform.SetPositionAndRotation(at, rot ?? Quaternion.Euler(0, 200f, 0));
            var look = go.GetComponent<OozeLook>();
            if (look != null) look.Apply(preset, size, hidden ?? look.hidden);
            if (clips.TryGetValue(clip, out var c)) c.SampleAnimation(go, Mathf.Min(t, c.length));
            if (look != null) look.UpdateRemains();
            foreach (var smr in go.GetComponentsInChildren<SkinnedMeshRenderer>()) smr.forceMatrixRecalculationPerRender = true;
            return go;
        }

        static void Goblin(Scene s, Vector3 at)
        {
            var gob = AssetDatabase.LoadAssetAtPath<GameObject>("Assets/Goblins/Prefabs/Goblin_Spearman.prefab");
            if (gob == null) return;
            var g = (GameObject)PrefabUtility.InstantiatePrefab(gob, s);
            g.transform.SetPositionAndRotation(at, Quaternion.Euler(0, 180f, 0));
        }

        static void Shoot(Scene s, string name, Vector3 pos, Vector3 target, float fov, string dir, string file, int w, int h)
        {
            var cam = MakeCamera(name, pos, target, fov);
            SceneManager.MoveGameObjectToScene(cam.gameObject, s);
            cam.scene = s;
            Render(cam, dir, file, w, h);
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
                go.transform.localScale = Vector3.one;
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

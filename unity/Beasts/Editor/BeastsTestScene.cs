using System.Collections.Generic;
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;
using static Beasts.EditorTools.BeastSetupUtil;

namespace Beasts.EditorTools
{
    /// <summary>
    /// Scenes/Beasts_Test: a wolf pack, a rat swarm, the woolly rhino, bears, a mammoth, deer and oozes (two, three small,
    /// a giant that splits) on random clips, and goblins around them (if Assets/Goblins is installed).
    /// Press Play. Tools > Beasts > Build Test Scene; the beast setups rebuild it too.
    /// </summary>
    public static class BeastsTestScene
    {
        public const string ScenePath = Scenes + "/Beasts_Test.unity";

        [MenuItem("Tools/Beasts/Build Test Scene")]
        public static void BuildMenu()
        {
            var log = new StringBuilder();
            Build(log);
            Debug.Log(log.ToString());
        }

        /// <summary>Built beside whatever is open (other tools and sessions keep their scenes): the test scene is
        /// created additively (or rebuilt in place if it is open), active only while it is filled, saved, and closed
        /// again if it wasn't open. When all that's open is an empty untitled scene (batch mode, a fresh project),
        /// there is nothing to keep, and Unity won't add a scene beside an unsaved one: it is built in its place.</summary>
        public static void Build(StringBuilder log)
        {
            var target = SceneManager.GetSceneByPath(ScenePath);
            bool wasOpen = target.IsValid() && target.isLoaded;
            if (wasOpen && target.isDirty)
            {
                log.AppendLine("  test scene skipped: it is open with unsaved changes (save it, then Tools > Beasts > Build Test Scene)");
                return;
            }
            var previous = SceneManager.GetActiveScene();
            bool untitled = !wasOpen && string.IsNullOrEmpty(previous.path) && SceneManager.sceneCount == 1;
            if (untitled && previous.isDirty)
            {
                log.AppendLine("  test scene skipped: the open untitled scene has unsaved changes (save it first)");
                return;
            }
            Scene scene;
            if (wasOpen)
            {
                scene = target;
                foreach (var r in scene.GetRootGameObjects()) Object.DestroyImmediate(r);
            }
            else scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, untitled ? NewSceneMode.Single : NewSceneMode.Additive);
            SceneManager.SetActiveScene(scene);
            try
            {
                Fill(scene, log);
                EditorSceneManager.SaveScene(scene, ScenePath);
            }
            finally
            {
                if (!untitled && previous.IsValid() && previous.isLoaded && previous != scene) SceneManager.SetActiveScene(previous);
                if (!wasOpen && !untitled) EditorSceneManager.CloseScene(scene, true);
            }
        }

        static void Fill(Scene scene, StringBuilder log)
        {
            Lighting(60f);
            var rng = new System.Random(11);
            var taken = new List<Vector3>();
            Vector3 Spot(float radius, float spacing)
            {
                for (int tries = 0; tries < 500; tries++)
                {
                    var p = new Vector3((float)(rng.NextDouble() * 2 - 1) * radius, 0, (float)(rng.NextDouble() * 2 - 1) * radius);
                    if (p.magnitude <= radius && taken.All(s => (s - p).magnitude > spacing)) { taken.Add(p); return p; }
                }
                return Vector3.zero;
            }
            var counts = new List<string>();
            foreach (var (prefabPath, setPath, label, plural, count, spacing, labelHeight, separation) in new[]
            {
                (WolfSetup.PrefabPath, WolfSetup.SetPath, "Wolf", "wolves", 7, 3.5f, 1.3f, 2.2f),
                (RatSetup.PrefabPath, RatSetup.SetPath, "Rat", "rats", 10, 2.0f, 0.7f, 1.3f),
                (RhinoSetup.PrefabPath, RhinoSetup.SetPath, "Rhino", "rhinos", 1, 6.0f, 2.3f, 4.0f),
                (BearSetup.PrefabPath, BearSetup.SetPath, "Bear", "bears", 2, 5.0f, 2.0f, 3.0f),
                (MammothSetup.PrefabPath, MammothSetup.SetPath, "Mammoth", "mammoths", 1, 8.0f, 3.5f, 5.0f),
                (DeerSetup.PrefabPath, DeerSetup.SetPath, "Deer", "deer", 3, 4.5f, 2.6f, 3.0f),
                (OozeSetup.PrefabPath, OozeSetup.SetPath, "Ooze", "oozes", 2, 6.0f, 1.6f, 3.5f),
                (OozeSetup.SmallPrefabPath, OozeSetup.SetPath, "SmallOoze", "small oozes", 3, 3.0f, 0.9f, 2.0f),
                (OozeSetup.GiantPrefabPath, OozeSetup.GiantSetPath, "GiantOoze", "giant oozes", 1, 8.0f, 2.5f, 5.5f),
                (WargSetup.PrefabPath, WargSetup.SetPath, "Warg", "wargs", 2, 5.0f, 1.9f, 3.2f),
                (WargSetup.RiddenPrefabPath, WargSetup.SetPath, "WargRidden", "saddled wargs", 2, 5.0f, 2.0f, 3.2f),
            })
            {
                var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(prefabPath);
                var set = AssetDatabase.LoadAssetAtPath<BeastAnimationSet>(setPath);
                if (prefab == null || set == null) continue;
                var parent = new GameObject(char.ToUpper(plural[0]) + plural.Substring(1)).transform;
                for (int i = 0; i < count; i++)
                {
                    var go = (GameObject)PrefabUtility.InstantiatePrefab(prefab, scene);
                    go.name = $"{label}_{i:00}";
                    go.transform.SetParent(parent, false);
                    go.transform.SetPositionAndRotation(Spot(10f, spacing), Quaternion.Euler(0, (float)rng.NextDouble() * 360f, 0));
                    var ra = go.AddComponent<BeastRandomAnimator>();
                    ra.set = set;
                    ra.home = Vector3.zero;
                    ra.wanderRadius = 13f;
                    ra.separation = separation;
                    ra.labelHeight = labelHeight;
                    var split = go.GetComponent<OozeSplit>();
                    if (split != null) split.respawnAfter = 25f;            // a split giant comes back to be watched again
                }
                counts.Add($"{count} {plural}");
            }
            int goblins = AddGoblins(rng, 8);
            var cam = new GameObject("Camera").AddComponent<Camera>();
            cam.tag = "MainCamera";
            cam.fieldOfView = 35f;
            cam.farClipPlane = 400f;
            cam.clearFlags = CameraClearFlags.SolidColor;
            cam.backgroundColor = new Color(0.47f, 0.52f, 0.58f);
            var ui = cam.gameObject.AddComponent<BeastTestUI>();
            ui.distance = 26f;
            ui.pitch = 36f;
            log.AppendLine($"  test scene: {ScenePath} ({string.Join(", ", counts)}, {goblins} goblins)");
        }

        /// <summary>Verification renders (not saved): the creature posed from its clips in a row, a goblin for scale.</summary>
        public static void RenderLineup(GameObject prefab, Dictionary<string, AnimationClip> clips, (string clip, float t)[] poses,
                                        string dir, float spacing, float lookHeight, StringBuilder log)
        {
            // in a preview scene (2026-10-12): the open scenes, other tools' and other sessions', are never touched
            var scene = EditorSceneManager.NewPreviewScene();
            bool async = ShaderUtil.allowAsyncCompilation;
            ShaderUtil.allowAsyncCompilation = false;
            try
            {
                void Add(GameObject g) => SceneManager.MoveGameObjectToScene(g, scene);
                var ground = GameObject.CreatePrimitive(PrimitiveType.Plane);
                Add(ground);
                ground.transform.localScale = new Vector3(4, 1, 4);
                var gm = AssetDatabase.LoadAssetAtPath<Material>(Scenes + "/M_BeastGround.mat");
                if (gm != null) ground.GetComponent<Renderer>().sharedMaterial = gm;
                var sun = new GameObject("Sun").AddComponent<Light>();
                Add(sun.gameObject);
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
                    g.transform.SetPositionAndRotation(new Vector3(x0 - 2.2f, 0, 0.8f), Quaternion.Euler(0, 180f, 0));
                }
                float w = poses.Length * spacing;
                void Shoot(string name, Vector3 pos, Vector3 at, float fov, string file, int pw, int ph, bool warm = false)
                {
                    var cam = MakeCamera(name, pos, at, fov);
                    Add(cam.gameObject);
                    cam.scene = scene;
                    if (warm) Render(cam, dir, file, pw, ph);    // the first render of fresh skinned meshes can come out
                    Render(cam, dir, file, pw, ph);              // empty (shadows only): render it twice
                }
                Shoot("CAM_Lineup", new Vector3(0, 3.5f + lookHeight, -w * 0.72f), new Vector3(0, lookHeight, 0), 45, "lineup.png", 1800, 800, true);
                Shoot("CAM_Close", new Vector3(x0 + 1.3f, 1.2f + lookHeight, -4.2f), new Vector3(x0, lookHeight, 0), 38, "close.png", 1200, 900);
                Shoot("CAM_Colony", new Vector3(0, 40 * Mathf.Sin(50 * Mathf.Deg2Rad), -40 * Mathf.Cos(50 * Mathf.Deg2Rad)),
                      new Vector3(0, 0.5f, 0), 30, "lineup_colony_40m.png", 1600, 900);
                log.AppendLine("  renders: " + dir);
            }
            finally
            {
                ShaderUtil.allowAsyncCompilation = async;
                EditorSceneManager.ClosePreviewScene(scene);
            }
        }

        /// <summary>Goblins from Assets/Goblins (if installed) on their own random clips around the pack.
        /// Added by type name so this package does not depend on the goblin scripts.</summary>
        static int AddGoblins(System.Random rng, int count)
        {
            var kinds = new[]
            {
                ("Assets/Goblins/Prefabs/Goblin_Spearman.prefab", "Assets/Goblins/Animation/GoblinAnims_Polearm.asset", true),
                ("Assets/Goblins/Prefabs/Goblin_Swordsman.prefab", "Assets/Goblins/Animation/GoblinAnims_SwordShield.asset", false),
                ("Assets/Goblins/Prefabs/Goblin_Archer.prefab", "Assets/Goblins/Animation/GoblinAnims_Archer.asset", false),
            };
            var animType = FindType("Goblins.GoblinRandomAnimator");
            var postureType = FindType("Goblins.GoblinPosture");
            var gripType = FindType("Goblins.GoblinTwoHandGrip");
            var root = new GameObject("Goblins").transform;
            int n = 0;
            for (int i = 0; i < count; i++)
            {
                var (prefabPath, setPath, twoHanded) = kinds[i % kinds.Length];
                var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(prefabPath);
                if (prefab == null) continue;
                float a = i * Mathf.PI * 2f / count + (float)rng.NextDouble() * 0.3f;
                var home = new Vector3(Mathf.Cos(a), 0, Mathf.Sin(a)) * 17f;
                var g = (GameObject)PrefabUtility.InstantiatePrefab(prefab);
                g.name = prefab.name + "_" + i.ToString("00");
                g.transform.SetParent(root, false);
                g.transform.SetPositionAndRotation(home, Quaternion.LookRotation(-home.normalized, Vector3.up));
                var gset = AssetDatabase.LoadAssetAtPath<ScriptableObject>(setPath);
                if (animType != null && gset != null)
                {
                    var comp = g.AddComponent(animType);
                    var so = new SerializedObject(comp);
                    so.FindProperty("set").objectReferenceValue = gset;
                    so.FindProperty("home").vector3Value = home;
                    so.FindProperty("wanderRadius").floatValue = 3.5f;
                    so.ApplyModifiedPropertiesWithoutUndo();
                    if (postureType != null) g.AddComponent(postureType);
                    if (twoHanded && gripType != null) g.AddComponent(gripType);
                }
                n++;
            }
            return n;
        }
    }
}

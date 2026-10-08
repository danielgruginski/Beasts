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
    /// Scenes/Beasts_Test: a wolf pack, a rat swarm and the woolly rhino on random clips, and goblins around them (if
    /// Assets/Goblins is installed).
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

        static bool AnyDirty() => Enumerable.Range(0, SceneManager.sceneCount).Any(i => SceneManager.GetSceneAt(i).isDirty);

        public static void Build(StringBuilder log)
        {
            if (AnyDirty())
            {
                log.AppendLine("  test scene skipped: an open scene has unsaved changes (save it, then Tools > Beasts > Build Test Scene)");
                return;
            }
            var previousPath = SceneManager.GetActiveScene().path;
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
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
            EditorSceneManager.SaveScene(scene, ScenePath);
            log.AppendLine($"  test scene: {ScenePath} ({string.Join(", ", counts)}, {goblins} goblins)");
            if (!string.IsNullOrEmpty(previousPath) && AssetDatabase.LoadAssetAtPath<SceneAsset>(previousPath) != null)
                EditorSceneManager.OpenScene(previousPath, OpenSceneMode.Single);
        }

        /// <summary>Verification renders (not saved): the creature posed from its clips in a row, a goblin for scale.</summary>
        public static void RenderLineup(GameObject prefab, Dictionary<string, AnimationClip> clips, (string clip, float t)[] poses,
                                        string dir, float spacing, float lookHeight, StringBuilder log)
        {
            if (AnyDirty())
            {
                log.AppendLine("  renders skipped: an open scene has unsaved changes");
                return;
            }
            var previousPath = SceneManager.GetActiveScene().path;
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            Lighting(40f);
            float x0 = -(poses.Length - 1) * 0.5f * spacing;
            for (int i = 0; i < poses.Length; i++)
            {
                var go = (GameObject)PrefabUtility.InstantiatePrefab(prefab);
                go.transform.position = new Vector3(x0 + i * spacing, 0, 0);
                go.transform.rotation = Quaternion.Euler(0, 200f, 0);
                if (clips.TryGetValue(poses[i].clip, out var c)) c.SampleAnimation(go, Mathf.Min(poses[i].t, c.length));
            }
            var gob = AssetDatabase.LoadAssetAtPath<GameObject>("Assets/Goblins/Prefabs/Goblin_Spearman.prefab");
            if (gob != null)
            {
                var g = (GameObject)PrefabUtility.InstantiatePrefab(gob);
                g.transform.SetPositionAndRotation(new Vector3(x0 - 2.2f, 0, 0.8f), Quaternion.Euler(0, 180f, 0));
            }
            float w = poses.Length * spacing;
            Render(MakeCamera("CAM_Lineup", new Vector3(0, 3.5f + lookHeight, -w * 0.72f), new Vector3(0, lookHeight, 0), 45), dir, "lineup.png", 1800, 800);
            Render(MakeCamera("CAM_Close", new Vector3(x0 + 1.3f, 1.2f + lookHeight, -4.2f), new Vector3(x0, lookHeight, 0), 38), dir, "close.png", 1200, 900);
            Render(MakeCamera("CAM_Colony", new Vector3(0, 40 * Mathf.Sin(50 * Mathf.Deg2Rad), -40 * Mathf.Cos(50 * Mathf.Deg2Rad)),
                              new Vector3(0, 0.5f, 0), 30), dir, "lineup_colony_40m.png", 1600, 900);
            log.AppendLine("  renders: " + dir);
            if (!string.IsNullOrEmpty(previousPath) && AssetDatabase.LoadAssetAtPath<SceneAsset>(previousPath) != null)
                EditorSceneManager.OpenScene(previousPath, OpenSceneMode.Single);
            else if (AssetDatabase.LoadAssetAtPath<SceneAsset>(ScenePath) != null)
                EditorSceneManager.OpenScene(ScenePath, OpenSceneMode.Single);
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

using System.Collections.Generic;
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEngine;
using UnityEngine.SceneManagement;
using static Beasts.EditorTools.BeastSetupUtil;

namespace Beasts.EditorTools
{
    /// <summary>
    /// Scenes/Farm_Test: the farm animals in small groups on a field, each group grazing and wandering round its own
    /// patch on random clips, a few goblins for scale (if Assets/Goblins is installed). Press Play. Tools > Beasts >
    /// Build Farm Test Scene; <see cref="FarmSetup"/> rebuilds it too. Built beside whatever is open, like
    /// <see cref="BeastsTestScene"/>.
    /// </summary>
    public static class FarmTestScene
    {
        public const string ScenePath = Scenes + "/Farm_Test.unity";

        [MenuItem("Tools/Beasts/Build Farm Test Scene")]
        public static void BuildMenu()
        {
            var log = new StringBuilder();
            Build(log);
            Debug.Log(log.ToString());
        }

        public static void Build(StringBuilder log) => BeastsTestScene.BuildScene(ScenePath, Fill, log);

        static void Fill(Scene scene, StringBuilder log)
        {
            Lighting(80f);
            var rng = new System.Random(5);
            var counts = new List<string>();
            // (animal, how many, patch centre, patch radius, spacing, label height, separation)
            foreach (var (name, count, centre, radius, spacing, labelHeight, separation) in new[]
            {
                ("Goat", 5, new Vector3(-9, 0, 6), 4f, 1.4f, 1.1f, 0.9f),
                ("Sheep", 6, new Vector3(0, 0, 9), 4.5f, 1.4f, 1.1f, 0.9f),
                ("Cow", 3, new Vector3(9, 0, 5), 5f, 3f, 1.8f, 2f),
                ("Horse", 2, new Vector3(8, 0, -7), 5f, 3.2f, 2.1f, 2.2f),
                ("Pig", 4, new Vector3(-8, 0, -6), 3.5f, 1.6f, 1f, 1.1f),
                ("Chicken", 10, new Vector3(0, 0, -2), 3f, 0.5f, 0.6f, 0.35f),
            })
            {
                var a = FarmSetup.Get(name);
                var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(a.PrefabPath);
                var set = AssetDatabase.LoadAssetAtPath<BeastAnimationSet>(a.SetPath);
                if (prefab == null || set == null) continue;
                var plural = name == "Sheep" ? "Sheep" : name + "s";
                var parent = new GameObject(plural).transform;
                var taken = new List<Vector3>();
                for (int i = 0; i < count; i++)
                {
                    var p = centre;
                    for (int tries = 0; tries < 200; tries++)
                    {
                        var q = centre + new Vector3((float)(rng.NextDouble() * 2 - 1), 0, (float)(rng.NextDouble() * 2 - 1)) * radius;
                        if (taken.All(t => (t - q).magnitude > spacing)) { p = q; break; }
                    }
                    taken.Add(p);
                    var go = (GameObject)PrefabUtility.InstantiatePrefab(prefab, scene);
                    go.name = $"{name}_{i:00}";
                    go.transform.SetParent(parent, false);
                    go.transform.SetPositionAndRotation(p, Quaternion.Euler(0, (float)rng.NextDouble() * 360f, 0));
                    var ra = go.AddComponent<BeastRandomAnimator>();
                    ra.set = set;
                    ra.home = centre;
                    ra.wanderRadius = radius * 1.5f;
                    ra.separation = separation;
                    ra.labelHeight = labelHeight;
                }
                counts.Add($"{count} {plural.ToLowerInvariant()}");
            }
            int goblins = BeastsTestScene.AddGoblins(rng, 3, 15f, 2f);
            var cam = new GameObject("Camera").AddComponent<Camera>();
            cam.tag = "MainCamera";
            cam.fieldOfView = 35f;
            cam.farClipPlane = 400f;
            cam.clearFlags = CameraClearFlags.SolidColor;
            cam.backgroundColor = new Color(0.47f, 0.52f, 0.58f);
            var ui = cam.gameObject.AddComponent<BeastTestUI>();
            ui.distance = 24f;
            ui.pitch = 36f;
            log.AppendLine($"  farm test scene: {ScenePath} ({string.Join(", ", counts)}, {goblins} goblins)");
        }
    }
}

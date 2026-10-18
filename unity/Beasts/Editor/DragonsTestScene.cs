using System.Collections.Generic;
using System.Text;
using UnityEditor;
using UnityEngine;
using UnityEngine.SceneManagement;
using static Beasts.EditorTools.BeastSetupUtil;

namespace Beasts.EditorTools
{
    /// <summary>
    /// Scenes/Dragons_Test: two dragons and two hydras on random clips over a wide field -- the dragons breathe fire and
    /// take off, fly a while and land (the "Flight" pool) -- with goblins around them for scale (if Assets/Goblins is
    /// installed). The viewer's presets are widened (presetScale 2.5) and it can follow one creature ("Follow next").
    /// Press Play. Tools > Beasts > Build Dragons Test Scene; DragonSetup and HydraSetup rebuild it too. Built beside
    /// whatever is open, like <see cref="BeastsTestScene"/>.
    /// </summary>
    public static class DragonsTestScene
    {
        public const string ScenePath = Scenes + "/Dragons_Test.unity";

        [MenuItem("Tools/Beasts/Build Dragons Test Scene")]
        public static void BuildMenu()
        {
            var log = new StringBuilder();
            Build(log);
            Debug.Log(log.ToString());
        }

        public static void Build(StringBuilder log) => BeastsTestScene.BuildScene(ScenePath, Fill, log);

        static void Fill(Scene scene, StringBuilder log)
        {
            Lighting(320f);
            var rng = new System.Random(7);
            var counts = new List<string>();
            foreach (var (prefabPath, setPath, label, plural, spots, wander, labelHeight, separation) in new[]
            {
                (DragonSetup.PrefabPath, DragonSetup.SetPath, "Dragon", "dragons",
                 new[] { new Vector3(-16, 0, 8), new Vector3(18, 0, -6) }, 45f, 6f, 9f),
                (HydraSetup.PrefabPath, HydraSetup.SetPath, "Hydra", "hydras",
                 new[] { new Vector3(-6, 0, -18), new Vector3(9, 0, 16) }, 30f, 4.5f, 7f),
            })
            {
                var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(prefabPath);
                var set = AssetDatabase.LoadAssetAtPath<BeastAnimationSet>(setPath);
                if (prefab == null || set == null) continue;
                var parent = new GameObject(char.ToUpper(plural[0]) + plural.Substring(1)).transform;
                for (int i = 0; i < spots.Length; i++)
                {
                    var go = (GameObject)PrefabUtility.InstantiatePrefab(prefab, scene);
                    go.name = $"{label}_{i:00}";
                    go.transform.SetParent(parent, false);
                    go.transform.SetPositionAndRotation(spots[i], Quaternion.Euler(0, (float)rng.NextDouble() * 360f, 0));
                    var ra = go.AddComponent<BeastRandomAnimator>();
                    ra.set = set;
                    ra.home = Vector3.zero;
                    ra.wanderRadius = wander;
                    ra.separation = separation;
                    ra.labelHeight = labelHeight;
                }
                counts.Add($"{spots.Length} {plural}");
            }
            int goblins = BeastsTestScene.AddGoblins(rng, 6, 30f, 4f);
            var cam = new GameObject("Camera").AddComponent<Camera>();
            cam.tag = "MainCamera";
            cam.fieldOfView = 35f;
            cam.farClipPlane = 900f;
            cam.clearFlags = CameraClearFlags.SolidColor;
            cam.backgroundColor = new Color(0.47f, 0.52f, 0.58f);
            var ui = cam.gameObject.AddComponent<BeastTestUI>();
            ui.focus = new Vector3(0, 2.5f, 0);
            ui.distance = 62f;
            ui.pitch = 28f;
            ui.presetScale = 2.5f;
            log.AppendLine($"  dragons test scene: {ScenePath} ({string.Join(", ", counts)}, {goblins} goblins)");
        }
    }
}

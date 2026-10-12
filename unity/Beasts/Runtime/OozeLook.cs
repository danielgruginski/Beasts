using System;
using System.Collections.Generic;
using UnityEngine;

namespace Beasts
{
    /// <summary>
    /// An ooze's look, rolled in Awake: a colour preset (the jelly shader maps T_Ooze's masks through its four colours,
    /// set per renderer with a MaterialPropertyBlock, so one material serves every colour), a size, and which of the
    /// remains inside show. In a big ooze the remains keep their real size (a giant's skull would read as a giant's).
    /// <see cref="Apply"/> sets a look after Awake (OozeSplit does, for the two halves of a split).
    /// </summary>
    public class OozeLook : MonoBehaviour
    {
        [Serializable]
        public struct Preset
        {
            public string name;
            public Color thin, mid, core, crevice;
            public float opacity;
            public Preset(string n, string t, string m, string c, string cr, float o)
            {
                name = n;
                thin = Hex(t);
                mid = Hex(m);
                core = Hex(c);
                crevice = Hex(cr);
                opacity = o;
            }
        }

        /// <summary>Same as ooze_paint.PRESETS in Blender.</summary>
        public static readonly Preset[] Presets =
        {
            new Preset("Green", "#a6d455", "#4f8c1c", "#2c5a12", "#173208", 1f),       // acid ooze
            new Preset("Grey", "#c4c8bf", "#868c84", "#4c524c", "#22261f", 1f),        // grey ooze
            new Preset("Black", "#5c4e62", "#2a2231", "#130f17", "#060408", 1.45f),    // black pudding
            new Preset("Ochre", "#f2d173", "#c88f2e", "#7e4f19", "#3a2208", 1f),       // ochre jelly
            new Preset("Crimson", "#e58272", "#a42c26", "#5a0f11", "#260405", 1.1f),
        };

        /// <summary>Content bones (the remains and the vacuoles) as the model names them.</summary>
        public static readonly string[] Remains =
            { "Skull", "Femur", "Shin", "Helm", "Sword", "Coins", "Vac1", "Vac2", "Vac3", "Vac4", "Vac5", "Vac6", "Vac7" };

        [Tooltip("Preset name; empty = random from randomFrom.")]
        public string preset = "Green";
        public string[] randomFrom = new string[0];
        [Tooltip("Uniform scale range.")]
        public Vector2 scale = new Vector2(0.9f, 1.1f);
        [Tooltip("Remains keep their real size when the ooze is bigger than 1 (they scale down with smaller ones).")]
        public bool lifeSizeRemains = true;
        [Tooltip("Content bones not shown (e.g. the half of a split that went the other way).")]
        public string[] hidden = new string[0];
        [Tooltip("0 = random every time.")]
        public int seed;

        public Preset Current { get; private set; }
        public string Summary => $"{Current.name} x{transform.localScale.x:0.00}";

        static readonly int ThinId = Shader.PropertyToID("_ThinColor"), MidId = Shader.PropertyToID("_MidColor"),
            CoreId = Shader.PropertyToID("_CoreColor"), CreviceId = Shader.PropertyToID("_CreviceColor"),
            OpacityId = Shader.PropertyToID("_Opacity");

        Renderer shell;
        MaterialPropertyBlock mpb;
        readonly List<Transform> remains = new List<Transform>();
        readonly List<bool> hide = new List<bool>();
        Vector3[] lastSet = new Vector3[0];

        void Awake()
        {
            var rng = new System.Random(seed != 0 ? seed : UnityEngine.Random.Range(1, int.MaxValue));
            string p = string.IsNullOrEmpty(preset) && randomFrom.Length > 0 ? randomFrom[rng.Next(randomFrom.Length)] : preset;
            Apply(p, Mathf.Lerp(scale.x, scale.y, (float)rng.NextDouble()), hidden);
        }

        public static Preset Find(string name)
        {
            foreach (var p in Presets) if (p.name == name) return p;
            return Presets[0];
        }

        /// <summary>Set the colour preset, the size (uniform scale) and the hidden content bones.</summary>
        public void Apply(string presetName, float size, string[] hiddenBones)
        {
            preset = presetName;
            hidden = hiddenBones ?? new string[0];
            Current = Find(presetName);
            transform.localScale = Vector3.one * size;
            if (shell == null)
            {
                foreach (var smr in GetComponentsInChildren<SkinnedMeshRenderer>(true))
                    if (smr.name == "OozeBody") shell = smr;
            }
            if (shell != null)
            {
                mpb ??= new MaterialPropertyBlock();
                shell.GetPropertyBlock(mpb);
                mpb.SetColor(ThinId, Current.thin);
                mpb.SetColor(MidId, Current.mid);
                mpb.SetColor(CoreId, Current.core);
                mpb.SetColor(CreviceId, Current.crevice);
                mpb.SetFloat(OpacityId, Current.opacity);
                shell.SetPropertyBlock(mpb);
            }
            remains.Clear();
            hide.Clear();
            var bones = new Dictionary<string, Transform>();
            foreach (var t in GetComponentsInChildren<Transform>(true)) bones[t.name] = t;
            foreach (var n in Remains)
                if (bones.TryGetValue(n, out var t))
                {
                    remains.Add(t);
                    hide.Add(Array.IndexOf(hidden, n) >= 0);
                }
            lastSet = new Vector3[remains.Count];
            for (int i = 0; i < lastSet.Length; i++) lastSet[i] = new Vector3(float.NaN, 0, 0);
        }

        /// <summary>After the Animator: hidden pieces to nothing; in a big ooze the rest back to their real size. The
        /// clips key these bones' scale (or don't, if Unity dropped constant curves), so a value is only adjusted
        /// once per write: a value still equal to the last one set here was not rewritten.</summary>
        void LateUpdate() => UpdateRemains();

        /// <summary>LateUpdate's work, callable in edit mode (after sampling a clip for a render).</summary>
        public void UpdateRemains()
        {
            float k = transform.lossyScale.x;
            float remainsK = lifeSizeRemains && k > 1f ? 1f / k : 1f;
            for (int i = 0; i < remains.Count; i++)
            {
                var t = remains[i];
                var s = t.localScale;
                if (s == lastSet[i]) continue;
                t.localScale = hide[i] ? Vector3.zero : s * remainsK;
                lastSet[i] = t.localScale;
            }
        }

        static Color Hex(string h)
        {
            ColorUtility.TryParseHtmlString(h, out var c);
            return c;
        }
    }
}

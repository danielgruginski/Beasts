using UnityEngine;
using UnityEngine.Rendering;

namespace Beasts
{
    /// <summary>
    /// A dragon's fire breath: a cone of flame from <see cref="mouth"/> (Socket_Mouth) between the clip's events
    /// (<c>OnBeastEvent</c> "Fire" starts it, "FireEnd" stops it, and it never runs longer than <see cref="maxSeconds"/>,
    /// so a clip cut short by a crossfade can't leave it burning). Built in Awake: a flame body, a hot additive core,
    /// smoke and an orange light, in world space so the stream bends as the head sweeps, and bouncing off colliders
    /// (the ground). The flame materials are the game's Resources/FX/M_FX_FlameBody, M_FX_FlameCore and M_FX_Smoke when
    /// the project has them (8 x 8 and 4 x 4 flipbooks); a soft additive blob stands in otherwise.
    /// </summary>
    public class BeastBreath : MonoBehaviour
    {
        public Transform mouth;
        public string startEvent = "Fire", stopEvent = "FireEnd";
        [Tooltip("How far the flames reach (metres, before the creature's scale).")]
        public float reach = 10f;
        [Tooltip("Half-angle of the cone (degrees).")]
        public float spread = 8f;
        public float maxSeconds = 1.6f;
        [Tooltip("Where the flames start, from the mouth socket, in the creature's own axes in the bind pose (metres): "
                 + "down and back between the open jaws.")]
        public Vector3 offset = new Vector3(0f, -0.28f, -0.15f);
        [Tooltip("Aim below the snout's line (degrees), so the stream washes over the ground ahead.")]
        public float aimDown = 12f;
        public Color hot = new Color(1f, 0.85f, 0.45f), mid = new Color(1f, 0.45f, 0.1f), cool = new Color(0.45f, 0.08f, 0.02f);

        ParticleSystem flames, core, smoke;
        Light glow;
        float stopAt = -1f, lightLevel;
        static Texture2D blob;

        public bool Burning => stopAt > 0f;

        void Awake()
        {
            if (mouth == null) mouth = transform;
            var root = new GameObject("Breath").transform;
            root.SetParent(mouth, false);
            root.position = mouth.position + transform.TransformVector(offset);
            root.rotation = Quaternion.AngleAxis(aimDown, transform.right) *
                            Quaternion.LookRotation(transform.forward, transform.up);    // the bind pose looks ahead
            float life = 0.75f;
            flames = Emitter(root, "Flames", Mat("M_FX_FlameBody", true), 8, life, reach / life, 0.5f, 3.2f, 110f,
                             Grad(new[] { hot, mid, cool }, new[] { 0f, 0.35f, 1f }, new[] { 0f, 1f, 0.9f, 0f }, new[] { 0f, 0.08f, 0.6f, 1f }));
            core = Emitter(root, "Core", Mat("M_FX_FlameCore", true), 8, life * 0.55f, reach / life, 0.25f, 1.4f, 70f,
                           Grad(new[] { Color.white, hot, mid }, new[] { 0f, 0.4f, 1f }, new[] { 0f, 1f, 0f }, new[] { 0f, 0.1f, 1f }));
            smoke = Emitter(root, "Smoke", Mat("M_FX_Smoke", false), 4, 1.8f, reach / life * 0.5f, 1.2f, 6f, 18f,
                            Grad(new[] { new Color(0.25f, 0.22f, 0.2f), new Color(0.4f, 0.4f, 0.4f) }, new[] { 0f, 1f },
                                 new[] { 0f, 0.35f, 0f }, new[] { 0f, 0.3f, 1f }));
            var sm = smoke.main;
            sm.gravityModifier = -0.12f;                                                    // smoke rises
            var sh = smoke.shape;
            sh.position = new Vector3(0, 0, reach * 0.35f);
            var light = new GameObject("BreathLight");
            light.transform.SetParent(root, false);
            light.transform.localPosition = new Vector3(0, 0, reach * 0.4f);
            glow = light.AddComponent<Light>();
            glow.type = LightType.Point;
            glow.color = mid;
            glow.range = reach * 1.6f;
            glow.intensity = 0f;
            glow.shadows = LightShadows.None;
            glow.enabled = false;
        }

        public void OnBeastEvent(string name)
        {
            if (name == startEvent) Ignite();
            else if (name == stopEvent || name == "Dead") Douse();
        }

        public void Ignite()
        {
            stopAt = Time.time + maxSeconds;
            foreach (var ps in new[] { flames, core, smoke }) ps.Play(true);
        }

        public void Douse()
        {
            stopAt = -1f;
            foreach (var ps in new[] { flames, core, smoke }) ps.Stop(true, ParticleSystemStopBehavior.StopEmitting);
        }

        void Update()
        {
            if (stopAt > 0f && Time.time > stopAt) Douse();
            float want = Burning ? 1f : 0f;
            lightLevel = Mathf.MoveTowards(lightLevel, want, Time.deltaTime * (Burning ? 6f : 2.5f));
            glow.enabled = lightLevel > 0.01f;
            glow.intensity = lightLevel * (6f + 1.5f * Mathf.PerlinNoise(Time.time * 9f, 0.3f));
        }

        ParticleSystem Emitter(Transform parent, string name, Material mat, int tiles, float life, float speed,
                               float size0, float size1, float rate, Gradient colour)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);
            var ps = go.AddComponent<ParticleSystem>();
            ps.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
            var main = ps.main;
            main.playOnAwake = false;
            main.loop = true;
            main.duration = 1f;
            main.startLifetime = new ParticleSystem.MinMaxCurve(life * 0.8f, life * 1.1f);
            main.startSpeed = new ParticleSystem.MinMaxCurve(speed * 0.85f, speed * 1.1f);
            main.startSize = size0;
            main.startRotation = new ParticleSystem.MinMaxCurve(0f, Mathf.PI * 2f);
            main.simulationSpace = ParticleSystemSimulationSpace.World;
            main.scalingMode = ParticleSystemScalingMode.Hierarchy;
            main.gravityModifier = -0.05f;
            main.maxParticles = 400;
            var em = ps.emission;
            em.rateOverTime = rate;
            var sh = ps.shape;
            sh.shapeType = ParticleSystemShapeType.Cone;                    // a cone emits along its Z: the mouth's ahead
            sh.angle = spread;
            sh.radius = 0.12f;
            var col = ps.colorOverLifetime;
            col.enabled = true;
            col.color = colour;
            var sz = ps.sizeOverLifetime;
            sz.enabled = true;
            sz.size = new ParticleSystem.MinMaxCurve(1f, AnimationCurve.EaseInOut(0f, 1f, 1f, size1 / size0));
            var rot = ps.rotationOverLifetime;
            rot.enabled = true;
            rot.z = new ParticleSystem.MinMaxCurve(-1.5f, 1.5f);
            var lim = ps.limitVelocityOverLifetime;                       // the stream slows and piles up at its end
            lim.enabled = true;
            lim.limit = speed * 0.35f;
            lim.dampen = 0.08f;
            var hit = ps.collision;
            hit.enabled = true;
            hit.type = ParticleSystemCollisionType.World;
            hit.mode = ParticleSystemCollisionMode.Collision3D;
            hit.quality = ParticleSystemCollisionQuality.Medium;
            hit.dampen = 0.5f;
            hit.bounce = 0.05f;
            hit.radiusScale = 0.3f;
            var r = ps.GetComponent<ParticleSystemRenderer>();
            r.sharedMaterial = mat;
            r.renderMode = ParticleSystemRenderMode.Billboard;
            r.shadowCastingMode = ShadowCastingMode.Off;
            r.receiveShadows = false;
            r.sortingFudge = name == "Core" ? -1f : name == "Smoke" ? 1f : 0f;
            if (mat != null && mat.mainTexture != null && mat.mainTexture != blob)
            {
                var ts = ps.textureSheetAnimation;
                ts.enabled = true;
                ts.mode = ParticleSystemAnimationMode.Grid;
                ts.numTilesX = ts.numTilesY = tiles;
                ts.animation = ParticleSystemAnimationType.WholeSheet;
                ts.frameOverTime = name == "Smoke" ? new ParticleSystem.MinMaxCurve(0f)
                                                   : new ParticleSystem.MinMaxCurve(1f, AnimationCurve.Linear(0f, 0f, 1f, 1f));
                ts.startFrame = new ParticleSystem.MinMaxCurve(0f, 1f);
                ts.cycleCount = 1;
            }
            return ps;
        }

        static Gradient Grad(Color[] c, float[] ct, float[] a, float[] at)
        {
            var g = new Gradient();
            var ck = new GradientColorKey[c.Length];
            for (int i = 0; i < c.Length; i++) ck[i] = new GradientColorKey(c[i], ct[i]);
            var ak = new GradientAlphaKey[a.Length];
            for (int i = 0; i < a.Length; i++) ak[i] = new GradientAlphaKey(a[i], at[i]);
            g.SetKeys(ck, ak);
            return g;
        }

        /// <summary>The game's FX material, or URP Particles/Unlit on a soft blob (additive or alpha blended).</summary>
        static Material Mat(string name, bool additive)
        {
            var m = Resources.Load<Material>("FX/" + name);
            if (m != null) return m;
            var sh = Shader.Find("Universal Render Pipeline/Particles/Unlit") ?? Shader.Find("Sprites/Default");
            if (sh == null) return null;
            if (blob == null) blob = Blob(64);
            m = new Material(sh) { name = name + " (stand-in)", mainTexture = blob };
            if (m.HasProperty("_BaseMap")) m.SetTexture("_BaseMap", blob);
            if (m.HasProperty("_Surface"))
            {
                m.SetFloat("_Surface", 1f);
                m.SetFloat("_Blend", additive ? 2f : 0f);
                m.SetFloat("_SrcBlend", (float)BlendMode.SrcAlpha);
                m.SetFloat("_DstBlend", additive ? (float)BlendMode.One : (float)BlendMode.OneMinusSrcAlpha);
                m.SetFloat("_ZWrite", 0f);
                m.SetOverrideTag("RenderType", "Transparent");
                m.EnableKeyword("_SURFACE_TYPE_TRANSPARENT");
                m.renderQueue = (int)RenderQueue.Transparent;
            }
            return m;
        }

        static Texture2D Blob(int n)
        {
            var t = new Texture2D(n, n, TextureFormat.RGBA32, false) { name = "BreathBlob", wrapMode = TextureWrapMode.Clamp };
            var px = new Color[n * n];
            for (int y = 0; y < n; y++)
                for (int x = 0; x < n; x++)
                {
                    float dx = (x + 0.5f) / n * 2f - 1f, dy = (y + 0.5f) / n * 2f - 1f;
                    float a = Mathf.Clamp01(1f - Mathf.Sqrt(dx * dx + dy * dy));
                    px[y * n + x] = new Color(1f, 1f, 1f, a * a);
                }
            t.SetPixels(px);
            t.Apply();
            return t;
        }
    }
}

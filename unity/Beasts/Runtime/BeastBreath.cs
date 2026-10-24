using UnityEngine;
using UnityEngine.Rendering;

namespace Beasts
{
    /// <summary>
    /// A dragon's fire breath: a cone of flame from <see cref="mouth"/> (Socket_Mouth) between the clip's events
    /// (<c>OnBeastEvent</c> "Fire" starts it, "FireEnd" stops it, and it never runs longer than <see cref="maxSeconds"/>,
    /// so a clip cut short by a crossfade can't leave it burning). Built in Awake (or <see cref="Build"/>) the way the
    /// game's campfires are (MedievalSetting's FireFx, 2026-10-24): a body of flame tongues (the 8 x 8 flipbook, alpha
    /// blended, so the flames piled up in the stream never wash out to white, tinted only lightly as they cool and
    /// stirred by turbulence), a smaller additive core, a faint warm glow round the stream's first half, embers stretched
    /// along their flight, dark smoke rising off its end, and a flickering orange light; in world space so the stream
    /// bends as the head sweeps, bouncing off colliders (the ground). The materials are the game's Resources/FX
    /// (M_FX_FlameBody, M_FX_FlameCore, M_FX_Glow, M_FX_Ember, M_FX_Smoke) when the project has them; soft blobs in the
    /// old colours stand in otherwise (the itch package). <see cref="Preview"/> burns it for a few seconds in edit mode
    /// (renders).
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
        [Tooltip("The stand-in blobs' colours (used only without the game's flame materials).")]
        public Color hot = new Color(1f, 0.85f, 0.45f), mid = new Color(1f, 0.45f, 0.1f), cool = new Color(0.45f, 0.08f, 0.02f);

        ParticleSystem flames, core, glowPuffs, embers, smoke;
        Light glow;
        float stopAt = -1f, lightLevel;
        bool built;
        static Texture2D blob;

        public bool Burning => stopAt > 0f;

        void Awake() => Build();

        /// <summary>The emitters and the light under the mouth (once).</summary>
        public void Build()
        {
            if (built) return;
            built = true;
            if (mouth == null) mouth = transform;
            var root = new GameObject("Breath").transform;
            root.SetParent(mouth, false);
            root.position = mouth.position + transform.TransformVector(offset);
            root.rotation = Quaternion.AngleAxis(aimDown, transform.right) *
                            Quaternion.LookRotation(transform.forward, transform.up);    // the bind pose looks ahead
            const float life = 0.75f;
            float speed = reach / life;
            bool real = Load("M_FX_FlameBody") != null;
            // the body: tongues of flame growing as they go, the flipbook played once from a random frame
            flames = Emitter(root, "Flames", Mat("M_FX_FlameBody", false), 8, true, new Vector2(life * 0.8f, life * 1.15f),
                             speed, new Vector2(1.6f, 2.6f), 110f, 220,
                             real ? FlameColours() : Grad(new[] { hot, mid, cool }, new[] { 0f, 0.35f, 1f }, new[] { 0f, 1f, 0.9f, 0f }, new[] { 0f, 0.08f, 0.6f, 1f }),
                             Curve(0f, 0.3f, 0.3f, 0.8f, 1f, 1.15f), -10f);
            Turbulence(flames, 0.7f, 0.6f, 0.7f);
            Upright(flames);
            // the hot heart, shorter and smaller, over the body
            core = Emitter(root, "Core", Mat("M_FX_FlameCore", true), 8, true, new Vector2(life * 0.45f, life * 0.65f),
                           speed, new Vector2(0.9f, 1.5f), 70f, 120,
                           real ? FlameColours() : Grad(new[] { Color.white, hot, mid }, new[] { 0f, 0.4f, 1f }, new[] { 0f, 1f, 0f }, new[] { 0f, 0.1f, 1f }),
                           Curve(0f, 0.35f, 0.4f, 0.9f, 1f, 0.8f), -11f);
            Turbulence(core, 0.4f, 0.6f, 0.7f);
            Upright(core);
            // a faint warm glow round the stream's first half (big additive puffs, no flipbook)
            var glowMat = Mat("M_FX_Glow", true);
            glowPuffs = Emitter(root, "Glow", glowMat, 0, false, new Vector2(life * 0.5f, life * 0.7f), speed * 0.6f,
                                new Vector2(3.5f, 5f), 22f, 30,
                                Grad(new[] { new Color(1f, 0.55f, 0.2f), new Color(1f, 0.55f, 0.2f) }, new[] { 0f, 1f },
                                     new[] { 0f, 0.35f, 0.25f, 0f }, new[] { 0f, 0.25f, 0.7f, 1f }),
                                Curve(0f, 0.6f, 1f, 1.2f), -5f);
            // embers flying out of the stream, yellow fading to red, stretched along their flight (orange from the
            // start: a paler spark comes out lime through the tonemapper)
            embers = Emitter(root, "Embers", Mat("M_FX_Ember", true), 0, false, new Vector2(0.5f, 1.1f), speed * 1.05f,
                             new Vector2(0.06f, 0.12f), 45f, 120,
                             Grad(new[] { new Color(1f, 0.72f, 0.3f), new Color(1f, 0.42f, 0.1f), new Color(0.75f, 0.12f, 0.02f) },
                                  new[] { 0f, 0.35f, 1f }, new[] { 1f, 1f, 0f }, new[] { 0f, 0.6f, 1f }),
                             Curve(0f, 1f, 1f, 0.4f), -12f);
            var esh = embers.shape;
            esh.angle = spread * 1.8f;
            esh.randomDirectionAmount = 0.2f;
            var emain = embers.main;
            emain.gravityModifier = 0.25f;                                  // they arc down out of the stream
            Turbulence(embers, 1.2f, 0.7f, 0.8f);
            var er = embers.GetComponent<ParticleSystemRenderer>();
            er.renderMode = ParticleSystemRenderMode.Stretch;
            er.velocityScale = 0.03f; er.lengthScale = 1.5f; er.cameraVelocityScale = 0f;
            // dark smoke rising off the stream's far end, paling as it spreads
            smoke = Emitter(root, "Smoke", Mat("M_FX_Smoke", false), 4, false, new Vector2(1.4f, 2.2f), speed * 0.35f,
                            new Vector2(1.6f, 2.8f), 20f, 80,
                            Grad(new[] { new Color(0.36f, 0.26f, 0.19f), new Color(0.2f, 0.19f, 0.18f), new Color(0.6f, 0.59f, 0.58f) },
                                 new[] { 0f, 0.25f, 1f }, new[] { 0f, 0.5f, 0.45f, 0f }, new[] { 0f, 0.15f, 0.55f, 1f }),
                            Curve(0f, 0.6f, 1f, 1.8f), 10f);
            var sm = smoke.main;
            sm.gravityModifier = -0.15f;                                    // smoke rises
            var ssh = smoke.shape;
            ssh.position = new Vector3(0, 0, reach * 0.45f);
            ssh.angle = spread * 2.5f;
            Turbulence(smoke, 0.4f, 0.25f, 0.2f);
            var rot = smoke.rotationOverLifetime;
            rot.enabled = true; rot.z = new ParticleSystem.MinMaxCurve(-0.3f, 0.3f);
            smoke.GetComponent<ParticleSystemRenderer>().sortMode = ParticleSystemSortMode.Distance;
            var light = new GameObject("BreathLight");
            light.transform.SetParent(root, false);
            light.transform.localPosition = new Vector3(0, 0, reach * 0.4f);
            glow = light.AddComponent<Light>();
            glow.type = LightType.Point;
            glow.color = new Color(1f, 0.55f, 0.22f);                      // the game's firelight
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
            Build();
            stopAt = Time.time + maxSeconds;
            foreach (var ps in Systems()) ps.Play(true);
        }

        public void Douse()
        {
            stopAt = -1f;
            foreach (var ps in Systems()) ps.Stop(true, ParticleSystemStopBehavior.StopEmitting);
        }

        /// <summary>Edit mode: the breath as it looks after burning for <paramref name="seconds"/>, the light lit (a render
        /// then shows it; nothing is saved). Pose the creature first (sample its Fire clip).</summary>
        public void Preview(float seconds)
        {
            Build();
            foreach (var ps in Systems()) ps.Simulate(seconds, true, true, true);
            glow.enabled = true;
            glow.intensity = 6.5f;
        }

        ParticleSystem[] Systems() => new[] { flames, core, glowPuffs, embers, smoke };

        void Update()
        {
            if (stopAt > 0f && Time.time > stopAt) Douse();
            float want = Burning ? 1f : 0f;
            lightLevel = Mathf.MoveTowards(lightLevel, want, Time.deltaTime * (Burning ? 6f : 2.5f));
            glow.enabled = lightLevel > 0.01f;
            glow.intensity = lightLevel * (6f + 1.5f * Mathf.PerlinNoise(Time.time * 9f, 0.3f));
        }

        /// <summary>FireFx's flame tint: the flipbook's own colour, dimming and reddening as it cools</summary>
        static Gradient FlameColours() =>
            Grad(new[] { Color.white, new Color(1f, 0.92f, 0.85f), new Color(0.8f, 0.45f, 0.35f) }, new[] { 0f, 0.45f, 1f },
                 new[] { 0f, 1f, 0.95f, 0f }, new[] { 0f, 0.1f, 0.6f, 1f });

        /// <summary>flame tongues stand up as FireFx's do (their tips up the screen, a little tilt, no spin); glow and
        /// smoke keep their random turn</summary>
        static void Upright(ParticleSystem ps)
        {
            var main = ps.main;
            main.startRotation = new ParticleSystem.MinMaxCurve(-0.12f, 0.12f);
            var rot = ps.rotationOverLifetime;
            rot.enabled = false;
        }

        static void Turbulence(ParticleSystem ps, float strength, float frequency, float scroll)
        {
            var noise = ps.noise;
            noise.enabled = true;
            noise.strength = strength;
            noise.frequency = frequency;
            noise.scrollSpeed = scroll;
            noise.damping = true;
        }

        ParticleSystem Emitter(Transform parent, string name, Material mat, int tiles, bool playSheet, Vector2 life, float speed,
                               Vector2 size, float rate, int max, Gradient colour, AnimationCurve grow, float fudge)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);
            var ps = go.AddComponent<ParticleSystem>();
            ps.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
            var main = ps.main;
            main.playOnAwake = false;
            main.loop = true;
            main.duration = 1f;
            main.startLifetime = new ParticleSystem.MinMaxCurve(life.x, life.y);
            main.startSpeed = new ParticleSystem.MinMaxCurve(speed * 0.85f, speed * 1.1f);
            main.startSize = new ParticleSystem.MinMaxCurve(size.x, size.y);
            main.startRotation = new ParticleSystem.MinMaxCurve(0f, Mathf.PI * 2f);
            main.startColor = Color.white;
            main.simulationSpace = ParticleSystemSimulationSpace.World;
            main.scalingMode = ParticleSystemScalingMode.Hierarchy;
            main.gravityModifier = -0.05f;
            main.maxParticles = max;
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
            sz.size = new ParticleSystem.MinMaxCurve(1f, grow);
            var rot = ps.rotationOverLifetime;
            rot.enabled = true;
            rot.z = new ParticleSystem.MinMaxCurve(-1.2f, 1.2f);
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
            r.maxParticleSize = 2f;                                         // big flames up close are not clipped
            r.sortMode = ParticleSystemSortMode.YoungestInFront;
            r.sortingFudge = fudge;
            if (tiles > 0 && mat != null && mat.mainTexture != null && mat.mainTexture != blob)
            {
                var ts = ps.textureSheetAnimation;
                ts.enabled = true;
                ts.mode = ParticleSystemAnimationMode.Grid;
                ts.numTilesX = ts.numTilesY = tiles;
                ts.animation = ParticleSystemAnimationType.WholeSheet;
                ts.frameOverTime = playSheet ? new ParticleSystem.MinMaxCurve(1f, AnimationCurve.Linear(0f, 0f, 1f, 1f))
                                             : new ParticleSystem.MinMaxCurve(0f);
                ts.startFrame = new ParticleSystem.MinMaxCurve(0f, 1f);    // a random frame (0..1 of the sheet in code)
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

        static AnimationCurve Curve(params float[] tv)
        {
            var k = new Keyframe[tv.Length / 2];
            for (int i = 0; i < k.Length; i++) k[i] = new Keyframe(tv[i * 2], tv[i * 2 + 1]);
            var c = new AnimationCurve(k);
            for (int i = 0; i < k.Length; i++) c.SmoothTangents(i, 0f);
            return c;
        }

        static Material Load(string name) => Resources.Load<Material>("FX/" + name);

        /// <summary>The game's FX material, or URP Particles/Unlit on a soft blob (additive or alpha blended).</summary>
        static Material Mat(string name, bool additive)
        {
            var m = Load(name);
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

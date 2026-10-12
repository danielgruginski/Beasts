using System.Collections.Generic;
using UnityEngine;

namespace Beasts
{
    /// <summary>
    /// The ooze's effects, built in code (no particle prefabs to keep in sync), coloured by its <see cref="OozeLook"/>:
    ///   a wet slime trail on the floor while it moves (an <see cref="OozeTrail"/>: splats merged in a wetness field);
    ///   drips falling from the raised pods' tips (Reach, Side, Probe);
    ///   splashes on the clips' events: Hit (Lash's slam, Grab's catch: at the pod's tip), Hurt, Grab, Engulf, Dead,
    ///   Split, Risen, and a spray at the mouth on Spit;
    ///   the acid glob on Spit: an <see cref="OozeGlob"/> from Socket_Spit to <see cref="spitTarget"/> (or 5 m ahead),
    ///   which leaves a sizzling puddle where it lands.
    /// The trail and the splashes live on an object of their own beside the ooze, so they outlast it (a split hides
    /// the big one at the moment it splashes). Listens to <see cref="BeastEvents"/>; <see cref="Splash"/> and
    /// <see cref="Spit"/> can be called by the game too.
    /// </summary>
    [RequireComponent(typeof(BeastEvents))]
    public class OozeFx : MonoBehaviour
    {
        public Material trailMaterial, dropMaterial, puddleMaterial, globMaterial;
        public Mesh globMesh;
        [Tooltip("Where Spit aims; null = 5 m ahead (times the ooze's size).")]
        public Transform spitTarget;
        public bool trail = true, drips = true;
        public float dripRate = 1.2f;

        BeastEvents events;
        OozeLook look;
        Transform fxRoot, mouth;
        OozeTrail trailR;
        ParticleSystem splash;
        readonly List<(ParticleSystem ps, Transform tip)> drippers = new List<(ParticleSystem, Transform)>();
        readonly Dictionary<string, Transform> bones = new Dictionary<string, Transform>();
        Vector3 lastPos;

        float Size => transform.lossyScale.x;

        void Awake()
        {
            events = GetComponent<BeastEvents>();
            look = GetComponent<OozeLook>();
            foreach (var t in GetComponentsInChildren<Transform>(true)) bones[t.name] = t;
            bones.TryGetValue("Socket_Spit", out mouth);
        }

        void Start()
        {
            fxRoot = new GameObject(name + "_Fx").transform;
            fxRoot.SetParent(transform.parent, false);
            var c = Colour(0.8f);
            if (trail && trailMaterial != null) BuildTrail(c);
            splash = BuildSplash(c);
            if (drips && dropMaterial != null)
                foreach (var tip in new[] { "Reach3", "Side3", "Probe3" })
                    if (bones.TryGetValue(tip, out var t)) drippers.Add((BuildDripper(t, c), t));
            lastPos = transform.position;
        }

        void OnEnable()
        {
            if (events == null) events = GetComponent<BeastEvents>();
            events.EventFired += OnEvent;
            if (trailR != null) trailR.Clear();
            lastPos = transform.position;
        }

        void OnDisable()
        {
            if (events != null) events.EventFired -= OnEvent;
            if (trailR != null) trailR.emitting = false;
            foreach (var (ps, _) in drippers)                          // they live beside it: stop them with it
            {
                var em = ps.emission;
                em.enabled = false;
            }
        }

        void OnDestroy()
        {
            if (fxRoot != null) Destroy(fxRoot.gameObject, 12f);        // let the trail and the last splash fade
        }

        Color Colour(float a)
        {
            var m = look != null ? look.Current.mid : new Color(0.31f, 0.55f, 0.11f);
            var t = look != null ? look.Current.thin : new Color(0.65f, 0.83f, 0.33f);
            var c = Color.Lerp(m, t, 0.35f);
            c.a = a;
            return c;
        }

        void LateUpdate()
        {
            if (trailR != null)
            {
                var p = transform.position;
                float v = (p - lastPos).magnitude / Mathf.Max(Time.deltaTime, 1e-4f);
                trailR.target = transform;
                trailR.emitting = v > 0.08f * Size;
                trailR.step = 0.15f * Size;
                trailR.radius = 0.8f * Size;
                trailR.behind = 1.0f * Size;
                lastPos = p;
            }
            float floor = transform.position.y;
            foreach (var (ps, tip) in drippers)                         // from under a raised tip only
            {
                var at = tip.position + Vector3.down * 0.17f * Size;
                ps.transform.position = at;
                var em = ps.emission;
                em.enabled = at.y - floor > 0.22f * Size;
            }
        }

        // ------------------------------------------------------------------------------------------- events
        void OnEvent(BeastEvents e, string ev)
        {
            switch (ev)
            {
                case "Hit":
                    Splash(TipOf("Probe3", "Reach3"), 16, 1f);
                    break;
                case "Hurt":
                    Splash(transform.position + Vector3.up * 0.6f * Size, 14, 0.9f);
                    break;
                case "Grab":
                    Splash(bones.TryGetValue("Socket_Mouth", out var m) ? m.position : transform.position, 10, 0.7f);
                    break;
                case "Engulf":
                    Splash(transform.position + Vector3.up * 0.9f * Size, 14, 0.6f);
                    break;
                case "Dead":
                    Splash(transform.position + Vector3.up * 0.25f * Size, 40, 1.2f);
                    break;
                case "Split":
                    Splash(transform.position + Vector3.up * 0.4f * Size, 70, 1.5f);
                    break;
                case "Risen":
                    Splash(transform.position + Vector3.up * 0.3f * Size, 20, 0.8f);
                    break;
                case "Spit":
                    Spit();
                    break;
            }
        }

        /// <summary>Whichever of the tips is lowest (Lash slams the Probe down, Grab swells Reach round its catch).</summary>
        Vector3 TipOf(params string[] tips)
        {
            Transform best = null;
            foreach (var n in tips)
                if (bones.TryGetValue(n, out var t) && (best == null || t.position.y < best.position.y)) best = t;
            return best != null ? best.position : transform.position;
        }

        /// <summary>A burst of droplets at a world point (size 1 = a normal ooze's).</summary>
        public void Splash(Vector3 at, int count, float strength)
        {
            if (splash == null) return;
            var ep = new ParticleSystem.EmitParams { applyShapeToPosition = true };
            for (int i = 0; i < count; i++)
            {
                var d = Random.onUnitSphere;
                d.y = Mathf.Abs(d.y) * 0.8f + 0.3f;
                ep.position = at + d * 0.12f * Size;
                ep.velocity = d.normalized * Random.Range(1.4f, 3.4f) * strength * Mathf.Sqrt(Size);
                ep.startSize = Random.Range(0.04f, 0.13f) * Size;
                ep.startLifetime = Random.Range(0.7f, 1.3f);
                ep.startColor = Colour(Random.Range(0.6f, 0.9f));
                splash.Emit(ep, 1);
            }
        }

        /// <summary>The acid glob, from the Probe's tip to the target.</summary>
        public void Spit()
        {
            var from = mouth != null ? mouth.position : transform.position + Vector3.up * 1.4f * Size;
            var to = spitTarget != null ? spitTarget.position : transform.position + transform.forward * 5f * Size;
            Splash(from, 8, 0.6f);
            if (globMaterial == null || globMesh == null) return;
            var g = new GameObject(name + "_Glob");
            g.AddComponent<MeshFilter>().sharedMesh = globMesh;
            var mr = g.AddComponent<MeshRenderer>();
            mr.sharedMaterial = globMaterial;
            mr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            var glob = g.AddComponent<OozeGlob>();
            glob.Launch(this, from, to, 0.16f * Size, look != null ? look.Current : OozeLook.Presets[0], puddleMaterial);
        }

        // ------------------------------------------------------------------------------------------- building
        void BuildTrail(Color c)
        {
            var go = new GameObject("Trail");
            go.transform.SetParent(fxRoot, false);
            trailR = go.AddComponent<OozeTrail>();
            trailR.cell = 0.1f * Size;                                  // fixed from here: the field is laid out in it
            trailR.life = 9f;
            trailR.step = 0.15f * Size;
            trailR.radius = 0.8f * Size;
            trailR.behind = 1.0f * Size;
            var slime = Color.Lerp(c, Color.black, 0.25f);
            slime.a = 1f;
            trailR.Init(trailMaterial, slime);
            trailR.target = transform;
            trailR.emitting = false;
        }

        ParticleSystem BuildSplash(Color c)
        {
            var go = new GameObject("Splash");
            go.transform.SetParent(fxRoot, false);
            var ps = go.AddComponent<ParticleSystem>();
            ps.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
            var main = ps.main;
            main.loop = false;
            main.playOnAwake = false;
            main.simulationSpace = ParticleSystemSimulationSpace.World;
            main.gravityModifier = 1.6f;
            main.maxParticles = 600;
            main.startColor = c;
            var em = ps.emission;
            em.enabled = false;
            var shape = ps.shape;
            shape.enabled = false;
            var col = ps.collision;
            col.enabled = true;
            col.type = ParticleSystemCollisionType.World;
            col.mode = ParticleSystemCollisionMode.Collision3D;
            col.quality = ParticleSystemCollisionQuality.Low;
            col.bounce = 0.15f;
            col.dampen = 0.6f;
            col.lifetimeLoss = 0.5f;
            var sz = ps.sizeOverLifetime;
            sz.enabled = true;
            sz.size = new ParticleSystem.MinMaxCurve(1f, new AnimationCurve(new Keyframe(0, 1), new Keyframe(0.8f, 0.9f), new Keyframe(1, 0)));
            var r = go.GetComponent<ParticleSystemRenderer>();
            r.sharedMaterial = dropMaterial;
            r.renderMode = ParticleSystemRenderMode.Billboard;
            r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            ps.Play();
            return ps;
        }

        ParticleSystem BuildDripper(Transform tip, Color c)
        {
            var go = new GameObject("Drips_" + tip.name);
            go.transform.SetParent(fxRoot, false);
            var ps = go.AddComponent<ParticleSystem>();
            ps.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
            var main = ps.main;
            main.loop = true;
            main.simulationSpace = ParticleSystemSimulationSpace.World;
            main.startSpeed = 0f;
            main.startLifetime = 1.6f;
            main.startSize = new ParticleSystem.MinMaxCurve(0.03f * Size, 0.065f * Size);
            main.gravityModifier = 1.1f;
            main.startColor = c;
            main.maxParticles = 40;
            var em = ps.emission;
            em.rateOverTime = dripRate;
            var shape = ps.shape;
            shape.shapeType = ParticleSystemShapeType.Sphere;
            shape.radius = 0.07f * Size;
            var col = ps.collision;
            col.enabled = true;
            col.type = ParticleSystemCollisionType.World;
            col.mode = ParticleSystemCollisionMode.Collision3D;
            col.quality = ParticleSystemCollisionQuality.Low;
            col.bounce = 0f;
            col.lifetimeLoss = 1f;                                      // a drip ends on the floor
            var sz = ps.sizeOverLifetime;                               // drawn out as it falls
            sz.enabled = true;
            sz.separateAxes = true;
            sz.x = new ParticleSystem.MinMaxCurve(1f, new AnimationCurve(new Keyframe(0, 1.2f), new Keyframe(1, 0.8f)));
            sz.y = new ParticleSystem.MinMaxCurve(1f, new AnimationCurve(new Keyframe(0, 0.9f), new Keyframe(1, 1.6f)));
            sz.z = new ParticleSystem.MinMaxCurve(1f, AnimationCurve.Constant(0, 1, 1));    // all three in one mode
            var r = go.GetComponent<ParticleSystemRenderer>();
            r.sharedMaterial = dropMaterial;
            r.renderMode = ParticleSystemRenderMode.Billboard;
            r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            ps.Play();
            return ps;
        }
    }
}

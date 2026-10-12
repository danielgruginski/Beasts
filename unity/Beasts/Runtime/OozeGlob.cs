using UnityEngine;

namespace Beasts
{
    /// <summary>
    /// The ooze's acid glob (OozeFx.Spit): a blob of the jelly on a ballistic arc, stretched along its flight and
    /// wobbling; where it lands it splashes and becomes a puddle that fizzes (small rising bubbles) and fades. The game
    /// can read <see cref="Landed"/> / <see cref="Position"/> for the damage.
    /// </summary>
    public class OozeGlob : MonoBehaviour
    {
        public float flightTime = 0.7f, puddleTime = 7f;
        public System.Action<OozeGlob> Landed;
        public Vector3 Position => transform.position;

        OozeFx owner;
        Vector3 velocity, target;
        float radius, t;
        bool landed;
        OozeLook.Preset look;
        Material puddleMaterial;
        MaterialPropertyBlock mpb;
        Transform puddle;
        ParticleSystem fizz;

        static readonly int ThinId = Shader.PropertyToID("_ThinColor"), MidId = Shader.PropertyToID("_MidColor"),
            CoreId = Shader.PropertyToID("_CoreColor"), CreviceId = Shader.PropertyToID("_CreviceColor"),
            BaseColorId = Shader.PropertyToID("_BaseColor");

        public void Launch(OozeFx from, Vector3 start, Vector3 to, float r, OozeLook.Preset colours, Material puddleMat)
        {
            owner = from;
            target = to;
            radius = r;
            look = colours;
            puddleMaterial = puddleMat;
            transform.position = start;
            float T = Mathf.Max(flightTime, 0.2f);
            var g = Physics.gravity;
            velocity = (to - start) / T - 0.5f * g * T;
            mpb = new MaterialPropertyBlock();
            var mr = GetComponent<MeshRenderer>();
            mr.GetPropertyBlock(mpb);
            mpb.SetColor(ThinId, look.thin);
            mpb.SetColor(MidId, look.mid);
            mpb.SetColor(CoreId, look.core);
            mpb.SetColor(CreviceId, look.crevice);
            mr.SetPropertyBlock(mpb);
        }

        void Update()
        {
            t += Time.deltaTime;
            if (!landed)
            {
                velocity += Physics.gravity * Time.deltaTime;
                var next = transform.position + velocity * Time.deltaTime;
                float floor = target.y;
                if (next.y <= floor + radius * 0.4f && velocity.y < 0)
                {
                    Land(new Vector3(next.x, floor, next.z));
                    return;
                }
                transform.position = next;
                var dir = velocity.normalized;                          // stretched along its flight, wobbling
                float w = 1f + 0.12f * Mathf.Sin(t * 31f);
                transform.rotation = Quaternion.LookRotation(dir);
                transform.localScale = new Vector3(radius * 2f / w, radius * 2f / w, radius * 2.6f * w);
                if (t > 4f) Destroy(gameObject);
                return;
            }
            float fade = Mathf.Clamp01((t - puddleTime * 0.55f) / (puddleTime * 0.45f));
            if (puddle != null)
            {
                var c = Color.Lerp(look.mid, look.thin, 0.3f);
                c.a = 0.75f * (1 - fade);
                var r = puddle.GetComponent<MeshRenderer>();
                r.GetPropertyBlock(mpb);
                mpb.SetColor(BaseColorId, c);
                r.SetPropertyBlock(mpb);
                float grow = Mathf.SmoothStep(0, 1, Mathf.Clamp01(t / 0.25f));
                puddle.localScale = Vector3.one * radius * 9f * (0.5f + 0.5f * grow);
            }
            if (fizz != null)
            {
                var em = fizz.emission;
                em.rateOverTime = 14f * (1 - fade);
            }
            if (t > puddleTime) Destroy(gameObject);
        }

        void Land(Vector3 at)
        {
            landed = true;
            t = 0;
            transform.position = at;
            transform.rotation = Quaternion.identity;
            transform.localScale = Vector3.one;
            GetComponent<MeshRenderer>().enabled = false;
            if (owner != null) owner.Splash(at + Vector3.up * radius, 18, 0.7f);
            if (puddleMaterial != null)
            {
                var q = GameObject.CreatePrimitive(PrimitiveType.Quad);
                Destroy(q.GetComponent<Collider>());
                q.name = "AcidPuddle";
                puddle = q.transform;
                puddle.SetParent(transform, false);
                puddle.localPosition = Vector3.up * 0.01f;
                puddle.localRotation = Quaternion.Euler(90, Random.Range(0f, 360f), 0);
                var r = q.GetComponent<MeshRenderer>();
                r.sharedMaterial = puddleMaterial;
                r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                fizz = BuildFizz();
            }
            Landed?.Invoke(this);
        }

        ParticleSystem BuildFizz()
        {
            var go = new GameObject("Fizz");
            go.transform.SetParent(transform, false);
            go.transform.localRotation = Quaternion.Euler(-90, 0, 0);
            var ps = go.AddComponent<ParticleSystem>();
            ps.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
            var main = ps.main;
            main.startSpeed = 0f;
            main.startLifetime = new ParticleSystem.MinMaxCurve(0.4f, 0.9f);
            main.startSize = new ParticleSystem.MinMaxCurve(radius * 0.15f, radius * 0.35f);
            var c = Color.Lerp(look.thin, Color.white, 0.4f);
            c.a = 0.7f;
            main.startColor = c;
            main.gravityModifier = -0.05f;
            var shape = ps.shape;
            shape.shapeType = ParticleSystemShapeType.Circle;
            shape.radius = radius * 3.2f;
            var em = ps.emission;
            em.rateOverTime = 14f;
            var vel = ps.velocityOverLifetime;                          // bubbles rising off the acid
            vel.enabled = true;
            vel.space = ParticleSystemSimulationSpace.World;
            vel.x = new ParticleSystem.MinMaxCurve(0f, 0f);                // (all three in the same mode)
            vel.y = new ParticleSystem.MinMaxCurve(0.15f, 0.4f);
            vel.z = new ParticleSystem.MinMaxCurve(0f, 0f);
            var sz = ps.sizeOverLifetime;
            sz.enabled = true;
            sz.size = new ParticleSystem.MinMaxCurve(1f, new AnimationCurve(new Keyframe(0, 0.4f), new Keyframe(0.7f, 1f), new Keyframe(1, 0)));
            var pr = go.GetComponent<ParticleSystemRenderer>();
            pr.sharedMaterial = owner != null ? owner.dropMaterial : null;
            pr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            ps.Play();
            return ps;
        }
    }
}

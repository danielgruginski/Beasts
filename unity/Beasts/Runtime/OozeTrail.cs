using UnityEngine;

namespace Beasts
{
    /// <summary>
    /// The ooze's slime trail, as splats that know about each other: the ooze paints them into a wetness field (a small
    /// R8 texture tied to the world, wrapping round, <see cref="cell"/> metres a texel) as it goes, and one flat sheet
    /// round it (Beasts/OozeSlick) shows slime wherever the field passes an edge threshold. So splats close together
    /// merge into one wet patch with smooth necks (no alpha piling up where they overlap); as the field dries the edges
    /// creep in and the patch breaks into puddles before it goes (<see cref="life"/>). The splats land at the ooze's rear
    /// edge (<see cref="behind"/>), so none appear under its see-through body. It lives beside the ooze (on its effects
    /// root), so it dries out after the ooze is gone. <see cref="OozeFx"/> drives it (target, emitting, sizes).
    /// (Replaced a ribbon, 2026-10-12: at 1.5 m wide it folded on turns, and its fresh end showed through the jelly.)
    /// </summary>
    public class OozeTrail : MonoBehaviour
    {
        public Transform target;
        public bool emitting;
        [Tooltip("Metres between splats.")]
        public float step = 0.15f;
        [Tooltip("A splat's radius (m).")]
        public float radius = 0.8f;
        [Tooltip("How far behind the ooze's centre the splats land (m): its rear edge.")]
        public float behind = 1.0f;
        [Tooltip("Seconds until fresh slime has dried away.")]
        public float life = 9f;
        [Tooltip("Metres per field texel; the field covers resolution x cell metres round the ooze.")]
        public float cell = 0.1f;
        public int resolution = 128;
        public float lift = 0.012f;

        const float Max = 1.3f;                 // the field's value at texture 1
        const float Fresh = 1.15f;              // a splat's centre
        const float Edge = 0.30f;               // the slime's edge (OozeSlick _Edge.x)

        float[] field;
        byte[] bytes;
        Texture2D tex;
        Material mat;
        MeshRenderer mr;
        Vector3 lastSplat;
        bool hasLast, wet;
        float lastTime = -1f;
        System.Random rng;

        public Material Material => mat;

        public void Init(Material slick, Color colour)
        {
            rng = new System.Random(GetInstanceID());
            field = new float[resolution * resolution];
            bytes = new byte[resolution * resolution];
            tex = new Texture2D(resolution, resolution, TextureFormat.R8, false, true)
            {
                name = "OozeTrailField", wrapMode = TextureWrapMode.Repeat, filterMode = FilterMode.Bilinear,
            };
            tex.SetPixelData(bytes, 0);
            tex.Apply(false);
            mat = new Material(slick) { name = slick.name + " (trail)" };
            mat.SetTexture("_Field", tex);
            mat.SetColor("_Color", colour);
            var mesh = new Mesh { name = "OozeTrailSheet" };
            mesh.vertices = new[] { new Vector3(-0.5f, 0, -0.5f), new Vector3(0.5f, 0, -0.5f), new Vector3(-0.5f, 0, 0.5f), new Vector3(0.5f, 0, 0.5f) };
            mesh.uv = new[] { new Vector2(0, 0), new Vector2(1, 0), new Vector2(0, 1), new Vector2(1, 1) };
            mesh.normals = new[] { Vector3.up, Vector3.up, Vector3.up, Vector3.up };
            mesh.triangles = new[] { 0, 2, 1, 1, 2, 3 };
            gameObject.AddComponent<MeshFilter>().sharedMesh = mesh;
            mr = gameObject.AddComponent<MeshRenderer>();
            mr.sharedMaterial = mat;
            mr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            mr.receiveShadows = true;
            mr.enabled = false;
        }

        public void Clear()
        {
            if (field != null) System.Array.Clear(field, 0, field.Length);
            hasLast = false;
            wet = false;
            if (mr != null) mr.enabled = false;
        }

        void LateUpdate() => Step(Time.time);

        void OnDestroy()
        {
            if (tex != null) Destroy(tex);
            if (mat != null) Destroy(mat);
            var mf = GetComponent<MeshFilter>();
            if (mf != null && mf.sharedMesh != null) Destroy(mf.sharedMesh);
        }

        /// <summary>One update at time <paramref name="now"/> (seconds): dry the field, lay splats behind the target,
        /// move the sheet with it, upload. LateUpdate calls it with Time.time; a test can drive it with its own clock.</summary>
        public void Step(float now)
        {
            if (field == null) return;
            float dt = lastTime < 0f ? 0f : Mathf.Clamp(now - lastTime, 0f, 0.25f);
            lastTime = now;
            float tau = life / Mathf.Log(Fresh / Edge);           // fresh slime reaches the edge value after `life`
            float keep = Mathf.Exp(-dt / tau), most = 0f;
            if (wet && dt > 0f)
                for (int i = 0; i < field.Length; i++)
                {
                    float v = field[i] * keep;
                    field[i] = v < 0.02f ? 0f : v;
                    if (v > most) most = v;
                }
            else if (wet) most = Fresh;
            if (target != null)
            {
                var fwd = target.forward;
                fwd.y = 0f;
                fwd = fwd.sqrMagnitude > 1e-6f ? fwd.normalized : Vector3.forward;
                var rear = target.position - fwd * behind;
                if (emitting)
                {
                    float d = hasLast ? (rear - lastSplat).magnitude : 0f;
                    if (!hasLast || d > 8f * step)                     // the first, or after a teleport
                    {
                        Splat(rear);
                        lastSplat = rear;
                    }
                    else if (d >= step)
                    {
                        int n = Mathf.FloorToInt(d / step);
                        for (int k = 1; k <= n; k++) Splat(Vector3.Lerp(lastSplat, rear, k * step / d));
                        lastSplat = Vector3.Lerp(lastSplat, rear, n * step / d);
                    }
                    hasLast = true;
                    most = Fresh;
                }
                else
                {
                    lastSplat = rear;                                   // resume from where it is, not with a line
                    hasLast = true;
                }
                float size = resolution * cell;                         // the sheet: round the ooze, on texel steps
                var c = target.position;
                transform.position = new Vector3(Mathf.Round(c.x / cell) * cell, c.y + lift, Mathf.Round(c.z / cell) * cell);
                transform.rotation = Quaternion.identity;
                var ps = transform.parent != null ? transform.parent.lossyScale : Vector3.one;
                transform.localScale = new Vector3(size * 0.96f / ps.x, 1f / ps.y, size * 0.96f / ps.z);
                mat.SetFloat("_FieldScale", 1f / size);
                mat.SetFloat("_FieldTexel", 1f / resolution);
            }
            wet = most > 0f;
            mr.enabled = wet;
            if (!wet) return;
            for (int i = 0; i < field.Length; i++) bytes[i] = (byte)(Mathf.Clamp01(field[i] / Max) * 255f + 0.5f);
            tex.SetPixelData(bytes, 0);
            tex.Apply(false);
        }

        /// <summary>One splat at a world point: a soft round blob with a ragged outline, a little off the path, the
        /// field keeping the wetter of what was there and the splat.</summary>
        void Splat(Vector3 at)
        {
            float R(double lo, double hi) => (float)(lo + (hi - lo) * rng.NextDouble());
            at += new Vector3(R(-1, 1), 0, R(-1, 1)) * 0.12f * radius;
            float r = radius * R(0.8, 1.15) / cell;                    // in texels
            float p1 = R(0, 6.28), p2 = R(0, 6.28), a1 = R(0.06, 0.14), a2 = R(0.04, 0.09);
            float amp = Fresh * R(0.82, 1.1);                          // wetter here and there: it dries into puddles
            float cx = at.x / cell - 0.5f, cz = at.z / cell - 0.5f;     // texel centres sit at +0.5
            int x0 = Mathf.FloorToInt(cx - r * 1.25f), x1 = Mathf.CeilToInt(cx + r * 1.25f);
            int z0 = Mathf.FloorToInt(cz - r * 1.25f), z1 = Mathf.CeilToInt(cz + r * 1.25f);
            int N = resolution;
            for (int z = z0; z <= z1; z++)
                for (int x = x0; x <= x1; x++)
                {
                    float dx = x - cx, dz = z - cz;
                    float dd = Mathf.Sqrt(dx * dx + dz * dz);
                    float th = Mathf.Atan2(dz, dx);
                    float rr = r * (1f + a1 * Mathf.Sin(3f * th + p1) + a2 * Mathf.Sin(5f * th + p2));
                    if (dd >= rr) continue;
                    float q = 1f - (dd / rr) * (dd / rr);
                    float v = amp * q * q;
                    int i = ((z % N + N) % N) * N + ((x % N + N) % N);
                    if (v > field[i]) field[i] = v;
                }
            wet = true;
        }
    }
}

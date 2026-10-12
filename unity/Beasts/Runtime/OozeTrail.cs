using System.Collections.Generic;
using UnityEngine;

namespace Beasts
{
    /// <summary>
    /// The ooze's slime trail: a wet ribbon lying on the floor behind it, as the TrailRenderer drew it (same width,
    /// taper, colour, texture), but built as a mesh of its own so it can't fold over itself on a turn: on the inside
    /// of a bend the ribbon's half is never wider than the bend's radius (the inner edge runs as a smaller curve),
    /// neither edge ever runs backward along the trail, and past a sharp corner (<see cref="corner"/>) a new strip
    /// starts. It lives beside the ooze (on its effects
    /// root), so it fades out after the ooze is gone. <see cref="OozeFx"/> drives it (target, emitting, width).
    /// </summary>
    public class OozeTrail : MonoBehaviour
    {
        public Transform target;
        public bool emitting;
        public float width = 1.5f, life = 9f, step = 0.25f, lift = 0.012f;
        [Tooltip("A turn sharper than this (degrees) between two steps starts a new strip.")]
        public float corner = 110f;
        [Tooltip("0 = the newest end, under the ooze; 1 = the oldest.")]
        public AnimationCurve widthCurve = new AnimationCurve(new Keyframe(0, 0.9f), new Keyframe(0.15f, 1f), new Keyframe(1, 0.35f));
        public Gradient colour;

        struct Point { public Vector3 p; public float born; public bool start; }

        readonly List<Point> points = new List<Point>();
        readonly List<(Vector3 p, float f)> strip = new List<(Vector3, float)>();
        readonly List<float> halfL = new List<float>(), halfR = new List<float>();
        readonly List<Vector3> verts = new List<Vector3>(), norms = new List<Vector3>();
        readonly List<Vector2> uvs = new List<Vector2>();
        readonly List<Color> cols = new List<Color>();
        readonly List<int> tris = new List<int>();
        Mesh mesh;
        Vector3 lastHead;
        bool hasLast;

        public int PointCount => points.Count;

        public void Init(Material mat)
        {
            mesh = new Mesh { name = "OozeTrail" };
            mesh.MarkDynamic();
            gameObject.AddComponent<MeshFilter>().sharedMesh = mesh;
            var mr = gameObject.AddComponent<MeshRenderer>();
            mr.sharedMaterial = mat;
            mr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            mr.receiveShadows = true;
        }

        public void Clear()
        {
            points.Clear();
            hasLast = false;
            if (mesh != null) mesh.Clear();
        }

        void LateUpdate() => Step(Time.time);

        void OnDestroy()
        {
            if (mesh != null) Destroy(mesh);
        }

        static Vector3 Flat(Vector3 v)
        {
            v.y = 0f;
            return v.sqrMagnitude > 1e-10f ? v.normalized : Vector3.forward;
        }

        void Add(Vector3 p, float now, bool start) => points.Add(new Point { p = p, born = now, start = start });

        /// <summary>One update at time <paramref name="now"/> (seconds): age the points out, follow the target, rebuild
        /// the mesh. LateUpdate calls it with Time.time; a test can drive it with a clock of its own.</summary>
        public void Step(float now)
        {
            while (points.Count > 0 && now - points[0].born > life) points.RemoveAt(0);
            if (points.Count > 0 && !points[0].start)                   // its strip's first point aged out
            {
                var q = points[0];
                q.start = true;
                points[0] = q;
            }
            bool withHead = false;
            var head = Vector3.zero;
            if (target != null)
            {
                head = target.position + Vector3.up * lift;
                bool jumped = hasLast && (head - lastHead).magnitude > 6f * step;     // a teleport: no ribbon across it
                if (emitting)
                {
                    if (points.Count == 0 || jumped) Add(head, now, true);
                    else
                    {
                        var last = points[points.Count - 1];
                        if ((head - last.p).magnitude >= step)
                        {
                            if (points.Count >= 2 && !last.start &&
                                Vector3.Angle(Flat(last.p - points[points.Count - 2].p), Flat(head - last.p)) > corner)
                                Add(last.p, now, true);                  // a sharp corner: a new strip from it
                            Add(head, now, false);
                        }
                        else withHead = true;                           // the live end, up to the ooze
                    }
                }
                lastHead = head;
                hasLast = true;
            }
            Rebuild(now, head, withHead);
        }

        void Rebuild(float now, Vector3 head, bool withHead)
        {
            if (mesh == null) return;
            verts.Clear();
            norms.Clear();
            uvs.Clear();
            cols.Clear();
            tris.Clear();
            int s0 = 0;
            for (int k = 1; k <= points.Count; k++)
                if (k == points.Count || points[k].start)
                {
                    Strip(s0, k, now, withHead && k == points.Count, head);
                    s0 = k;
                }
            mesh.Clear();
            if (verts.Count == 0) return;
            mesh.SetVertices(verts);
            mesh.SetNormals(norms);
            mesh.SetUVs(0, uvs);
            mesh.SetColors(cols);
            mesh.SetTriangles(tris, 0);
            mesh.RecalculateBounds();
        }

        /// <summary>points[a..b) as one ribbon, oldest first; u = age (0 newest .. 1 oldest), v across.</summary>
        void Strip(int a, int b, float now, bool withHead, Vector3 head)
        {
            strip.Clear();
            for (int k = a; k < b; k++) strip.Add((points[k].p, Mathf.Clamp01((now - points[k].born) / life)));
            if (withHead && strip.Count > 0 && (head - strip[strip.Count - 1].p).sqrMagnitude > 1e-4f) strip.Add((head, 0f));
            if (strip.Count < 2) return;
            int n = strip.Count;
            // half-widths each side: on the inside of a bend, no wider than the bend's radius (so the inner edge
            // runs as a smaller curve instead of folding back), eased over the neighbours so it doesn't pinch
            halfL.Clear();
            halfR.Clear();
            for (int k = 0; k < n; k++)
            {
                float w = 0.5f * width * widthCurve.Evaluate(strip[k].f);
                float wl = w, wr = w;
                if (k > 0 && k < n - 1)
                {
                    Vector3 q0 = strip[k - 1].p, q1 = strip[k].p, q2 = strip[k + 1].p;
                    q0.y = q1.y = q2.y = 0f;
                    float ab = (q1 - q0).magnitude, bc = (q2 - q1).magnitude, ca = (q0 - q2).magnitude;
                    float cross = Vector3.Cross(q1 - q0, q2 - q1).y;                 // + turning right (Unity: y up, left-handed)
                    float area2 = Mathf.Abs(cross);
                    if (area2 > 1e-6f)
                    {
                        float radius = ab * bc * ca / (2f * area2);
                        float lim = 0.85f * radius;
                        if (cross > 0f) wr = Mathf.Min(wr, lim);               // turning right: the right side is inside
                        else wl = Mathf.Min(wl, lim);
                    }
                }
                halfL.Add(wl);
                halfR.Add(wr);
            }
            for (int pass = 0; pass < 2; pass++)
                for (int k = 1; k < n - 1; k++)
                {
                    halfL[k] = Mathf.Min(halfL[k], (halfL[k - 1] + halfL[k] + halfL[k + 1]) / 3f);
                    halfR[k] = Mathf.Min(halfR[k], (halfR[k - 1] + halfR[k] + halfR[k + 1]) / 3f);
                }
            var toLocal = transform.worldToLocalMatrix;
            var up = toLocal.MultiplyVector(Vector3.up).normalized;
            int v0 = verts.Count;
            Vector3 pl = Vector3.zero, pr = Vector3.zero;
            for (int k = 0; k < n; k++)
            {
                var p = strip[k].p;
                var t = Flat(k == 0 ? strip[1].p - p : k == n - 1 ? p - strip[k - 1].p : strip[k + 1].p - strip[k - 1].p);
                var side = Vector3.Cross(Vector3.up, t);                         // to the right of the path
                float f = strip[k].f;
                Vector3 l = p - side * halfL[k], r = p + side * halfR[k];
                if (k > 0)                                              // and as a safety net: an edge never runs backward
                {
                    if (Vector3.Dot(l - pl, t) < 0f) l = pl;
                    if (Vector3.Dot(r - pr, t) < 0f) r = pr;
                }
                pl = l;
                pr = r;
                var c = colour != null ? colour.Evaluate(f) : Color.white;
                verts.Add(toLocal.MultiplyPoint3x4(l));
                verts.Add(toLocal.MultiplyPoint3x4(r));
                norms.Add(up);
                norms.Add(up);
                uvs.Add(new Vector2(f, 0f));
                uvs.Add(new Vector2(f, 1f));
                cols.Add(c);
                cols.Add(c);
                if (k > 0)
                {
                    int i = v0 + 2 * (k - 1);
                    tris.Add(i);
                    tris.Add(i + 2);
                    tris.Add(i + 1);
                    tris.Add(i + 1);
                    tris.Add(i + 2);
                    tris.Add(i + 3);
                }
            }
        }
    }
}

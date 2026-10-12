using System.Collections.Generic;
using UnityEngine;

namespace Beasts
{
    /// <summary>
    /// A big ooze dividing in two. On the Split clip's event (the strand snapping, behind OozeFx's splash) it spawns two
    /// <see cref="childPrefab"/>s where its halves are (the HalfL / HalfR bones), each <see cref="childScale"/> times its
    /// own size (half the volume), in its colour, each keeping the remains on its side and starting on
    /// <see cref="childPool"/> (Reform: a blob taking shape) if it is driven by a BeastRandomAnimator. Then it is gone:
    /// <see cref="SplitInto"/> hands the two to the game first. With <see cref="respawnAfter"/> (test scenes) it only
    /// goes dormant (hidden, not animated) and comes back after a while, rising from a puddle near home, clearing its
    /// halves.
    /// </summary>
    [RequireComponent(typeof(BeastEvents))]
    public class OozeSplit : MonoBehaviour
    {
        public GameObject childPrefab;
        public float childScale = 0.79f;
        public string childPool = "Reform";
        public BeastAnimationSet childSet;
        [Tooltip("Content bones that go with the left half (the rest go right); set by OozeSetup from the model.")]
        public string[] leftRemains = new string[0], rightRemains = new string[0];
        [Tooltip("Test scenes: come back after this many seconds (0 = destroyed on splitting).")]
        public float respawnAfter;

        public System.Action<OozeSplit, GameObject, GameObject> SplitInto;
        public bool Dormant { get; private set; }

        BeastEvents events;
        readonly List<GameObject> children = new List<GameObject>();
        Transform halfL, halfR;
        float backAt;

        void Awake()
        {
            events = GetComponent<BeastEvents>();
            foreach (var t in GetComponentsInChildren<Transform>(true))
            {
                if (t.name == "HalfL") halfL = t;
                if (t.name == "HalfR") halfR = t;
            }
        }

        void OnEnable() => events.EventFired += OnEvent;
        void OnDisable() => events.EventFired -= OnEvent;

        void OnEvent(BeastEvents e, string ev)
        {
            if (ev == "Split" && !Dormant) Split();
        }

        public void Split()
        {
            if (childPrefab == null) return;
            var look = GetComponent<OozeLook>();
            string preset = look != null ? look.preset : "Green";
            float size = transform.localScale.x * childScale;
            var ra = GetComponent<BeastRandomAnimator>();
            var made = new GameObject[2];
            for (int i = 0; i < 2; i++)
            {
                var half = i == 0 ? halfL : halfR;
                var at = half != null ? half.position : transform.position;
                at.y = transform.position.y;
                var away = at - transform.position;                      // facing a little outward
                var rot = transform.rotation * Quaternion.Euler(0, (Vector3.Dot(away, transform.right) > 0 ? 1 : -1) * 25f, 0);
                var go = Instantiate(childPrefab, at, rot, transform.parent);
                go.name = $"{name}_{(i == 0 ? "L" : "R")}";
                var cl = go.GetComponent<OozeLook>();
                if (cl != null) cl.Apply(preset, size, i == 0 ? rightRemains : leftRemains);   // hide the other side's
                if (ra != null && childSet != null)
                {
                    var cra = go.GetComponent<BeastRandomAnimator>() ?? go.AddComponent<BeastRandomAnimator>();
                    cra.set = childSet;
                    cra.home = ra.home;
                    cra.wanderRadius = ra.wanderRadius;
                    cra.separation = ra.separation;
                    cra.labelHeight = ra.labelHeight * childScale;
                    cra.PlayPool(childPool);
                }
                children.Add(go);
                made[i] = go;
            }
            SplitInto?.Invoke(this, made[0], made[1]);
            if (respawnAfter <= 0)
            {
                Destroy(gameObject);
                return;
            }
            Dormant = true;
            backAt = Time.time + respawnAfter;
            Show(false);
        }

        void Update()
        {
            if (!Dormant || Time.time < backAt) return;
            foreach (var c in children) if (c != null) Destroy(c);
            children.Clear();
            var ra = GetComponent<BeastRandomAnimator>();
            if (ra != null) transform.position = ra.home + new Vector3(Random.Range(-3f, 3f), 0, Random.Range(-3f, 3f));
            Dormant = false;
            Show(true);
            if (ra != null) ra.PlayPool("Rise");
        }

        /// <summary>Hidden and not animated, or back (the test UI's other creatures carry on).</summary>
        void Show(bool on)
        {
            foreach (var r in GetComponentsInChildren<Renderer>(true)) r.enabled = on;
            var anim = GetComponent<Animator>();
            if (anim != null) anim.enabled = on;
            foreach (var b in GetComponents<Behaviour>())
                if (b is BeastRandomAnimator || b is OozeFx) b.enabled = on;
        }
    }
}

using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Animations;
using UnityEngine.Playables;

namespace Beasts
{
    /// <summary>
    /// A rider (any Humanoid: a goblin on a warg, an orc driving a mammoth) sitting on its mount's seat bone. Its clips
    /// were made in Blender on top of the mount's own: for every mount clip X there is a rider clip
    /// <see cref="prefix"/>X of the same length, keyed in the seat's space (the hips where the seat has them in that
    /// frame, feet in the stirrups, a fist on the reins), so the rider plays the clip of whatever the mount plays at the
    /// mount's own clip time, crossfades included. Own clips (<see cref="PlayAction"/>: a sword cut, a spear jab, a
    /// flinch) play over the upper body (<see cref="upperBody"/>); <see cref="Fall"/> lets go of the seat and plays the
    /// fall to the ground. The mount's Death has a rider clip too: thrown off.
    /// The rider's Animator is driven by this component's own graph, evaluated after the mount has animated. This
    /// object is the rider's root: it is parented to the seat.
    /// </summary>
    public class MountedRider : MonoBehaviour
    {
        [Tooltip("The rider's Humanoid Animator (on this object or a child: a Humans character's model root).")]
        public Animator animator;
        [Tooltip("What the mount plays (clip name and time).")]
        public BeastRandomAnimator mount;
        [Tooltip("The mount's seat bone (Socket_Saddle, Socket_Driver).")]
        public Transform seat;
        [Tooltip("The rider root's pose in the seat bone's space: the seat bone's head, the mount's own axes (from its bind pose).")]
        public Vector3 seatPosition;
        public Quaternion seatRotation = Quaternion.identity;
        [Tooltip("Rider clips: <prefix><mount clip> for the synced ones, <prefix><name> for the own ones.")]
        public string prefix = "WargRider_";
        public AnimationClip[] clips = new AnimationClip[0];
        [Tooltip("Played when the mount's clip has no rider clip.")]
        public string fallback = "Idle";
        [Tooltip("The own clips' layer: spine, head and the weapon arm.")]
        public AvatarMask upperBody;
        public float actionFade = 0.12f;
        [Tooltip("Kept at its parent's origin (a Humans character's model root, which HumanFace lifts for standing clips: "
                 + "the rider clips have the build's hips in them already).")]
        public Transform keepAtOrigin;
        [Tooltip("Test scenes: an own clip now and then (seconds between, min / max); 0 = never.")]
        public Vector2 demoActions;
        public string[] demoNames = new string[0];

        public bool Dismounted { get; private set; }
        public string CurrentAction => actionPlaying ? actionName : "";

        readonly Dictionary<string, AnimationClip> byName = new Dictionary<string, AnimationClip>();
        Animator anim;
        PlayableGraph graph;
        AnimationLayerMixerPlayable layers;
        AnimationMixerPlayable baseMix;
        AnimationClipPlayable cur, prev, action;
        string curName, prevName, actionName;
        bool actionPlaying, falling;
        float actionTime, fallTime, nextDemo;

        void Awake()
        {
            anim = animator != null ? animator : GetComponentInChildren<Animator>();
            foreach (var c in clips)
                if (c != null) byName[c.name.StartsWith(prefix) ? c.name.Substring(prefix.Length) : c.name] = c;
        }

        void OnEnable()
        {
            if (anim == null) anim = animator != null ? animator : GetComponentInChildren<Animator>();
            anim.applyRootMotion = false;
            anim.cullingMode = AnimatorCullingMode.AlwaysAnimate;
            anim.runtimeAnimatorController = null;
            graph = PlayableGraph.Create(name + "_Rider");
            graph.SetTimeUpdateMode(DirectorUpdateMode.Manual);
            var output = AnimationPlayableOutput.Create(graph, "Rider", anim);
            layers = AnimationLayerMixerPlayable.Create(graph, 2);
            baseMix = AnimationMixerPlayable.Create(graph, 2);
            graph.Connect(baseMix, 0, layers, 0);
            layers.SetInputWeight(0, 1f);
            if (upperBody != null) layers.SetLayerMaskFromAvatarMask(1, upperBody);
            output.SetSourcePlayable(layers);
            graph.Play();
            Seat();
            nextDemo = Time.time + Random.Range(demoActions.x, demoActions.y);
        }

        void OnDisable()
        {
            if (graph.IsValid()) graph.Destroy();
        }

        /// <summary>Onto the seat (again).</summary>
        public void Seat()
        {
            if (seat == null) return;
            transform.SetParent(seat, false);
            transform.localPosition = seatPosition;
            transform.localRotation = seatRotation;
            Dismounted = falling = false;
        }

        /// <summary>One of the own clips over the upper body (Slash, Thrust, Flinch); false if there is none.</summary>
        public bool PlayAction(string clipName)
        {
            if (Dismounted || !byName.TryGetValue(clipName, out var clip)) return false;
            if (action.IsValid())
            {
                graph.Disconnect(layers, 1);
                action.Destroy();
            }
            action = AnimationClipPlayable.Create(graph, clip);
            graph.Connect(action, 0, layers, 1);
            actionName = clipName;
            actionTime = 0f;
            actionPlaying = true;
            return true;
        }

        /// <summary>Killed in the saddle: let go of the seat (upright, where it was) and fall to the ground.</summary>
        public bool Fall(string clipName = "Fall")
        {
            if (Dismounted || !byName.TryGetValue(clipName, out var clip)) return false;
            var p = transform.position;
            var fwd = Vector3.ProjectOnPlane(transform.forward, Vector3.up);
            transform.SetParent(null, true);
            transform.SetPositionAndRotation(p, Quaternion.LookRotation(fwd.sqrMagnitude > 1e-6f ? fwd : Vector3.forward));
            Dismounted = falling = true;
            fallTime = 0f;
            actionPlaying = false;
            layers.SetInputWeight(1, 0f);
            SetSlot(0, ref cur, ref curName, clip, "fall:" + clipName, 0f);
            if (prev.IsValid()) baseMix.SetInputWeight(1, 0f);
            baseMix.SetInputWeight(0, 1f);
            return true;
        }

        AnimationClip RiderClip(string mountClip)
        {
            if (string.IsNullOrEmpty(mountClip)) return null;
            int at = mountClip.LastIndexOf('@');
            var key = at >= 0 ? mountClip.Substring(at + 1) : mountClip;
            if (byName.TryGetValue(key, out var c)) return c;
            return byName.TryGetValue(fallback, out c) ? c : null;
        }

        void LateUpdate()
        {
            if (!graph.IsValid()) return;
            float dt = Time.deltaTime;
            if (falling)
            {
                fallTime += dt;
                if (cur.IsValid()) cur.SetTime(Mathf.Min(fallTime, cur.GetAnimationClip().length));
            }
            else if (mount != null)
            {
                var c = RiderClip(mount.CurrentClip);
                if (c != null)
                {
                    SetSlot(0, ref cur, ref curName, c, mount.CurrentClip, Wrap(c, mount.CurrentTime, mount.CurrentLoops));
                    var p = RiderClip(mount.PreviousClip);
                    float w = p != null ? mount.Fade : 1f;
                    if (p != null) SetSlot(1, ref prev, ref prevName, p, mount.PreviousClip, Wrap(p, mount.PreviousTime, mount.PreviousLoops));
                    baseMix.SetInputWeight(0, w);
                    baseMix.SetInputWeight(1, prev.IsValid() ? 1f - w : 0f);
                }
            }
            if (actionPlaying)
            {
                actionTime += dt;
                float len = action.GetAnimationClip().length;
                action.SetTime(Mathf.Min(actionTime, len));
                float w = Mathf.Clamp01(Mathf.Min(actionTime, len - actionTime) / Mathf.Max(actionFade, 1e-3f));
                layers.SetInputWeight(1, w);
                if (actionTime >= len) { actionPlaying = false; layers.SetInputWeight(1, 0f); }
            }
            if (!Dismounted && demoActions.y > 0 && demoNames.Length > 0 && Time.time > nextDemo)
            {
                PlayAction(demoNames[Random.Range(0, demoNames.Length)]);
                nextDemo = Time.time + Random.Range(demoActions.x, demoActions.y);
            }
            if (keepAtOrigin != null) keepAtOrigin.localPosition = Vector3.zero;
            graph.Evaluate(0f);
        }

        /// <summary>The rider clip's time for the mount's: round again when the mount's clip loops, else held at the
        /// end (whatever the rider clip's own import flags say).</summary>
        static float Wrap(AnimationClip c, float t, bool loops)
        {
            float len = Mathf.Max(c.length, 1e-3f);
            return loops ? Mathf.Repeat(t, len) : Mathf.Min(t, len);
        }

        void SetSlot(int input, ref AnimationClipPlayable slot, ref string slotName, AnimationClip clip, string key, float time)
        {
            if (!slot.IsValid() || slotName != key)
            {
                if (slot.IsValid())
                {
                    graph.Disconnect(baseMix, input);
                    slot.Destroy();
                }
                slot = AnimationClipPlayable.Create(graph, clip);
                slot.Pause();
                graph.Connect(slot, 0, baseMix, input);
                slotName = key;
            }
            slot.SetTime(time);
        }
    }
}

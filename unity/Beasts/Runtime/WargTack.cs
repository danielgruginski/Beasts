using UnityEngine;

namespace Beasts
{
    /// <summary>
    /// The warg's tack: the saddle, straps, bridle and reins (<see cref="tackRenderer"/>) and the goblins' bone war-mask
    /// (<see cref="maskRenderer"/>), both skinned to the warg's own rig, so turning them on or off is all it takes.
    /// Wild wargs go bare; the ones goblins ride wear both. A rider sits on the Socket_Saddle bone.
    /// </summary>
    [ExecuteAlways]
    public class WargTack : MonoBehaviour
    {
        public bool saddled = true;
        [Tooltip("The bone war-mask (only on the ridden ones, as a rule).")]
        public bool masked = true;
        public Renderer tackRenderer;
        public Renderer maskRenderer;

        public Transform Seat { get; private set; }

        void Awake() => Apply();
        void OnValidate() => Apply();

        public void Apply()
        {
            if (tackRenderer != null) tackRenderer.enabled = saddled;
            if (maskRenderer != null) maskRenderer.enabled = masked;
            if (Seat == null)
                foreach (var t in GetComponentsInChildren<Transform>(true))
                    if (t.name == "Socket_Saddle") { Seat = t; break; }
        }
    }
}

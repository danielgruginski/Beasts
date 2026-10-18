using UnityEngine;

namespace Beasts
{
    /// <summary>
    /// The war mammoth's driver tack (<see cref="tackRenderer"/>: a felt rug on the neck, a foot rope behind the ears, a
    /// rope grip), skinned to the mammoth's own rig, so turning it on or off is all it takes. Wild mammoths go bare; an
    /// orc driver sits on the Socket_Driver bone (<see cref="Seat"/>).
    /// </summary>
    [ExecuteAlways]
    public class MammothTack : MonoBehaviour
    {
        public bool saddled = true;
        public Renderer tackRenderer;

        public Transform Seat { get; private set; }

        void Awake() => Apply();
        void OnValidate() => Apply();

        public void Apply()
        {
            if (tackRenderer != null) tackRenderer.enabled = saddled;
            if (Seat == null)
                foreach (var t in GetComponentsInChildren<Transform>(true))
                    if (t.name == "Socket_Driver") { Seat = t; break; }
        }
    }
}

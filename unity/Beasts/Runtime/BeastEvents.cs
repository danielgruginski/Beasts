using System;
using UnityEngine;

namespace Beasts
{
    /// <summary>
    /// Receives the clips' animation events (<c>OnBeastEvent(name)</c>: Bite, Howl, Dead) and raises
    /// <see cref="EventFired"/>; hook damage and sound there.
    /// </summary>
    public class BeastEvents : MonoBehaviour
    {
        public event Action<BeastEvents, string> EventFired;
        public void OnBeastEvent(string name) => EventFired?.Invoke(this, name);
    }
}

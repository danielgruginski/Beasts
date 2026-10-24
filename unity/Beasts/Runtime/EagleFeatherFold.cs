using UnityEngine;

namespace Beasts
{
    /// <summary>
    /// The eagle's folded wing creases round its body (2026-10-24): the feather cards that cross the fold's two creases
    /// bend there, as EagleBody's blend shapes FoldL and FoldR (0 spread, 100 folded). Each follows its gauge bone,
    /// WingFoldL / WingFoldR, which the clips slide <see cref="gauge"/> metres from its rest place as the wing lays on the
    /// flank (not when it only flexes in flight), so any clip, blend or cross-fade bends the cards with the wing.
    /// </summary>
    [ExecuteAlways]
    [DefaultExecutionOrder(100)]
    public class EagleFeatherFold : MonoBehaviour
    {
        public SkinnedMeshRenderer body;
        public Transform gaugeL, gaugeR;
        [Tooltip("The gauges' rest localPosition (the bind pose).")]
        public Vector3 restL, restR;
        [Tooltip("The gauge's slide at a full fold (m): eagle_body.FOLD_GAUGE.")]
        public float gauge = 0.1f;
        int shapeL = -1, shapeR = -1;

        void OnEnable() => Bind();

        public void Bind()
        {
            var mesh = body != null ? body.sharedMesh : null;
            shapeL = mesh != null ? mesh.GetBlendShapeIndex("FoldL") : -1;
            shapeR = mesh != null ? mesh.GetBlendShapeIndex("FoldR") : -1;
        }

        void LateUpdate() => Apply();

        /// <summary>The blend shapes from the gauges now (call it after sampling a clip by hand).</summary>
        public void Apply()
        {
            if (body == null) return;
            if (shapeL < 0 && shapeR < 0) Bind();
            Set(shapeL, gaugeL, restL);
            Set(shapeR, gaugeR, restR);
        }

        void Set(int shape, Transform g, Vector3 rest)
        {
            if (shape < 0 || g == null) return;
            body.SetBlendShapeWeight(shape, 100f * Mathf.Clamp01(Vector3.Distance(g.localPosition, rest) / gauge));
        }
    }
}

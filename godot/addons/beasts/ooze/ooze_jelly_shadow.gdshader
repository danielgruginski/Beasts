shader_type spatial;

// The ooze jelly's shadow: the shadow-only twin of OozeBody (cast_shadow = SHADOWS_ONLY), dithered by the jelly's
// opacity (Unity: OozeJelly's ShadowCaster pass). See ooze_jelly.gdshaderinc.
#define JELLY_SHADOW
#include "res://addons/beasts/ooze/ooze_jelly.gdshaderinc"

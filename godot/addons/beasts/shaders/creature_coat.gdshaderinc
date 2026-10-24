// A creature's painted coat, as the Unity pack's URP Lit material: colour x tint, the smoothness in the texture's alpha
// (Godot's roughness = 1 - alpha x smoothness, as URP's perceptual roughness), not metallic, and an optional
// tangent-space normal map (OpenGL, Y up, as Blender writes it: the warg's fur). Variants (a .gdshader each: defines
// and this file):
//   CREATURE_TWO_SIDED  both faces (a dragon's wing membrane, a hydra's fins)
//   CREATURE_BLEND      alpha blended, both faces, the smoothness a constant (the wasp's and bat's wings: the alpha is
//                       their shape); in the transparent pass, so it casts no shadow, as in Unity

#ifdef CREATURE_BLEND
render_mode blend_mix, depth_draw_opaque, cull_disabled;
#elif defined(CREATURE_TWO_SIDED)
render_mode cull_disabled;
#else
render_mode cull_back;
#endif

uniform sampler2D coat : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform vec4 tint : source_color = vec4(1.0);
uniform float smoothness : hint_range(0.0, 1.0) = 1.0;
uniform bool use_normal_map = false;
uniform sampler2D normal_map : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform float normal_scale = 1.0;

void fragment() {
	vec4 c = texture(coat, UV);
	ALBEDO = c.rgb * tint.rgb;
	METALLIC = 0.0;
#ifdef CREATURE_BLEND
	ROUGHNESS = 1.0 - smoothness;
	ALPHA = c.a * tint.a;
#else
	ROUGHNESS = 1.0 - c.a * smoothness;
#endif
	if (use_normal_map) {
		NORMAL_MAP = texture(normal_map, UV).rgb;
		NORMAL_MAP_DEPTH = normal_scale;
	}
}

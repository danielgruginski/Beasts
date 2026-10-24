// The dungeon ooze's see-through jelly (Unity: Beasts/OozeJelly + OozeJellyForward.hlsl; Blender's preview of it is
// ooze_paint.shell_material). Two materials over the same mesh, alpha blended without depth writes: the far side
// (ooze_jelly_far.gdshader: back faces, the normal turned toward the eye, faded by back_fade) and, as its next_pass, the
// near side (ooze_jelly_near.gdshader), so the shell reads as a solid lump with the contents (a separate opaque mesh)
// inside. Godot draws a next_pass whenever its sorting says, so the far side has render_priority -1 and the near side 0
// (set by OozeLook.make_jelly): every far side is drawn before the near sides.
// T_Ooze holds masks, linear (R tone: thin -> mid -> core by the jelly's thickness, G shade: creases dark, B detail,
// A opacity), mapped through four colours, so any ooze colour is a material setting (one material per preset:
// OozeLook.PRESETS). Opacity = the texture's alpha (thick core denser, pod tips and the skirt's edge clear) x opacity +
// a fresnel rim. Premultiplied (blend_premul_alpha; URP Lit's "Premultiply"): the diffuse fades with the opacity, the
// highlights don't, so it stays wet and glossy where it is clear. A faint glow of its own colour keeps the shaded side
// from going black; a small vertex wobble. A transparent surface casts no shadow in Godot: OozeLook gives the body a
// shadow-only twin (ooze_jelly_shadow.gdshader) dithered by the same opacity.
// Variants (a .gdshader each: a define and this file):
//   JELLY_FAR     the far side
//   JELLY_SHADOW  the shadow-only twin: opaque, cut by a 4x4 ordered dither at shadow_density

#ifdef JELLY_FAR
render_mode blend_premul_alpha, depth_draw_never, cull_front, world_vertex_coords;
#elif defined(JELLY_SHADOW)
render_mode cull_disabled, world_vertex_coords;
#else
render_mode blend_premul_alpha, depth_draw_never, cull_back, world_vertex_coords;
#endif

// Masks: tone, shade, detail, opacity (linear)
uniform sampler2D masks : hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
uniform vec4 thin_color : source_color = vec4(0.651, 0.831, 0.333, 1.0);
uniform vec4 mid_color : source_color = vec4(0.310, 0.549, 0.110, 1.0);
uniform vec4 core_color : source_color = vec4(0.173, 0.353, 0.071, 1.0);
uniform vec4 crevice_color : source_color = vec4(0.090, 0.196, 0.031, 1.0);
uniform float fresnel : hint_range(0.0, 1.0) = 0.45;
uniform float fresnel_power : hint_range(0.5, 8.0) = 2.5;
uniform float smoothness : hint_range(0.0, 1.0) = 0.9;
uniform float glow : hint_range(0.0, 1.0) = 0.08;
uniform float back_fade : hint_range(0.0, 1.0) = 0.75;
uniform float wobble : hint_range(0.0, 0.05) = 0.008;
uniform float wobble_speed : hint_range(0.0, 6.0) = 1.6;
#ifdef JELLY_SHADOW
uniform float shadow_density : hint_range(0.0, 1.0) = 0.6;
// the preset's opacity, per ooze (OozeLook sets it on its twin)
instance uniform float opacity = 1.0;
#else
uniform float opacity : hint_range(0.0, 2.0) = 1.0;
#endif

// world space in, world space out (world_vertex_coords): metres, whatever the ooze's size
vec3 jelly_wobble(vec3 p, vec3 n) {
	float t = TIME * wobble_speed;
	float w = sin(p.x * 3.1 + t) * sin(p.z * 2.7 - t * 0.8) + 0.5 * sin(p.y * 4.3 + t * 1.3);
	return p + n * (w * wobble);
}

void vertex() {
	VERTEX = jelly_wobble(VERTEX, normalize(NORMAL));
}

#ifdef JELLY_SHADOW
// a 2x2 ordered dither in shadow-map texels: the shadow filter averages it into a partial shadow (Unity's 4x4 left
// a coarser screen-door pattern under Godot's default "Soft Low" filter; it is smooth at Soft High / Ultra or with a
// larger shadow_blur on the light; a solid shadow instead darkened the floor seen through the jelly far too much, and
// interleaved-gradient noise looked no better). The jelly receives its own partial shadow, as in Unity.
const float BAYER[4] = float[4](0.0, 2.0, 3.0, 1.0);

void fragment() {
	ivec2 p = ivec2(mod(FRAGCOORD.xy, 2.0));
	float a = clamp(texture(masks, UV).a * opacity + 0.15, 0.0, 1.0) * shadow_density;
	if (a < (BAYER[p.y * 2 + p.x] + 0.5) / 4.0) {
		discard;
	}
	ALBEDO = vec3(0.0);
}
#else
// The masks to a colour (ooze_paint.shell_material builds the same in Blender): tone through thin, mid and core;
// creases toward the crevice colour; detail lightens lumps and darkens the streaks.
vec3 jelly_colour(vec4 m) {
	vec3 c = m.r < 0.5 ? mix(thin_color.rgb, mid_color.rgb, m.r * 2.0) : mix(mid_color.rgb, core_color.rgb, m.r * 2.0 - 1.0);
	c = mix(c, crevice_color.rgb, 1.0 - smoothstep(0.55, 0.95, m.g));
	return c * (0.75 + 0.25 * m.g) * (0.55 + 0.9 * m.b);
}

void fragment() {
	vec4 m = texture(masks, UV);
	vec3 col = jelly_colour(m);
	vec3 n = normalize(NORMAL);
#ifdef JELLY_FAR
	// seen from inside: the normal turned toward the eye
	if (dot(n, VIEW) < 0.0) {
		n = -n;
	}
#endif
	float rim = pow(1.0 - clamp(dot(n, VIEW), 0.0, 1.0), fresnel_power);
	float a = clamp(m.a * opacity + rim * fresnel, 0.0, 1.0);
	NORMAL = n;
	ALBEDO = col * a;               // premultiplied: the diffuse carries the opacity, the highlights don't
	METALLIC = 0.0;
	ROUGHNESS = 1.0 - smoothness;
	EMISSION = col * (glow * a);
#ifdef JELLY_FAR
	ALPHA = a * back_fade;
	PREMUL_ALPHA_FACTOR = back_fade; // the whole far side (highlights too) scaled by back_fade, as Unity's "* fade"
#else
	ALPHA = a;
#endif
}
#endif

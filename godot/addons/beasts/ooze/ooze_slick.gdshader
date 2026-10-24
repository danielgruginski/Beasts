shader_type spatial;
render_mode blend_premul_alpha, depth_draw_never, cull_disabled;

// The dungeon ooze's slime trail (OozeTrail; Unity: Beasts/OozeSlick): one flat sheet over the floor round the ooze,
// showing a wetness field the trail paints into (a small float texture tied to the world and wrapping: texel i covers
// world [i, i + 1) x cell). Where the field passes the edge threshold there is slime, so splats close together merge
// into one wet patch with smooth necks between them (no alpha piling up where they overlap), and as the field dries the
// edges creep in and the patch breaks into puddles before it goes. The field's slope tilts the normal, so the edge
// carries a bead of highlight. Premultiplied like the jelly: the diffuse fades with the opacity, the highlights only
// with the coverage. render_priority -2 (OozeTrail sets it): drawn before the jelly, which blends over it.
// The drying runs here, not on the CPU (Unity dried its field texel by texel every frame): a texel keeps when it was
// wet, as log-wetness at the trail's clock (wetness(now) = exp(L - now / tau)), so the field only changes where a splat
// lands. R: the settled wetness; G: the newest splat's, welling out over `grow` seconds since B (its birth; a splat
// landing on one still spreading joins it).

uniform sampler2D field : filter_nearest, repeat_enable;
// texels a side (a power of two: the field wraps by bit mask)
uniform int field_size = 128;
// metres a texel
uniform float cell = 0.1;
// the trail's clock (seconds) and the drying's time constant
uniform float now = 0.0;
uniform float tau = 6.7;
uniform float grow = 1.0;
uniform vec4 color : source_color = vec4(0.20, 0.36, 0.08, 1.0);
// the slime's edge: from, to
uniform vec2 edge = vec2(0.30, 0.40);
// opacity: drying, fresh
uniform vec2 opacity = vec2(0.20, 0.60);
uniform float smoothness : hint_range(0.0, 1.0) = 0.92;
uniform float bump : hint_range(0.0, 20.0) = 4.0;
// the sheet's border fade (uv)
uniform float border : hint_range(0.001, 0.5) = 0.08;

varying vec3 world_pos;

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

float wet_texel(ivec2 i) {
	vec4 t = texelFetch(field, i & ivec2(field_size - 1), 0);
	float k = now / tau;
	float g = clamp((now - t.b) / max(grow, 1e-3), 0.0, 1.0);
	return max(exp(t.r - k), exp(t.g - k) * g * g * (3.0 - 2.0 * g));
}

// the field at q (texel units, texel centres on whole numbers), filtered bilinearly in wetness
float wet(vec2 q) {
	vec2 f0 = floor(q);
	vec2 f = q - f0;
	ivec2 i = ivec2(f0);
	return mix(mix(wet_texel(i), wet_texel(i + ivec2(1, 0)), f.x),
			mix(wet_texel(i + ivec2(0, 1)), wet_texel(i + ivec2(1, 1)), f.x), f.y);
}

void fragment() {
	vec2 q = world_pos.xz / cell - 0.5;
	float f = wet(q);
	vec2 b = min(UV, 1.0 - UV);
	float cover = smoothstep(edge.x, edge.y, f) * smoothstep(0.0, border, min(b.x, b.y));
	if (cover < 0.002) {
		discard;
	}
	// the slope over two texels each way: across the seams where splats meet (the field keeps the wetter of two, so its
	// slope breaks there) a one-texel slope draws a bright zig-zag; the edges keep their bead
	float fx = wet(q + vec2(2.0, 0.0)) - wet(q - vec2(2.0, 0.0));
	float fz = wet(q + vec2(0.0, 2.0)) - wet(q - vec2(0.0, 2.0));
	vec3 nw = normalize(vec3(-fx * bump * 0.5, 1.0, -fz * bump * 0.5));
	float a = cover * mix(opacity.x, opacity.y, clamp((f - edge.x) / max(1.0 - edge.x, 0.01), 0.0, 1.0));
	NORMAL = normalize((VIEW_MATRIX * vec4(nw, 0.0)).xyz);
	ALBEDO = color.rgb * a;         // premultiplied: the diffuse carries the opacity
	METALLIC = 0.0;
	ROUGHNESS = 1.0 - smoothness;
	ALPHA = a;
	PREMUL_ALPHA_FACTOR = cover;    // the highlights end where the slime does
}

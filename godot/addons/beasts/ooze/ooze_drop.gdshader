shader_type spatial;
render_mode blend_mix, depth_draw_never, cull_disabled;

// A wet droplet: the ooze's drips, splashes and the acid's fizz (ooze_drops.gdshader moves them). A camera-facing quad
// (each axis keeps the particle's own scale, so a drip draws out as it falls), round, with a highlight painted in,
// glossy, tinted by the particle's colour (Unity: M_OozeDrop, URP Particles/Lit on T_OozeDrop; the texture's shape is
// drawn here instead).

uniform float smoothness : hint_range(0.0, 1.0) = 0.9;

void vertex() {
	mat4 face = mat4(normalize(INV_VIEW_MATRIX[0]), normalize(INV_VIEW_MATRIX[1]), normalize(INV_VIEW_MATRIX[2]), MODEL_MATRIX[3]);
	face = face * mat4(vec4(length(MODEL_MATRIX[0].xyz), 0.0, 0.0, 0.0), vec4(0.0, length(MODEL_MATRIX[1].xyz), 0.0, 0.0),
			vec4(0.0, 0.0, length(MODEL_MATRIX[2].xyz), 0.0), vec4(0.0, 0.0, 0.0, 1.0));
	MODELVIEW_MATRIX = VIEW_MATRIX * face;
	MODELVIEW_NORMAL_MATRIX = mat3(MODELVIEW_MATRIX);
}

void fragment() {
	// T_OozeDrop (OozeSetup.MakeFx): a soft disc, a little lighter in the middle, a highlight up and left
	vec2 uv = vec2(UV.x, 1.0 - UV.y);
	float r = length(uv - 0.5) * 2.0;
	float a = 1.0 - smoothstep(0.72, 1.0, r);
	vec2 h = uv - vec2(0.36, 0.64);
	float hl = exp(-dot(h, h) / 0.006);
	float c = min(0.82 + 0.18 * (1.0 - r) + 0.6 * hl, 1.0);
	ALBEDO = COLOR.rgb * pow(c, 2.2);
	METALLIC = 0.0;
	ROUGHNESS = 1.0 - smoothness;
	ALPHA = a * COLOR.a;
}

shader_type spatial;
render_mode blend_mix, depth_draw_never, cull_disabled;

// The acid glob's puddle where it lands (OozeGlob): a splat lying on the floor, a ragged round patch with droplets
// thrown round it, glossy, in the ooze's colour, fading as it goes (Unity: M_OozePuddle, URP Particles/Lit on
// T_OozeSplat; the texture's shape is drawn here instead). Colour and fade per puddle: tint (linear, alpha = opacity).

uniform float smoothness : hint_range(0.0, 1.0) = 0.95;
instance uniform vec4 tint = vec4(0.3, 0.5, 0.1, 0.75);

// GLSL's smoothstep, with edges either way round
float smooth01(float e0, float e1, float x) {
	float t = clamp((x - e0) / (e1 - e0), 0.0, 1.0);
	return t * t * (3.0 - 2.0 * t);
}

void fragment() {
	// T_OozeSplat (OozeSetup.MakeFx)
	float x = UV.x - 0.5;
	float y = 0.5 - UV.y;
	float ang = atan(y, x);
	float rim = 0.36 + 0.05 * sin(ang * 5.0 + 0.7) + 0.035 * sin(ang * 11.0 + 2.1);
	float r = length(vec2(x, y));
	float a = 1.0 - smooth01(rim - 0.05, rim + 0.01, r);
	for (int k = 0; k < 7; k++) {       // droplets thrown round it
		float da = float(k) * 0.9 + 0.4;
		float dr = 0.42 + 0.03 * float(k % 3);
		a = max(a, 1.0 - smooth01(0.018, 0.032, length(vec2(x - cos(da) * dr, y - sin(da) * dr))));
	}
	float c = 0.85 + 0.15 * smooth01(rim, 0.0, r);
	ALBEDO = tint.rgb * pow(c, 2.2);
	METALLIC = 0.0;
	ROUGHNESS = 1.0 - smoothness;
	ALPHA = a * 0.95 * tint.a;
}

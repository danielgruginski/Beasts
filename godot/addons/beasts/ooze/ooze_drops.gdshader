shader_type particles;

// The ooze's wet droplets, simulated (GPUParticles3D, world space; OozeFx and OozeGlob build the emitters; Unity:
// OozeFx's and OozeGlob's ParticleSystems). Godot's particles collide only with GPUParticlesCollision nodes, so the
// floor is a height here (floor_y: the ooze's own, as Unity's world collision met the floor under it). Three kinds:
//   0 drip    from a sphere round a raised pod's tip, no start speed, falls, drawn out as it falls, ends on the floor
//   1 splash  a burst thrown up and out from a point (OozeFx.splash: hit, hurt, death, split...), bounces on the
//             floor (losing life_loss of its life each time), shrinks away at the end
//   2 fizz    bubbles rising off the acid puddle (OozeGlob), from a flat circle
// ooze_drop.gdshader draws them.

uniform int kind = 0;
uniform vec4 colour : source_color = vec4(0.5, 0.7, 0.2, 0.8);
// the droplets' alpha, random in the range (colour's own alpha is not used)
uniform vec2 alpha_range = vec2(0.8, 0.8);
// metres
uniform vec2 size_range = vec2(0.03, 0.065);
// seconds; at most the emitter's lifetime
uniform vec2 life_range = vec2(1.6, 1.6);
// splash: speed out (m/s, times strength); fizz: rise speed
uniform vec2 speed_range = vec2(1.4, 3.4);
uniform float strength = 1.0;
// the emission shape's radius (m): a sphere (drip, splash) or a flat circle (fizz)
uniform float spread = 0.07;
// m/s² down (negative: up)
uniform float gravity = 10.8;
uniform float floor_y = 0.0;
uniform float bounce = 0.15;
uniform float dampen = 0.6;
uniform float life_loss = 0.5;

float rand_from_seed(inout uint seed) {
	int k;
	int s = int(seed);
	if (s == 0) {
		s = 305420679;
	}
	k = s / 127773;
	s = 16807 * (s - k * 127773) - 2836 * k;
	if (s < 0) {
		s += 2147483647;
	}
	seed = uint(s);
	return float(seed % uint(65536)) / 65535.0;
}

uint hash(uint x) {
	x = ((x >> uint(16)) ^ x) * uint(73244475);
	x = ((x >> uint(16)) ^ x) * uint(73244475);
	x = (x >> uint(16)) ^ x;
	return x;
}

void start() {
	uint seed = hash(NUMBER + uint(1) + RANDOM_SEED);
	vec3 origin = EMISSION_TRANSFORM[3].xyz;
	float z = rand_from_seed(seed) * 2.0 - 1.0;
	float ang = rand_from_seed(seed) * TAU;
	vec3 d = vec3(sqrt(1.0 - z * z) * cos(ang), z, sqrt(1.0 - z * z) * sin(ang));
	vec3 pos = origin;
	if (kind == 0) {
		pos += d * spread * pow(rand_from_seed(seed), 1.0 / 3.0);
		VELOCITY = vec3(0.0);
	} else if (kind == 1) {
		d.y = abs(d.y) * 0.8 + 0.3;
		pos += d * spread;
		VELOCITY = normalize(d) * mix(speed_range.x, speed_range.y, rand_from_seed(seed)) * strength;
	} else {
		float r = sqrt(rand_from_seed(seed)) * spread;
		pos += vec3(cos(ang) * r, 0.0, sin(ang) * r);
		VELOCITY = vec3(0.0, mix(speed_range.x, speed_range.y, rand_from_seed(seed)), 0.0);
	}
	float size = mix(size_range.x, size_range.y, rand_from_seed(seed));
	TRANSFORM = mat4(vec4(size, 0.0, 0.0, 0.0), vec4(0.0, size, 0.0, 0.0), vec4(0.0, 0.0, size, 0.0), vec4(pos, 1.0));
	COLOR = vec4(colour.rgb, mix(alpha_range.x, alpha_range.y, rand_from_seed(seed)));
	// x: age, y: its own lifetime, z: its size
	CUSTOM = vec4(0.0, mix(life_range.x, life_range.y, rand_from_seed(seed)), size, 0.0);
}

void process() {
	CUSTOM.x += DELTA;
	float life = max(CUSTOM.y, 1e-3);
	if (CUSTOM.x >= life) {
		ACTIVE = false;
	}
	VELOCITY.y -= gravity * DELTA;
	if (kind != 2 && TRANSFORM[3].y < floor_y && VELOCITY.y < 0.0) {
		if (kind == 0) {
			ACTIVE = false;             // a drip ends on the floor
		} else {
			TRANSFORM[3].y = floor_y;
			VELOCITY.y = -VELOCITY.y * bounce;
			VELOCITY.xz *= 1.0 - dampen;
			CUSTOM.x += life * life_loss;
		}
	}
	float t = clamp(CUSTOM.x / life, 0.0, 1.0);
	vec3 s;
	if (kind == 0) {
		s = vec3(mix(1.2, 0.8, t), mix(0.9, 1.6, t), 1.0);     // drawn out as it falls
	} else if (kind == 1) {
		float k = t < 0.8 ? mix(1.0, 0.9, t / 0.8) : mix(0.9, 0.0, (t - 0.8) / 0.2);
		s = vec3(k);
	} else {
		float k = t < 0.7 ? mix(0.4, 1.0, t / 0.7) : mix(1.0, 0.0, (t - 0.7) / 0.3);
		s = vec3(k);
	}
	s *= CUSTOM.z;
	TRANSFORM[0] = vec4(s.x, 0.0, 0.0, 0.0);
	TRANSFORM[1] = vec4(0.0, s.y, 0.0, 0.0);
	TRANSFORM[2] = vec4(0.0, 0.0, s.z, 0.0);
}

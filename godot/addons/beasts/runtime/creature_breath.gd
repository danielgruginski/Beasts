class_name CreatureBreath
extends Node3D
## A dragon's fire breath (on Socket_Mouth through a BoneAttachment3D; dragon_setup.gd places it): a cone of flame
## between the clip's events ("Fire" starts it, "FireEnd" or "Dead" stops it, and it never runs longer than
## max_seconds, so a clip cut short by a crossfade can't leave it burning). Built when it enters the tree the way the
## game's campfires are (MedievalSetting's FireFx; Unity's BeastBreath, reworked 2026-10-24): a body of flame tongues
## (the 8 x 8 flipbook, alpha blended, so the flames piled up in the stream never wash out to white, tinted only lightly
## as they cool and stirred by turbulence), a smaller additive core, a faint warm glow round the stream's first half,
## embers, dark smoke rising off its end, and a flickering orange light; in world space so the stream bends as the head
## sweeps. The flipbooks are the game's (res://beasts/FX/: FX_FlameSheet_soft, FX_FlameSheet, FX_Glow, FX_Spark,
## FX_SmokeSheet; tools/install_to_godot.py copies them when MedievalSetting is there); soft blobs stand in otherwise.
## (Unity's particles also bounce off colliders; Godot's GPU particles would need collision nodes.)

const FX := "res://beasts/FX/"

@export var start_event := "Fire"
@export var stop_event := "FireEnd"
## how far the flames reach (metres, before the creature's scale)
@export var reach := 10.0
## half-angle of the cone (degrees)
@export var spread := 8.0
@export var max_seconds := 1.6
## the stand-in blobs' colours (without the flipbooks)
@export var hot := Color(1.0, 0.85, 0.45)
@export var mid := Color(1.0, 0.45, 0.1)
@export var cool := Color(0.45, 0.08, 0.02)

var burning := false
var _systems: Array[GPUParticles3D] = []
var _glow: OmniLight3D
var _stop_at := 0.0
var _t := 0.0
var _light := 0.0


func _ready() -> void:
	var life := 0.75
	var speed := reach / life
	var real := ResourceLoader.exists(FX + "FX_FlameSheet_soft.png")
	var flame_tint := [Color.WHITE, Color(1.0, 0.92, 0.85), Color(0.8, 0.45, 0.35)]
	# the body: tongues of flame growing as they go, the flipbook played once from a random frame
	var body := _emitter("Flames", "FX_FlameSheet_soft.png", 8, true, false, 1.4, Vector2(life * 0.8, life * 1.15), speed,
		Vector2(1.6, 2.6), 110.0, flame_tint if real else [hot, mid, cool], [0.0, 0.45, 1.0], [0.0, 1.0, 0.95, 0.0],
		[0.0, 0.1, 0.6, 1.0], [0.3, 0.8, 1.15])
	_turbulence(body, 0.7, 0.6)
	_upright(body)
	# the hot heart, shorter and smaller, over the body
	var core := _emitter("Core", "FX_FlameSheet.png", 8, true, true, 0.6, Vector2(life * 0.45, life * 0.65), speed,
		Vector2(0.9, 1.5), 70.0, flame_tint if real else [Color.WHITE, hot, mid], [0.0, 0.45, 1.0], [0.0, 1.0, 0.95, 0.0],
		[0.0, 0.1, 0.6, 1.0], [0.35, 0.9, 0.8])
	_turbulence(core, 0.4, 0.6)
	_upright(core)
	# a faint warm glow round the stream's first half (big additive puffs)
	_emitter("Glow", "FX_Glow.png", 0, false, true, 1.0, Vector2(life * 0.5, life * 0.7), speed * 0.6, Vector2(3.5, 5.0),
		22.0, [Color(1.0, 0.55, 0.2), Color(1.0, 0.55, 0.2)], [0.0, 1.0], [0.0, 0.35, 0.25, 0.0], [0.0, 0.25, 0.7, 1.0],
		[0.6, 0.9, 1.2])
	# embers flying out of the stream, yellow fading to red, arcing down
	var embers := _emitter("Embers", "FX_Spark.png", 0, false, true, 1.2, Vector2(0.5, 1.1), speed * 1.05,
		Vector2(0.06, 0.12), 45.0, [Color(1.0, 0.72, 0.3), Color(1.0, 0.42, 0.1), Color(0.75, 0.12, 0.02)], [0.0, 0.35, 1.0],
		[1.0, 1.0, 0.0], [0.0, 0.6, 1.0], [1.0, 0.7, 0.4])
	var em := embers.process_material as ParticleProcessMaterial
	em.spread = spread * 1.8
	em.gravity = Vector3(0, -2.5, 0)
	_turbulence(embers, 1.2, 0.7)
	# dark smoke rising off the stream's far end, paling as it spreads (one random puff of the 4 x 4 sheet each)
	var smoke := _emitter("Smoke", "FX_SmokeSheet.png", 4, false, false, 1.0, Vector2(1.4, 2.2), speed * 0.35,
		Vector2(1.6, 2.8), 20.0, [Color(0.36, 0.26, 0.19), Color(0.2, 0.19, 0.18), Color(0.6, 0.59, 0.58)], [0.0, 0.25, 1.0],
		[0.0, 0.5, 0.45, 0.0], [0.0, 0.15, 0.55, 1.0], [0.6, 1.2, 1.8])
	smoke.position = Vector3(0, 0, reach * 0.45)
	var sm := smoke.process_material as ParticleProcessMaterial
	sm.spread = spread * 2.5
	sm.gravity = Vector3(0, 1.5, 0)            # smoke rises
	_turbulence(smoke, 0.4, 0.25)
	_glow = OmniLight3D.new()
	_glow.position = Vector3(0, 0, reach * 0.4)
	_glow.light_color = Color(1.0, 0.55, 0.22)  # the game's firelight
	_glow.omni_range = reach * 1.6
	_glow.light_energy = 0.0
	_glow.visible = false
	add_child(_glow)
	var c := _creature()
	if c != null:
		c.creature_event.connect(_on_event)


func _creature() -> Creature:
	var n := get_parent()
	while n != null and not (n is Creature):
		n = n.get_parent()
	return n as Creature


func _on_event(_c: Creature, event_name: String) -> void:
	if event_name == start_event:
		ignite()
	elif event_name == stop_event or event_name == "Dead":
		douse()


func ignite() -> void:
	burning = true
	_stop_at = _t + max_seconds
	for p in _systems:
		p.emitting = true


func douse() -> void:
	burning = false
	for p in _systems:
		p.emitting = false


func _process(delta: float) -> void:
	_t += delta
	if burning and _t > _stop_at:
		douse()
	_light = move_toward(_light, 1.0 if burning else 0.0, delta * (6.0 if burning else 2.5))
	_glow.visible = _light > 0.01
	_glow.light_energy = _light * (2.0 + 0.5 * sin(_t * 23.0) * sin(_t * 9.0))


## flame tongues stand up as the game's campfires' do (tips up the screen, a little tilt, no spin); glow and smoke keep
## their random turn
func _upright(p: GPUParticles3D) -> void:
	var m := p.process_material as ParticleProcessMaterial
	m.angle_min = -7.0
	m.angle_max = 7.0
	m.angular_velocity_min = 0.0
	m.angular_velocity_max = 0.0


func _turbulence(p: GPUParticles3D, strength: float, frequency: float) -> void:
	var m := p.process_material as ParticleProcessMaterial
	m.turbulence_enabled = true
	m.turbulence_noise_strength = strength
	m.turbulence_noise_scale = 1.0 / maxf(frequency, 0.05)
	m.turbulence_noise_speed_random = 0.5
	m.turbulence_influence_min = 0.05
	m.turbulence_influence_max = 0.15


## one layer of the breath; tiles: the flipbook's n x n (0: none), play: through it once over the life from a random
## frame (else one random frame); brightness multiplies the colours (the game's material colours: above 1 brighter
## than the texture); grow: the size at the life's start, a third in, and its end
func _emitter(n: String, tex: String, tiles: int, play: bool, additive: bool, brightness: float, life: Vector2,
		speed: float, size: Vector2, rate: float, colors: Array, color_at: Array, alphas: Array, alpha_at: Array,
		grow: Array) -> GPUParticles3D:
	var p := GPUParticles3D.new()
	p.name = n
	p.emitting = false
	p.amount = maxi(8, int(rate * life.y * 1.2))
	p.lifetime = life.y
	p.randomness = 1.0 - life.x / life.y
	p.local_coords = false                      # the stream bends as the head sweeps
	p.visibility_aabb = AABB(Vector3(-reach, -reach, -1.0), Vector3(reach * 2.0, reach * 2.0, reach * 1.6))
	p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var m := ParticleProcessMaterial.new()
	m.direction = Vector3(0, 0, 1)              # along the attachment's +Z: ahead out of the jaws
	m.spread = spread
	m.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_SPHERE
	m.emission_sphere_radius = 0.12
	m.initial_velocity_min = speed * 0.85
	m.initial_velocity_max = speed * 1.1
	m.gravity = Vector3(0, 0.5, 0)
	m.damping_min = speed * 0.35                # the stream slows and piles up at its end
	m.damping_max = speed * 0.5
	m.angle_min = 0.0
	m.angle_max = 360.0
	m.angular_velocity_min = -70.0
	m.angular_velocity_max = 70.0
	m.scale_min = size.x
	m.scale_max = size.y
	var sc := Curve.new()
	sc.max_value = 2.0
	sc.add_point(Vector2(0.0, grow[0]))
	sc.add_point(Vector2(0.33, grow[1]))
	sc.add_point(Vector2(1.0, grow[2]))
	var sct := CurveTexture.new()
	sct.curve = sc
	m.scale_curve = sct
	var ramp := Gradient.new()
	var offs := PackedFloat32Array()
	var cols := PackedColorArray()
	var g := Gradient.new()
	g.offsets = PackedFloat32Array(color_at)
	g.colors = PackedColorArray(colors)
	for i in 9:
		var t := i / 8.0
		var c := g.sample(t)
		c = Color(c.r * brightness, c.g * brightness, c.b * brightness, _sample(alphas, alpha_at, t))
		offs.append(t)
		cols.append(c)
	ramp.offsets = offs
	ramp.colors = cols
	var rt := GradientTexture1D.new()
	rt.gradient = ramp
	rt.use_hdr = true                           # the material colours brighter than the texture
	m.color_ramp = rt
	var path := FX + tex
	var has_tex := ResourceLoader.exists(path)
	if has_tex and tiles > 0:
		m.anim_offset_min = 0.0                 # a random frame
		m.anim_offset_max = 1.0
		m.anim_speed_min = 1.0 if play else 0.0  # 1: through the sheet once over the life
		m.anim_speed_max = 1.0 if play else 0.0
	p.process_material = m
	var quad := QuadMesh.new()
	quad.size = Vector2.ONE
	var mat := StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.blend_mode = BaseMaterial3D.BLEND_MODE_ADD if additive else BaseMaterial3D.BLEND_MODE_MIX
	mat.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
	mat.vertex_color_use_as_albedo = true
	mat.depth_draw_mode = BaseMaterial3D.DEPTH_DRAW_DISABLED
	mat.proximity_fade_enabled = true           # soft where the flames meet the ground (the game's soft particles)
	mat.proximity_fade_distance = 0.4
	if has_tex:
		mat.albedo_texture = load(path)
		if tiles > 0:
			mat.particles_anim_h_frames = tiles
			mat.particles_anim_v_frames = tiles
			mat.particles_anim_loop = false
	else:
		mat.albedo_texture = _blob()
	quad.material = mat
	p.draw_pass_1 = quad
	add_child(p)
	_systems.append(p)
	return p


static func _sample(vals: Array, at: Array, t: float) -> float:
	for i in range(1, at.size()):
		if t <= at[i]:
			return lerpf(vals[i - 1], vals[i], (t - at[i - 1]) / maxf(at[i] - at[i - 1], 1e-5))
	return vals[-1]


static var _blob_tex: GradientTexture2D


## a soft round blob (the stand-in without the game's flipbooks, as Unity's)
static func _blob() -> GradientTexture2D:
	if _blob_tex == null:
		var g := Gradient.new()
		g.offsets = PackedFloat32Array([0.0, 1.0])
		g.colors = PackedColorArray([Color(1, 1, 1, 1), Color(1, 1, 1, 0)])
		_blob_tex = GradientTexture2D.new()
		_blob_tex.gradient = g
		_blob_tex.fill = GradientTexture2D.FILL_RADIAL
		_blob_tex.fill_from = Vector2(0.5, 0.5)
		_blob_tex.fill_to = Vector2(1.0, 0.5)
		_blob_tex.width = 64
		_blob_tex.height = 64
	return _blob_tex

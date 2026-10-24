class_name OozeFx
extends Node
## The ooze's effects (a child of its Creature root), built in code, coloured by its OozeLook's preset:
##   a wet slime trail on the floor while it moves (an OozeTrail: splats merged in a wetness field);
##   drips falling from the raised pods' tips (Reach3, Side3, Probe3);
##   splashes on the clips' events: Hit (Lash's slam, Grab's catch: at the pod's tip), Hurt, Grab, Engulf, Dead,
##   Split, Risen, and a spray at the mouth on Spit;
##   the acid glob on Spit: an OozeGlob from Socket_Spit to spit_target (or 5 m ahead, times the ooze's size), which
##   leaves a sizzling puddle where it lands.
## The trail and the splashes live on a node of their own beside the ooze ("<name>_Fx", a sibling), so they outlast it
## (a split hides the big one at the moment it splashes); it is freed 12 s after the ooze. Listens to the Creature's
## creature_event; splash() and spit() can be called by the game too. The droplets are GPUParticles3D on
## ooze_drops.gdshader (the floor is the ooze's height: Godot's particles meet no world geometry). Unity: OozeFx.

## emitted when a glob is spat (the game can hook its `landed` signal for the damage)
signal spat(glob: OozeGlob)

## where Spit aims; null = 5 m ahead (times the ooze's size)
@export var spit_target: Node3D
@export var trail := true
@export var drips := true
@export var drip_rate := 1.2

const DROPS := preload("res://addons/beasts/ooze/ooze_drops.gdshader")
const DROP := preload("res://addons/beasts/ooze/ooze_drop.gdshader")
const SPLASH_MAX := 70              # the most droplets one splash throws (Split)
const SPLASHES := 4                 # splashes that can be in the air at once

var creature: Creature
var look: OozeLook
var fx_root: Node3D
var trail_node: OozeTrail

var _skeleton: Skeleton3D
var _bones := {}
var _splashes: Array[GPUParticles3D] = []
var _next_splash := 0
var _drippers: Array[GPUParticles3D] = []
var _drip_tips := PackedInt32Array()
var _drip_material: ShaderMaterial
var _last_pos := Vector3.ZERO
var _active := true
var _built := false

static var _drop_material: ShaderMaterial


func _ready() -> void:
	process_priority = 20               # after CreatureWanderer has moved the ooze this frame
	creature = get_parent() as Creature
	if creature == null:
		push_warning("OozeFx: not under a Creature")
		return
	if not creature.is_node_ready():
		await creature.ready            # the Creature rolls its look in its own _ready, after ours
	look = creature.find_child("OozeLook", true, false) as OozeLook
	_skeleton = creature.find_child("Skeleton3D", true, false) as Skeleton3D
	if _skeleton != null:
		for i in _skeleton.get_bone_count():
			_bones[_skeleton.get_bone_name(i)] = i
	_build()
	creature.creature_event.connect(_on_event)


func _notification(what: int) -> void:
	if what == NOTIFICATION_PREDELETE and fx_root != null and is_instance_valid(fx_root):
		_stop_drips()
		if trail_node != null:
			trail_node.target = null
		if fx_root.is_inside_tree():    # let the trail and the last splash fade
			fx_root.get_tree().create_timer(12.0).timeout.connect(fx_root.queue_free)
		else:
			fx_root.queue_free()


## the ooze's size (its uniform scale; 1 = a normal ooze's)
func size() -> float:
	return creature.global_basis.get_scale().x if creature != null else 1.0


## Off: no trail laid, no drips (OozeSplit's dormant giant); on again: the trail starts afresh.
func set_active(on: bool) -> void:
	_active = on
	if not _built:
		return
	if trail_node != null:
		trail_node.emitting = false
		if on:
			trail_node.clear()
	if not on:
		_stop_drips()
	_last_pos = creature.global_position
	set_process(on)


## the effects' colour: between the preset's mid and thin (sRGB), at alpha a
func colour(a: float) -> Color:
	var c := look.colours() if look != null else OozeLook.preset_colours("Green")
	var col: Color = (c["mid"] as Color).lerp(c["thin"], 0.35)
	col.a = a
	return col


func _process(_delta: float) -> void:
	if not _built or not _active:
		return
	var k := size()
	var dt := get_process_delta_time()
	if trail_node != null:
		var p := creature.global_position
		var v := (p - _last_pos).length() / maxf(dt, 1e-4)
		trail_node.target = creature
		trail_node.emitting = v > 0.08 * k
		trail_node.step = 0.15 * k
		trail_node.radius = 0.8 * k
		trail_node.behind = 1.0 * k
		_last_pos = p
	var floor_y := creature.global_position.y
	if _drip_material != null:
		_drip_material.set_shader_parameter("floor_y", floor_y)
	for i in _drippers.size():                  # from under a raised tip only
		var at := _bone_position(_drip_tips[i]) + Vector3.DOWN * 0.17 * k
		_drippers[i].global_position = at
		_drippers[i].emitting = at.y - floor_y > 0.22 * k


# ------------------------------------------------------------------------------------------------- events
func _on_event(_c: Creature, ev: String) -> void:
	if not _built or not _active:
		return
	var k := size()
	var at := creature.global_position
	match ev:
		"Hit":
			splash(_lowest_tip(["Probe3", "Reach3"]), 16, 1.0)
		"Hurt":
			splash(at + Vector3.UP * 0.6 * k, 14, 0.9)
		"Grab":
			splash(_bone_position(_bones["Socket_Mouth"]) if _bones.has("Socket_Mouth") else at, 10, 0.7)
		"Engulf":
			splash(at + Vector3.UP * 0.9 * k, 14, 0.6)
		"Dead":
			splash(at + Vector3.UP * 0.25 * k, 40, 1.2)
		"Split":
			splash(at + Vector3.UP * 0.4 * k, 70, 1.5)
		"Risen":
			splash(at + Vector3.UP * 0.3 * k, 20, 0.8)
		"Spit":
			spit()


## whichever of the tips is lowest (Lash slams the Probe down, Grab swells Reach round its catch)
func _lowest_tip(tips: Array) -> Vector3:
	var best := Vector3.ZERO
	var found := false
	for n: String in tips:
		if _bones.has(n):
			var p := _bone_position(_bones[n])
			if not found or p.y < best.y:
				best = p
				found = true
	return best if found else creature.global_position


func _bone_position(b: int) -> Vector3:
	return _skeleton.global_transform * _skeleton.get_bone_global_pose(b).origin


## A burst of droplets at a world point (size 1 = a normal ooze's); floor_y: where they land (NAN = the ooze's floor).
func splash(at: Vector3, count: int, strength: float, floor_y: float = NAN) -> void:
	if _splashes.is_empty():
		return
	var k := size()
	var e := _splashes[_next_splash]
	_next_splash = (_next_splash + 1) % _splashes.size()
	var m := e.process_material as ShaderMaterial
	m.set_shader_parameter("strength", strength * sqrt(k))
	m.set_shader_parameter("spread", 0.12 * k)
	m.set_shader_parameter("size_range", Vector2(0.04, 0.13) * k)
	m.set_shader_parameter("floor_y", creature.global_position.y if is_nan(floor_y) else floor_y)
	m.set_shader_parameter("colour", colour(0.8))
	e.global_position = at
	e.amount_ratio = clampf(float(count) / SPLASH_MAX, 0.0, 1.0)
	e.restart()


## The acid glob, from the spitting pod's tip to the target (and a spray at the mouth).
func spit() -> OozeGlob:
	var k := size()
	var from := _bone_position(_bones["Socket_Spit"]) if _bones.has("Socket_Spit") else creature.global_position + Vector3.UP * 1.4 * k
	var to := spit_target.global_position if spit_target != null else creature.global_position + creature.global_basis.z.normalized() * 5.0 * k
	splash(from, 8, 0.6)
	var g := OozeGlob.new()
	g.name = creature.name + "_Glob"
	var holder := fx_root.get_parent() if fx_root != null and fx_root.get_parent() != null else creature.get_parent()
	holder.add_child(g)
	g.launch(self, from, to, 0.16 * k, look.colours() if look != null else OozeLook.preset_colours("Green"))
	spat.emit(g)
	return g


# ------------------------------------------------------------------------------------------------- building
func _build() -> void:
	fx_root = Node3D.new()
	fx_root.name = creature.name + "_Fx"
	creature.get_parent().add_child.call_deferred(fx_root)
	await fx_root.tree_entered
	if not is_instance_valid(creature):
		return
	var k := size()
	if trail:
		trail_node = OozeTrail.new()
		trail_node.name = "Trail"
		trail_node.cell = 0.1 * k                   # fixed from here: the field is laid out in it
		trail_node.life = 9.0
		trail_node.step = 0.15 * k
		trail_node.radius = 0.8 * k
		trail_node.behind = 1.0 * k
		fx_root.add_child(trail_node)
		trail_node.init(_slime_colour())
		trail_node.target = creature
	for i in SPLASHES:
		_splashes.append(_splash_emitter())
	if drips:
		_drip_material = _drops_material(0)
		_drip_material.set_shader_parameter("size_range", Vector2(0.03, 0.065) * k)
		_drip_material.set_shader_parameter("spread", 0.07 * k)
		_drip_material.set_shader_parameter("life_range", Vector2(1.6, 1.6))
		_drip_material.set_shader_parameter("gravity", 9.8 * 1.1)
		_drip_material.set_shader_parameter("alpha_range", Vector2(0.8, 0.8))
		for tip in ["Reach3", "Side3", "Probe3"]:
			if _bones.has(tip):
				var e := _emitter("Drips_" + tip, _drip_material, maxi(1, roundi(drip_rate * 1.6)), 1.6)
				e.randomness = 0.4
				e.emitting = false
				_drippers.append(e)
				_drip_tips.append(_bones[tip])
	_last_pos = creature.global_position
	_built = true
	if look != null:
		look.preset_changed.connect(func(_p: String) -> void: _recolour())
	if not _active:
		set_active(false)


## the trail's slime: the effects' colour, a quarter darker
func _slime_colour() -> Color:
	var slime := colour(1.0).lerp(Color.BLACK, 0.25)
	slime.a = 1.0
	return slime


## the ooze's preset changed after the effects were built (a reroll, OozeLook.apply on an ooze in the tree)
func _recolour() -> void:
	if trail_node != null:
		trail_node.set_colour(_slime_colour())
	if _drip_material != null:
		_drip_material.set_shader_parameter("colour", colour(0.8))


func _splash_emitter() -> GPUParticles3D:
	var m := _drops_material(1)
	m.set_shader_parameter("life_range", Vector2(0.7, 1.3))
	m.set_shader_parameter("speed_range", Vector2(1.4, 3.4))
	m.set_shader_parameter("alpha_range", Vector2(0.6, 0.9))
	m.set_shader_parameter("gravity", 9.8 * 1.6)
	var e := _emitter("Splash", m, SPLASH_MAX, 1.3)
	e.one_shot = true
	e.explosiveness = 1.0
	e.emitting = false
	return e


## a droplet process material of a kind (ooze_drops.gdshader: 0 drip, 1 splash, 2 fizz) in the ooze's colour
func _drops_material(kind: int) -> ShaderMaterial:
	var m := ShaderMaterial.new()
	m.shader = DROPS
	m.set_shader_parameter("kind", kind)
	m.set_shader_parameter("colour", colour(0.8))
	return m


## A world-space droplet emitter on the effects root, drawn with the drop material.
func _emitter(emitter_name: String, process: ShaderMaterial, amount: int, lifetime: float) -> GPUParticles3D:
	var e := make_emitter(process, amount, lifetime)
	e.name = emitter_name
	fx_root.add_child(e)
	return e


## A world-space droplet emitter (not yet in the tree): quads drawn with ooze_drop.gdshader, no shadows.
static func make_emitter(process: ShaderMaterial, amount: int, lifetime: float) -> GPUParticles3D:
	if _drop_material == null:
		_drop_material = ShaderMaterial.new()
		_drop_material.shader = DROP
	var e := GPUParticles3D.new()
	e.local_coords = false
	e.amount = amount
	e.lifetime = lifetime
	e.process_material = process
	var quad := QuadMesh.new()
	quad.material = _drop_material
	e.draw_pass_1 = quad
	e.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	e.visibility_aabb = AABB(Vector3(-3, -4, -3), Vector3(6, 7, 6))
	return e


func _stop_drips() -> void:
	for e in _drippers:
		if is_instance_valid(e):
			e.emitting = false

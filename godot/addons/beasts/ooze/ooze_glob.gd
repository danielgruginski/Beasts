class_name OozeGlob
extends Node3D
## The ooze's acid glob (OozeFx.spit): a blob of the jelly (its preset's colours on a flat mask) on a ballistic arc,
## stretched along its flight and wobbling; where it lands it splashes and becomes a puddle that fizzes (small rising
## bubbles) and fades. The game can hook `landed` (or read global_position) for the damage. Unity: OozeGlob.

signal landed(glob: OozeGlob)

@export var flight_time := 0.7
@export var puddle_time := 7.0

const PUDDLE := preload("res://addons/beasts/ooze/ooze_puddle.gdshader")
const DROPS := preload("res://addons/beasts/ooze/ooze_drops.gdshader")

var _owner_fx: OozeFx
var _velocity := Vector3.ZERO
var _target := Vector3.ZERO
var _radius := 0.16
var _t := 0.0
var _landed := false
var _colours := {}
var _blob: MeshInstance3D
var _puddle: MeshInstance3D
var _fizz: GPUParticles3D
var _gravity := Vector3.DOWN * 9.8

static var _puddle_material: ShaderMaterial


## Flies from `start` to `to` (world points) in flight_time; r: its radius (m); colours: OozeLook.colours().
func launch(from: OozeFx, start: Vector3, to: Vector3, r: float, colours: Dictionary) -> void:
	_owner_fx = from
	_target = to
	_radius = r
	_colours = colours
	top_level = true
	global_position = start
	_gravity = ProjectSettings.get_setting("physics/3d/default_gravity", 9.8) * \
			ProjectSettings.get_setting("physics/3d/default_gravity_vector", Vector3.DOWN)
	var tt := maxf(flight_time, 0.2)
	_velocity = (to - start) / tt - 0.5 * _gravity * tt
	_blob = MeshInstance3D.new()
	_blob.name = "Blob"
	var sphere := SphereMesh.new()
	sphere.radius = 0.5
	sphere.height = 1.0
	sphere.radial_segments = 14
	sphere.rings = 10
	_blob.mesh = sphere
	_blob.material_override = OozeLook.glob_material(colours.get("name", "Green"))
	_blob.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(_blob)
	_shape()


func _process(delta: float) -> void:
	_t += delta
	if not _landed:
		_velocity += _gravity * delta
		var next := global_position + _velocity * delta
		if next.y <= _target.y + _radius * 0.4 and _velocity.y < 0.0:
			_land(Vector3(next.x, _target.y, next.z))
			return
		global_position = next
		_shape()
		if _t > 4.0:
			queue_free()
		return
	var fade := clampf((_t - puddle_time * 0.55) / (puddle_time * 0.45), 0.0, 1.0)
	if _puddle != null:
		var c: Color = (_colours["mid"] as Color).lerp(_colours["thin"], 0.3).srgb_to_linear()
		c.a = 0.75 * (1.0 - fade)
		_puddle.set_instance_shader_parameter("tint", c)
		var g := smoothstep(0.0, 1.0, clampf(_t / 0.25, 0.0, 1.0))
		_puddle.scale = Vector3.ONE * _radius * 9.0 * (0.5 + 0.5 * g)
	if _fizz != null:
		_fizz.amount_ratio = 1.0 - fade
	if _t > puddle_time:
		queue_free()


## stretched along its flight, wobbling
func _shape() -> void:
	var dir := _velocity.normalized()
	var w := 1.0 + 0.12 * sin(_t * 31.0)
	var up := Vector3.UP if absf(dir.y) < 0.99 else Vector3.RIGHT
	var b := Basis.looking_at(dir, up, true)
	_blob.basis = b.scaled_local(Vector3(_radius * 2.0 / w, _radius * 2.0 / w, _radius * 2.6 * w))


func _land(at: Vector3) -> void:
	_landed = true
	_t = 0.0
	global_position = at
	_blob.visible = false
	if _owner_fx != null and is_instance_valid(_owner_fx):
		_owner_fx.splash(at + Vector3.UP * _radius, 18, 0.7, at.y)
	if _puddle_material == null:
		_puddle_material = ShaderMaterial.new()
		_puddle_material.shader = PUDDLE
		_puddle_material.render_priority = -2      # on the floor, under the jelly
	_puddle = MeshInstance3D.new()
	_puddle.name = "AcidPuddle"
	var plane := PlaneMesh.new()
	plane.size = Vector2.ONE
	_puddle.mesh = plane
	_puddle.material_override = _puddle_material
	_puddle.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_puddle.position = Vector3.UP * 0.01
	_puddle.rotation.y = randf() * TAU
	_puddle.scale = Vector3.ONE * _radius * 4.5
	add_child(_puddle)
	_fizz = _build_fizz(at.y)
	landed.emit(self)


## bubbles rising off the acid
func _build_fizz(floor_y: float) -> GPUParticles3D:
	var m := ShaderMaterial.new()
	m.shader = DROPS
	m.set_shader_parameter("kind", 2)
	var c: Color = (_colours["thin"] as Color).lerp(Color.WHITE, 0.4)
	m.set_shader_parameter("colour", c)
	m.set_shader_parameter("alpha_range", Vector2(0.7, 0.7))
	m.set_shader_parameter("size_range", Vector2(0.15, 0.35) * _radius)
	m.set_shader_parameter("life_range", Vector2(0.4, 0.9))
	m.set_shader_parameter("speed_range", Vector2(0.15, 0.4))
	m.set_shader_parameter("spread", _radius * 3.2)
	m.set_shader_parameter("gravity", -0.05 * 9.8)
	m.set_shader_parameter("floor_y", floor_y)
	var e := OozeFx.make_emitter(m, 13, 0.9)
	e.name = "Fizz"
	add_child(e)
	return e

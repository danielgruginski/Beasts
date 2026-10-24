class_name OozeTrail
extends MeshInstance3D
## The ooze's slime trail, as splats that know about each other: the ooze paints them into a wetness field (a small
## float texture tied to the world, wrapping round, `cell` metres a texel) as it goes, and one flat sheet round it
## (this node; ooze_slick.gdshader) shows slime wherever the field passes an edge threshold. So splats close together
## merge into one wet patch with smooth necks (no alpha piling up where they overlap); a new splat wells out from its
## middle over `grow` seconds, and as the field dries the edges creep in and the patch breaks into puddles before it
## goes (`life`). The splats land at the ooze's rear edge (`behind`), so none appear under its see-through body. It lives
## beside the ooze (on its effects root), so it dries out after the ooze is gone. OozeFx drives it (target, emitting,
## sizes). Unity: OozeTrail.
## The drying is the shader's: a texel holds when it was wet (log-wetness on the trail's clock), so a splat is the only
## work here and the field is uploaded only when one lands (Unity dried the whole field on the CPU every frame).

## what lays the trail (the ooze); null = stop laying, let it dry
var target: Node3D
var emitting := false
## metres between splats
var step := 0.15
## a splat's radius (m)
var radius := 0.8
## how far behind the target's centre the splats land (m): its rear edge
var behind := 1.0
## seconds until fresh slime has dried away
var life := 9.0
## seconds a new splat takes to spread to its full size (it wells out from its middle instead of appearing whole)
var grow := 1.0
## metres per field texel (fixed by init(): the field is laid out in it); the field covers resolution x cell metres
var cell := 0.1
## field texels a side (a power of two)
var resolution := 128
var lift := 0.012

const SLICK := preload("res://addons/beasts/ooze/ooze_slick.gdshader")
const FRESH := 1.15                 # a splat's centre
const EDGE := 0.30                  # the slime's edge (ooze_slick edge.x)
const DRY := -1.0e6                 # log-wetness of a dry texel

var _field := PackedFloat32Array()  # RGBA per texel: settled log-wetness, newest splat's, its birth, unused (DRY)
var _image: Image
var _texture: ImageTexture
var _material: ShaderMaterial
var _now := 0.0
var _tau := 1.0
var _last_splat := Vector3.ZERO
var _has_last := false
var _last_wet := -1.0e9
var _dirty := false
var _rng := RandomNumberGenerator.new()


## Sets up the field, the sheet and its material in `colour` (sRGB). Call once, after setting cell and resolution.
func init(colour: Color) -> void:
	top_level = true
	process_priority = 30               # after OozeFx has set this frame's target, emitting and sizes
	_rng.randomize()
	_field.resize(resolution * resolution * 4)
	clear()
	_image = Image.create_from_data(resolution, resolution, false, Image.FORMAT_RGBAF, _field.to_byte_array())
	_texture = ImageTexture.create_from_image(_image)
	_material = ShaderMaterial.new()
	_material.shader = SLICK
	_material.render_priority = -2     # under the jelly, which blends over it
	_material.set_shader_parameter("field", _texture)
	_material.set_shader_parameter("field_size", resolution)
	_material.set_shader_parameter("cell", cell)
	_material.set_shader_parameter("grow", grow)
	_material.set_shader_parameter("color", colour)
	var sheet := PlaneMesh.new()
	sheet.size = Vector2.ONE * resolution * cell * 0.96
	mesh = sheet
	material_override = _material
	cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	visible = false


## the slime's colour (sRGB)
func set_colour(colour: Color) -> void:
	if _material != null:
		_material.set_shader_parameter("color", colour)


## dries it at once and forgets where the last splat was
func clear() -> void:
	_field.fill(DRY)
	_has_last = false
	_last_wet = -1.0e9
	_dirty = true
	visible = false


func _process(delta: float) -> void:
	step_trail(delta)


## One update `dt` seconds on: lay splats behind the target, move the sheet with it, upload what changed. _process calls
## it; a test can drive it with its own clock.
func step_trail(dt: float) -> void:
	if _material == null:
		return
	_now += clampf(dt, 0.0, 0.25)
	_tau = life / log(FRESH / EDGE)     # fresh slime reaches the edge value after `life`
	if target != null and is_instance_valid(target):
		var fwd := target.global_basis.z            # the creatures' front is +Z
		fwd.y = 0.0
		fwd = fwd.normalized() if fwd.length_squared() > 1e-6 else Vector3.BACK
		var rear := target.global_position - fwd * behind
		if emitting:
			var d := rear.distance_to(_last_splat) if _has_last else 0.0
			if not _has_last or d > 8.0 * step:     # the first, or after a teleport
				_splat(rear)
				_last_splat = rear
			elif d >= step:
				var n := floori(d / step)
				for k in range(1, n + 1):
					_splat(_last_splat.lerp(rear, k * step / d))
				_last_splat = _last_splat.lerp(rear, n * step / d)
			_has_last = true
		else:
			_last_splat = rear                      # resume from where it is, not with a line
			_has_last = true
		var c := target.global_position            # the sheet: round the ooze, on texel steps
		global_transform = Transform3D(Basis.IDENTITY, Vector3(roundf(c.x / cell) * cell, c.y + lift, roundf(c.z / cell) * cell))
	visible = _now - _last_wet < grow + life * 1.3
	if not visible:
		return
	if _dirty:
		_image.set_data(resolution, resolution, false, Image.FORMAT_RGBAF, _field.to_byte_array())
		_texture.update(_image)
		_dirty = false
	_material.set_shader_parameter("now", _now)
	_material.set_shader_parameter("tau", _tau)


## A new splat at a world point: a soft round blob with a ragged outline, a little off the path, a little wetter or
## drier than the last (so it dries into puddles). It is stamped once, with its birth: the shader wells it out.
func _splat(at: Vector3) -> void:
	at += Vector3(_rng.randf_range(-1, 1), 0, _rng.randf_range(-1, 1)) * 0.12 * radius
	var cx := at.x / cell - 0.5                    # in texels (their centres sit at +0.5)
	var cz := at.z / cell - 0.5
	var r := radius * _rng.randf_range(0.8, 1.15) / cell
	var p1 := _rng.randf_range(0, TAU)
	var p2 := _rng.randf_range(0, TAU)
	var a1 := _rng.randf_range(0.06, 0.14)
	var a2 := _rng.randf_range(0.04, 0.09)
	var amp := FRESH * _rng.randf_range(0.82, 1.1)
	var k := (_now + grow) / _tau                   # it starts drying once it has spread (Unity restamped it till then)
	var n := resolution
	var reach := r * 1.25
	for z in range(floori(cz - reach), ceili(cz + reach) + 1):
		for x in range(floori(cx - reach), ceili(cx + reach) + 1):
			var dx := x - cx
			var dz := z - cz
			var dd := sqrt(dx * dx + dz * dz)
			if dd >= reach:
				continue
			var th := atan2(dz, dx)
			var rr := r * (1.0 + a1 * sin(3.0 * th + p1) + a2 * sin(5.0 * th + p2))
			if dd >= rr:
				continue
			var q := 1.0 - (dd / rr) * (dd / rr)
			var v := amp * q * q
			if v < 0.02:
				continue
			var i := (posmod(z, n) * n + posmod(x, n)) * 4
			var nl := log(v) + k
			var old := _field[i]
			if nl <= old:
				continue                            # already wetter here than this splat will be
			var prev := _field[i + 1]
			if prev > DRY and _now - _field[i + 2] < grow:
				_field[i + 1] = maxf(prev, nl)      # the one before it still spreading: this one spreads with it
				continue
			if prev > DRY:                          # the one before it has spread: it settles, this one wells out
				_field[i] = maxf(old, prev)
			_field[i + 1] = nl
			_field[i + 2] = _now
	_last_wet = _now
	_dirty = true
	visible = true

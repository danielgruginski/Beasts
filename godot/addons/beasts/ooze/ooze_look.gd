class_name OozeLook
extends SkeletonModifier3D
## An ooze's look (a child of its Skeleton3D, so it runs after the AnimationPlayer has posed the bones). The colour and
## size are rolled by the Creature root like any creature's skin: one jelly material per colour preset (PRESETS; its
## resource_name is the preset's name), built by ooze_setup.gd with make_jelly(). This node adds what the ooze has of its
## own:
##   the remains inside (Skull, Femur, ... and the vacuoles: REMAINS): hidden ones are scaled to nothing, and in a big
##   ooze the rest keep their real size (a giant's skull would read as a giant's);
##   the body's shadow: a transparent surface casts none in Godot, so OozeBody has a shadow-only twin (OozeShadow, same
##   mesh, skin and skeleton; ooze_jelly_shadow.gdshader) dithered by the preset's opacity.
## apply() sets a look on a fresh instance before it enters the tree (OozeSplit does, for the two halves of a split).
## Unity: OozeLook (a MaterialPropertyBlock per renderer there, a material per preset here).

## the preset showing changed (the Creature's roll, a reroll, apply()): OozeFx recolours its effects
signal preset_changed(preset_name: String)

## colour presets: same as ooze_paint.PRESETS in Blender (thin, mid, core, crevice: sRGB hex; opacity scales the masks')
const PRESETS := {
	"Green": {"thin": "#a6d455", "mid": "#4f8c1c", "core": "#2c5a12", "crevice": "#173208", "opacity": 1.0},
	"Grey": {"thin": "#c4c8bf", "mid": "#868c84", "core": "#4c524c", "crevice": "#22261f", "opacity": 1.0},
	"Black": {"thin": "#5c4e62", "mid": "#2a2231", "core": "#130f17", "crevice": "#060408", "opacity": 1.45},
	"Ochre": {"thin": "#f2d173", "mid": "#c88f2e", "core": "#7e4f19", "crevice": "#3a2208", "opacity": 1.0},
	"Crimson": {"thin": "#e58272", "mid": "#a42c26", "core": "#5a0f11", "crevice": "#260405", "opacity": 1.1},
}
## content bones (the remains and the vacuoles) as the model names them
const REMAINS: PackedStringArray = ["Skull", "Femur", "Shin", "Helm", "Sword", "Coins", "Vac1", "Vac2", "Vac3", "Vac4", "Vac5", "Vac6", "Vac7"]
const JELLY_FAR := preload("res://addons/beasts/ooze/ooze_jelly_far.gdshader")
const JELLY_NEAR := preload("res://addons/beasts/ooze/ooze_jelly_near.gdshader")

## content bones not shown (a small ooze has only eaten rats; the half of a split that went the other way)
@export var hidden := PackedStringArray()
## remains keep their real size when the ooze is bigger than 1 (they scale down with smaller ones)
@export var life_size_remains := true
## the jelly material of every preset, for apply() (the Creature's skins may hold only some of them)
@export var materials: Array[Material] = []
## the shadow-only twin of OozeBody (its mesh and skin are copied from the body when the ooze enters the tree)
@export var shadow_twin: NodePath = ^"../OozeShadow"
@export var body: NodePath = ^"../OozeBody"

## the preset showing, e.g. "Green" (from the body's material)
var preset := ""

var _bones := PackedInt32Array()
var _hide: Array[bool] = []
var _material: Material
var _twin: MeshInstance3D
var _body: MeshInstance3D

static var _flat_masks: ImageTexture
static var _glob_materials := {}


func _ready() -> void:
	_body = get_node_or_null(body) as MeshInstance3D
	_twin = get_node_or_null(shadow_twin) as MeshInstance3D
	if _twin != null and _body != null:
		_twin.mesh = _body.mesh
		_twin.skin = _body.skin
		_twin.skeleton = _twin.get_path_to(get_skeleton()) if get_skeleton() != null else _body.skeleton
		_twin.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_SHADOWS_ONLY
		_body.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF   # the twin casts it
	_find_bones()


## Sets the colour preset, the size (uniform scale of the creature) and the hidden content bones. Before the ooze
## enters the tree it only steers the Creature's roll (its skins and scale range); in the tree it re-rolls at once.
func apply(preset_name: String, size: float, hidden_bones: PackedStringArray) -> void:
	hidden = hidden_bones
	var c := _creature()
	var m := material_for(preset_name)
	if c != null:
		if m != null:
			var only: Array[Material] = [m]
			c.skins = only
		c.scale_range = Vector2(size, size)
		if c.is_inside_tree():
			c.reroll()
	if is_inside_tree():
		_find_bones()


## the jelly material of a preset (from `materials`, else the Creature's skins); null if there is none
func material_for(preset_name: String) -> Material:
	for list: Array[Material] in [materials, _creature().skins if _creature() != null else materials]:
		for m in list:
			if m != null and m.resource_name == preset_name:
				return m
	return null


## the preset's colours as Colors (sRGB): thin, mid, core, crevice, and its opacity
func colours() -> Dictionary:
	return preset_colours(preset if preset != "" else _current_preset())


static func preset_colours(preset_name: String) -> Dictionary:
	var p: Dictionary = PRESETS.get(preset_name, PRESETS["Green"])
	return {"thin": Color.html(p["thin"]), "mid": Color.html(p["mid"]), "core": Color.html(p["core"]),
			"crevice": Color.html(p["crevice"]), "opacity": float(p["opacity"]), "name": preset_name}


## A jelly material for a preset: the far side (render_priority -1) with the near side (0) as its next_pass, both on
## `masks` (T_Ooze, linear) in the preset's colours. ooze_setup.gd saves one per preset; OozeGlob uses one on flat masks.
static func make_jelly(preset_name: String, masks: Texture2D) -> ShaderMaterial:
	var c := preset_colours(preset_name)
	var far := ShaderMaterial.new()
	far.shader = JELLY_FAR
	far.render_priority = -1
	var near := ShaderMaterial.new()
	near.shader = JELLY_NEAR
	near.render_priority = 0
	for m: ShaderMaterial in [far, near]:
		m.resource_name = preset_name
		m.set_shader_parameter("masks", masks)
		m.set_shader_parameter("thin_color", c["thin"])
		m.set_shader_parameter("mid_color", c["mid"])
		m.set_shader_parameter("core_color", c["core"])
		m.set_shader_parameter("crevice_color", c["crevice"])
		m.set_shader_parameter("opacity", c["opacity"])
	far.next_pass = near
	return far


## The acid glob's jelly (Unity: M_OozeGlob): the preset's colours on a flat mask (T_OozeFlat: tone 0.55, no creases,
## detail 0.5, opacity 0.42), one per preset, made the first time it is needed.
static func glob_material(preset_name: String) -> ShaderMaterial:
	if _glob_materials.has(preset_name):
		return _glob_materials[preset_name]
	if _flat_masks == null:
		var img := Image.create(4, 4, false, Image.FORMAT_RGBA8)
		img.fill(Color(0.55, 1.0, 0.5, 0.42))
		_flat_masks = ImageTexture.create_from_image(img)
	var m := make_jelly(preset_name, _flat_masks)
	_glob_materials[preset_name] = m
	return m


## After the AnimationPlayer (Skeleton3D runs its modifiers then, and puts the animated pose back after skinning, so
## nothing here builds up frame to frame): hidden pieces to nothing; in a big ooze the rest back to their real size.
func _process_modification_with_delta(_delta: float) -> void:
	_sync_preset()
	var sk := get_skeleton()
	if sk == null:
		return
	var k := sk.global_basis.get_scale().x
	var rk := 1.0 / k if life_size_remains and k > 1.0 else 1.0
	for i in _bones.size():
		var b := _bones[i]
		if _hide[i]:
			sk.set_bone_pose_scale(b, Vector3.ZERO)
		elif rk != 1.0:
			sk.set_bone_pose_scale(b, sk.get_bone_pose_scale(b) * rk)


## follows the body's material (the Creature's roll, a reroll, apply()): the preset's name and the twin's opacity
func _sync_preset() -> void:
	if _body == null:
		return
	var m := _body.get_surface_override_material(0)
	if m == _material:
		return
	_material = m
	preset = _current_preset()
	if _twin != null:
		_twin.set_instance_shader_parameter("opacity", float(PRESETS.get(preset, PRESETS["Green"])["opacity"]))
	preset_changed.emit(preset)


func _current_preset() -> String:
	var m := _body.get_surface_override_material(0) if _body != null else null
	if m != null and PRESETS.has(m.resource_name):
		return m.resource_name
	return "Green"


func _find_bones() -> void:
	_bones.clear()
	_hide.clear()
	var sk := get_skeleton()
	if sk == null:
		return
	for n in REMAINS:
		var b := sk.find_bone(n)
		if b >= 0:
			_bones.append(b)
			_hide.append(hidden.has(n))


func _creature() -> Creature:
	var n := get_parent()
	while n != null and not (n is Creature):
		n = n.get_parent()
	return n as Creature

@tool
class_name Creature
extends Node3D
## A creature of the pack (the root of each creature scene). The scene only references its model (the .glb instance
## "Model", nothing in it changed or saved), and this node dresses it: when it enters the game it rolls a look, a skin
## from `skins` on surface `surface` of `target` (list one twice to make it twice as likely) and a size in
## `scale_range`; a second mesh can follow the roll (paired_target takes paired_skins[i] whenever target takes skins[i]:
## a dragon's wings match its hide). `materials`, `shown` and `hidden` set the rest of the model's look (a second
## surface's coat, extra meshes, a variant's tack). Set look_seed for a fixed look, call reroll() for another. It raises
## creature_event as a clip passes one of its events (Bite, Howl, Dead...: hook damage and sound there). In the editor
## it shows the first skin at size 1. Unity: BeastAppearance + BeastEvents.

signal creature_event(creature: Creature, event_name: String)

@export var skins: Array[Material] = []
@export var target: NodePath
@export var surface := 0
@export var paired_target: NodePath
@export var paired_skins: Array[Material] = []
@export var scale_range := Vector2(0.85, 1.2)
## 0 = a new look each time
@export var look_seed := 0
## its clip pools (CreatureWanderer plays them; a game can read them too)
@export var animation_set: CreatureAnimationSet
## other materials, by "<mesh path from here>:<surface>": a second surface's coat (the wasp's wings), extra meshes'
## own (the warg's tack, the ooze's remains)
@export var materials: Dictionary[String, Material] = {}
## meshes shown / hidden over the model's own visibility (a variant: the saddled warg, the tacked mammoth)
@export var shown: Array[NodePath] = []
@export var hidden: Array[NodePath] = []
## nodes of this scene moved under the model's Skeleton3D when it enters the game (the ooze's OozeLook, a
## SkeletonModifier3D, must be the skeleton's child; a scene saves nothing inside its .glb instance)
@export var skeleton_children: Array[NodePath] = []

## the skin and size rolled, e.g. "Black x1.04"
var summary := ""
var player: AnimationPlayer

var _clip := ""
var _pos := 0.0
var _placed := false


func _enter_tree() -> void:
	if Engine.is_editor_hint() or _placed:
		return
	_placed = true
	var skel := find_child("Skeleton3D", true, false) as Skeleton3D
	if skel == null:
		return
	for p in skeleton_children:
		var n := get_node_or_null(p)
		if n != null:
			n.reparent(skel, false)


func _ready() -> void:
	player = find_child("AnimationPlayer", true, false) as AnimationPlayer
	_dress()
	if Engine.is_editor_hint():
		set_process(false)
		_show_skin(0)
		return
	_roll(look_seed if look_seed != 0 else randi())


func reroll() -> void:
	_roll(randi())


func _dress() -> void:
	for key: String in materials:
		var at := key.rfind(":")
		var mi := get_node_or_null(key.left(at)) as MeshInstance3D
		if mi != null:
			mi.set_surface_override_material(int(key.substr(at + 1)), materials[key])
	for p in shown:
		var n := get_node_or_null(p) as Node3D
		if n != null:
			n.visible = true
	for p in hidden:
		var n := get_node_or_null(p) as Node3D
		if n != null:
			n.visible = false


func _roll(s: int) -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = s
	var skin := ""
	if not skins.is_empty():
		var i := rng.randi_range(0, skins.size() - 1)
		skin = _show_skin(i)
	var k := lerpf(scale_range.x, scale_range.y, rng.randf())
	scale = Vector3.ONE * k
	summary = "%s x%.2f" % [skin, k]


## skins[i] on the target (and paired_skins[i] on the paired mesh); its name
func _show_skin(i: int) -> String:
	var mesh := _mesh(target)
	if mesh == null or i >= skins.size() or skins[i] == null:
		return ""
	mesh.set_surface_override_material(surface, skins[i])
	var pm := _mesh(paired_target) if not paired_target.is_empty() else null
	if pm != null and i < paired_skins.size() and paired_skins[i] != null:
		pm.set_surface_override_material(0, paired_skins[i])
	return skins[i].resource_name


func _mesh(path: NodePath) -> MeshInstance3D:
	if path.is_empty():
		return _first_mesh(self)
	return get_node_or_null(path) as MeshInstance3D


func _first_mesh(n: Node) -> MeshInstance3D:
	for c in n.get_children():
		if c is MeshInstance3D:
			return c
		var f := _first_mesh(c)
		if f != null:
			return f
	return null


func _process(_delta: float) -> void:
	# the events the current clip passed since the last frame (once round a loop's end too)
	if player == null:
		return
	var a := String(player.current_animation)
	if a == "":
		_clip = ""
		return
	var pos := player.current_animation_position
	if a != _clip:
		_clip = a
		_pos = -1.0
	var evs: Array = player.get_animation(a).get_meta("events", [])
	for e: Dictionary in evs:
		var t: float = e["time"]
		if (_pos < t and t <= pos) or (pos < _pos and (t > _pos or t <= pos)):
			creature_event.emit(self, e["name"])
	_pos = pos

class_name OozeSplit
extends Node
## A big ooze dividing in two (a child of the giant's Creature root). On the Split clip's event (the strand snapping,
## with OozeFx's splash) it spawns two child_scene oozes where its halves are (the HalfL / HalfR bones), each
## child_scale times its own size (half the volume), in its colour, each keeping the remains on its side and starting
## on child_pool (Reform: a blob taking shape), with a CreatureWanderer like its own if it has one. Then it is gone:
## split_into hands the two to the game first. With respawn_after (test scenes) it only goes dormant (hidden, not
## animated) and comes back after a while, rising from a puddle near home, clearing its halves. Unity: OozeSplit.

signal split_into(split: OozeSplit, left: Creature, right: Creature)

## the ooze each half becomes
@export_file("*.tscn") var child_scene := "res://beasts/Ooze/Ooze.tscn"
@export var child_scale := 0.79
@export var child_pool := "Reform"
## content bones that go with the left half (the rest go right); set by ooze_setup.gd from the model
@export var left_remains := PackedStringArray()
@export var right_remains := PackedStringArray()
## test scenes: come back after this many seconds (0 = freed on splitting)
@export var respawn_after := 0.0

var dormant := false
var creature: Creature

var _children: Array[Node] = []
var _back_at := 0.0
var _skeleton: Skeleton3D


func _ready() -> void:
	creature = get_parent() as Creature
	if creature == null:
		return
	_skeleton = creature.find_child("Skeleton3D", true, false) as Skeleton3D
	creature.creature_event.connect(func(_c: Creature, ev: String) -> void:
		if ev == "Split" and not dormant:
			split())
	set_process(false)


func split() -> void:
	var scene := load(child_scene) as PackedScene if child_scene != "" else null
	if scene == null or creature == null:
		return
	var parent := creature.get_parent()
	var look := creature.find_child("OozeLook", true, false) as OozeLook
	var preset := look.preset if look != null and look.preset != "" else "Green"
	var size := creature.scale.x * child_scale
	var wanderer := _wanderer(creature)
	var made: Array[Creature] = []
	for i in 2:
		var bone := _skeleton.find_bone("HalfL" if i == 0 else "HalfR") if _skeleton != null else -1
		var at := creature.global_position
		if bone >= 0:
			at = _skeleton.global_transform * _skeleton.get_bone_global_pose(bone).origin
		at.y = creature.global_position.y
		var away := at - creature.global_position              # facing a little outward
		var turn := deg_to_rad(25.0) * (1.0 if away.dot(creature.global_basis.x) > 0.0 else -1.0)
		var xf := Transform3D(creature.global_basis.rotated(Vector3.UP, turn).orthonormalized(), at)
		var c := scene.instantiate() as Creature
		c.name = "%s_%s" % [creature.name, "L" if i == 0 else "R"]
		var cl := c.find_child("OozeLook", true, false) as OozeLook
		if cl != null:
			cl.apply(preset, size, right_remains if i == 0 else left_remains)  # hide the other side's
		else:
			c.scale_range = Vector2(size, size)
		c.transform = (parent as Node3D).global_transform.affine_inverse() * xf if parent is Node3D else xf
		var cw: CreatureWanderer = null
		if wanderer != null:
			cw = CreatureWanderer.new()
			cw.home = wanderer.home
			cw.wander_radius = wanderer.wander_radius
			cw.separation = wanderer.separation
			cw.label_height = wanderer.label_height * child_scale
			c.add_child(cw)
		parent.add_child(c)
		if cw != null:
			cw.play_pool(child_pool)
		elif c.player != null and c.player.has_animation(child_pool):
			c.player.play(child_pool)
		_children.append(c)
		made.append(c)
	split_into.emit(self, made[0], made[1])
	if respawn_after <= 0.0:
		creature.queue_free()
		return
	dormant = true
	_back_at = Time.get_ticks_msec() / 1000.0 + respawn_after
	_show(false)
	set_process(true)


func _process(_delta: float) -> void:
	if not dormant or Time.get_ticks_msec() / 1000.0 < _back_at:
		return
	for c in _children:
		if is_instance_valid(c):
			c.queue_free()
	_children.clear()
	var w := _wanderer(creature)
	if w != null:
		creature.global_position = w.home + Vector3(randf_range(-3, 3), 0, randf_range(-3, 3))
	dormant = false
	_show(true)
	set_process(false)
	if w != null:
		w.play_pool("Rise")


## Hidden and not animated, or back (the others carry on).
func _show(on: bool) -> void:
	var model := creature.find_child("Model", false, false) as Node3D
	if model != null:
		model.visible = on
	if creature.player != null:
		creature.player.active = on
	var w := _wanderer(creature)
	if w != null:                       # (and out of the others' way while it is gone)
		w.process_mode = Node.PROCESS_MODE_INHERIT if on else Node.PROCESS_MODE_DISABLED
		if on and not CreatureWanderer.all.has(w):
			CreatureWanderer.all.append(w)
		elif not on:
			CreatureWanderer.all.erase(w)
	var fx := creature.find_child("OozeFx", false, false) as OozeFx
	if fx != null:
		fx.set_active(on)


static func _wanderer(c: Node) -> CreatureWanderer:
	for n in c.get_children():
		if n is CreatureWanderer:
			return n
	return null

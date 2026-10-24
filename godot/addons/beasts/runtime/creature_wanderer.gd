class_name CreatureWanderer
extends Node
## Plays random clips from a CreatureAnimationSet (its own, else the creature's) on its creature (the parent), for
## looking at the animation: pools
## that move carry the creature by their root motion; it meanders, turns back toward `home` when it strays past
## wander_radius, and keeps `separation` from the others. Pools marked vertical may lift it (flight); any other pool
## settles it back onto the height it took off from. A game would drive the clips from its own state instead. Unity:
## BeastRandomAnimator.

@export var animation_set: CreatureAnimationSet
@export var crossfade := 0.2
@export var home := Vector3.ZERO
@export var wander_radius := 12.0
## metres kept from the others, before the creature's scale
@export var separation := 2.6
@export var speed_range := Vector2(0.94, 1.06)
## label height above the root, for viewers
@export var label_height := 1.4

static var all: Array[CreatureWanderer] = []

var current_clip := ""
var pool: CreaturePool
var body: Node3D
var player: AnimationPlayer

var _step := 0
var _step_end := 0.0
var _t := 0.0
var _speed := 1.0
var _ground_y := 0.0
var _aloft := false
var _noise := FastNoiseLite.new()


func _ready() -> void:
	process_priority = 10               # after the AnimationPlayer has taken this frame's root motion
	body = get_parent() as Node3D
	player = body.find_child("AnimationPlayer", true, false) as AnimationPlayer
	if animation_set == null and body is Creature:
		animation_set = (body as Creature).animation_set
	all.append(self)
	_speed = randf_range(speed_range.x, speed_range.y)
	player.speed_scale = _speed
	_noise.noise_type = FastNoiseLite.TYPE_PERLIN
	_noise.seed = randi()
	_noise.frequency = 1.0
	if animation_set != null:
		restart()


func _exit_tree() -> void:
	all.erase(self)


## up in the air (a flight pool lifted it more than a metre): the others don't step around it
func is_aloft() -> bool:
	return _aloft and body.global_position.y > _ground_y + 1.0


func restart() -> void:
	_start_pool(animation_set.pick_weighted())


## jump to a named pool (a test UI); false if the set has no such pool
func play_pool(pool_name: String) -> bool:
	var p := animation_set.get_pool(pool_name) if animation_set != null else null
	if p == null or p.clips.is_empty():
		return false
	_start_pool(p)
	return true


func _start_pool(p: CreaturePool) -> void:
	if p.vertical and not _aloft:
		_ground_y = body.global_position.y
		_aloft = true
	pool = p
	_step = 0
	_play(p.clips[0] if p.sequence else p.clips[randi() % p.clips.size()])


func _play(clip: String) -> void:
	var anim := player.get_animation(clip)
	if anim == null:
		push_warning("%s: no clip %s" % [body.name, clip])
		return
	var again := String(player.current_animation) == clip
	player.play(clip, crossfade)
	if again:
		player.seek(0.0, true)           # the same one-shot twice: from its start (play() alone would carry on)
	current_clip = clip
	var looping := anim.loop_mode != Animation.LOOP_NONE
	var dur := randf_range(pool.hold.x, pool.hold.y) if looping else anim.length / _speed - crossfade * 0.5 + pool.hold_after
	_step_end = _t + maxf(0.2, dur)


func _process(delta: float) -> void:
	_t += delta
	if pool == null or player == null:
		return
	_move(delta)
	if _t < _step_end:
		return
	if pool.sequence and _step + 1 < pool.clips.size():
		_step += 1
		_play(pool.clips[_step])
		return
	if pool.relocate.y > 0.0:
		_relocate(pool.relocate)
	var nx := animation_set.get_pool(pool.next) if pool.next != "" else null
	_start_pool(nx if nx != null and not nx.clips.is_empty() else animation_set.pick_weighted())


## root motion, then steering (Unity: OnAnimatorMove) and keeping out of the others (LateUpdate)
func _move(delta: float) -> void:
	var k := body.scale.x
	# the root motion's travel, in the creature's frame (Godot's root-motion recipe), by its scale
	var q := body.quaternion
	var dp := (player.get_root_motion_rotation_accumulator().inverse() * q) * player.get_root_motion_position() * k
	var up := pool.vertical
	if not up:
		dp.y = 0.0
	body.position += dp
	body.quaternion = q * player.get_root_motion_rotation()
	if _aloft:                          # never below the ground it took off from; settle back down after
		var y := body.global_position.y
		y = maxf(y, _ground_y) if up else move_toward(y, _ground_y, 6.0 * delta)
		body.global_position.y = y
		if not up and y <= _ground_y + 1e-4:
			_aloft = false
	var sep := separation * k
	if pool.moves:
		var to_home := home - body.global_position
		to_home.y = 0.0
		var d := to_home.length()
		var fwd := body.global_basis.z          # the creatures' front is +Z (glTF's)
		fwd.y = 0.0
		if d > wander_radius * 0.6:
			var urgency := inverse_lerp(wander_radius * 0.6, wander_radius, d)
			var want := atan2(to_home.x, to_home.z)
			var have := atan2(fwd.x, fwd.z)
			var step := deg_to_rad(35.0 + 110.0 * clampf(urgency, 0.0, 1.0)) * delta
			body.rotate_y(clampf(angle_difference(have, want), -step, step))
		else:
			var turn := _noise.get_noise_2d(_t * 0.3, 0.0) * 50.0       # lazy meander
			for o in all:                                              # step around the others
				if o == self or o.is_aloft() or is_aloft():
					continue
				var away := body.global_position - o.body.global_position
				away.y = 0.0
				if away.length_squared() < sep * sep * 1.6 and fwd.dot(-away) > 0.0:
					turn += 80.0 if fwd.signed_angle_to(away, Vector3.UP) > 0.0 else -80.0
			body.rotate_y(deg_to_rad(turn) * delta)
	for o in all:                                                      # no standing inside each other
		if o == self or o.is_aloft() or is_aloft():
			continue
		var away := body.global_position - o.body.global_position
		away.y = 0.0
		var m := away.length()
		var want_d := (sep + o.separation * o.body.scale.x) * 0.35
		if m < want_d and m > 1e-4:
			body.global_position += away / m * (want_d - m) * 0.5


## moved while hidden (underground): a random distance in range, heading for home when far out
func _relocate(r: Vector2) -> void:
	var d := randf_range(r.x, r.y) * body.scale.x
	var dir := Vector3.FORWARD.rotated(Vector3.UP, randf() * TAU)
	var to_home := home - body.global_position
	to_home.y = 0.0
	if to_home.length() > wander_radius * 0.5:
		dir = dir.slerp(to_home.normalized(), 0.7).normalized()
	body.global_position += dir * d
	body.rotation.y = randf() * TAU

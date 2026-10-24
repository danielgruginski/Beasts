class_name CreatureDemo
extends Node3D
## The viewer of a demo scene (its root; demo_builder.gd builds the scenes): an orbit camera with colony / mid / close
## presets (right-drag orbits, middle-drag pans, the wheel zooms), labels over the creatures (look, clip), a time
## scale, re-roll looks, reshuffle, buttons that make every creature do one thing at once (Bite, Howl...), and a follow
## camera that steps through the creatures. Esc goes back to the menu. Unity: BeastTestUI / InsectTestUI.

## the colony preset's distance (m)
@export var distance := 26.0
## widens the presets for big creatures (the dragons)
@export var preset_scale := 1.0
@export var menu_scene := "res://demo/demo_menu.tscn"
@export var labels_on := true

var _cam: Camera3D
var _yaw := 0.0
var _pitch := deg_to_rad(50.0)
var _dist := 26.0
var _target := Vector3.ZERO
var _follow := -1
var _labels := {}
var _show_labels := true
var _status: Label


func _ready() -> void:
	_dist = distance
	_show_labels = labels_on
	_cam = Camera3D.new()
	_cam.fov = 35.0
	_cam.far = 600.0
	add_child(_cam)
	_cam.current = true
	_build_ui()
	_place_camera()


func _wanderers() -> Array[CreatureWanderer]:
	return CreatureWanderer.all


func _build_ui() -> void:
	var ui := CanvasLayer.new()
	add_child(ui)
	var panel := PanelContainer.new()
	panel.position = Vector2(10, 10)
	ui.add_child(panel)
	var box := VBoxContainer.new()
	panel.add_child(box)
	var title := Label.new()
	title.text = "%s  -  right-drag orbit, middle-drag pan, wheel zoom, Esc menu" % name
	box.add_child(title)
	box.add_child(_row([["Colony", func(): _preset(1.0, 50.0)], ["Mid", func(): _preset(0.5, 35.0)],
		["Close", func(): _preset(0.22, 18.0)], ["Follow next", _follow_next], ["Free", func(): _follow = -1]]))
	box.add_child(_row([["Re-roll looks", _reroll], ["Reshuffle", _reshuffle],
		["Labels", func(): _show_labels = not _show_labels]]))
	var speed := HBoxContainer.new()
	var sl := Label.new()
	sl.text = "Time 1.0x"
	var slider := HSlider.new()
	slider.min_value = 0.1
	slider.max_value = 2.0
	slider.step = 0.05
	slider.value = 1.0
	slider.custom_minimum_size = Vector2(160, 0)
	slider.value_changed.connect(func(v: float) -> void:
		Engine.time_scale = v
		sl.text = "Time %.2fx" % v)
	speed.add_child(sl)
	speed.add_child(slider)
	box.add_child(speed)
	# a button per pool any creature here has (the follow-ups such as GetUp left out)
	var pools: Array[String] = []
	for w in _wanderers():
		if w.animation_set == null:
			continue
		for p in w.animation_set.pools:
			if p.weight > 0.0 and not pools.has(p.name):
				pools.append(p.name)
	var grid := HFlowContainer.new()
	grid.custom_minimum_size = Vector2(520, 0)
	for pn in pools:
		var b := Button.new()
		b.text = pn
		b.pressed.connect(func() -> void:
			for w in _wanderers():
				w.play_pool(pn))
		grid.add_child(b)
	box.add_child(grid)
	_status = Label.new()
	box.add_child(_status)


func _row(items: Array) -> HBoxContainer:
	var r := HBoxContainer.new()
	for it in items:
		var b := Button.new()
		b.text = it[0]
		b.pressed.connect(it[1])
		r.add_child(b)
	return r


func _preset(k: float, pitch_deg: float) -> void:
	_dist = distance * k * (preset_scale if k < 1.0 else 1.0)
	_pitch = deg_to_rad(pitch_deg)


func _follow_next() -> void:
	var ws := _wanderers()
	if ws.is_empty():
		return
	_follow = (_follow + 1) % ws.size()
	_preset(0.22, 20.0)


func _reroll() -> void:
	for w in _wanderers():
		if w.body is Creature:
			(w.body as Creature).reroll()


func _reshuffle() -> void:
	for w in _wanderers():
		var a := randf() * TAU
		var r := sqrt(randf()) * w.wander_radius * 0.7
		w.body.global_position = w.home + Vector3(cos(a), 0.0, sin(a)) * r
		w.body.rotation.y = randf() * TAU
		w.restart()


func _unhandled_input(e: InputEvent) -> void:
	if e is InputEventMouseMotion:
		if e.button_mask & MOUSE_BUTTON_MASK_RIGHT:
			_yaw -= e.relative.x * 0.005
			_pitch = clampf(_pitch + e.relative.y * 0.005, deg_to_rad(5.0), deg_to_rad(85.0))
		elif e.button_mask & MOUSE_BUTTON_MASK_MIDDLE:
			_follow = -1
			var right := _cam.global_basis.x
			var fwd := Vector3(_cam.global_basis.z.x, 0.0, _cam.global_basis.z.z).normalized()
			_target += (-right * e.relative.x + fwd * -e.relative.y) * _dist * 0.002
	elif e is InputEventMouseButton and e.pressed:
		if e.button_index == MOUSE_BUTTON_WHEEL_UP:
			_dist = maxf(_dist * 0.9, 1.5)
		elif e.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			_dist = minf(_dist * 1.1, 400.0)
	elif e is InputEventKey and e.pressed and e.physical_keycode == KEY_ESCAPE:
		Engine.time_scale = 1.0
		if ResourceLoader.exists(menu_scene):
			get_tree().change_scene_to_file(menu_scene)


func _process(_delta: float) -> void:
	var ws := _wanderers()
	if _follow >= ws.size():
		_follow = -1
	if _follow >= 0:
		_target = ws[_follow].body.global_position + Vector3.UP * ws[_follow].label_height * 0.5
	_place_camera()
	_update_labels(ws)
	if _follow >= 0:
		var w := ws[_follow]
		_status.text = "Following %s: %s  (%s)" % [w.body.name, w.current_clip, (w.body as Creature).summary if w.body is Creature else ""]
	else:
		_status.text = "%d creatures" % ws.size()


func _place_camera() -> void:
	var off := Vector3(sin(_yaw) * cos(_pitch), sin(_pitch), cos(_yaw) * cos(_pitch)) * _dist
	_cam.global_position = _target + off
	_cam.look_at(_target, Vector3.UP)


func _update_labels(ws: Array[CreatureWanderer]) -> void:
	for w in ws:
		var l: Label3D = _labels.get(w)
		if l == null or not is_instance_valid(l):
			l = Label3D.new()
			l.billboard = BaseMaterial3D.BILLBOARD_ENABLED
			l.fixed_size = true
			l.pixel_size = 0.0005
			l.font_size = 20
			l.outline_size = 5
			l.no_depth_test = true
			add_child(l)
			_labels[w] = l
		l.visible = _show_labels
		var c := w.body as Creature
		l.text = "%s %s\n%s" % [String(w.body.name).get_slice("_", 0), c.summary if c != null else "", w.current_clip]
		l.global_position = w.body.global_position + Vector3.UP * w.label_height * w.body.scale.x
	for k in _labels.keys():
		if not is_instance_valid(k) or not ws.has(k):
			(_labels[k] as Node).queue_free()
			_labels.erase(k)

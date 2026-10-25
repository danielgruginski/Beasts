extends Control
## The creatures pack's demo menu (res://demo/demo_menu.tscn, the project's main scene): one button per demo scene
## demo_builder.gd made. Unity: the test scenes, opened by hand.

const DEMOS := [
	["Beasts", "res://demo/beasts_demo.tscn", "wolves, wargs, zombie wolves, rats, bears, a rhino, a mammoth, deer, oozes"],
	["Dragons", "res://demo/dragons_demo.tscn", "two dragons and two hydras"],
	["Farm", "res://demo/farm_demo.tscn", "goats, sheep, cows, horses, pigs, hens"],
	["Insectoids", "res://demo/insectoids_demo.tscn", "spiders, a broodmother, spiderlings, wasps, centipedes; bats, leeches, turtles, eagles"],
	["Lineup", "res://demo/lineup_demo.tscn", "every creature side by side"],
]


func _ready() -> void:
	set_anchors_preset(Control.PRESET_FULL_RECT)
	var bg := ColorRect.new()
	bg.color = Color(0.1, 0.11, 0.12)
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(bg)
	var box := VBoxContainer.new()
	box.position = Vector2(40, 40)
	box.add_theme_constant_override("separation", 10)
	add_child(box)
	var title := Label.new()
	title.text = "Creatures (CC0)"
	title.add_theme_font_size_override("font_size", 30)
	box.add_child(title)
	var sub := Label.new()
	sub.text = "Pick a scene. In it: right-drag orbits, the wheel zooms, Esc comes back here."
	box.add_child(sub)
	for d in DEMOS:
		if not ResourceLoader.exists(d[1]):
			continue
		var b := Button.new()
		b.text = "%s  -  %s" % [d[0], d[2]]
		b.custom_minimum_size = Vector2(520, 44)
		b.alignment = HORIZONTAL_ALIGNMENT_LEFT
		var path: String = d[1]
		b.pressed.connect(func() -> void: get_tree().change_scene_to_file(path))
		box.add_child(b)

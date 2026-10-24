@tool
extends RefCounted
## Builds the pack's demo scenes in res://demo/ (as the Unity pack's test scenes: Beasts_Test, Dragons_Test, Farm_Test,
## Insectoids_Test) from the creature scenes creature_builder.gd made: groups of each creature scattered round a home,
## each with a CreatureWanderer; a sun, a sky and a ground; a CreatureDemo root (the viewer); plus a lineup of every
## creature and the menu (demo_menu.tscn, the project's main scene). Creatures not built yet are left out. Headless:
## godot --headless --path <project> --script res://addons/beasts/demo/demo_cli.gd

const OUT := "res://demo/"

## per scene: viewer distance, preset scale, groups [scene, how many, scatter radius, spacing, label height, separation,
## wander radius, (centre)]
const DEMOS := {
	"beasts_demo": {"distance": 26.0, "scale": 1.0, "groups": [
		["res://beasts/Wolf/Wolf.tscn", 7, 10.0, 3.5, 1.3, 2.2, 13.0],
		["res://beasts/Rat/Rat.tscn", 10, 10.0, 2.0, 0.7, 1.3, 13.0],
		["res://beasts/Rhino/Rhino.tscn", 1, 10.0, 6.0, 2.3, 4.0, 13.0],
		["res://beasts/Bear/Bear.tscn", 2, 10.0, 5.0, 2.0, 3.0, 13.0],
		["res://beasts/Mammoth/Mammoth.tscn", 1, 10.0, 8.0, 3.5, 5.0, 13.0],
		["res://beasts/Deer/Deer.tscn", 3, 10.0, 4.5, 2.6, 3.0, 13.0],
		["res://beasts/Ooze/Ooze.tscn", 2, 10.0, 6.0, 1.6, 3.5, 13.0],
		["res://beasts/Ooze/OozeSmall.tscn", 3, 10.0, 3.0, 0.9, 2.0, 13.0],
		["res://beasts/Ooze/OozeGiant.tscn", 1, 10.0, 8.0, 2.5, 5.5, 13.0],
		["res://beasts/Warg/Warg.tscn", 2, 10.0, 5.0, 1.9, 3.2, 13.0],
		["res://beasts/Warg/WargRidden.tscn", 2, 10.0, 5.0, 2.0, 3.2, 13.0],
		["res://beasts/ZombieWolf/ZombieWolf.tscn", 3, 10.0, 3.5, 1.3, 2.2, 13.0],
	]},
	"dragons_demo": {"distance": 62.0, "scale": 2.5, "groups": [
		["res://beasts/Dragon/Dragon.tscn", 2, 18.0, 20.0, 6.0, 9.0, 45.0],
		["res://beasts/Hydra/Hydra.tscn", 2, 18.0, 16.0, 4.5, 7.0, 30.0],
	]},
	"farm_demo": {"distance": 24.0, "scale": 1.0, "groups": [
		["res://beasts/Goat/Goat.tscn", 5, 4.0, 1.4, 1.1, 0.9, 6.0, Vector3(-9, 0, 6)],
		["res://beasts/Sheep/Sheep.tscn", 6, 4.5, 1.4, 1.1, 0.9, 6.75, Vector3(0, 0, 9)],
		["res://beasts/Cow/Cow.tscn", 3, 5.0, 3.0, 1.8, 2.0, 7.5, Vector3(9, 0, 5)],
		["res://beasts/Horse/Horse.tscn", 2, 5.0, 3.2, 2.1, 2.2, 7.5, Vector3(8, 0, -7)],
		["res://beasts/Pig/Pig.tscn", 4, 3.5, 1.6, 1.0, 1.1, 5.25, Vector3(-8, 0, -6)],
		["res://beasts/Chicken/Chicken.tscn", 10, 3.0, 0.5, 0.6, 0.35, 4.5, Vector3(0, 0, -2)],
	]},
	"insectoids_demo": {"distance": 26.0, "scale": 1.0, "groups": [
		["res://insectoids/Spider/Spider.tscn", 5, 10.0, 5.0, 1.4, 2.6, 13.0],
		["res://insectoids/Wasp/Wasp.tscn", 4, 10.0, 4.0, 2.6, 2.2, 13.0],
		["res://insectoids/Centipede/Centipede.tscn", 3, 10.0, 5.0, 0.9, 3.2, 13.0],
		["res://insectoids/Spiderling/Spiderling.tscn", 4, 10.0, 2.5, 0.6, 1.0, 13.0],
		["res://insectoids/Broodmother/Broodmother.tscn", 1, 10.0, 8.0, 2.6, 4.5, 13.0],
		["res://beasts/Bat/Bat.tscn", 3, 10.0, 3.0, 1.2, 1.6, 13.0],
		["res://beasts/Leech/Leech.tscn", 3, 10.0, 2.0, 0.5, 1.0, 13.0],
		["res://beasts/Turtle/Turtle.tscn", 2, 10.0, 3.0, 1.0, 2.0, 13.0],
		["res://beasts/Eagle/Eagle.tscn", 2, 10.0, 4.0, 1.2, 2.0, 13.0],
	]},
}

const LINEUP := ["Wolf", "Warg", "ZombieWolf", "Rat", "Bear", "Rhino", "Deer", "Mammoth", "Ooze", "Goat", "Sheep", "Cow",
	"Horse", "Pig", "Chicken", "Leech", "Turtle", "Bat", "Eagle", "Spider", "Spiderling", "Broodmother", "Wasp",
	"Centipede", "Hydra", "Dragon"]


static func build_all() -> String:
	DirAccess.make_dir_recursive_absolute(OUT)
	var lines := PackedStringArray()
	for n: String in DEMOS:
		lines.append(_demo(n, DEMOS[n]))
	lines.append(_lineup())
	var menu := Control.new()
	menu.name = "DemoMenu"
	menu.set_script(load("res://addons/beasts/demo/demo_menu.gd"))
	lines.append("DEMO menu -> %s" % _save(menu, OUT + "demo_menu.tscn"))
	return "\n".join(lines)


static func _stage(root: Node3D, ground_size: float) -> void:
	var env := Environment.new()
	env.background_mode = Environment.BG_SKY
	var sky := Sky.new()
	var sm := ProceduralSkyMaterial.new()
	sm.sky_top_color = Color(0.38, 0.5, 0.66)
	sm.sky_horizon_color = Color(0.68, 0.72, 0.76)
	sm.ground_horizon_color = Color(0.5, 0.5, 0.46)
	sm.ground_bottom_color = Color(0.3, 0.3, 0.27)
	sky.sky_material = sm
	env.sky = sky
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.tonemap_mode = Environment.TONE_MAPPER_AGX
	env.ssao_enabled = true
	var we := WorldEnvironment.new()
	we.name = "WorldEnvironment"
	we.environment = env
	_add(root, we)
	var sun := DirectionalLight3D.new()
	sun.name = "Sun"
	sun.rotation_degrees = Vector3(-50, 30, 0)
	sun.light_energy = 1.3
	sun.shadow_enabled = true
	sun.directional_shadow_max_distance = ground_size
	_add(root, sun)
	var ground := MeshInstance3D.new()
	ground.name = "Ground"
	var pm := PlaneMesh.new()
	pm.size = Vector2(ground_size, ground_size)
	var gm := StandardMaterial3D.new()
	gm.albedo_color = Color(0.4, 0.44, 0.31)
	gm.roughness = 1.0
	pm.material = gm
	ground.mesh = pm
	_add(root, ground)
	var body := StaticBody3D.new()
	body.name = "GroundBody"
	var cs := CollisionShape3D.new()
	cs.shape = WorldBoundaryShape3D.new()
	body.add_child(cs)
	_add(root, body)
	cs.owner = root


static func _demo(scene_name: String, d: Dictionary) -> String:
	var root := Node3D.new()
	root.name = scene_name.capitalize().replace(" ", "")
	root.set_script(load("res://addons/beasts/demo/creature_demo.gd"))
	root.set("distance", d["distance"])
	root.set("preset_scale", d["scale"])
	_stage(root, 200.0)
	var rng := RandomNumberGenerator.new()
	rng.seed = 11
	var taken: Array[Vector3] = []
	var counts := PackedStringArray()
	for g: Array in d["groups"]:
		if not ResourceLoader.exists(g[0]):
			continue
		var ps: PackedScene = load(g[0])
		var centre: Vector3 = g[7] if g.size() > 7 else Vector3.ZERO
		var group := Node3D.new()
		group.name = String(g[0]).get_file().get_basename() + "s"
		_add(root, group)
		for i in int(g[1]):
			var c: Node3D = ps.instantiate()
			c.name = "%s_%02d" % [String(g[0]).get_file().get_basename(), i]
			c.position = centre + _spot(rng, taken, g[2], g[3])
			c.rotation.y = rng.randf() * TAU
			group.add_child(c)
			c.owner = root
			var w := CreatureWanderer.new()
			w.name = "Wanderer"
			w.home = centre
			w.wander_radius = g[6]
			w.separation = g[5]
			w.label_height = g[4]
			c.add_child(w)
			w.owner = root
		counts.append("%d %s" % [g[1], String(g[0]).get_file().get_basename()])
	return "DEMO %s: %s -> %s" % [scene_name, ", ".join(counts), _save(root, OUT + scene_name + ".tscn")]


static func _spot(rng: RandomNumberGenerator, taken: Array[Vector3], radius: float, spacing: float) -> Vector3:
	for t in 500:
		var p := Vector3(rng.randf_range(-1, 1) * radius, 0, rng.randf_range(-1, 1) * radius)
		if p.length() > radius:
			continue
		var ok := true
		for s in taken:
			if s.distance_to(p) <= spacing:
				ok = false
				break
		if ok:
			taken.append(p)
			return p
	return Vector3.ZERO


static func _lineup() -> String:
	var root := Node3D.new()
	root.name = "Lineup"
	root.set_script(load("res://addons/beasts/demo/creature_demo.gd"))
	root.set("distance", 70.0)
	root.set("labels_on", false)
	_stage(root, 200.0)
	var x := -36.0
	var row := 0
	var n := 0
	for c_name: String in LINEUP:
		var path := "res://beasts/%s/%s.tscn" % [c_name, c_name]
		if not ResourceLoader.exists(path):
			path = "res://insectoids/%s/%s.tscn" % [c_name, c_name]
		if not ResourceLoader.exists(path):
			continue
		var c: Node3D = (load(path) as PackedScene).instantiate()
		var aabb := _extent(c)
		var w := maxf(2.5, aabb.size.x + 1.0)
		if x + w > 36.0:
			x = -36.0
			row += 1
		c.position = Vector3(x + w * 0.5, 0, -row * 9.0)
		c.rotation_degrees.y = 35.0
		x += w
		_add(root, c)
		var wd := CreatureWanderer.new()             # idle in place: a set of its Idle pool only
		wd.name = "Wanderer"
		wd.home = c.position
		wd.wander_radius = 0.01
		wd.label_height = maxf(1.0, aabb.size.y + 0.3)
		var only := CreatureAnimationSet.new()
		var p := CreaturePool.new()
		p.name = "Idle"
		p.clips = PackedStringArray(["Idle"])
		only.pools = [p]
		wd.animation_set = only
		c.add_child(wd)
		wd.owner = root
		n += 1
	return "DEMO lineup: %d creatures -> %s" % [n, _save(root, OUT + "lineup_demo.tscn")]


static func _extent(n: Node) -> AABB:
	var box := AABB()
	var first := true
	for mi in n.find_children("*", "MeshInstance3D", true, false):
		var b: AABB = (mi as MeshInstance3D).get_aabb()
		box = b if first else box.merge(b)
		first = false
	return box


static func _add(root: Node, n: Node) -> void:
	root.add_child(n)
	n.owner = root


static func _save(root: Node, path: String) -> String:
	var packed := PackedScene.new()
	var err := packed.pack(root)
	if err == OK:
		err = ResourceSaver.save(packed, path)
	root.free()
	return "%s (%s)" % [path, error_string(err)]

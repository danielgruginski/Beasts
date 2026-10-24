@tool
extends RefCounted
## Builds each creature listed in res://addons/beasts/creatures.json and the addons' data/*.json (beasts, insectoids)
## from its exports in res://beasts/<Name>/ (or the entry's "dir": the insectoids' res://insectoids/<Name>/; the .glb
## imported by creature_import.gd, the textures): its coat materials (M_<Name>_<Skin>.tres on creature_coat), its
## clip pools for CreatureWanderer (<Name>_anims.tres) and its scene <Name>.tscn: a Creature root (skins, size range,
## the model's other materials and hidden meshes) with the model under it as a plain reference to the .glb (nothing in
## it is changed, so the scene stays a few KB and a re-exported model shows up without a rebuild; setups put their
## nodes beside it, on bones through attach()). Run from Project > Tools > Beasts: Build Creature
## Scenes, or headless: godot --headless --path <project> --script res://addons/beasts/build/build_cli.gd.
## Unity: the <Creature>Setup editor scripts.

const DATA := "res://addons/beasts/creatures.json"
const DATA_DIRS := ["res://addons/beasts/data/", "res://addons/insectoids/data/"]
const ROOT := "res://beasts/"
const SHADERS := {
	"": "res://addons/beasts/shaders/creature_coat.gdshader",
	"two_sided": "res://addons/beasts/shaders/creature_coat_two_sided.gdshader",
	"blend": "res://addons/beasts/shaders/creature_coat_blend.gdshader",
}

## the materials made in this build, by path
static var _made := {}


static func build_all(only: PackedStringArray = PackedStringArray()) -> String:
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(DATA))
	# and one file per creature in data/ ({"<Name>": {...}}), so creatures can be added without touching the others
	for dd: String in DATA_DIRS:
		if DirAccess.dir_exists_absolute(dd):
			for fn in DirAccess.get_files_at(dd):
				if fn.ends_with(".json"):
					data.merge(JSON.parse_string(FileAccess.get_file_as_string(dd + fn)), true)
	var lines := PackedStringArray()
	for creature_name: String in data:
		if not only.is_empty() and not only.has(creature_name):
			continue
		lines.append(build(creature_name, data[creature_name]))
	return "\n".join(lines)


static func build(creature_name: String, c: Dictionary) -> String:
	_made.clear()
	var dir: String = c.get("dir", ROOT + creature_name + "/")
	var glb := dir + creature_name + ".glb"
	if not ResourceLoader.exists(glb):
		return "BUILD %s: no %s (install the exports first)" % [creature_name, glb]
	# coats
	var mats := {}
	for skin: Dictionary in c.get("skins", []):
		var m := _material(dir, creature_name, skin)
		mats[skin["name"]] = m
	var skins: Array[Material] = []
	for skin: Dictionary in c.get("skins", []):
		for i in int(skin.get("weight", 1)):
			skins.append(mats[skin["name"]])
	# the clip pools
	var aset := CreatureAnimationSet.new()
	for p: Dictionary in c.get("pools", []):
		var cp := CreaturePool.new()
		cp.name = p["name"]
		cp.weight = p.get("weight", 1.0)
		cp.clips = PackedStringArray(p["clips"])
		cp.sequence = p.get("sequence", false)
		cp.moves = p.get("moves", false)
		cp.vertical = p.get("vertical", false)
		cp.hold = Vector2(p.get("hold", [3, 6])[0], p.get("hold", [3, 6])[1])
		cp.hold_after = p.get("after", 0.0)
		cp.next = p.get("next", "")
		var rl: Array = p.get("relocate", [0, 0])
		cp.relocate = Vector2(rl[0], rl[1])
		aset.pools.append(cp)
	var aset_path := dir + creature_name + "_anims.tres"
	ResourceSaver.save(aset, aset_path)
	# the scene
	var root := Creature.new()
	root.name = creature_name
	var model := (load(glb) as PackedScene).instantiate()
	model.name = "Model"
	root.add_child(model)
	model.owner = root
	var target: MeshInstance3D = model.find_child(c["target"], true, false) as MeshInstance3D if c.has("target") else null
	if target == null:
		target = _first_mesh(model)
	root.skins = skins
	root.target = root.get_path_to(target)
	root.surface = int(c.get("surface", 0))
	var sc: Array = c.get("scale", [0.85, 1.2])
	root.scale_range = Vector2(sc[0], sc[1])
	# the rest of the look, set by the Creature on the model (the scene saves nothing inside the .glb instance, so it
	# only references the model): the paired mesh's skins, other surfaces' and meshes' materials, hidden meshes
	if c.has("paired"):
		var pr: Dictionary = c["paired"]
		var pm := model.find_child(pr["target"], true, false) as MeshInstance3D
		var paired: Array[Material] = []
		for s: Dictionary in pr["skins"]:
			for i in int(s.get("weight", 1)):
				paired.append(_material(dir, creature_name, s))
		root.paired_target = root.get_path_to(pm)
		root.paired_skins = paired
	for surf: String in c.get("surfaces", {}):          # other surfaces of the target (the wasp's wings: surface 1)
		root.materials["%s:%s" % [root.get_path_to(target), surf]] = _material(dir, creature_name, c["surfaces"][surf])
	for mesh_name: String in c.get("meshes", {}):
		var mm := model.find_child(mesh_name, true, false) as MeshInstance3D
		var spec: Dictionary = c["meshes"][mesh_name]
		if mm != null:
			root.materials["%s:%d" % [root.get_path_to(mm), int(spec.get("surface", 0))]] = _material(dir, creature_name, spec)
			if spec.has("visible"):
				_show(root, mm, spec["visible"])
	root.animation_set = load(aset_path)
	# what a creature adds of its own (the ooze's jelly and effects, the dragon's breath...): creatures.json "setup"
	# names a script with static func setup(root: Creature, model: Node, dir: String, data: Dictionary) -> String
	var extra := ""
	if c.has("setup"):
		extra = " " + str(load(c["setup"]).setup(root, model, dir, c))
	var packed := PackedScene.new()
	var err := packed.pack(root)
	var path := dir + creature_name + ".tscn"
	if err == OK:
		err = ResourceSaver.save(packed, path)
	# variants: the same creature with other meshes shown or hidden (the saddled warg, the tacked mammoth)
	for v: Dictionary in c.get("variants", []):
		for n: String in v.get("show", []):
			_show(root, model.find_child(n, true, false), true)
		for n: String in v.get("hide", []):
			_show(root, model.find_child(n, true, false), false)
		root.name = v["name"]
		var vp := PackedScene.new()
		vp.pack(root)
		ResourceSaver.save(vp, dir + v["name"] + ".tscn")
		extra += " +" + v["name"]
	root.free()
	return "BUILD %s: %d skins (%d materials), %d pools -> %s (%s)%s" % [creature_name, skins.size(), mats.size(), aset.pools.size(), path, error_string(err), extra]


## M_<Name>_<Skin>.tres: the coat shader on the skin's texture, tint, normal map, smoothness
static func _material(dir: String, creature_name: String, skin: Dictionary) -> Material:
	var path := dir + "M_%s_%s.tres" % [creature_name, skin["name"]]
	if _made.has(path):                                 # one material per name (the warg's tack and mask share one)
		return _made[path]
	var m := ShaderMaterial.new()
	m.resource_name = skin["name"]
	m.shader = load(SHADERS[skin.get("mode", "")])
	m.set_shader_parameter("coat", load(dir + skin["texture"] + ".png"))
	var t: Array = skin.get("tint", [1, 1, 1, 1])
	m.set_shader_parameter("tint", Color(t[0], t[1], t[2], t[3] if t.size() > 3 else 1.0))
	m.set_shader_parameter("smoothness", skin.get("smoothness", 1.0))
	if skin.has("normal"):
		m.set_shader_parameter("use_normal_map", true)
		m.set_shader_parameter("normal_map", load(dir + skin["normal"] + ".png"))
		m.set_shader_parameter("normal_scale", skin.get("normal_scale", 1.0))
	ResourceSaver.save(m, path)
	m.take_over_path(path)
	_made[path] = m
	return m


## a model's mesh shown or hidden by the Creature (its shown / hidden lists)
static func _show(root: Creature, n: Node, on: bool) -> void:
	var p := root.get_path_to(n)
	root.shown.erase(p)
	root.hidden.erase(p)
	if on:
		root.shown.append(p)
	else:
		root.hidden.append(p)


## A BoneAttachment3D named `node_name` on the model's bone `bone`, under the root (saved with the scene; it follows
## the bone through use_external_skeleton, as nothing inside the .glb instance is saved); null when the rig has no such
## bone. Setup scripts put their nodes under it.
static func attach(root: Node, model: Node, bone: String, node_name: String) -> BoneAttachment3D:
	var skel := model.find_child("Skeleton3D", true, false) as Skeleton3D
	if skel == null or skel.find_bone(bone) < 0:
		return null
	var att := BoneAttachment3D.new()
	att.name = node_name
	root.add_child(att)
	att.owner = root
	att.use_external_skeleton = true
	att.external_skeleton = att.get_path_to(skel)
	att.bone_name = bone
	return att


static func _first_mesh(n: Node) -> MeshInstance3D:
	for c in n.get_children():
		if c is MeshInstance3D:
			return c
		var f := _first_mesh(c)
		if f != null:
			return f
	return null

@tool
extends RefCounted
## The dungeon ooze's scene extras (creatures.json "setup"; creature_builder.gd calls setup() on Ooze.tscn before
## saving it), and its two other scenes, built here the same way: OozeSmall and OozeGiant (creatures.json
## "ooze_variants"; the builder's own "variants" only show or hide meshes). Each ooze gets
##   the jelly: one material per colour preset (M_Ooze_<Preset>.tres: the far side with the near side as next_pass,
##   OozeLook.make_jelly on T_Ooze) as the Creature's skins, weighted by the entry's "presets" list;
##   OozeLook (remains, the shadow twin's opacity) and OozeShadow, OozeBody's shadow-only twin (M_Ooze_Shadow.tres),
##   both moved under the skeleton when the ooze enters the game (Creature.skeleton_children); the body casts none;
##   OozeFx (trail, drips, splashes, the acid glob) under the root;
##   the giant: OozeSplit, splitting into two Oozes at "split" "scale", which remains go with which half read from
##   the bind pose, and its own clip pools (the normal ones and its "pools": Split).
## The contents keep the coat material the builder gives them ("meshes": M_Ooze_Contents.tres).
## Unity: OozeSetup (Ooze, SmallOoze and GiantOoze prefabs).

const BUILDER := "res://addons/beasts/build/creature_builder.gd"


static func setup(root: Creature, model: Node, dir: String, data: Dictionary) -> String:
	var jelly := _jelly_materials(dir)
	if jelly.is_empty():
		return "no %sT_Ooze.png: no jelly" % dir
	var shadow := _shadow_material(dir)
	var all: Array[Material] = []
	for p: String in OozeLook.PRESETS:
		all.append(jelly[p])
	var lines := PackedStringArray()
	lines.append(_dress(root, model, data.get("presets", ["Green"]), PackedStringArray(), jelly, all, shadow))
	var variants: Dictionary = data.get("ooze_variants", {})
	for vname: String in variants:
		lines.append(_variant(vname, variants[vname], root, dir, data, jelly, all, shadow))
	return "; ".join(lines)


## Adds the ooze's own nodes to a creature scene and sets its skins: presets (names, repeats weigh more), hidden remains.
static func _dress(root: Creature, model: Node, presets: Array, hidden: PackedStringArray, jelly: Dictionary,
		all: Array[Material], shadow: Material) -> String:
	var skel := model.find_child("Skeleton3D", true, false) as Skeleton3D
	var body := model.find_child("OozeBody", true, false) as MeshInstance3D
	if skel == null or body == null:
		return "%s: no Skeleton3D / OozeBody" % root.name
	var skins: Array[Material] = []
	for p: String in presets:
		if jelly.has(p):
			skins.append(jelly[p])
	root.skins = skins
	# the twin and the look are saved beside the model and moved under its skeleton when the ooze enters the game
	# (Creature.skeleton_children: the scene saves nothing inside the .glb instance)
	var twin := MeshInstance3D.new()
	twin.name = "OozeShadow"
	twin.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_SHADOWS_ONLY
	twin.material_override = shadow
	root.add_child(twin)
	twin.owner = root
	var look := OozeLook.new()
	look.name = "OozeLook"
	look.hidden = hidden
	look.materials = all
	root.add_child(look)
	look.owner = root
	root.skeleton_children = [NodePath("OozeShadow"), NodePath("OozeLook")]
	var fx := OozeFx.new()
	fx.name = "OozeFx"
	root.add_child(fx)
	fx.owner = root
	return "%s: %d skins, scale %.2f-%.2f%s" % [root.name, skins.size(), root.scale_range.x, root.scale_range.y,
			", hides " + ", ".join(hidden) if not hidden.is_empty() else ""]


## Another ooze scene (OozeSmall, OozeGiant) from the same model, built as creature_builder builds Ooze.tscn.
static func _variant(vname: String, v: Dictionary, base: Creature, dir: String, data: Dictionary, jelly: Dictionary,
		all: Array[Material], shadow: Material) -> String:
	var glb := dir + "Ooze.glb"
	var root := Creature.new()
	root.name = vname
	var model := (load(glb) as PackedScene).instantiate()
	model.name = "Model"
	root.add_child(model)
	model.owner = root
	var target := model.find_child(data.get("target", "OozeBody"), true, false) as MeshInstance3D
	root.target = root.get_path_to(target)
	root.surface = base.surface
	var sc: Array = v.get("scale", data.get("scale", [0.9, 1.1]))
	root.scale_range = Vector2(sc[0], sc[1])
	# the contents' coat and the hidden meshes, as the builder gave the base scene ("meshes")
	root.materials = base.materials.duplicate()
	root.shown = base.shown.duplicate()
	root.hidden = base.hidden.duplicate()
	# clip pools: the base ones, and the variant's own pools added (or replacing ones of the same name)
	var aset := base.animation_set
	var extra: Array = v.get("pools", [])
	if not extra.is_empty():
		var own := CreatureAnimationSet.new()
		for p: Dictionary in data.get("pools", []):
			own.pools.append(_pool(p))
		for p: Dictionary in extra:
			var cp := _pool(p)
			var old := own.get_pool(cp.name)
			if old != null:
				own.pools.erase(old)
			own.pools.append(cp)
		var aset_path := dir + vname + "_anims.tres"
		ResourceSaver.save(own, aset_path)
		aset = load(aset_path)
	root.animation_set = aset
	var hidden := PackedStringArray(v.get("hidden", []))
	var line := _dress(root, model, v.get("presets", data.get("presets", ["Green"])), hidden, jelly, all, shadow)
	if v.has("split"):
		line += ", " + _add_split(root, model, dir, v["split"])
	var packed := PackedScene.new()
	var err := packed.pack(root)
	var path := dir + vname + ".tscn"
	if err == OK:
		err = ResourceSaver.save(packed, path)
	root.free()
	return "%s -> %s (%s)" % [line, path, error_string(err)]


## The giant's split: into `into` (a scene name in the same folder) at `scale`, starting on `pool`; the remains on
## HalfL's side of the body (in the bind pose) go with the left half, the rest with the right.
static func _add_split(root: Creature, model: Node, dir: String, s: Dictionary) -> String:
	var skel := model.find_child("Skeleton3D", true, false) as Skeleton3D
	var split := OozeSplit.new()
	split.name = "OozeSplit"
	split.child_scene = dir + String(s.get("into", "Ooze")) + ".tscn"
	split.child_scale = s.get("scale", 0.79)
	split.child_pool = s.get("pool", "Reform")
	var left := PackedStringArray()
	var right := PackedStringArray()
	var hl := skel.find_bone("HalfL")
	var side := signf(skel.get_bone_global_rest(hl).origin.x) if hl >= 0 else 1.0
	for n in OozeLook.REMAINS:
		var b := skel.find_bone(n)
		if b < 0:
			continue
		var x := skel.get_bone_global_rest(b).origin.x
		if signf(x) == side or absf(x) < 1e-4:
			left.append(n)
		else:
			right.append(n)
	split.left_remains = left
	split.right_remains = right
	root.add_child(split)
	split.owner = root
	return "splits into 2 x %s at %.2f (left %s; right %s)" % [s.get("into", "Ooze"), split.child_scale, " ".join(left), " ".join(right)]


static func _pool(p: Dictionary) -> CreaturePool:
	var cp := CreaturePool.new()
	cp.name = p["name"]
	cp.weight = p.get("weight", 1.0)
	cp.clips = PackedStringArray(p["clips"])
	cp.sequence = p.get("sequence", false)
	cp.moves = p.get("moves", false)
	cp.vertical = p.get("vertical", false)
	var h: Array = p.get("hold", [3, 6])
	cp.hold = Vector2(h[0], h[1])
	cp.hold_after = p.get("after", 0.0)
	cp.next = p.get("next", "")
	return cp


## M_Ooze_<Preset>.tres for every preset (name -> material); empty if T_Ooze is missing
static func _jelly_materials(dir: String) -> Dictionary:
	var masks_path := dir + "T_Ooze.png"
	if not ResourceLoader.exists(masks_path):
		return {}
	var masks := load(masks_path) as Texture2D
	var out := {}
	for p: String in OozeLook.PRESETS:
		var m := OozeLook.make_jelly(p, masks)
		var path := dir + "M_Ooze_%s.tres" % p
		ResourceSaver.save(m, path)
		m.take_over_path(path)
		out[p] = m
	return out


## M_Ooze_Shadow.tres: the twin's dithered shadow (its opacity per ooze: OozeLook sets it from the preset)
static func _shadow_material(dir: String) -> Material:
	var m := ShaderMaterial.new()
	m.resource_name = "Shadow"
	m.shader = load("res://addons/beasts/ooze/ooze_jelly_shadow.gdshader")
	m.set_shader_parameter("masks", load(dir + "T_Ooze.png"))
	var path := dir + "M_Ooze_Shadow.tres"
	ResourceSaver.save(m, path)
	m.take_over_path(path)
	return m

@tool
extends EditorScenePostImport
## Runs on every creature .glb (its .import names it; tools/install_to_godot.py writes them): the clips listed in
## <name>_clips.json beside the .glb get their loop mode, their root motion (the Motion bone, a sibling of the skeleton's
## root that carries the travel: AnimationPlayer.root_motion_track) and their events (Animation metadata "events":
## [{name, time}], read by Creature, which raises creature_event as a clip passes one). Unity: BeastSetupUtil's
## ConfigureModel and ConfigureClips.


func _post_import(scene: Node) -> Object:
	var src := get_source_file()
	var json_path := src.get_base_dir().path_join(src.get_file().get_basename().to_lower() + "_clips.json")
	var player := _find(scene, "AnimationPlayer") as AnimationPlayer
	if player == null:
		return scene                    # a model without clips (an egg, a prop)
	if not FileAccess.file_exists(json_path):
		push_warning("%s: no %s, clips left as imported" % [src, json_path.get_file()])
		return scene
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(json_path))
	var missing := []
	for c: Dictionary in data["clips"]:
		var anim := player.get_animation(c["name"])
		if anim == null:
			missing.append(c["name"])
			continue
		anim.loop_mode = Animation.LOOP_LINEAR if c["loop"] else Animation.LOOP_NONE
		anim.set_meta("events", c["events"])
		anim.set_meta("root_motion", c["rootMotion"])
	if not missing.is_empty():
		push_warning("%s: clips not in the file: %s" % [src, ", ".join(missing)])
	var skel := _find(scene, "Skeleton3D") as Skeleton3D
	if skel != null and skel.find_bone("Motion") >= 0:
		var root := player.get_node(player.root_node)
		player.root_motion_track = NodePath(String(root.get_path_to(skel)) + ":Motion")
	return scene


func _find(n: Node, cls: String) -> Node:
	if n.is_class(cls):
		return n
	for c in n.get_children():
		var f := _find(c, cls)
		if f != null:
			return f
	return null

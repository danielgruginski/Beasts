@tool
extends RefCounted
## The eagle's scene extras (creatures.json "setup"; creature_builder.gd calls setup()): the folded wing's creases
## (EagleFeatherFold drives EagleBody's FoldL / FoldR from the WingFoldL / WingFoldR gauge bones).


static func setup(root: Creature, model: Node, _dir: String, _data: Dictionary) -> String:
	var skel := model.find_child("Skeleton3D", true, false) as Skeleton3D
	var body := model.find_child("EagleBody", true, false) as MeshInstance3D
	if skel == null or body == null:
		return "no skeleton or EagleBody: no feather fold"
	var fold := EagleFeatherFold.new()
	fold.name = "FeatherFold"
	root.add_child(fold)
	fold.owner = root
	fold.body = fold.get_path_to(body)
	fold.skeleton = fold.get_path_to(skel)
	return "feather fold (%d blend shapes)" % body.mesh.get_blend_shape_count()

class_name EagleFeatherFold
extends Node
## The eagle's folded wing creases round its body: the feather cards crossing the fold's creases bend there, as
## EagleBody's blend shapes FoldL and FoldR (0 spread, 1 folded). Each follows its gauge bone, WingFoldL / WingFoldR,
## which the clips slide `gauge` metres from its rest place as the wing lays on the flank (not when it only flexes in
## flight), so any clip, blend or crossfade bends the cards with the wing. A child of the eagle (eagle_setup.gd puts
## it there). Unity: EagleFeatherFold.

@export var body: NodePath
@export var skeleton: NodePath
## the gauge's slide at a full fold (m): eagle_body.FOLD_GAUGE
@export var gauge := 0.1

var _mesh: MeshInstance3D
var _skel: Skeleton3D
var _shape := [-1, -1]
var _bone := [-1, -1]


func _ready() -> void:
	process_priority = 10               # after the AnimationPlayer has posed the gauges
	_mesh = get_node_or_null(body) as MeshInstance3D
	_skel = get_node_or_null(skeleton) as Skeleton3D
	if _mesh == null or _skel == null:
		return
	for i in 2:
		_shape[i] = _mesh.find_blend_shape_by_name(["FoldL", "FoldR"][i])
		_bone[i] = _skel.find_bone(["WingFoldL", "WingFoldR"][i])


func _process(_delta: float) -> void:
	if _mesh == null or _skel == null:
		return
	for i in 2:
		if _shape[i] < 0 or _bone[i] < 0:
			continue
		var d := _skel.get_bone_pose_position(_bone[i]).distance_to(_skel.get_bone_rest(_bone[i]).origin)
		_mesh.set_blend_shape_value(_shape[i], clampf(d / gauge, 0.0, 1.0))

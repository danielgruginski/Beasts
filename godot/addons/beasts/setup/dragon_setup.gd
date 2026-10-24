@tool
extends RefCounted
## The dragon's scene extras (creatures.json "setup"; creature_builder.gd calls setup()): the fire breath on its
## mouth. A BoneAttachment3D on Socket_Mouth carries a CreatureBreath placed as Unity's BeastBreath: offset from the
## socket down and back between the open jaws (in the creature's own axes in the bind pose) and aimed ahead, tipped
## aim_down below the snout's line so the stream washes over the ground ahead.

const BUILDER := "res://addons/beasts/build/creature_builder.gd"
const OFFSET := Vector3(0.0, -0.28, -0.15)
const AIM_DOWN := 12.0


static func setup(root: Creature, model: Node, _dir: String, _data: Dictionary) -> String:
	var att: BoneAttachment3D = load(BUILDER).attach(root, model, "Socket_Mouth", "Mouth")
	if att == null:
		return "no Socket_Mouth: no breath"
	var skel := model.find_child("Skeleton3D", true, false) as Skeleton3D
	var rest := skel.get_bone_global_rest(skel.find_bone("Socket_Mouth"))
	var want := Transform3D(Basis(Vector3.RIGHT, deg_to_rad(AIM_DOWN)), rest.origin + OFFSET)
	var breath := CreatureBreath.new()
	breath.name = "Breath"
	att.add_child(breath)
	breath.owner = root
	breath.transform = rest.affine_inverse() * want
	return "breath on Socket_Mouth"

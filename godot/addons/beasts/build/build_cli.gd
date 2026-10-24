extends SceneTree
## Headless build of the creature scenes (creature_builder.gd):
##   godot --headless --path <project> --script res://addons/beasts/build/build_cli.gd [-- Wolf Rat ...]


func _initialize() -> void:
	print(load("res://addons/beasts/build/creature_builder.gd").build_all(PackedStringArray(OS.get_cmdline_user_args())))
	quit()

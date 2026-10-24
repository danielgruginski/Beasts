extends SceneTree
## Headless build of the demo scenes (demo_builder.gd):
##   godot --headless --path <project> --script res://addons/beasts/demo/demo_cli.gd


func _initialize() -> void:
	print(load("res://addons/beasts/demo/demo_builder.gd").build_all())
	quit()

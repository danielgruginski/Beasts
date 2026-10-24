@tool
extends EditorPlugin
## The Beasts menu (Project > Tools): build the creature scenes and their materials from res://beasts/<Name>/ (the
## exports tools/install_to_godot.py copies there) and creatures.json.

const BUILD := "Beasts: Build Creature Scenes"


func _enter_tree() -> void:
	add_tool_menu_item(BUILD, func() -> void: print(load("res://addons/beasts/build/creature_builder.gd").build_all()))


func _exit_tree() -> void:
	remove_tool_menu_item(BUILD)

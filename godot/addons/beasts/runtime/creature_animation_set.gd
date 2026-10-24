class_name CreatureAnimationSet
extends Resource
## Weighted pools of clips for CreatureWanderer (one .tres per creature, built from creatures.json). Unity:
## BeastAnimationSet.

@export var pools: Array[CreaturePool] = []


func get_pool(pool_name: String) -> CreaturePool:
	for p in pools:
		if p.name == pool_name:
			return p
	return null


func pick_weighted() -> CreaturePool:
	var total := 0.0
	for p in pools:
		if not p.clips.is_empty():
			total += p.weight
	var r := randf() * total
	for p in pools:
		if p.clips.is_empty():
			continue
		r -= p.weight
		if r <= 0.0 and p.weight > 0.0:
			return p
	return pools[0]

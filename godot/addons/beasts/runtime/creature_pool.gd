class_name CreaturePool
extends Resource
## A pool of clips for CreatureWanderer: it plays one of its clips at random, or all of them in order (sequence).
## Unity: BeastAnimationSet.Pool.

@export var name := ""
@export var weight := 1.0
@export var clips := PackedStringArray()
## play the clips in order instead of picking one
@export var sequence := false
## root-motion locomotion: the creature steers while this plays
@export var moves := false
## root motion may lift it off the ground (a dragon's takeoff, flight and landing); other pools keep it at its height
## and settle it back down if it was left up in the air
@export var vertical := false
## seconds a looping clip is held
@export var hold := Vector2(3, 6)
## seconds to hold the last frame of a one-shot clip (lying dead)
@export var hold_after := 0.0
## the pool to play next; empty = a random one
@export var next := ""
## after this pool, move the creature this far (random in the range, random heading) before the next one: a burrowed
## centipede travels underground and surfaces somewhere else; 0 = stay
@export var relocate := Vector2.ZERO

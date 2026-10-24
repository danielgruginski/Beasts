# Beasts

Enemy animals for the colony sim / RPG, built procedurally in Blender like the goblins and insectoids. Both are installed
in Unity (MedievalSetting, `Assets/Beasts`), with shared code in the `beast_*` modules:

- the **grey wolf**: model, rig, three coats and 12 clips;
- the **giant rat**: model, rig, three coats and 10 clips (see [Giant rat](#giant-rat));
- the **woolly rhino**, the woods' solo boss: model, rig, one coat, a removable spear and 13 clips (see
  [Woolly rhino](#woolly-rhino));
- the **cave bear**: model, rig, two coats and 13 clips (see [Cave bear](#cave-bear));
- the **woolly mammoth**: model, rig with a six-bone trunk, two coats and 12 clips (see [Woolly mammoth](#woolly-mammoth));
- the **red deer stag** (prey): model, rig, one coat and 11 clips, exported, not yet in Unity (see [Red deer stag](#red-deer-stag));
- the **dungeon ooze**, an amoeba-like jelly with pseudopods that eats what it finds, adventurers included: model,
  see-through shell with the remains inside, rig and 10 clips, in Unity with its own jelly shader (see [Dungeon ooze](#dungeon-ooze));
- the **farm animals** (2026-10-20): goat, sheep, cow, horse and pig on the red deer's body (`farm_body.Hoofed`, one
  class warped to each animal) and a hen on a bird rig of her own; 3-4 coats and 11-12 clips each, in Unity through
  `FarmSetup.cs` and `Scenes/Farm_Test`. Built headless into `blender/farm_<name>.blend`:
  `blender.exe -b --factory-startup --python tools/farm_run.py -- goat build review coats clips lowest sheets export`
  (see HANDOFF.md, "Farm animals");
- the **zombie wolf** (2026-10-23, the undead batch): the wolf dead and risen on the wolf's own skeleton, so the
  wolf's clips play on it unchanged; three coats; exported with a Unity setup, not installed yet (see
  [Zombie wolf](#zombie-wolf));
- the **giant bat** (2026-10-23, Daniel's card game): wolf-sized body, 2.9 m of leathery wings on the dragon's membrane
  code, always in the air; seven clips; exported with a Unity setup, not installed yet (see [Giant bat](#giant-bat));
- the **giant turtle** (2026-10-23, Daniel's card game): a 2.6 m mossy shell with three knobbed keels on elephantine
  legs, a snapping turtle's hooked beak; seven clips including Withdraw into the shell; exported with a Unity setup,
  not installed yet (see [Giant turtle](#giant-turtle));
- the **leech** (2026-10-23, Daniel's card game): a 1.8 m swamp leech, a chain that loops like an inchworm, a toothed
  oral sucker, swelling pulses; five clips; exported with a Unity setup, not installed yet (see [Leech](#leech));
- the **golden eagle** (2026-10-24, "one of the models we need is an eagle or a falcon"): at natural size (2.03 m
  span), layered feather cards with their own undersides on 86 bones, golden and bald presets; revised the same day
  ("Yes, fix them", "the head looks like a vulture structure"): an eagle's head and beak, a broad wing, a tucked fold
  with scapulars, shorter legs (a third pass on the folded wing was reverted at Daniel's call); then animated ("Lets
  accept the issue and animate it"): ten clips on the ground and in the air (perched idle, walk, take-off, flap and
  glide loops, a stoop with a talon strike, landing, screech, hit, death), exported with a Unity setup, not installed
  yet (see [Golden eagle](#golden-eagle)).

![The wolf in the bind pose](docs/images/wolf_34.png)

Blender file: `blender/beasts.blend`, scenes **Wolf**, **Rat**, **Rhino**, **Bear**, **Mammoth**, **Deer** and **Ooze**. It is not in the repo, and neither are `export/`,
`textures/` or `renders/`. Everything in them is rebuilt from `src/`, starting from any Blender file.

## Rebuild

In Blender (Python console or the MCP). `show()` creates the creature's scene if needed and puts it on screen. Run
it in its own call before `build_all()`: a scene switch applies only after the call returns.

```python
import sys; sys.path.insert(0, r"E:\Unity\Projects\GameArtGeneration\Beasts\src")
import wolf_build
wolf_build.show()
wolf_build.build_all()     # body -> rig -> weights -> UVs -> 3 painted coats -> 12 clips (~40 s)
wolf_build.export()        # export/Wolf.fbx, Textures/T_Wolf*.png, Anims/Wolf@<clip>.fbx + wolf_clips.json

import wolf_anim
wolf_anim.use("Lunge")     # preview a clip on the rig (the skeleton plays in place; Motion carries the travel)
wolf_anim.clear()          # back to the bind pose
wolf_build.show()          # Wolf scene on screen, material preview

import rat_build
rat_build.show()           # the Rat scene on screen (in its own call: the switch applies after the call returns)
rat_build.build_all()      # (~35 s)
rat_build.export()         # export/Rat.fbx, Textures/T_Rat*.png, Anims/Rat@<clip>.fbx + rat_clips.json

import rhino_build
rhino_build.show()         # the Rhino scene on screen (in its own call)
rhino_build.build_all()    # body -> rig -> weights -> UVs -> coat -> spear split off -> 13 clips (~40 s)
rhino_build.export()       # export/Rhino.fbx (RhinoBody + Spear), Textures/T_Rhino.png, Anims/Rhino@<clip>.fbx + rhino_clips.json
rhino_build.build_model()  # just the model (body, rig, weights, UVs, coat; the spear still joined), for iterating

import bear_build
bear_build.show()          # the Bear scene on screen (in its own call)
bear_build.build_all()     # body -> rig -> weights -> UVs -> 2 coats -> 13 clips (~40 s)
bear_build.export()        # export/Bear.fbx, Textures/T_Bear.png + T_Bear_Old.png, Anims/Bear@<clip>.fbx + bear_clips.json

import mammoth_build
mammoth_build.show()       # the Mammoth scene on screen (in its own call)
mammoth_build.build_all()  # body -> rig -> weights -> UVs -> 2 coats -> 12 clips (~45 s)
mammoth_build.export()     # export/Mammoth.fbx, Textures/T_Mammoth.png + T_Mammoth_Dark.png, Anims/Mammoth@<clip>.fbx + mammoth_clips.json

import deer_build
deer_build.show()          # the Deer scene on screen (in its own call)
deer_build.build_all()     # body -> rig -> weights -> UVs -> coat -> 11 clips (~40 s); build_model() for the model alone
deer_build.export()        # export/Deer.fbx, Textures/T_Deer.png, Anims/Deer@<clip>.fbx + deer_clips.json
deer_build.review()        # renders/deer_<view>.png; review_test_pose(), review_joins(), clip_sheets() (deer_clip_<Name>.png)

import ooze_build
ooze_build.show()          # the Ooze scene on screen (in its own call)
ooze_build.build_all()     # shell -> contents -> UVs -> 2 textures -> materials -> rig + weights -> 12 clips (~45 s)
ooze_build.export()        # export/Ooze.fbx (OozeBody + OozeContents), Textures/T_Ooze*.png, Anims/Ooze@<clip>.fbx + ooze_clips.json
ooze_build.review()        # renders/ooze_<view>.png (EEVEE); clip_sheets() -> ooze_clip_<Name>.png; ooze_anim.report()
```

Builds are not bit-identical from run to run: the voxel remesh varies slightly, which moves the decimated mesh and
the UVs. Always export after a rebuild, so the FBX and the textures in `textures/` match.

| Script | Does |
|---|---|
| `wolf_body.py` | Landmarks, parts (lofts and ellipsoids), stylised fur tufts, voxel fuse, crease fillet, face sculpt, decimation; the lower jaw, tongue, teeth and eyes as separate pieces; `rest_bones()` |
| `wolf_rig.py` | Heat-map skinning, rigid jaw/tongue/teeth/eyes, jowls that follow the jaw, a stress-test pose |
| `wolf_paint.py` | Seams and unwrap; per-texel painted coats (grey, black, white) |
| `wolf_anim.py` | Clips keyed from computed bone matrices: trunk/spine/neck/tail bends, 2-bone leg IK + pastern/hock angle, gaits |
| `rat_body.py`, `rat_rig.py`, `rat_paint.py`, `rat_anim.py`, `rat_build.py` | The same for the giant rat; the tail is a separate ringed shell weighted along its length |
| `rhino_*.py`, `bear_*.py`, `mammoth_*.py`, `deer_*.py` | The same for the woolly rhino, the cave bear, the woolly mammoth and the red deer (body, rig, paint, anim, build) |
| `farm_body.py`, `farm_rig.py`, `farm_paint.py`, `farm_anim.py`, `farm_build.py`, `farm_goat.py` ... `farm_pig.py` | The hoofed farm animals: the deer's recipe as a class in deer units, warped to each species; skinning, painter, clips and builds shared; one species module each |
| `chicken_body.py`, `chicken_anim.py`, `chicken_paint.py`, `chicken_build.py` | The hen: bird body and rig, her own pose system (shank tilt + two-bone leg IK), plumage, build |
| `zwolf_body.py`, `zwolf_rig.py`, `zwolf_paint.py`, `zwolf_anim.py`, `zwolf_build.py`, `tools/zwolf_run.py` | The zombie wolf on the wolf's skeleton: starved body, bald patches, the torn flank with rib bars, torn ear, bared teeth; the rot painter; the wolf's clips; headless build (see [Zombie wolf](#zombie-wolf)) |
| `bat_body.py`, `bat_anim.py`, `bat_paint.py`, `bat_build.py` | The giant bat: fused fur body, lofted arms, fingers and legs, the dragon's membranes with a bat `WingSpec`; its own small pose system with the dragon's wing strokes; built headless by `tools/creature_run.py` (see [Giant bat](#giant-bat)) |
| `turtle_body.py`, `turtle_anim.py`, `turtle_paint.py`, `turtle_build.py` | The giant turtle: fused skin, a parametric carapace (closed shell, keels, scutes), plastron and bridges; beast_anim's quadruped clips with the neck sliding into the shell (`p.retract`) (see [Giant turtle](#giant-turtle)) |
| `leech_body.py`, `leech_anim.py`, `leech_paint.py`, `leech_build.py` | The leech: a ringed tube built ring by ring with a toothed cup and a rear disc; a chain posed along curves (flat stretches, fitted arches and Beziers), swell bones for the pulses (see [Leech](#leech)) |
| `eagle_body.py`, `eagle_pose.py`, `eagle_paint.py`, `eagle_build.py` | The golden eagle: fused body, the beak built from its profiles, feet and wing flesh pieces, layered feather cards (`Fe`): a bone per primary and per tail feather, the secondaries with the greater coverts on a two-bone row, the tertials along the arm on one, scapulars; the perched and spread poses (folded, the wing one stack leaning in over the flank); scallop and feather-card painter with two presets; the overlap check and the before/after views; the clips' checks, renders and export (see [Golden eagle](#golden-eagle)) |
| `eagle_anim.py` | The eagle's ten clips on eagle_pose's pose system: wing strokes with a fold split into a rigid lay and an in-plane fold (no card crosses another on the way), legs with the thigh held to the trunk (knee and ankle IK) and the toes kept on their spots, the height in the skeleton (see [Golden eagle](#golden-eagle)) |
| `beast_review.py`, `tools/creature_run.py` | Headless builds in files of their own: scene, game cameras, the wolf appended for scale, render sheets, lowest vertex per clip, a root-motion trace, a UV overlap count; the runner (`-- <creature> <steps>`) |
| `tools/before_after.py` | Labelled before/after sheets from two folders of renders (system Python with Pillow, not Blender; 2026-10-24, the eagle's revision) |
| `ooze_body.py`, `ooze_contents.py`, `ooze_paint.py`, `ooze_rig.py`, `ooze_anim.py`, `ooze_scene.py`, `ooze_build.py` | The dungeon ooze: a distance-field shell meshed with openvdb, the contents, charted UVs and per-texel paint without Cycles bakes, the rig, the clips and their checks, EEVEE review renders (see [Dungeon ooze](#dungeon-ooze)) |
| `beast_coat.py` | Long coats: coat volumes (lofts), hem fringes snapped to their volume or dropped onto the body, clumps, the hair's root-to-tip `t` |
| `beast_body.py` | Mesh helpers and the body pipeline: `fuse_body` (voxel fuse, fillet, sculpts, decimate, edge flips, fold relaxing), `build_tufts`, `sculpt_fur`, `join_pieces` |
| `beast_paint.py` | Seams from the skin weights plus the creature's cuts, unwrap (with a guard against blown-up degenerate islands), data bakes, fur strokes, texture writing |
| `beast_anim.py` | Species, Pose, leg IK, gaits (walk, trot, gallop, bound), tail drag, key tracks, clip keying, `ground_report` |
| `beast_rig.py` | Armature from a bone table (Generic rig), heat-map skinning, pose maths for keyed clips (from the insectoids) |
| `beast_scene.py`, `beast_common.py` | Cameras, lights, renders; lofts, noise, gutter fill (from the insectoids) |
| `beast_export.py` | FBX for Unity |

## Budget (colony camera, ~40 m at 50°, no LODs)

| Part | Triangles |
|---|---|
| Fur body (incl. nose) | ~4,000 |
| Lower jaw, tongue | 392, 108 |
| Teeth, eyes | 232, 120 |
| **Wolf** | **4,851** |

One material, one 1024² texture: RGB is colour and A is smoothness (URP Lit: Smoothness Source = Albedo Alpha).
The coats are `T_Wolf` (grey/timber), `T_Wolf_Black` and `T_Wolf_White`, all on the same UVs.

Size: 1.71 m nose to tail tip, 0.78 m at the withers, 1.06 m to the ear tips. The head is enlarged 12%
(`HEAD_K`) so it reads from the colony camera. A warg for goblin riders would be this wolf scaled up, with a saddle
on `Socket_Saddle`.

## How it is built

- **Body:** lofted trunk, neck, legs, tail, muzzle and ears, plus ellipsoids (cranium, cheeks, jowls, thighs, ruff,
  paws and toes). These are fused by a voxel remesh (4 mm), symmetrised, and their creases filleted. The face is
  sculpted (eye sockets, brow, nostrils, cupped ears), with a light fur-noise sculpt along the fur flow. The mesh is
  then decimated to ~4k triangles (the face and legs keep more), and the triangles cleaned up with edge flips.
- **Fur silhouette:** 33 hand-placed tufts (curved cones: cheek ruff, neck mane, hackles, brisket and belly
  fringe, elbows, breeches, tail) fused into the body. The noise sculpt alone decimates away.
- **Mouth:** the upper muzzle is a box section whose lips hang below the top of the lower jaw. The upper teeth hang
  from the palate into the closed jaw, so with the mouth shut only the fang tips show. The jaw, tongue and lower teeth
  are a separate shell on the `Jaw` bone, and the bottom of the jowls follows the jaw part of the way.
  ![Jaw open in the stress-test pose](docs/images/wolf_jaw_test.png)
- **UVs:** seams along hidden lines. They run down the belly and throat and up between the hind legs, under the chin
  and through the palate, down the inside of each leg and under the tail. The ears are split front and back and the
  paw soles cut off. Islands come from the skin weights; the head is at 1.6x and the eyes at 3x density.
  `renders/uv_layout_wolf.png` shows the layout.
- **Texture:** painted per texel from Cycles bakes of position, normal, part id and AO. Fur strokes are noise
  averaged along the fur flow, so they run continuously across seams. Grey coat: charcoal grizzled saddle, buff
  flanks, cream underside and face mask, dark tear lines, cinnamon legs and ears, a dark stripe down the forelegs,
  a dark-topped tail with a black tip, amber eyes, black lips and nose.

## Clips (30 fps)

| Clip | Length | Notes |
|---|---|---|
| Idle / IdlePant | 4.0 s / 3.0 s loops | looks around, ear flicks; panting with the tongue out |
| Walk / Trot / Run | 0.8 / 0.53 / 0.4 s loops | lateral walk 1.0 m/s, diagonal trot 2.06 m/s, rotary gallop 5.5 m/s (root motion) |
| Bite | 1.1 s | event `Bite` at 0.47 s |
| Lunge | 1.5 s | leaps 1.6 m (root motion), event `Bite` at 0.87 s |
| Threat | 2.4 s | head low, ears pinned, jaw chattering |
| Howl | 3.5 s | event `Howl` at 0.8 s |
| Hit | 0.5 s | |
| Death / GetUp | 2.2 s / 1.5 s | collapses onto its side (event `Dead` at 1.9 s); GetUp reverses the collapse |

Events call `OnBeastEvent(name)` on the wolf; `BeastEvents` raises `EventFired` for damage and sound.

## Unity

![The clips posed in Unity, a goblin for scale](docs/images/unity_lineup.png)

```
powershell -ExecutionPolicy Bypass -File tools\install_to_unity.ps1 -Project E:\Unity\Projects\MedievalSetting
```

Then **Tools > Beasts > Rebuild Wolf** (runs by itself the first time). A report and renders go to
`Logs/WolfSetup`. It creates:

- `Materials/M_Wolf`, `M_Wolf_Black`, `M_Wolf_White` and `M_Wolf_Brown` (the grey coat, tinted);
- `Prefabs/Wolf`: Animator, `BeastAppearance` (random coat and size) and `BeastEvents`;
- `Animation/WolfAnims`: clip pools for `BeastRandomAnimator`;
- `Scenes/Beasts_Test`: a pack of 7 wolves and 8 goblins on random clips. Press Play; the buttons make every wolf
  lunge, howl and so on.

The runtime and editor scripts are copies of the insectoids' (`Beasts` namespace), so the packages don't depend on
each other.

## Skeleton (Unity Generic)

`Root` and `Motion` sit at the origin, point up with +Z toward the wolf's front, and are siblings: `Motion` carries
the root motion and nothing hangs from it (see `../Insectoids/HANDOFF.md`).

- **Spine:** Hips, Spine1, Spine2, Chest, Neck1, Neck2, Head.
- **Head:** Jaw, Tongue1, Tongue2, EarL/R.
- **Tail:** Tail1–5.
- **Front legs:** ScapulaL/R, UpperArm, Forearm, FrontPaw, FrontToes.
- **Hind legs:** ThighL/R, Shin, HindFoot, HindToes.

That is 41 bones including the sockets. Legs and spine bend about their local X: on the legs Z points forward, on
the spine Z points up.

| Socket | Parent | Axes | For |
|---|---|---|---|
| Socket_Saddle | Spine2 | +Y up, +Z forward | warg saddle / rider |
| Socket_Head | Head | +Y up, +Z forward | head armour, helmet |
| Socket_Mouth | Jaw | +Y up, +Z forward | carried prey, a bone |
| Socket_Collar | Neck1 | +Y along the neck, +Z up | spiked collar |

## Giant rat

![The rat in Unity: walking and reared up, a goblin for scale](docs/images/rat_unity_close.png)

A sewer rat the size of a dog: 0.95 m nose to rump plus a 0.9 m naked tail, 0.46 m at the arched back. It has a
mangy crest down the spine, a pointed snout with orange incisors that always show, whiskers, big round thin ears,
beady bulging eyes (black with a red rim), pink hands and plantigrade feet. Blender scene **Rat**
(`RAT_*` collections and cameras).

| Part | Triangles |
|---|---|
| Fur body (incl. nose) | ~2,100 |
| Tail (separate shell, 8 bones) | 464 |
| Lower jaw, incisors, whiskers, eyes | 264, 88, 128, 120 |
| **Rat** | **3,164** |

One 1024² texture: `T_Rat` (brown sewer rat), `T_Rat_Black`, `T_Rat_Plague` (pale, bald scabby patches, red eyes).
In Unity, `M_Rat`, `M_Rat_Black` and `M_Rat_Plague`, rolled by `BeastAppearance` (size 0.85–1.15).

| Clip | Length | Notes |
|---|---|---|
| Idle | 3.0 s loop | sniffing in bursts, looks around, ear flicks |
| Rear | 2.8 s | rears up on its hind legs, hands to the chest, sniffs the air |
| Walk / Run | 0.53 / 0.33 s loops | scurry 0.86 m/s, half-bound 2.7 m/s with the spine flexing (root motion) |
| Bite | 0.8 s | event `Bite` at 0.4 s |
| Lunge | 1.2 s | leaps 0.8 m, event `Bite` at 0.73 s (root motion) |
| Threat | 2.0 s | back humped, incisors bared, tail lashing, a front-foot stamp |
| Hit | 0.47 s | knocked back and to its left, forelegs buckling, a small rebound |
| Death / GetUp | 1.8 s / 1.1 s | flips onto its back, legs curled (event `Dead` at 1.6 s); GetUp reverses the flip |

It uses the wolf's bone names (8 tail bones, no tongue), with `Socket_Back`, `Socket_Head` and `Socket_Mouth`.
Unity: **Tools > Beasts > Rebuild Rat** (`Logs/RatSetup`); `Scenes/Beasts_Test` holds 10 rats next to the wolves.

## Woolly rhino

The woods' optional solo boss (design: the "Woods Boss" doc, written for a boar; Daniel swapped it for a woolly
rhino on 2026-10-07). A Coelodonta: a high hump falling to a lower rump, the head carried hanging 45° down, a long
flattened front horn from a broad base on the nose tip, swept forward, and a short upright second horn, cup-shaped
ears, short columnar legs on three-toed feet, and a mammoth's coat: a cape of long hair over the hump and a skirt
hanging from the flanks, both with ragged hems, and feathering over the feet. A snapped boar spear stands out of
the left shoulder. 1.84 m at the hump, 3.0 m snout to rump, the horn reaches 0.5 m past the snout. Blender scene
**Rhino** (`RHN_*`), with an instance of the wolf beside it for scale.

![The woolly rhino](docs/images/rhino_34.png)

| Part | Triangles |
|---|---|
| Fused body (volumes: trunk, hump, cape, skirt, head, legs) | 2,000 |
| Hair: fringes along the hems and round the feet, a few clumps (beard, breeches, tail) | 1,970 |
| Horns, ears, chin, eyes | 308, 156, 180, 120 |
| **RhinoBody** | **4,734** |
| **Spear** (its own object, on the Chest bone) | **210** |

One 1024² texture, `T_Rhino` (no other coats: it is a one-off).

How it differs from the wolf and the rat:

- **The coat is two layers.** The volumes are fused like the wolf's body. The hair is separate low-poly shells:
  *fringes* (thick curtains along each volume's edge, folded into ridges and valleys, the hem a zig-zag of uneven
  points) and a few clumps. Each hair vertex is skinned like the skin at its root (`root` attribute), so it rides
  without stretching. Fused locks melted away at this budget, and separate clumps in rows read as teeth.
- **The head is built in its own frame** (`rhino_body.hx` / `hx_inv`: horizontal, then hung 45° down from the
  poll). Sculpt masks, the painter and the rig's masks work in head space.
- **The coat rides on the spine above the skirt's hem**: the legs swing inside the skirt (`rhino_rig._coat_on_trunk`).
- **The spear** is part of the mesh until after painting (one atlas), then split into `Spear`.

![Top: the Charge, the horn levelled ahead. Bottom: the Gore, the head drops, then tosses up and hooks](docs/images/rhino_attacks.png)

| Clip | Length | Notes |
|---|---|---|
| Sleep | 3.0 s loop | lying on its belly, legs folded, slow breathing, an ear twitch |
| Wake | 1.5 s | heaves up front end first, shakes its head, ends in the Idle stance |
| Idle | 2.5 s loop | breathing, head bob, a snort, ear flicks, tail swish |
| Walk / Run | 1.0 / 0.53 s loops | lateral walk 1.3 m/s, trot 3.75 m/s (root motion) |
| Charge | 0.33 s loop | head-down gallop, the horn levelled ahead like a lance, 9 m/s (root motion; play it faster for more) |
| Gore | 1.0 s | the horn attack: head drops, tosses up and hooks to its right; event `Bite` at 0.45 s |
| Paw | 1.2 s loop | the tell before a charge: head low, the right forefoot scrapes back twice |
| Daze | 2.0 s loop | staggering after a charge into an obstacle, legs splayed, head wobbling |
| Stamp | 1.3 s | rears its front end and slams down; event `Bite` at 1.0 s |
| Roar | 1.5 s | head up, a long bellow; event `Roar` at 0.3 s |
| Hit | 0.47 s | knocked back and to its left, forelegs buckling, a small rebound |
| Death | 2.0 s | collapses onto its right side, the spear standing up for looting; event `Dead` at 1.6 s |

Bones: the wolf's names with 3 tail bones and no tongue; sockets `Socket_Head`, `Socket_Horn` (the horn tip, for
the gore's effects), `Socket_Mouth`, `Socket_Back`, `Socket_Spear` (at the wound, +Y out of it).
Unity: **Tools > Beasts > Rebuild Rhino** (`Logs/RhinoSetup`): `M_Rhino`, `Prefabs/Rhino` (Animator, BeastEvents;
the spear is the child `Spear`), `Animation/RhinoAnims` (Paw leads into Charge, Sleep into Wake), and one rhino in
`Scenes/Beasts_Test`.

## Cave bear

A close-quarters brute (Daniel picked it on 2026-10-07 from a cave bear, war mammoth, warg and giant elk). Ursus
spelaeus: a hump over the shoulders, a steep domed forehead over a long muzzle, small round ears, plantigrade legs on
broad paws with long pale claws, and a shaggy coat (a mane over the neck and shoulders, a short belly fringe, fringed
forearms, breeches on the hind legs, cheek ruffs). 1.5 m at the hump, 2.5 m nose to tail; reared up it stands
2.7 m. Blender scene **Bear** (`BER_*`), with an instance of the wolf beside it for scale.

![The cave bear](docs/images/bear_34.png)

| Part | Triangles |
|---|---|
| Fused body (volumes: trunk, hump, cape, skirt, head, legs) | 2,280 |
| Hair: fringes (cape and belly hems, backs of the legs), clumps (elbows, breeches, tail) | 1,594 |
| Lower jaw, tongue, teeth (fangs that show when it roars) | 180, 60, 120 |
| Ears, eyes, claws, nose | 156, 100, 200, 20 |
| **BearBody** | **4,710** |

Two 1024² coats on the same UVs: `T_Bear` (dark brown, grizzled) and `T_Bear_Old` (greyer, more scars).

It is built like the rhino (shared `beast_coat`, `HeadFrame`, `coat_on_trunk`), with a few differences:

- **Plantigrade feet** on all four legs: the wrists and heels sit near the ground and the long feet keep their leg
  weights even inside the coat (`bear_rig._leg_share`), or the trunk dragged them.
- **The mouth** has hanging lips over the jaw line so no gap shows when it opens, and a band-limited lips mask in
  the painter (one-sided, it painted the chin black).
- **Rearing** turns the whole trunk about the hip joints (`beast_anim.pivot`); the forelegs ride with the chest and
  the neck and head pitch back so the face looks ahead.

![Rows: Idle, Walk, Run, Swipe / Bite, Slam (rearing), Slam (the crash), Hug / Rear, Roar, Sleep, Death](docs/images/bear_clips.png)

| Clip | Length | Notes |
|---|---|---|
| Sleep | 3.0 s loop | lying on its belly, head on its forepaws, slow breathing, an ear twitch |
| Wake | 1.5 s | heaves up front end first, shakes its head, ends in the Idle stance |
| Idle | 3.0 s loop | breathing, a look round, a forepaw shifted, a sniff of the air, ear flicks |
| Walk / Run | 1.07 / 0.43 s loops | heavy lateral walk, head low and swinging, 1.03 m/s; bounding gallop 5.3 m/s (root motion) |
| Swipe | 1.0 s | a right-paw haymaker from the side across the front; event `Bite` at 0.42 s |
| Bite | 1.0 s | coils, lunges with the right forepaw stepping in, head thrust out level, bites and shakes; event `Bite` at 0.4 s |
| Slam | 1.4 s | rears and crashes down on both forepaws; event `Bite` at 0.77 s |
| Hug | 2.0 s | rears, opens its forelegs wide and crushes them shut; event `Bite` at 0.73 s |
| Rear | 2.7 s | stands up to its full height, paws out at chest height, and roars upward; event `Roar` at 0.9 s |
| Roar | 2.0 s | swats the ground with a forepaw, then roars with the head thrust out and swinging; event `Roar` at 0.3 s |
| Hit | 0.47 s | knocked back and to its left, forelegs buckling, a small rebound |
| Death | 2.0 s | sags, rolls onto its left side, a last paw twitch; event `Dead` at 1.6 s |

Bones: the wolf's names with 2 tail bones and no tongue; sockets `Socket_Head`, `Socket_Mouth`, `Socket_Back`,
`Socket_PawL`, `Socket_PawR` (the forepaws, for the swipe's and the slam's effects).
Unity: **Tools > Beasts > Rebuild Bear** (`Logs/BearSetup`): `M_Bear`, `M_Bear_Old`, `Prefabs/Bear` (Animator,
BeastAppearance rolling the two coats 2:1 and the size 0.92-1.08, BeastEvents), `Animation/BearAnims` (Sleep leads
into Wake), and two bears in `Scenes/Beasts_Test`.

## Woolly mammoth

Mammuthus primigenius, a big bull (asked for on 2026-10-08). 3.1 m at the shoulder hump, the back falling in one long
slope to a low rump, a high domed skull with a dip behind it and the forehead sloping in one line down into a thick trunk root, small furry ears, a trunk hanging nearly to the ground
with its tip curled out, long tusks spiralling down, out, forward and up with the tips turning in, columnar legs on
round feet with pale toenails, a short tufted tail. The coat hangs in three tiers down the flanks (the hump's hem,
mid flank, the skirt's hem), with long hair on the cheeks, a bib at the chest, hair down the backs of the legs and breeches.
Blender scene **Mammoth** (`MAM_*`), with an instance of the wolf beside it for scale.

![The woolly mammoth](docs/images/mammoth_34.png)

| Part | Triangles |
|---|---|
| Fused body (trunk volume, skirt, head, the trunk's stump, legs) | 2,600 |
| Hair: three tiers of fringes, cheeks, strips down the legs, clumps (bib, breeches, tail) | 2,156 |
| Trunk (a separate tube on Trunk1-6) | 340 |
| Tusks, lower lip, ears, eyes | 736, 180, 156, 100 |
| **MammothBody** | **6,268** |

Two 1024² coats on the same UVs: `T_Mammoth` (reddish brown, ginger tips) and `T_Mammoth_Dark` (near black).

How it differs:

- **The trunk is a separate clean tube** (its root hides a short stump fused into the face), skinned along Trunk1-6
  by arc length (`mammoth_rig._skin_trunk`). Fused and decimated, a tube this thin twisted into long diagonal
  facets; the legs had the same problem until `_dec_weight` kept more triangles on them.
- **No coat volume over the hump.** A volume wider than the body left a ledge (like a saddle blanket), so the hump's
  long hair is fringe strips rooted on the fused body along the flank's widest line; higher up, hair hanging off the
  rounded back stands out as fins.
- **The trunk's bones** are posed through `Species.trunk_n` / `Pose.trunk` in `beast_anim` (+ pitch curls it toward
  its front); `mammoth_anim` names its shapes (HANG, RAISED, TUCKED, TO_MOUTH, REACH, ON_GROUND).

![Rows: Idle, Walk, Run, Charge / Trumpet, TuskSwipe, Stomp (rearing), Stomp (the slam) / Graze (reach), Graze (to the mouth), Sleep, Death](docs/images/mammoth_clips.png)

| Clip | Length | Notes |
|---|---|---|
| Sleep | 4.0 s loop | lying on its belly, legs folded, the trunk out along the ground, slow breathing |
| Wake | 2.0 s | heaves up front end first, shakes its head, ends in the Idle stance |
| Idle | 3.0 s loop | breathing, the trunk swaying and sniffing, ear flaps, tail swish, weight shifting |
| Walk / Run | 1.6 / 0.8 s loops | lateral walk 1.38 m/s; an elephant's amble (no suspension) 4.5 m/s (root motion) |
| Charge | 0.67 s loop | head down with the tusks levelled, trunk tucked under the chin, ears pinned, 6.3 m/s (root motion) |
| Trumpet | 2.0 s | stamps, rears its head with the trunk raised high, ears flared; event `Roar` at 0.6 s |
| TuskSwipe | 1.2 s | winds up to its left, sweeps the tusks across to the right with a step in, hooking up; event `Bite` at 0.5 s |
| Stomp | 1.6 s | rears its front end up, trunk high, and slams both forefeet down; event `Bite` at 1.03 s |
| Graze | 4.0 s loop | the trunk reaches to the ground, grips, curls the grass up to its mouth, it chews |
| Hit | 0.5 s | a flinch, the trunk whipping |
| Death | 2.5 s | staggers, kneels, sinks onto its belly and slumps right, the tusks propping the head; event `Dead` at 2.2 s |

Bones: the wolf's names with 2 tail bones, no tongue, Trunk1-6; sockets `Socket_Head`, `Socket_Mouth`,
`Socket_Back` (on the hump: a rider or a howdah), `Socket_Trunk` (the tip), `Socket_TuskL` / `Socket_TuskR` (the
tips). Unity: **Tools > Beasts > Rebuild Mammoth** (`Logs/MammothSetup`): `M_Mammoth`, `M_Mammoth_Dark`,
`Prefabs/Mammoth` (Animator, BeastAppearance rolling the two coats 2:1 and the size 0.92-1.06, BeastEvents),
`Animation/MammothAnims` (Sleep leads into Wake), and one mammoth in `Scenes/Beasts_Test`.

## Red deer stag

Cervus elaphus, a mature stag in autumn: prey for the hunting grounds (hide and venison), asked for on 2026-10-11.
1.20 m at the withers, 2.0 m nose to rump, 2.37 m to the antler tips; a deep chest, a slim waist, a rounded rump,
long thin legs on cloven hooves with dewclaws, a long thick neck with a full, shaggy rut mane under the throat, a long
head with a blunt, deep muzzle and a broad nose pad, big ears, large eyes (~1.5x), a short tail over a pale rump
patch, and antlers 0.93 m across (brow, bez and trez tines and a crown of three each side, the tines angled forward
and up). Blender scene **Deer** (`DER_*`), with an instance of the wolf beside it for scale.

| Part | Triangles |
|---|---|
| Fused body (trunk, neck, mane, head, shoulders and leg stumps, haunches, tail; incl. nose) | 2,522 |
| Lower legs (clean tubes grafted onto the stumps), hooves' claws and dewclaws | 864, 336 |
| Lower jaw, eyes, ears | 144, 120, 156 |
| **Body without antlers** | **4,142** |
| Antlers (lofted tubes, rigid on Head) | 1,248 |
| **DeerBody** | **5,390** |

One 1024² coat, `T_Deer`: grey-brown flanks with russet over the back, a grey-brown neck and a darker mane in long
locks, buff to cream belly, inner legs and rump patch (the tail's upper side dark), darker lower legs, a dark muzzle
and nose with a pale chin, a dark preorbital gland, brown grooved antlers with pale tips. The material is matte
(`deer_paint.matte`).

How it differs: **each leg is one surface in two parts**, a fused stump (upper arm to mid forearm, stifle to mid
gaskin) and a clean lofted lower leg stitched onto it (`deer_body._graft_legs`: fused and decimated, legs this thin
twist into diagonal facets), skinned down the leg by height; the **antlers** are lofted tubes (`PART['antler']`).
Bones: the wolf's names with **3 neck bones** (`Species(neck_n=3)`), 2 tail bones, no tongue; sockets `Socket_Head`,
`Socket_Mouth`, `Socket_Back`, `Socket_AntlerL` / `Socket_AntlerR` (the beams' tips). `deer_build.review_joins()`
renders the leg joins close up in the stress-test stride.

| Clip | Length | Notes |
|---|---|---|
| Idle | 4.0 s loop | breathing, a weight shift with a hind foot cocked, ear flicks, a tail flick, a slow look round |
| Graze | 5.0 s loop | head down at the grass (three neck bones), chewing, ears turning, a slow step forward (root motion 0.16 m a loop) |
| Alert | 1.5 s | head snaps up high, ears forward and stiff, tail up, a forefoot stamp; holds the end |
| Walk / Trot | 1.2 / 0.67 s loops | four-beat lateral walk 1.1 m/s, the head nodding; diagonal trot 2.9 m/s (root motion) |
| Run | 0.47 s loop | the flight gallop 8.1 m/s: long bounding strides, the back gathering and stretching, tail up over the rump patch, head forward (root motion) |
| Attack | 1.2 s | head down, a lunge forward and up with a twist of the antlers, the right forefoot stepping in; event `Bite` at 0.5 s |
| Hit | 0.5 s | a flinch sideways |
| Death | 2.2 s | the legs fold, it falls onto its left side, the head last with the antlers turned up; event `Dead` at 1.9 s; holds |
| Sleep / Wake | 4.0 s loop / 2.0 s | lying on its belly, legs folded under, the head low; rises hind end first |

Hooves slide at most 8 mm in Walk, Trot and Run (`deer_anim.slide_report`); the lowest vertex stays within 2.4 cm of
the ground in every clip (lying: the hooves).

## Dungeon ooze

An amoeba-like jelly that crawls through dungeons eating what it finds, adventurers included, asked for on
2026-10-12. It has a lumpy, see-through dome that spreads where it meets the floor, six blunt pseudopods, and a
wrinkled knot at the rear (the uroid, where a crawling amoeba's tail end bunches up). Inside it you can see a
dark-red nucleus (the weak spot), food vacuoles, and a half-digested adventurer: skull, two bones, a nasal helm,
coins, and a rusty sword that went in through its back and still sticks out. It is 3.0 x 2.9 m across with the pods
out and 1.2 m tall, hip-high on a person (`renders/ooze_scale.png` has a Humans body beside it). Blender scene
**Ooze** (`OOZ_*` cameras, floor and rim light).

![The ooze, 3/4 view](docs/images/ooze_34.png)

| Part | Triangles | Texture |
|---|---|---|
| `OozeBody`: the shell (dome, skirt, 6 pseudopods, uroid), open at the floor | 2,844 | `T_Ooze` 1024², linear masks: R tone (thin, mid, core), G shade, B detail, A opacity; the colour is the shader's |
| `OozeContents`: nucleus (and its hidden twin), 7 vacuoles, skull, femur, shin, helm, 7 coins, sword | 2,070 | `T_OozeContents` 512²: RGB colour, A smoothness |

How it differs from the furred beasts:

- **The shell is one distance field** (`ooze_body.field`), meshed with openvdb like the Humans skeleton's skull and
  decimated uniformly. Its parts: three ellipsoids for the mass plus a skirt; round cones along splines for the pods
  (`POD`, each 4 control points `(x, y, z, r)`, a swollen tip); balls for the uroid; low-frequency noise.
  - Below 10 cm the wall is carried straight down and leans out to the floor, so there is no undercut and no paper
    edge.
  - The sole is cut away, together with every down-facing sliver near the floor.
- **The contents sit at least 7 cm inside the field** (`ooze_contents`), except the sword.
- **UVs**: 14 charts (each pod, a top cap, four sides), plus a slit along each raised pod's underside. Texel density
  stays within 0.4–1.5x of the median.
- **Paint without Cycles**: `ooze_paint.texel_bake` rasterises the UVs in numpy. The shell's colour and opacity come
  from the field:
  - thickness: the thick core is darker and more opaque, the tips and the skirt's edge clearer;
  - AO;
  - streaks along the pods (cytoplasm streaming).

  These are written as masks, not colours. A colour preset (`ooze_paint.PRESETS`, the same as Unity's
  `OozeLook.Presets`: Green, Grey, Black, Ochre, Crimson) maps them through thin, mid, core and crevice colours.
- **Materials** (the Blender preview of the Unity look):
  - `M_Ooze`: the masks coloured by a preset (`shell_material(preset=...)`), dithered alpha. Opacity is the texture
    times the preset's opacity, plus a fresnel rim. It has a faint emission, is two-sided,
    smoothness 0.9, and casts a transparent shadow.
  - `M_OozeContents`: opaque.

**Rig** (`ooze_rig`, 47 bones):
- Root, Motion;
- Body, then:
  - HalfL / HalfR, the mass's halves, which part in Split. Each carries its own dome (DomeL / DomeR: leaves for
    squash, stretch and lean, which move as one Dome in every other clip) and its side's pods;
  - WaistTop / WaistLow, the middle band, which pinches to a strand in Split;
  - Tail (the uroid);
- `<Pod>1–3` for Reach, Back and Bud (left) and Lead, Side and Probe (right);
- Gut, with one bone per floating piece: Nucleus and Nucleus2 (its twin hidden inside, which divides out in Split),
  Skull, Femur, Shin, Helm, Sword, Coins, Vac1–7;
- sockets: `Socket_Gut` (a swallowed victim), `Socket_Mouth` (a grabbed one, carried in by Engulf) and `Socket_Spit`
  (the Probe's tip).

How the shell is weighted:
- by a soft minimum over the shape's pieces (`ooze_body.parts`);
- along each pod, by hat weights on the chain, so a stretched pod stretches along its whole length;
- in the mass, upper or lower by height, split left/right across the middle;
- smoothed;
- after smoothing, the middle band is re-split onto the waist (`_waist_pass`), and a vertex that is mostly pod takes
  its pod's side;
- below 16 cm handed to the lower mass, so the rim stays on the floor.

Pods are posed by bending, by stretching (child bones slide along the chain) or by laying the chain along a curve to a
target (`OozePose.curve`). Whatever sits in the domed part of the mass follows the Dome by the skin's own weight.

| Clip | Length | Notes |
|---|---|---|
| Idle | 3.0 s loop | the dome breathes, a wave runs down each pod, the uroid wags, the contents drift, the nucleus pulses |
| Crawl | 2.0 s loop | amoeboid flow at 0.6 m/s (root motion 1.2 m a loop): the leading pods reach out, the mass surges into them, the rear pods and the uroid trail, the contents slosh |
| Lash | 1.33 s | the Probe rears back and slams down in front; event `Hit` at 0.67 s |
| Grab | 1.47 s | Reach shoots out 0.5 m, swells round what it caught and hauls it back; event `Hit` at 0.6 s |
| Engulf | 2.67 s | Reach and Lead close round a victim in front, the dome rolls over it and the Probe comes down on top; `Socket_Mouth` carries the victim in to `Socket_Gut`; events `Grab` at 0.73 s, `Engulf` at 1.53 s |
| Spit | 1.47 s | the Probe aims forward and up, the dome contracts and pumps; event `Spit` at 0.7 s (from `Socket_Spit`) |
| Hit | 0.8 s | a jolt: a damped wobble, the pods flinch |
| Death | 2.33 s | collapses into a puddle with a last shudder: raised pods flop, the vacuoles pop one by one, the remains sink to the floor; event `Dead` at 1.87 s; holds |
| Puddle / Rise | 3.0 s loop / 1.67 s | lying flat and alive (an ambush), rippling; rises from it with an overshoot; event `Risen` at 1.0 s |
| Split | 2.5 s | binary fission, for a big ooze: the pods draw in, the nucleus divides, the halves part with a waist pinching between them; event `Split` at 1.93 s (the strand snaps: the game swaps in two oozes, behind a splash) |
| Reform | 1.67 s | such a new ooze taking shape: from a blob (Split's end pose, half of it) the pods push out with an overshoot |

The Hit clip also has an event, `Hurt` at 0.07 s, for a splash.

`ooze_anim.report()` checks every clip. Last run:
- the rim stays within 4 cm of the floor;
- the shell goes at most 4.4 cm under the floor (the Lead pod in Engulf);
- no content vertex leaves the shell (a majority vote of three upward rays);
- the remains lie on the floor in Death and Puddle (`_sink_z` reads their lowest points from the mesh: a centroid
  target sank the rotated helm through the floor).

**In Unity** (2026-10-12):
- **Rebuild:** Tools > Beasts > Rebuild Ooze (`OozeSetup.cs`). It writes a report, renders and a root-motion trace
  to `Logs/OozeSetup`. It needs `Shaders/OozeJelly.shader` + `OozeJellyForward.hlsl`, which the install script now
  copies.
- **The jelly shader (`Beasts/OozeJelly`):**
  - two passes over the shell, the far side (back faces) first, then the near side;
  - the colour comes from four material colours (thin, mid, core, crevice) mapping T_Ooze's masks. `OozeLook` sets
    them per renderer with a MaterialPropertyBlock, so one material serves every colour;
  - premultiplied alpha: the diffuse fades with the opacity, the highlights don't;
  - opacity = the texture's alpha x `_Opacity` + a fresnel rim, a faint glow of its own colour, a small vertex wobble;
  - a shadow dithered by the opacity;
  - Forward+ lighting through `UniversalFragmentPBR`, so torches light it.
- **The contents** use URP Lit (`M_OozeContents`).
- **`OozeLook`:**
  - a colour preset (fixed, or random from a list), a size, which remains are hidden;
  - in an ooze bigger than 1x the remains keep their real size (done after the Animator, idempotently).
- **`OozeFx`** (built in code):
  - a slime trail while it moves (`OozeTrail`, shader `Beasts/OozeSlick`): splats that know about each other. The ooze
    paints soft, ragged splats at its rear edge into a small wetness field (128² R8, 0.1 m a texel x size, tied to the
    world and wrapping); one flat sheet round it shows slime where the field passes an edge threshold, its slope
    tilting the normal for a wet highlight. Splats merge into one sheet with smooth necks (no alpha piling up where
    they overlap). A new splat wells out from its middle over a second (`grow`: the drying in reverse), so none is
    stamped in whole, and as the field dries over 9 s the edges creep in and it breaks into puddles. No splat lands
    under the see-through body. (It replaced a TrailRenderer that folded on turns and showed its fresh end through the
    jelly, then a fold-free ribbon whose end still showed.)

    ![The slime trail in Unity: merged splats behind the ooze, drying into puddles further back](docs/images/ooze_unity_trail.png)

  - drips from under the raised pods' tips;
  - splashes on Hit, Hurt, Grab, Engulf, Dead, Split and Risen;
  - on Spit, an `OozeGlob` arcs from `Socket_Spit` to a target, splashes, and leaves a fizzing acid puddle.

  The trail and splashes live on an object beside the ooze, so they outlast it.
- **`OozeSplit`:** on the Split event it spawns two `childPrefab`s at the HalfL / HalfR bones, at 0.79x the size,
  in the same colour. Each keeps only the remains on its own side (worked out from the model by `OozeSetup`) and
  starts on Reform. `SplitInto` hands the two to the game. With `respawnAfter` (the test scene: 25 s) the big one
  only goes dormant and comes back rising from a puddle.
- **Prefabs**, each with an Animator, `OozeLook`, `BeastEvents` and `OozeFx`; renderer bounds padded 0.8 m for the
  reaching pods:
  - `Ooze`: random colour, 0.9–1.1x;
  - `GiantOoze`: 1.6x, green or black pudding, with `OozeSplit`;
  - `SmallOoze`: 0.5–0.6x, with no skull, helm or sword inside.
- **The clip pools** (`OozeAnims`, plus `GiantOozeAnims` with Split): Puddle leads into Rise, and so does Death.
  `Beasts_Test` has two oozes, three small ones and a giant.
- **Effect assets**, drawn by `OozeSetup`: `Textures/FX/` (drop, splat, flat mask), `M_OozeTrail` (Beasts/OozeSlick),
  `M_OozeDrop`, `M_OozePuddle` (URP Particles/Lit, with "preserve specular" off: on, every quad showed whole),
  `M_OozeGlob` and `Models/OozeGlob.asset`.
- **Checked:** avatar valid; Crawl 0.60 m/s, `dir=(0, 0, 1)`; 1.200 m per loop over 3 loops, with the Body's offset
  unchanged at every loop start.
- **The test scene and the renders no longer change the scenes open in the editor:** `BeastsTestScene.Build` fills
  the scene additively, and the ooze's renders use a preview scene.

![The ooze in Unity: the clips posed, a goblin for scale](docs/images/ooze_unity_lineup.png)

![Colour presets in Unity, with a giant black pudding, a small grey ooze and a goblin](docs/images/ooze_unity_presets.png)
![Split from the front, from above and at 3/4](docs/images/ooze_clip_split.png)
![Split in Unity: the giant just before the snap (the fold in its middle), and the two oozes it becomes](docs/images/ooze_unity_split.png)
![The effects: acid glob, puddle, splash and drips](docs/images/ooze_unity_fx.png)

## Warg

The goblin raiders' mount (2026-10-12), from Daniel's reference: a massive, shaggy, dark brown-grey wolf with yellow
eyes and bared fangs; the goblins' ones wear a saddle, a bridle and a bone war-mask. About 1.35x the wolf (withers
1.1 m, nose to rump 2.1 m). Blender scene **Warg** (`WRG_*` cameras, a wolf beside it for scale).

![The ridden warg, 3/4 view](docs/images/warg_34.png)

| Part | Triangles | Texture |
|---|---|---|
| `WargBody`: fused fur body 4.3k, jaw, tongue, teeth and eyes 0.9k, hair shells 1.9k | 7,072 | `T_Warg` (dark), `T_Warg_Ash`, `T_Warg_Black` 1024², A = smoothness; `T_Warg_Normal` for all three |
| `WargTack`: blanket, seat, girth, breast collar, stirrups, bridle, bit rings, reins | 1,564 | `T_WargTack` 512² + `T_WargTack_Normal` |
| `WargMask`: the bone war-mask, two horns | 304 | (the tack's) |

How it is built:

- **The wolf's recipe, made bigger** (`warg_body`): the wolf's landmarks edited for a deeper chest, broader skull,
  thicker legs and big paws, then mapped to the world by `hw()`, which enlarges the head, shortens and deepens the
  muzzle (`_mz`) and scales everything by `S = 1.35`. The masks, the painter and the rig read wolf units through
  `hw_inv`, so they read like the wolf's.
- **The shag is separate hair** (`beast_coat.clump`): staggered tiers of spiky locks round the neck (`TIERS`: the
  mane from the poll to the shoulders, each tier lying back over the next and stopping before the saddle), a bib
  under the throat, a belly fringe, rings of locks making the tail a brush (`TAIL_RINGS`), fringes down the backs of
  the forearms and single locks (cheeks, elbows, breeches). Each is rooted by a ray cast onto the fur and skinned like
  the skin at its root. (Fused tufts melted into lumps at this size.)
- **Eyes:** slanted almonds low at the stop under a heavy brow, laid onto a smooth fit of the socket.
- **Paint** (`warg_paint`, the wolf's painter): long painted locks with dark partings on the coat, and on each hair
  lock (its texels know its root: `bake_data(roots=True)`) strands down its length, a dark root and grizzled tips.
  The same relief makes the normal map (`beast_paint.write_normal_map`, image-space gradients within each island).
- **Tack** (`warg_tack`), for the ridden ones only: fitted onto the built body by ray casts (straps lie on the fur,
  the blanket drapes over the back, the mask is notched clear of the eyes). Weights are copied from the skin under
  each piece; the bridle and the mask ride on Head, the reins blend Head → Neck1 → Spine2. The info attribute holds
  the part and (along, across) for the painter: stitching inside the straps' edges, the blanket's ochre border, the
  mask's cracks and red war paint.

Clips (`warg_anim`): the wolf's twelve, every distance ×1.35, the gaits a little slower.

| Clip | Length | Notes |
|---|---|---|
| Idle / IdlePant | 4.0 s / 3.0 s loop | |
| Walk / Trot / Run | 0.93 / 0.6 / 0.47 s loop | root motion 1.16 / 2.48 / 6.36 m/s |
| Bite | 1.2 s | event `Bite` at 0.5 s |
| Lunge | 1.6 s | leaps 2.2 m, event `Bite` at 0.93 s |
| Threat, Howl, Hit | 2.4, 3.5, 0.5 s | `Howl` at 0.8 s |
| Death / GetUp | 2.2 / 1.5 s | onto its left side, `Dead` at 1.9 s |

**In Unity:** Tools > Beasts > Rebuild Warg (`WargSetup.cs`). `Prefabs/Warg` is wild (tack and mask off);
`Prefabs/WargRidden` is saddled and masked. The `WargTack` component switches the two meshes (`saddled`, `masked`)
and finds `Socket_Saddle` (`Seat`) for a rider. `BeastAppearance.target` puts the coat on `WargBody` only.

![In Unity, ridden, with a goblin for scale](docs/images/warg_unity_ridden.png)

![Clip poses in Unity: Idle, Walk, Trot, Run, Bite, Lunge, Howl, Death](docs/images/warg_unity_lineup.png)

Rebuild in Blender (Warg scene on screen):

```python
import warg_build
warg_build.show()
body, rig, report = warg_build.build_model()      # body, rig, weights, UVs, coats
import warg_tack; warg_tack.build(body, rig)      # the tack and the mask (work layer on: warg_build.work_layer(True))
warg_build.export()                               # clips + Warg.fbx + textures into export/
```

## Zombie wolf

A unit from Daniel's card game, in the undead batch (the zombies, skeletons and the ghoul are in the Humans repo).
Daniel: "don't bother with adding them to the game, build the creatures" - so model, paint and export; no game side.
The grey wolf dead and risen: starved, mangy, torn open. Its own file, `blender/zombie_wolf.blend` (scene
**ZombieWolf**, cameras `ZWF_CAM_*`), built headless.

![The zombie wolf from the right: the torn flank, the torn ear, bared teeth](docs/images/zwolf_34r.png)

![At the game camera (22 m, 50°, fov 30), blown up x3: the dark thin body, a knobbly spine, the red flank](docs/images/zwolf_game.png)

| Part | Triangles | Texture |
|---|---|---|
| Fur body (starved, the cavity, spine processes, hip points) | 3,891 | `T_ZombieWolf` (grey), `T_ZombieWolf_Dark`, `T_ZombieWolf_Pale` 1024², A = smoothness, no normal map (the wolf has none) |
| Lower jaw, tongue, nose | 392, 108, 9 | |
| Teeth (bared), eyes (milky) | 256, 120 | |
| Rib bars across the hole | 300 | |
| **ZombieWolfBody** | **5,076** | |

**The wolf's skeleton, exactly.** `zwolf_body` keeps `wolf_body`'s landmarks, head warp and `rest_bones()`; the rig is
named `WolfRig` like the wolf's. So every wolf clip plays on it unchanged, in Blender and in Unity (the clips' curve
paths are the same: the export's bind pose matches Wolf.fbx bone for bone). `zwolf_anim` keys `wolf_anim.CLIPS` onto it
and they are exported as `ZombieWolf@<clip>.fbx`, so its Unity setup stands alone.

How it is built:

- **Starved:** the wolf's lofts with a narrow ribcage, the belly drawn up behind the last ribs, wasted thighs,
  shoulders and neck, thin upper legs with knobby wrists and stifles, a thin tail. Fused ellipsoids under the skin:
  the spine's processes (withers to croup), hip points, pin bones and the shoulder blades' ridges.
- **Mangy:** nine of the wolf's tufts, longer and thinner; bald patches (`BALD`, one mask shared by the fur sculpt and
  the painter, domain-warped and frayed) get no fur and sink 2.5 mm. The spine's strip is broken, the tail's end bare in
  patches, the leg patches on the outside only.
- **The torn right flank** (`WOUND`): a cavity sculpted 3.4 cm deep with a ragged outline and a raised torn rim, high
  on the flank (the game camera looks down at 50°), with five rib bars across it as separate lofts (each its own width
  and depth, one snapped), laid on the flank's surface from before the cavity and weighted from the skin under them.
  The painter knows how deep each vertex really sits (`info.b`). A shallow torn patch over the left haunch (`GASH`).
- **Face:** the right ear torn (its tip gone, a V out of its outer edge: a clamp in the ear's own frame, after the
  symmetrize), the upper lip drawn back off the teeth (the muzzle's lip line raised, the upper teeth rooted in the gum
  and hanging outside the lower jaw), deep sockets, gaunt cheeks and temples, eyes 1.12x the wolf's.
- **Paint** (`zwolf_paint`, the wolf's layout dulled and dirty): grey-green rotting skin with bruises, green rot and
  veins, the fur thinning into it in strands; ribs drawn on both flanks, hip bones picked out pale; the spine a broken
  line of knobs (2026-10-23: the bald strip had read as a racing stripe at the game camera): its skin dark grey-green
  near the coat's own back colour, matted fur across it in stretches, most processes stained dark and only six
  (`PALE_KNOBS`) bone-pale; the cavity near-black with wet red walls, a pale torn edge, dried blood round it and drips below; milky eyes in
  dark sockets, dark gums, yellow teeth, blood round the mouth and down the throat, the torn ear's edge crusted. The
  rot is the Humans zombies' (`#7f8b72`, `#8e9680`, bone `#d8cfb4`). Coats: grey (default), dark (a black wolf's),
  pale (a white wolf's, yellowed).

Clips: the wolf's twelve (see [Clips](#clips-30-fps)). Death lies on its left side, so the torn flank faces up. Lowest
vertex: standing clips 0.0, Lunge -0.008, Death and GetUp -0.025.

Rebuild (headless; two to three minutes for everything):

```
blender.exe -b --factory-startup --python tools/zwolf_run.py -- build review game clips lowest testpose closeups sheets coats export
blender.exe -b --factory-startup blender/zombie_wolf.blend --python tools/zwolf_run.py -- paint review game
```

`paint` repaints the built model (same UVs) for paint-only changes. Renders: `renders/zwolf_<view>.png` (34, 34r, side,
sider, top, face, facer, headside(r), headfront, rear, wound, above, colony), `zwolf_game_sheet.png` (the game camera:
22 m, 50°, fov 30, the wolf ~90 px, blown up x3), `zwolf_frames_<Clip>.png` (EEVEE frames round the wound and the face),
`zwolf_clip_<Clip>.png`, `zwolf_coats.png`, `uv_layout_zwolf.png`, `zwolf_vs_wolf_game.png` (the grey wolf above, the
zombie below, at the game camera) and `zwolf_spine_game_before_after.png` (the spine before and after 2026-10-23).

**In Unity:** copy the new files (assets first, then the script) and run Tools > Beasts > Rebuild Zombie Wolf
(`ZombieWolfSetup.cs`; it also runs by itself on the first import). It makes `M_ZombieWolf` (+ `_Dark`, `_Pale`),
`Prefabs/ZombieWolf` (Animator, `BeastAppearance` with the three coats, `BeastEvents`), `Animation/ZombieWolfAnims`
(the wolf's pools) and lineup renders in `Logs/ZombieWolfSetup` (a preview scene). It touches no scene.

```
$B = "E:\Unity\Projects\GameArtGeneration\Beasts"; $U = "E:\Unity\Projects\MedievalSetting\Assets\Beasts"
Copy-Item "$B\export\ZombieWolf.fbx" "$U\Models\"
Copy-Item "$B\export\Anims\ZombieWolf@*.fbx" "$U\Models\Anims\"
Copy-Item "$B\export\Anims\zombiewolf_clips.json" "$U\Models\Anims\"
Copy-Item "$B\textures\T_ZombieWolf*.png" "$U\Textures\"
Copy-Item "$B\unity\Beasts\Editor\ZombieWolfSetup.cs" "$U\Scripts\Editor\"
```

## Giant bat

A unit from Daniel's card game (2026-10-23; "Keep moving on the creatures", "don't bother with adding them to the
game, build the creatures"): model, paint, clips and export, no game side. My calls: a wolf-sized body (0.80 m nose to
rump), 2.9 m across the wings, big upright ears, a short pug snout with an upturned nose pad and a nose leaf, two long
upper fangs outside the lower jaw, red eyes, dark brown-black fur with a rusty mantle, dark leather wings that thin
and redden toward the trailing edge; no tail and no tail membrane. Its own file, `blender/bat.blend` (scene **Bat**,
cameras `BAT_CAM_*`), built headless.

![Hovering, the tense hover before a dive](docs/images/bat_hover.png)

![At the game camera (22 m, 50°, fov 30), blown up x3, the grey wolf beside it for scale](docs/images/bat_game.png)

| Part | Triangles | Texture |
|---|---|---|
| Fused fur body (trunk, mantle, shoulders, pectorals, thigh stumps, head, muzzle, nose pad and leaf, brows) | 1,896 | `T_Bat` 1024², A = smoothness, one texture for both meshes |
| Arms, fingers, thumbs, hind legs (clean lofts); claws | 632; 88 | |
| Ears, eyes, fangs, lower jaw | 156, 100, 68, 220 | |
| **BatBody** | **3,160** | `M_Bat` |
| **BatWing**: the membranes (Coons patches), 960, and their underside (the same faces copied and flipped), 960 | **1,920** | `M_BatWing`: the same texture, back faces culled |
| **Bat** | **5,080** | |

How it is built:

- **Always in the air.** The bind pose is the flying pose with the body's centre 1.6 m over the Root (`bat_body.H`).
  The game moves it on the ground like the other beasts; only Death brings it down.
- **The dragon's wings, parametrised** (`dragon_body.WingSpec`; the dragon's own is `DRAGON_WING`, and its bones,
  membranes and helper poses come out bit-identical): four fingers (digit 2 along the leading edge, 3 to the tip, 4
  and 5), the thumb with its claw, the arm panel's flank edge running down the body to the knee and the ankle
  (`WS.flank`, weighted on Chest, Spine1, Thigh, Shin) and its 12 helper bones (`WingMem*`), finer scallops.
- **Pieces in a `dragon_body.Acc`**, so every vertex carries its own weights: chain weights along the arm, finger and
  leg lofts, the membranes' Coons weights, ears, eyes, fangs and jaw rigid. The fused fur gets heat weights solved on
  a copy of the fur alone (`bat_body.heat_weights`), so the membrane sheets stay out of the heat solve.
- **The wings are split off after painting** (`BatWing`); both meshes share the UVs and `T_Bat`. The membranes face up
  in the bind pose (`_membranes_up`).
- **The membrane has an underside of its own** (2026-10-23): `bat_build._two_layers` copies every wing face onto new
  vertices (same UVs, weights, info), flips the copies and tags them (`back` face attribute); `M_BatWing` culls back
  faces, in Blender and in Unity. A material drawn from both sides (URP Lit `_Cull` 0) lit the underside with the upper
  side's normals, so it read as bright as the top from below; now each side is lit with its own normal in any shader
  or render path. `paint` bakes the single sheet (`_one_layer`) and puts the underside back.
  `renders/bat_underside_before_after.png`: from below and from a low 3/4, left the old look (back faces shaded with
  the front normal, as Unity did), right the two layers.
- **Paint** (`bat_paint`): fur strokes along the flow, a grizzled crown, the bare face, the ears' cross ridges, the
  wings darker along the bones with veins branching off them and creases along the fingers.

Bones: Root, Motion, Hips, Spine1, Chest, Neck1, Head, Jaw, EarL/R, Thigh/Shin/HindFoot/HindToes, the dragon's wing
chain (WingScap, WingArm, WingForearm, WingHand, WingThumb, WingF1_1..F4_2) and `WingMem<i><j>` per side; sockets
`Socket_Head`, `Socket_Mouth`. 74 bones.

| Clip | Length | Notes |
|---|---|---|
| Idle | 1.6 s loop | a lazy hover: two slow beats, the body raised, legs hanging, looking round, an ear flick |
| Hover | 1.07 s loop | the tense hover facing a target: two quicker beats, upright, jaw ajar, claws forward |
| Fly | 0.67 s loop | one wingbeat, down and forward, up with the hand drawn in; root motion 4.5 m/s |
| Dive | 1.5 s | rears, half folds and swoops 1 m forward and 0.8 m down to bite, the hind claws reaching, and beats back up (in place); event `Bite` at 0.73 s |
| Screech | 1.8 s | rears with the wings spread, head out, jaw wide, ears back; event `Screech` at 0.5 s |
| Hit | 0.5 s | knocked back and up, the wings flinch |
| Death | 2.0 s | the wings jerk and fold, it drops and lies on its belly, the wings flat, the head turned; event `Dead` at 1.3 s; holds |

Wing strokes are the dragon's: the spread wing turned about the shoulder (`Y` down/up, `Z` sweep, `X` pitch), blended
bone by bone toward the folded wing (`bat_anim.FOLD`) and curled. A stroke that would put a joint or finger tip under
the ground is lifted (`Pose.floor`, bisected). Lowest vertex: the flying clips stay above 0.6 m, the Dive's wingtips
0.19 m, Death -0.012 at the landing. Fly traced over 3 loops: 3.0 m a loop, Motion's turn 0, the head's step at the
seam as inside the loop.

Rebuild (headless, about a minute):

```
blender.exe -b --factory-startup --python tools/creature_run.py -- bat build review game clips lowest trace sheets closeups hero export
blender.exe -b --factory-startup blender/bat.blend --python tools/creature_run.py -- bat paint review
```

Renders: `renders/bat_<view>.png` (front, side, top, below, 34, 34r, rear, face, facer, headside, headfront, wing),
`bat_game_sheet.png`, `bat_vs_wolf_game.png` and `bat_vs_wolf_34.png` (the wolf from `blender/beasts.blend`),
`bat_clip_<Clip>.png`, `bat_frames_<Clip>.png`, `bat_hero*.png`, `uv_layout_bat.png`.

**In Unity:** copy the files (assets first, then the script) and run Tools > Beasts > Rebuild Bat (`BatSetup.cs`; it
also runs by itself on the first import). It makes `M_Bat`, `M_BatWing` (back faces culled, `_Cull` 2), `Prefabs/Bat` (Animator,
`BeastAppearance` for the size, `BeastEvents`; the renderers' bounds padded for the wings), `Animation/BatAnims`
(Idle and Hover, Fly, Screech leading into Dive, Hit, Death) and lineup renders in `Logs/BatSetup` (a preview scene).
It touches no scene.

```
$B = "E:\Unity\Projects\GameArtGeneration\Beasts"; $U = "E:\Unity\Projects\MedievalSetting\Assets\Beasts"
Copy-Item "$B\export\Bat.fbx" "$U\Models\"
Copy-Item "$B\export\Anims\Bat@*.fbx" "$U\Models\Anims\"
Copy-Item "$B\export\Anims\bat_clips.json" "$U\Models\Anims\"
Copy-Item "$B\textures\T_Bat.png" "$U\Textures\"
Copy-Item "$B\unity\Beasts\Editor\BatSetup.cs" "$U\Scripts\Editor\"
```

## Giant turtle

The second card-game unit of the round (2026-10-23; no game side). My calls: a huge, slow land and swamp turtle
after the alligator snapping turtle: a 2.6 m carapace standing 1.6 m high, domed, with three keels of pointed knobs
and a saw-toothed back rim, moss over the top and lichen and barnacle crusts toward the rim; a small plastron joined
by bridges; a big wedge-shaped head with a hooked beak, amber eyes with a dark star, a pink mouth with the snapper's
worm-like lure on its tongue; a thick wrinkled neck; columnar, elephantine legs on round feet with blunt claws; a
short crested tail. 3.5 m from beak to tail tip. Its own file, `blender/turtle.blend` (scene **Turtle**, cameras
`TRT_CAM_*`), built headless.

![The turtle gaping (its Idle's lure), 3/4 view](docs/images/turtle_34.png)

![At the game camera (22 m, 50°, fov 30), blown up x3, the grey wolf beside it for scale](docs/images/turtle_game.png)

| Part | Triangles | Texture |
|---|---|---|
| Fused skin (a core under the shell, neck, head, legs and feet, tail) | 2,796 | `T_Turtle` 1024², A = smoothness |
| Carapace (outer dome, rolled lip, inner dome), plastron, bridges | 2,208 | |
| Lower beak, eyes, claws | 312, 120, 396 | |
| **TurtleBody** | **5,832** | `M_Turtle` |

How it is built:

- **The carapace is one parametric closed shell** (`turtle_body.build_carapace`): a superellipse outline, rim heights
  lower at the sides than at the front and back (the leg and neck openings), a domed profile plus the keels' knobs
  (`_relief`), the marginal scutes rolled out and under into a lip, and an inner dome back up. It rides rigid on
  Spine1; the spine never bends.
- **The skin is fused** (`beast_body.fuse_body`, 12 mm voxels) and heat-weighted on its own
  (`beast_rig.skin_with_pieces`, shared with the bat); the lower beak is a separate loft on `Jaw`, and the skin under
  the head follows it (`jaw_weight`, bounded on every side).
- **UVs:** the carapace unwraps as one disc (its builder cuts round the rim); the hidden inner dome and the plastron
  are packed small (`beast_paint.unwrap(island_scale=...)`, from tags in `info.b`). **Paint:** the scutes laid out
  like a turtle's (vertebrals with chevron borders, costals fanning out, marginals), grooves and growth rings, worn
  knobs, moss, lichen and barnacles, mud low down; mottled scaly skin, a pale throat, the horn beaks.

| Clip | Length | Notes |
|---|---|---|
| Idle | 4.0 s loop | slow breathing, looks one way and the other, gapes for a while (the lure) and shuts |
| Walk | 1.6 s loop | a slow lateral walk, the shell rocking; root motion 0.34 m/s |
| Bite | 1.1 s | draws the head back, jaw wide, then the neck shoots 0.36 m out and the beak snaps shut; event `Bite` at 0.53 s |
| Withdraw | 1.2 s | the head and neck slide into the shell, the legs fold in, the shell drops onto its plastron; holds |
| Emerge | 1.4 s | out again and a look round |
| Hit | 0.5 s | a jolt, the head half pulled in |
| Death | 2.5 s | the legs give way, the shell drops and tips a little, the head slides out onto the ground, jaw slack; event `Dead` at 2.0 s; holds |

`p.retract` (`turtle_anim`) slides the neck, head and jaw along the trunk (back into the shell, or out for the snap)
in the Species' extra hook. Lowest vertex: standing clips within 1.6 cm, Withdraw/Emerge 3.1 cm (a foot pad mid-way),
Death 1.9 cm. Walk traced over 3 loops: 0.55 m a loop, Motion's turn 0, the head steady.

Bones: the beasts' names with 3 neck and 3 tail bones, no tongue, no ears; sockets `Socket_Head`, `Socket_Mouth`,
`Socket_Back` (on the shell's top: a rider or a howdah). 35 bones.

Rebuild (headless, under a minute):

```
blender.exe -b --factory-startup --python tools/creature_run.py -- turtle build review game clips lowest trace sheets closeups hero export
blender.exe -b --factory-startup blender/turtle.blend --python tools/creature_run.py -- turtle paint review
```

**In Unity:** copy the files (assets first, then the script) and run Tools > Beasts > Rebuild Turtle
(`TurtleSetup.cs`; it also runs by itself on the first import). It makes `M_Turtle`, `Prefabs/Turtle` (Animator,
`BeastAppearance` for the size, `BeastEvents`), `Animation/TurtleAnims` (Withdraw holds 3 s, then Emerge) and lineup
renders in `Logs/TurtleSetup`. It touches no scene.

```
$B = "E:\Unity\Projects\GameArtGeneration\Beasts"; $U = "E:\Unity\Projects\MedievalSetting\Assets\Beasts"
Copy-Item "$B\export\Turtle.fbx" "$U\Models\"
Copy-Item "$B\export\Anims\Turtle@*.fbx" "$U\Models\Anims\"
Copy-Item "$B\export\Anims\turtle_clips.json" "$U\Models\Anims\"
Copy-Item "$B\textures\T_Turtle.png" "$U\Textures\"
Copy-Item "$B\unity\Beasts\Editor\TurtleSetup.cs" "$U\Scripts\Editor\"
```

## Leech

The third card-game unit of the round (2026-10-23; no game side). My calls: a medicinal leech made big and swampy,
1.8 m long stretched out and 0.25 m across, flattened with a flat belly, ringed all along; the back dark olive to
black with two rows of rusty spots and a thin broken pale stripe, the belly a mottled yellow-olive; the front narrows
to a round oral sucker, a cup with three rows of teeth inside (a lamprey's mouth more than a leech's: it reads from
the game camera), five pairs of eye spots; a broad rear sucker under the tail end; wet and glossy. Its own file,
`blender/leech.blend` (scene **Leech**, cameras `LCH_CAM_*`), built headless.

![Crawling: the rear sucker drawn up behind the front one](docs/images/leech_crawl.png)

![The oral sucker](docs/images/leech_mouth.png)

![At the game camera (22 m, 50°, fov 30), blown up x3, the grey wolf beside it for scale](docs/images/leech_game.png)

| Part | Triangles | Texture |
|---|---|---|
| The tube (rear cap, 71 rings of 14, the lip, the cup) | 2,128 | `T_Leech` 1024², A = smoothness (wet) |
| Teeth (30), rear sucker disc | 120, 128 | |
| **LeechBody** | **2,376** | `M_Leech` |

How it is built:

- **One clean tube, ring by ring** (`leech_body.build_tube`; no voxel fuse): a flattened section (the belly flatter),
  every other ring 3% fatter for the annuli, the front folding inward into the cup and a throat, the rear capped over
  the disc. Its faces are oriented by hand (the outside test, fooled by the cup folding inward, turned it inside
  out). Seams down the belly and round two rings: three short islands pack better than one 1.8 m strip.
- **A chain** (the ooze and the centipede are the other path bodies): Sucker, Body1-10, Head, rear to front, weights by
  arc length; a leaf **Swell<k>** on each body bone takes 60% of it (35% on the belly) and its uniform scale swells
  the segment. `beast_rig.apply_pose(scale_bones=...)` keys their scale (leaf bones only: no shear in Unity).
- **Poses are curves** (`leech_anim`): flat stretches on the ground, bell-shaped arches fitted to a length
  (`arch_fit`) and Beziers fitted to a length (`bezier_fit`); the bones sit at their rest arc positions scaled to the
  curve's length (it stretches and shrinks), framed by parallel transport from the rear, with a roll. The world curve
  is turned into the skeleton's frame once; Motion carries the root motion.

| Clip | Length | Notes |
|---|---|---|
| Idle | 3.0 s loop | lying stretched out, the front end raised and searching side to side, two pulses running down the body |
| Crawl | 2.0 s loop | looping like an inchworm: the rear sucker lets go and is drawn up behind the front one (the body arches ~0.45 m), then the front reaches forward; root motion 0.33 m/s |
| Lunge | 2.2 s | rears its front up and back, strikes 0.3 m past its head and latches on 0.4 m up (event `Bite` at 0.6 s), drinks (swellings run back from the mouth, the body pumps; events `Drain` 1.1 s, `Drain2` 1.5 s), lets go |
| Hit | 0.5 s | a writhe, the front recoiling |
| Death | 2.0 s | writhes, curls into a C on its side and shrinks; event `Dead` at 1.6 s; holds |

Lowest vertex: 2 mm above the ground in every clip but Death (-1.8 cm while it rolls onto its side). Crawl traced
over 3 loops: 0.65 m a loop, Motion's turn 0, the head's step at the seam 0.1 mm (inside the loop up to 13 mm: it
stops and goes). Export re-imported: 26 bones, one mesh, the Swell bones' scale keys kept.

Rebuild (headless, under a minute):

```
blender.exe -b --factory-startup --python tools/creature_run.py -- leech build review game clips lowest trace sheets closeups hero export
blender.exe -b --factory-startup blender/leech.blend --python tools/creature_run.py -- leech paint review
```

**In Unity:** copy the files (assets first, then the script) and run Tools > Beasts > Rebuild Leech
(`LeechSetup.cs`; it also runs by itself on the first import). It makes `M_Leech`, `Prefabs/Leech` (Animator,
`BeastAppearance` for the size, `BeastEvents`; bounds padded for the arch), `Animation/LeechAnims` and lineup renders
in `Logs/LeechSetup`. It touches no scene.

```
$B = "E:\Unity\Projects\GameArtGeneration\Beasts"; $U = "E:\Unity\Projects\MedievalSetting\Assets\Beasts"
Copy-Item "$B\export\Leech.fbx" "$U\Models\"
Copy-Item "$B\export\Anims\Leech@*.fbx" "$U\Models\Anims\"
Copy-Item "$B\export\Anims\leech_clips.json" "$U\Models\Anims\"
Copy-Item "$B\textures\T_Leech.png" "$U\Textures\"
Copy-Item "$B\unity\Beasts\Editor\LeechSetup.cs" "$U\Scripts\Editor\"
```

## Golden eagle

Daniel (2026-10-24): "You know, one of the models we need is an eagle or a falcon, can you model us one of those?
Dont use the chicken as base, that model is bad". His rule here is model first, then animate, so this is the model:
shape, feathers, paint and a rig that poses it perched (wings folded) and flying (wings spread); nothing comes from
the hen. The clips, the export and the Unity setup came after Daniel accepted the model (see [Clips](#eagle-clips)
below). Its own file is `blender/eagle.blend` (scene **Eagle**, cameras `EGL_*`), built headless.

**Revision (2026-10-24, the second pass).** Daniel saw `eagle_presets.png` and `eagle_game_spread_x2.5.png` and
answered my review of the first pass: "Yes, fix them", and "the head looks like a vulture structure, needs a pass
too". What changed (before/after sheets: `renders/eagle_ba_*.png`):
- **The head** read as a vulture's: a long head on a thin neck with a long beak. Now:
  - a broad, flat-topped, short skull (6.8 cm across, 7.9 cm across the brow shelves; poll to beak tip 12.5 cm, was
    14.2), its section boxy;
  - a brow shelf over each eye, its outer edge and front end down and the front turned in (the frown);
  - the eye an eyeball in a sculpted socket under the brow (a 9.4 mm cap standing about 3 mm out of it), looking
    45° forward;
  - a short, deep beak built from its side profile: 4.7 cm from the cere to the hook (a ~5 cm chord), 2.9 cm deep
    at the cere with the lower mandible (it was 7.8 cm long). The culmen runs in one arc from the cere to the hook,
    and the cutting edge runs back to below the eye's front;
  - a short, thick neck (4.2-5.6 cm radius) with a hackle ruff behind the crown.
- **The spread wing** read as a hand or a comb from above. Now:
  - the primaries' tips are laid on a broad, near-rectangular outline: P1 at 62° down to P10 at 4° (was 80° to −9°);
  - the six fingers (P5-P10) step 5-7° apart (was 8-12°) and separate only over their outer 34-42%, with narrow gaps;
  - the secondaries are 0.33-0.40 m long (were 0.27-0.33), fanned 72-97° so the trailing edge runs on into the
    hand's: a ~0.44 m chord, gently S-curved;
  - the span is 2.03 m (2.01 before);
  - the arm's flesh is painted as small dark coverts, so no flesh-coloured strip shows above or below;
  - the alula lies flat along the hand's leading edge (it stuck out like a spike).
- **The folded wing** looked like planks standing off the body, with saw-toothed edges. Now:
  - the fold plane leans in 32° (was 17.5°) and the forearm lies lower on the flank;
  - the secondaries hang 16° down-back (were 32°) with their fan closed (`FOLD_CLOSE`);
  - new **scapulars** (four cards a side on a `Scap` bone) roll out over the wing's top edge and the humerus, so the
    back runs on into the wing from above and behind;
  - the cards' tips are blunt and rounded (three edges), not blunt chevrons;
  - 12 narrower greater coverts with a third row, in low-contrast paint;
  - the feather sculpt is mirrored, so both sides clear the cards alike;
  - the wingtips reach the tail's middle, beside it (see the gotchas in HANDOFF).
- **The legs** were thin stilts. Now:
  - the tarsus is 9.2 cm (was 10.4) and the shin longer (16.3 cm, was 15.4), so the reach and the perched height
    (0.60 m, was 0.62) stay;
  - a feathered sock covers the top 44% of the tarsus, over a slimmer lower half: bare and yellow in the bald preset;
  - the trousers are fuller (5 cm radius at the knee, was 4.5) and run down past the ankle to a slightly flared hem.
- **The golden paint:**
  - the hackles are tawny gold (`#9a7a3c` streaked `#563c20`) on the hind crown, nape and hindneck only (they were
    lemon yellow over the whole head), fading into a dark forehead, brow and face;
  - the beak is horn darkening to the hook, with the yellow cere saddle (the nostril in it), a thin dark cutting edge
    and a soft yellow gape;
  - the lower mandible is in the beak's own colours (no dark bar);
  - the iris is dark amber-brown, with a dark rim, the pupil and the brow's shadow;
  - the bars on the remiges and the tail are subtler, and the trousers are painted round the legs only.

![The head before and after (golden, then bald)](docs/images/eagle_revision_head.png)

![The spread wing before and after](docs/images/eagle_revision_spread.png)

![The folded wing before and after](docs/images/eagle_revision_fold.png)

**A third pass on the folded wing (2026-10-24) was reverted.** Daniel asked for it ("Do another pass on the folded wing first: curve it around the body so it doesn't read as flat boards from behind and above"): the stack wrapped round a convex profile, one bone per secondary and tertial (114 bones). It closed the wings round the back from behind and above, but Daniel judged the second pass better ("The before actually looks better than the after, can we go back?"), and the second pass's fold, rig and code are back (HANDOFF has the attempt's numbers).

**The folded wing creased (2026-10-24).** Daniel: "The feathers are all quads, what if each individual feather could be folded in 2 places, so we make things fit. Yes, much more polygons, we would go over budget, but that is how real feathers work". The second pass's fold stays; on top of it the folded wing creases along two lines across it (`eagle_drape`), and every card that crosses a crease is folded there:
- **The creases** (`CREASES`, 7 and 19 cm back along the fold's long axis; each turns about an axis on the stack's inner face, along the stack's up tilted 15° toward its outer side so the tips come in, not down): everything beyond a crease turns in toward the body as one piece, so the layers, 1.1 mm apart, keep their order. The first crease takes the primaries and the secondaries, the second only the primaries (the innermost layers, running on toward the tail). Perched they turn 18° and 15° (the first is TURN's limit; the second stops on P7).
- **The cards' crease rows:** a card gets a row where it crosses a crease (`eagle_body.HINGE_T`, measured in the perched pose before the body is made), slanted so its shaft and both edges lie on the crease's plane; 22 cards a side (P1-P10, S1-S12), P4-P10 on both creases. A card whose rounded tip would cross a crease gets no row there and stays flat.
- **In the rig:** the turns are two shape keys, `FoldL` and `FoldR` (each card's offset taken back to the bind through its skinning), driven by two unweighted gauge bones, `WingFoldL` and `WingFoldR`, that slide 10 cm at a full fold (`eagle_pose.gauge`); the clips slide them with the wing's lay (not on a flex in flight), times a share per clip (`eagle_anim.GAUGE`): Idle, Screech, Hit and Land 0.94, TakeOff 0.75, Death 0.53, Walk 0.22. The shares are the largest that keep every frame clean (`eagle_build.fold_fit`): in Walk the legs swing under the folded wing, and in the crouch, the touchdown and the fall the wingtips come to the ground, so there the creased feathers relax. In Unity `EagleFeatherFold` sets the blend shapes from the gauges.
- **Cost:** 464 triangles (5,820 in all).

![The folded wing before and after the creases](docs/images/eagle_crease.png)

From behind the lower wing now comes in to the tail and the primaries' tips toward it; the upper half of the folded wing, in front of the first crease, is still the flat stack (the first crease cannot move forward: the tertials' roots lie just in front of it), and the tertials, the coverts and the scapulars over the creased cards stay flat.

**The arm's feathers (2026-10-24).** Daniel, looking at the eagle in Unity: "The feathers that should connect on the "forearm" are not connecting there" ("I meant "arm", not forearm, the thing after the shoulders"), "The feathers that should be there already exists, but they are "glued" in a fan position from the feathers of the "forearm"", "see, the feathers are there, but they don't connect to the arm bone":
- **The tertials along the arm.** They were four, rooted by the elbow, fanned on from the secondaries and carried by the forearm, so the humerus was a bare rod from the shoulder out, and a bending elbow (the upstroke, take-off, landing) took them further from it. Now six (T1-T6), spread along the humerus from the elbow toward the shoulder and pointing back (`T_AT`, `T_ANG`), on a two-bone row that rides the humerus (`WingTertA` at T3, holding T1-T3; `WingTertB` at T6, its child, turned alike), so in flight the six are one rigid piece: it turns back with a flex as every wing bone does but keeps its head on the arm. Folded, `eagle_pose.FOLD_CARRY` carries the row where the forearm carried the tertials, so the folded stack is the one the fold was tuned with, and `FOLD_SLIDE` slides the T6 end 8 cm down and 6 cm back in the cards' plane: spread up as they are along the arm, T4-T6 otherwise stood up out of the folded wing as a fin over the scapulars (part of the "boxy" look Daniel saw). `TERT_GAP` (3 mm) between them, the secondaries under them and the greater coverts over them, which the forearm moves against them in a flex; toward the shoulder the inner vanes narrow (`T_LEAD`) and the cards turn less, so they stay outboard of the shoulder's pivot (inboard, a rising wing lowered them onto the back).
- **The flesh meets the roots.** The feather layers float 1-3 cm over the wing's line and the arm's and forearm's flesh was 0.5-1.6 cm tall, so a strip of light showed between the arm and its feathers. The slabs' rear half now rises (`ARM_RISE`, `FORE_RISE`) to take the tertials' and secondaries' roots 2 mm in: the inner wing is a thick wedge by the body, as an eagle's is. Only in flight: the fold's shape keys (`FoldL`/`FoldR`) take the lift back off (`eagle_drape._flesh_unlift`, `eagle_body.slab_lift`), since lifted it stood out of the folded wing's top corners.

![Perched, parts coloured (green the wing's flesh, red the tertials, yellow the greater coverts, cyan the primary coverts, magenta the alula): this morning, before the creases and the arm work, and now](docs/images/eagle_tuck.png)

![The tertials before (fanned from the elbow, on the forearm) and after (along the arm, on the arm): debug colours, tertials red, secondaries blue, the wing's flesh green; the Fly upstroke, TakeOff and Land](docs/images/eagle_tertials.png)

My calls (the first pass, unreviewed unless named above):
- **Species and size:** a golden eagle (Aquila chrysaetos) at natural size: 0.84 m beak to tail tip, 2.03 m across the
  wings, 0.60 m tall perched. Unity can scale it up for a giant eagle; the game renders check x1 and x2.5.
- **Head:** see the revision above. The bald preset keeps its read: a white head, a yellow beak and a pale eye.
- **Legs and feet:** feathered trousers and tarsus; bare yellow toes (three forward, the hallux back) with curved black
  talons.
- **Wings and tail:** a long, broad wing whose outer six primaries (P5-P10) end in slotted fingers, and a fan tail of
  twelve feathers.
- **Two paint presets:** golden and bald (white head and tail, yellow beak and feet, pale eye, a bare lower tarsus).

![Perched, wings folded](docs/images/eagle_perched.png)

![Spread, from above](docs/images/eagle_spread.png)

![The two presets: golden (top) and bald](docs/images/eagle_presets.png)

![Spread at the game camera (22 m top, 13 m bottom; 50°, fov 30), blown up x3, the grey wolf for scale](docs/images/eagle_game.png)

| Part | Triangles | Texture |
|---|---|---|
| Fused body (trunk with a boxy section, neck, a boxy head with brow shelves, eye sockets and cheeks, the nape's ruff, shoulders, flanks, trousers) | 2,000 | `T_Eagle` (golden) / `T_Eagle_Bald` 1024², A = smoothness |
| Upper beak with cere, lower mandible (built from their profiles), eyes | 260, 180, 100 | |
| Tarsi (sock and slim half) and toes, talons | 624, 176 | |
| Wing flesh: humerus slab (with the patagium's fill), forearm slab | 280 | |
| Feather cards, one layer: primaries 424, primary coverts 72, secondaries 288, greater coverts 192, tertials 96, alula 16, scapulars 64, tail 144 (with the crease rows) | 1,296 | |
| The cards' undersides (each card copied and flipped; none for the greater and primary coverts and the scapulars, never seen from below) | 968 | |
| **EagleBody** | **5,884** (5,820 with four tertials; 5,356 before the creases; first pass 5,224) | `M_Eagle` / `M_Eagle_Bald`, back faces culled; shape keys `FoldL`, `FoldR` |

How it is built:

- **Bind pose:** the flight posture standing on its feet: the body level, the wings spread with the fingers open, the
  tail closed. The feathers are laid out where their outline matters, nothing overlaps (clean UVs, bakes and AO) and
  the feet are modelled open. Perched and spread are pose functions (`eagle_pose`).
- **The body:** fused like the beasts' (`beast_body.fuse_body`, then `zwolf_body.tidy`) with heat weights. The sculpts
  are the eye sockets (`_socket`) and the feather clumps, mirrored (`_fur`).
- **The pieces:** the eyes, feet and wing flesh are clean lofts and domes in a `dragon_body.Acc`, each vertex with its
  own weights: rigid, or chain weights along the toes. The two mandibles are built by `_mandible` from their side
  profiles (`BEAK_UP`, `BEAK_LOW`: culmen and cutting edge, or cutting edge and gonys, and a half width per row) with a
  ring across (`UP_RING`, `LOW_RING`); their (h, t) go into `root` for the painter.
- **The feather cards** (`eagle_body.Fe`): open strips three vertices across (leading edge, shaft, trailing edge), with
  a slight V, a slight ventral curve and a rounded tip (the last row narrowed, its edges drawn back by `chev`). Each
  card is its own UV island; its coordinates (u across, v along, kind and index) go into the `root` attribute and are
  baked for the painter.
- **Card layers:** one order holds for both poses, from bottom/inside to top/outside: P10, P9, PC9 … P1, PC1, S1…S12,
  T1…T6, G1…G12, A2, A1. In the open wing the proximal feather lies over the distal one; folded, the same order runs
  inside to outside. A layer is 1.1 mm (1.4 mm in the primaries, each covert half a step over its own primary). Drops,
  curves and camber are matched per stack, so overlapping cards stay parallel. The scapulars (SC1…SC4, the front one on
  top) lie on the back, apart from the wing's stack.
- **Undersides:** every card that can be seen from below has its faces copied onto new vertices and flipped (the bat's
  fix), and the material culls back faces. Each side of a card is lit with its own normal.
- **Feather bones:**
  - one bone per primary (its covert rides it), per tail feather (the fan spreads) and per side for the scapulars
    (`Scap`, a child of the chest);
  - the six tertials ride `WingTertA` (a child of the humerus) and `WingTertB` (its child), turned alike (see "The arm's feathers" above);
  - the 12 secondaries and the 12 greater coverts ride two bones, `WingSecA` and `WingSecB` (children of the
    forearm), each card's weight fixed from where its root sits
    between the two heads; when both bones turn the same way, linear blend skinning moves every card rigidly about its
    own root, as a folding forearm moves its feathers.
- **The fold** (`eagle_pose`): one stack in a plane against the flank (`FOLD`: its outer side leaning in 32°, its
  long axis back and a little down); the humerus aims back at `elbow`, the forearm forward at `wrist` (the bend of the
  wing at the breast's side), every other wing bone at an angle in that plane (`FOLD_ANG`: the hand and the primaries
  3° down, the secondaries hanging 16° down-back, the tertials 4° down); the secondaries' fan closes (`FOLD_CLOSE`, 25°)
  so they lie parallel; the alula is lifted onto the coverts (`FOLD_LIFT`); the scapulars roll out and down over the
  wing's top edge (`FOLD_SCAP`). Each wing bone turns from its spread aim to its folded aim by the shortest rotation,
  so a clip can blend `fold` from 0 to 1.
- **Paint** (`eagle_paint`):
  - the body's feathers are scallops: a jittered 3D lattice squeezed along the feather flow, with a pale fringe on
    each tip; the hackles are streaked, and the wing's flesh gets the small scallops of the coverts;
  - the cards have barred bases, a dark trailing band, the shaft, darker vane edges and pale fringes on the coverts;
    the scapulars are the back's brown;
  - the tail is barred with a broad dark tip (golden) or white (bald);
  - the head has the brow's shadow, a thin lid, a soft yellow gape and the beak in its own coordinates;
  - the toes have scutes and the talons are black.

Bones (88): Root, Motion, Hips, Spine1, Chest, Neck1-3, Head, Jaw (the lower mandible), Tail1 and TailF1-6 L/R,
Thigh/Shin/Tarsus and Toe1-4_1/_2 per leg (1 = the hallux). Per wing: WingArm, WingForearm, WingHand, WingAlula,
WingP1-10, WingSecA/B and WingTertA/B; ScapL/R; the unweighted gauges WingFoldL/R (the creases' shape keys follow
them). Sockets: `Socket_Head`, `Socket_Mouth` and `Socket_Grip` (the right
foot, for carried prey). Bone collections: Wings, Feathers (with Scap), TailFan, Toes.

| Pose | What |
|---|---|
| `perched()` | the body raised 50°, the neck bent back so the head is level, the wings folded along the flank (one stack leaning in 32°, the scapulars rolled out over its top edge), the tail closed and lifted 6°, the feet planted (two-bone IK to the bind pose's ankles), the toes gripping 4° |
| `spread()` | 0.9 m up, the body level, the wings as bound with the fingers 3° wider, the tail fanned 34°, the feet tucked under the tail (IK to body-space targets), the toes closed |
| `folded()` | the bind pose with the wings folded (body level): for tuning the fold in the body's own axes |

Checks (`eagle_build.check`; bind / perched / spread):
- Card faces beyond their quills (`ROOT_T`) crossing the body: 0 / 0 / 0. The hit's place along the card is estimated
  per hit, not per face.
- Cards crossing other cards: 0 / 0 / 0.
- Card vertices inside the body (ray parity, three rays voting): 0 / 0 / 0.
- Cards against the wing's own flesh: 0 / 353 / 0 (the flesh lifted to the roots, 2026-10-24: their quills in it). Folded, the bases of the primaries run along the forearm slab under
  the secondaries, and the scapulars' roots cross the humerus slab under them.
- Lowest vertex: 0.2 mm (talon tips), −4 mm (talon tips, gripping) and 1.13 m.
- Weights: 0 unweighted, 0 with more than 4 influences. UV overlap: 0 texels; 83% coverage. Shape keys FoldL / FoldR: the undersides bend with their tops (0 mm apart, perched).
- `folded()` (the bind pose with the wings folded, body level) is for tuning the fold in the body's own axes.

Rebuild (headless, about 50 s for everything):

```
blender.exe -b --factory-startup --python tools/creature_run.py -- eagle build check review closeups game presets compare
blender.exe -b --factory-startup blender/eagle.blend --python tools/creature_run.py -- eagle fold_fit nosave   # refit the clips' crease shares (needs the clips keyed)
blender.exe -b --factory-startup blender/eagle.blend --python tools/creature_run.py -- eagle paint review
blender.exe -b --factory-startup --python tools/creature_run.py -- eagle model check quick qhead qfold nosave   # no paint: debug colours, fast
py tools/before_after.py renders/eagle_before renders renders/eagle_ba_head.png "Head" eagle_cmp_head_profile:profile ...
```

Renders (`renders/`):
- the poses:
  - `eagle_perched_<front|side|back|34|34back|above>.png` and the sheet `eagle_perched.png`;
  - `eagle_spread_<front|side|back|34|above|below>.png` and the sheet `eagle_spread.png`;
- close-ups:
  - `eagle_head_profile.png`, `eagle_head_34.png`;
  - `eagle_foot.png`, `eagle_foot_side.png`;
  - `eagle_fold_side.png`, `eagle_fold_back34.png`;
  - `eagle_wingtip_above.png`, `eagle_wingtip_below.png`;
- the game camera: `eagle_game_<perched|spread>_x<1|2.5>.png` (top row 22 m, bottom row 13 m; azimuth 30 and 210; the
  wolf from `blender/beasts.blend`) and `eagle_game_frames.png` (the whole 22 m frames);
- paint and UVs: `eagle_presets.png`, `eagle_uv_golden.png`, `eagle_uv_bald.png`, `eagle_textures.png`;
- the revision's fixed views (`compare`): `eagle_cmp_<view>.png` (head profile/3/4/front/above, golden and bald; fold
  side/back/above/3/4 back; legs side/3/4; spread above/below and the wing tip). The first pass's renders and fixed
  views are in `renders/eagle_before/`. The before/after sheets (`tools/before_after.py`) are
  `eagle_ba_<head|spread|fold|legs|game|presets>.png`;
- the quick Workbench looks (debug colours): `eagle_q_<bind|folded|perched|spread>.png`, `eagle_q_head.png`,
  `eagle_q_fold.png`.

### Eagle clips

Daniel (2026-10-24), after the third fold pass: "Lets accept the issue and animate it", and the folded wing went back to
the second pass's ("The before actually looks better than the after, can we go back?"). The clips leave the model as
it is: `eagle_anim.py` poses the accepted rig and keys it.

![TakeOff from the side (top) and from above: crouch, spring, the wings unfold over the back, three hard beats, rising 1.5 m](docs/images/eagle_takeoff.png)

![Dive: a beat up, the stoop with the wings tucked, the talons thrown forward and struck onto the ground, heavy beats back up](docs/images/eagle_dive.png)

![Glide at the game camera (22 m, 50°, fov 30), x2.5, blown up x3, the grey wolf for scale](docs/images/eagle_game_glide.png)

| Clip | Length | Root motion | Events | What |
|---|---|---|---|---|
| Idle | 6.0 s loop | in place | | perched: breathing, quick head turns and tilts, one feather rouse (a body shake, the wings and tail shaken loose) |
| Walk | 1.33 s loop | 0.195 m/s | | a slow strut: the body rolls over the planted foot, a head bob, the toes curl in the swing |
| TakeOff | 2.0 s | 5.0 m, 0 → 6 m/s | | from perched: crouch, spring, the wings unfold over the back, three hard downstrokes, rising 1.5 m; ends in Fly's first frame |
| Fly | 0.8 s loop | 6 m/s | | one wingbeat: down and forward with the wing out, up with the wrist drawn in |
| Glide | 3.0 s loop | 9 m/s | | soaring: wings fixed, banking ±11°, the tail twisting, the head looking round |
| Dive | 2.6 s | 16.3 m, 6 → 11 → 4 → 6 m/s | `Strike` 1.27 s | a beat up to 2.0 m, the wings tucked, the stoop, the talons thrown forward and struck onto a spot on the ground, heavy beats back up; ends in Fly's first frame |
| Land | 2.2 s | 4.6 m, 6 → 0 m/s | | a descending glide, braking flaps with the body upright, the legs swung forward, touchdown at 1.47 s, the wings folded; ends perched (Idle's first frame) |
| Screech | 2.0 s | in place | `Screech` 0.53 s | the body leans in, the neck stretches the head out and up, the beak wide |
| Hit | 0.6 s | in place | | a flinch back, the wings jerk open, recovers |
| Death | 2.5 s | in place | `Dead` 1.0 s | the wings jerk, the legs give and fold back, it pitches onto its breast, the wings drooping open on the ground, the head on its side; holds |

How they work:
- **The height is in the skeleton**, as the bat's is: the eagle flies with its body 1.5 m over its perched place
  (`FLY_H`), so the GameObject stays on the ground and Motion travels only forward. TakeOff climbs, Land comes down and
  Dive stoops to the ground in the skeleton. The hand-overs match exactly: TakeOff, Dive and Land start or end in Fly's
  first frame, Land ends in Idle's.
- **The fold without crossings.** eagle_pose's fold turns each wing bone from its spread aim to its folded one by the
  shortest rotation; the two ends are clean, but between them 500-1,500 card pairs crossed (the cards of a fan twist
  against each other at 1.1-1.4 mm layer steps). `_place_wing` splits each bone's turn from spread (S) to folded (F)
  into F = G R S: G lays the wing's plane onto the fold plane rigidly (one turn for the whole wing), and R, nearly a
  turn about the wing's normal, is split into its twist about the normal (an in-plane fold, in which every card keeps
  its height over the plane) and the small swing left over. `fold` runs all three together; `flex` runs the in-plane
  part alone: the wrist drawn in on an upstroke, the wings tucked in the stoop. The ends are eagle_pose's own.
- **Wing strokes** are the bat's: the spread wing turned about the shoulder (`Y` down/up, `Z` sweep, `X` pitch). The
  beat runs from Y −30° (raised, wrist a little flexed) to +36° (down and forward). Raised further, or swept back at the
  top, the innermost tertial slides over the back into the scapulars.
- **The thigh is held to the trunk.** The skin of the back and the flanks under the scapulars and the folded primaries
  carries up to 0.67 of the thigh's heat weight, so a thigh swinging with the leg pushed that skin through the cards.
  The thigh turns with the trunk at its perched frame or its tucked one (`Pose.thigh`, 0..1), and the knee and ankle do
  the work (IK knee → ankle → ball), as a bird walks with its femur held still.
- **Feet on the ground** keep the toes' rest orientation and their bases on their rest spots (their middle stays put,
  none goes below its rest height), so the talons stay as the perched model has them.
- **Envelopes are eased segments** (`eagle_anim.E`), not Catmull-Rom keys, wherever an overshoot would hurt: a
  Catmull-Rom key next to a plateau went negative and threw the feet up onto the back.

Checks (`eagle_build`: `cards`, `lowest`, `trace`, `chains`, `feet`):
- Every frame of every clip through the model's overlap test: cards through the body 0, cards through cards 0, card
  vertices inside the body 0, in all 701 frames, with the creases and the tertials along the arm (2026-10-24). Cards
  against the wing's own flesh peak at 356 face pairs (folded, the model's hidden contact).
- Lowest vertex: Idle, Walk, TakeOff, Screech and Hit −3.2 mm (the talon tips, as perched), Land −5.3 mm, Death −9.0 mm
  (a primary's tip in the fall; −6.8 mm before the creases); Dive's talons stop 7 cm over the ground at the strike; Fly stays above 1.44 m,
  Glide above 1.67 m.
- Root motion as Unity plays it (`beast_review.motion_trace`, three loops): Walk 0.26 m a loop, Fly 4.8 m, Glide
  27.0 m, Motion's turn 0; the head's step at the seam no bigger than inside the loop (Fly 1.6 / 1.9 mm, Glide 0.2 /
  0.4 mm, Walk 1.1 / 1.1 mm).
- Hand-overs (largest bone jump between one clip's last frame and the next one's first): TakeOff → Fly, Fly → Dive,
  Dive → Fly, Fly → Land, Land → Idle 0 mm at matching speeds; the loops' seams 0 mm. Fly ↔ Glide and Idle ↔ Walk
  differ and are crossfaded.
- Walk's planted feet drift at most 1.9 mm a frame.
- The export read back in an empty Blender (`reimport`, before the creases): 86 bones, Motion and Root the two roots, one mesh (5,356 tris,
  one UV layer, 79 groups, `M_Eagle`); Fly's Motion travels 4.8 m with the head steady at 1.9 m; the JSON's loops,
  root motion and events as above.

Rebuild (the model is built already; about two and a half minutes with the renders):

```
blender.exe -b --factory-startup blender/eagle.blend --python tools/creature_run.py -- eagle clips cards lowest trace chains feet sheets gameclips gifs export
blender.exe -b --factory-startup --python tools/creature_run.py -- eagle reimport nosave
py tools/frames_to_gif.py renders/eagle_gif_Fly renders/eagle_Fly.gif --step 2      # one per clip
```

Renders (`renders/`): `eagle_clip_<Clip>.png` (frame strips: side on top, above below; the flight clips' cameras follow
the trunk), `eagle_game_<Fly|Glide|Dive|TakeOff>_x<1|2.5>.png` (the game camera beside the wolf: top row azimuth 30,
bottom row 210, blown up x3) and `eagle_game_frame_x<s>.png` (a whole 22 m frame), `eagle_<Clip>.gif` (3/4 view, in
place), `eagle_unfold.png` and `eagle_fold_land.png` (the wings opening in TakeOff and folding after touchdown, close),
`eagle_screech_head.png`.

**In Unity:** copy the files (assets first, then the script) and run Tools > Beasts > Rebuild Eagle (`EagleSetup.cs`;
it also runs by itself on the first import). It makes `M_Eagle` and `M_Eagle_Bald` (URP Lit, back faces culled: the
cards have undersides of their own), `Prefabs/Eagle` (Animator, `BeastAppearance` rolling golden or bald and the size,
`BeastEvents`; the mesh's bounds ride on Hips, a 2.6 m cube, since the body flies up to 2.3 m over the GameObject),
`Animation/EagleAnims` and lineup renders in `Logs/EagleSetup` (a preview scene). It touches no scene. Pools: Idle,
Walk, Screech, Hit, Death and TakeOff on the ground; TakeOff leads to Flight (Fly, Glide, Fly, Dive, Fly, Glide in a
row), Flight to Land, Land to Idle (Flight and Land have weight 0: only the chain reaches them). No pool is `vertical`:
Motion never climbs.

```
$B = "E:\Unity\Projects\GameArtGeneration\Beasts"; $U = "E:\Unity\Projects\MedievalSetting\Assets\Beasts"
Copy-Item "$B\export\Eagle.fbx" "$U\Models\"
Copy-Item "$B\export\Anims\Eagle@*.fbx" "$U\Models\Anims\"
Copy-Item "$B\export\Anims\eagle_clips.json" "$U\Models\Anims\"
Copy-Item "$B\textures\T_Eagle.png", "$B\textures\T_Eagle_Bald.png" "$U\Textures\"
Copy-Item "$B\unity\Beasts\Editor\EagleSetup.cs" "$U\Scripts\Editor\"
```

## Dragon and hydra

Two big creatures built on the same machinery as the beasts above. Each has its own .blend: `blender/dragon.blend`
and `blender/hydra.blend`.
- **The dragon:** six limbs, about 12 m long with a 16 m wingspan. Body ~30k tris, plus the wing membranes.
- **The hydra:** aquatic, with three heads (the dragon's head, made slimmer), no wings and no spikes. ~40k tris,
  plus the fins.

Both are painted at 4096 with three presets and normal maps.

| Dragon clip | Length | Notes |
|---|---|---|
| Idle / Walk / Run | 4.0 / 1.6 / 0.8 s loop | root motion 1.25 / 5.5 m/s |
| Bite, Claw, TailSweep | 1.4, 1.2, 1.8 s | event `Bite` |
| Fire | 2.5 s | `Fire` at 0.9 s, `FireEnd` at 2.0 s |
| Roar, Hit, Death | 2.2, 0.6, 3.0 s | `Roar` 0.6 s, `Dead` 2.0 s |
| Takeoff | 2.2 s | leaps (`TakeOff` 0.63 s) and climbs: 10 m forward, **7 m up** |
| Fly / Glide | 1.2 / 2.0 s loop | 10 / 14 m/s |
| Land | 2.4 s | 15.6 m forward, **7 m down**, `Land` at 1.4 s |

| Hydra clip | Length | Notes |
|---|---|---|
| Idle / Walk / Run | 4.0 / 1.33 / 0.67 s loop | root motion 1.0 / 3.9 m/s |
| Bite | 1.4 s | the middle head, `Bite` at 0.6 s |
| TripleBite | 2.4 s | left, middle, right: `Bite`, `Bite2`, `Bite3` at 0.6, 1.2, 1.8 s |
| TailSweep, Roar, Hit, Death | 1.8, 2.2, 0.6, 3.0 s | `Bite` 0.8 s, `Roar` 0.6 s, `Dead` 2.3 s |

**In Unity:**
- **Setup:** Tools > Beasts > Rebuild Dragon / Rebuild Hydra (`DragonSetup.cs`, `HydraSetup.cs`). Textures are imported
  at 2048. The wings and fins are drawn from both sides and always take the same preset as the hide
  (`BeastAppearance.pairedTarget`).
- **Flight:** Takeoff and Land keep their root motion's height. A pool marked `vertical` lets the random animator
  lift the creature, and the dragon's `Flight` pool plays Takeoff, Fly, Glide, Fly and Land in a row.
- **Fire:** `BeastBreath` breathes fire from `Socket_Mouth` between the Fire clip's events.
- **Test scene:** `Scenes/Dragons_Test` has two dragons and two hydras, with goblins for scale. Its viewer has wider
  presets and a follow camera.

![The dragon in Unity, a goblin for scale](docs/images/dragon_unity_close.png)
![Fire breath: BeastBreath on the Fire clip](docs/images/dragon_unity_fire.png)
![The hydra in Unity](docs/images/hydra_unity_close.png)

Export (in the live Blender, or headless when it is busy):

```python
import dragon_build; dragon_build.export()      # clips + Dragon.fbx + textures into export/
import hydra_build; hydra_build.export()
```

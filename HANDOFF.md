# Handoff

This file covers where the beasts stand and how to pick them up. The README is the reference (rebuild commands,
budget, skeleton, sockets). This file holds the working agreements, the conventions that bite, open issues and
checks.

## Working agreements

- These are the same as for the goblins and insectoids (`../Goblins/HANDOFF.md`, `../Insectoids/HANDOFF.md`):
  - Daniel watches Blender live, reviews in Unity and sends screenshots.
  - He prefers the obvious fix and asks for commits in batches.
- Budget: colony camera ~40 m at 50°, no LODs. The wolf is ~4.8k triangles with one 1024² texture. Report counts
  when adding parts.
- Daniel's calls (2026-09-26): enemy beasts start with the wolf. Model first, then animate it and send it to Unity.
  He asked why the eyes were so small; they are now stylised at ~1.3x a real wolf's so they read in game.

## Conventions that bite

- **Head warp:** the head is modelled at natural size and enlarged by `hw()` (`HEAD_K` = 1.12). Anything placed on
  the head must go through `hw()`: parts, tuft anchors, the jaw and teeth, and bones (`_bone` does it). Masks that
  are written in natural coordinates first undo it with `hw_inv()`: the face sculpt, the fur amount and flow, and
  the painter.
- **Decimation fills small dents:** the eyes are placed on the *game* mesh's socket, not the dense one; on the dense
  socket they ended up 8 mm inside the head. Flat areas get sliver triangles, which show as dark slits when
  smooth-shaded. `triangulate` + `beautify_fill` after the decimate fixes that. Thin plates (the first attempt at
  lip flews) also made slits, which is why the muzzle is a deep box section instead.
- **The legs need a bigger share of the triangles** (the decimate vertex group). With less, the legs became 5-sided
  tubes, and any mask built from normals turned into hard per-face edges. Leg colour masks use position, not
  normals.
- **Heat-map weights** are computed on the joined mesh. The mouth pieces are then overwritten as rigid (`info.g`
  marks the pieces that ride on the jaw), and only the fur vertices are smoothed.
- **Attributes are empty in edit mode:** read `info` and the vertex groups before `mode_set('EDIT')`
  (`wolf_paint.unwrap`).
- **AO specks:** folded faces at the tuft roots bake as near-black specks. `_despeckle` lifts texels toward their
  neighbourhood mean.
- **Mesh and UV-layer names:** see the insectoids' notes. `mesh_obj` deletes orphan meshes with the same name.
- **Opening another .blend from the MCP:** schedule `open_mainfile` with `bpy.app.timers.register`, so it runs
  after the MCP call returns.

- **Leg IK uses the bind pose's own knee side and bone twist** (`rest_data` 'pole'); a zero WolfPose reproduces
  the bind pose to 1e-6. The rest legs are not planar, so a generic forward/back pole put the knee 1 cm off.
- **Paw targets are clamped above the ground** in `_leg`, and so are the toe tips. In Death the trunk-carried paw
  on the down side went 16 cm under the ground mid-roll. Check the lowest vertex per clip after changes.
- **Death comes down only as fast as it rolls:** the trunk rests on its flank at z ~0.16, and dropping faster sank
  it into the ground.
- **Decimation folds:** `unfold()` relaxes vertices whose faces turn against their neighbours (dark notches); it
  also softens the tuft tips a little.

- **Shared modules (2026-09-27):** the generic code moved out of the wolf files into `beast_body`, `beast_rig`
  (skinning), `beast_paint` and `beast_anim`. The move was checked against a snapshot: the wolf's clip matrices are
  identical. Its mesh isn't, but the voxel remesh isn't reproducible anyway (two runs of the same code differ by
  a few vertices).
- **Export after every rebuild:** the UVs change from build to build. Installing new textures with an old FBX
  breaks the mapping.
- **Degenerate UV islands:** a few near-zero-area faces left by decimation came out of `average_islands_scale`
  67,000x too big (half the rat's texture). `beast_paint._tame_islands` shrinks any island whose UV/area ratio is
  far above the median.
- **Tufts must point away from the surface:** tufts laid along the back sink in and get filleted away. The rat's
  crest points up (z 0.6–0.85); flank tufts read as thorns, so there are none.
- **A tail lying on the ground drags** (`Species.tail_floor`, `beast_anim._tail_drag`). Otherwise any trunk tilt
  swings the far end of a 0.9 m tail through the floor. Upside down (the rat's Death), + tail pitch bends it toward
  the ground.
- **The toe ground clamp is relative to the rest toes.** At a fixed 1.2 cm it bent the rat's resting fingers.
- **Plantigrade hind feet** (rat): `HindFoot` runs heel to ball along the ground, so the hind flex is negative
  (the heel lifts).
- **Scene switching:** `rat_build.build_all` asserts that the Rat scene is on screen, because collections are
  created in the current scene.

- **Rhino (2026-10-07):**
  - **Hair shells snap to their own volume.** Snapping a hem to the fused body jumped between the cape, trunk, legs
    and head (`rhino_body._Snap` uses the volume's loft alone; strips drop onto the body from above).
  - **A loft whose centre line rises tilts its rings** (they stay perpendicular to the path), so the top leans
    forward: the cape's first try buried the ears. Keep coat volumes' centre lines level and shape them with the radii.
  - **Create bmesh layers before any vertex:** adding the `root` layer later orphaned the BMVerts already made, so
    the horns and eyes were tagged as jaw.
  - **Masks in head space need bounds on every side:** the jaw-follow mask (cheek) also caught the forelegs, which
    then trailed the head in the gallop.
  - **Short legs, short strides:** a stance sweep over about +-0.35 m stretches the 1 m legs flat. The charge is
    9 m/s; the game should play it faster rather than lengthen the stride.
  - **Split the spear after painting, and deselect everything first:** the unwrap leaves all faces selected, and the
    first split took the whole mesh.
  - Lowest vertex: the standing clips stay within 3 cm. In Sleep the hem's hair tips go 15 cm into the ground (it
    lies in the wallow's mud), in Death a down-side foot's edge briefly dips.

- **Cave bear (2026-10-07):**
  - **Long plantigrade feet stick out of the "near the leg" mask:** `coat_on_trunk` moved the feet's weights to the
    trunk; `bear_rig._leg_share` now keeps every vertex below 0.3-0.4 m on its leg.
  - **One-sided masks paint the wrong side:** the lips mask (a single smoothstep) painted the chin black; make
    masks bands. The palate mask caught the lips until bounded to |x| < 0.045.
  - **Reared forelegs:** with the trunk at 75°, boff +y is world down and +z world back toward the chest; boff 0
    reaches the paws straight forward. Ask for "paws up at head height", not raised arms.
  - **Open mouths need the head lifted:** the head hangs 25° down, so a 40° gape pointed the jaw at the floor and
    it read as a stick hanging off the chin. Roar, Bite and Rear now lift the head as the jaw opens (about as much
    as the gape), the tongue is narrower than the jaw so the dark gums frame it, and the fangs are long enough to
    show (hidden inside the jaw and snout when shut).
  - **Reared paws in front of the face hide the roar:** Rear holds them out at chest height, wider apart.
  - **Death roll:** the down-side forepaw sank mid-roll; it now draws in (`tuck`) and its toes lift while the body
    turns over. Lowest vertex: body within 2 cm in every clip; in Sleep, Wake and Death only hair tips dip
    (lying on the ground).

- **Woolly mammoth (2026-10-08):**
  - **Thin tubes don't survive the voxel fuse + decimation:** the forelegs and the trunk twisted into long diagonal
    facets (Daniel spotted both). The legs now keep more triangles (`_dec_weight`); the trunk is a separate loft
    with clean rings over a fused stump, skinned by arc length.
  - **A coat volume wider than the body leaves a ledge**; hair hanging from where the back turns over stands out as
    fins; fringe loops round the shins read as leg-warmer cuffs; clumps lying on the back read as scales.
  - **A hidden view-layer collection makes the export silently skip its objects** (the rig's eye toggled off in the
    outliner gave 4 KB clip files with no armature). `beast_export` now reveals the collections while exporting.
  - **The head, after Daniel's reference photo:** it read as a ball with an upright face and a thin trunk stuck on.
    Now the dome sits high at the back, the forehead (a rotated ellipsoid) slopes in one line down and forward into
    a flared trunk root (a fused stump the tube starts inside), and the ears are small flaps pressed to the head
    (hollow facing out, so they don't show edge-on as blades). Daniel was happy with the tusks; they are unchanged.
  - Lowest vertex: the body within 3 cm in every clip, the tusks rest on the ground in Death; lying (Sleep, Wake,
    Death) the skirt's hair tips go up to 0.4 m into the ground.

- **Red deer stag (2026-10-11):**
  - **Thin legs: fused stump + grafted clean tube, one surface.** The stumps (upper arm to mid forearm, stifle to
    mid gaskin) are fused, so the elbow and stifle bend in heat-weighted skin. Below `deer_body.SEAM` the stump is
    cut off and a clean lofted lower leg is stitched onto its rim (`_graft_legs`: rim snapped to an ellipse, a zip
    strip, the slivers beautified and relaxed). A separate tube out of the body, then out of the stump's end, both
    showed a ragged crossing line in a stride; seating and tucking the overlap didn't cure it.
  - **The grafted legs keep the fur's part id** (`body["leg_verts"]` lists them): the baked part id is interpolated
    across faces, and a stitch between ids 1 and 17 painted dashes of nose, eye and claw colours.
  - **The legs skin down by height** (`deer_rig.LEG_CHAIN`) and copy the stump's weights at the seam; the heat
    weights round the shoulders and haunches get extra smoothing (a lifted leg pinched a fold).
  - **Workbench renders use the material's viewport roughness/specular** (defaults 0.4 / 0.5: glossy, dark):
    `deer_paint.matte` sets 1.0 / 0.0 and a low BSDF specular. The painted light is lighter than the wolf's.
  - **Mane:** cone tufts decimated into shards, fringe strips read as a spiky collar with a dark gap down the
    chest. Now the neck's full throat side, a strong fur sculpt there and long dark strokes in the texture.
  - **Tines:** a flared ring at the beam's surface and one just outside, so the root is soft and the flat root's
    bent normals stay inside the beam; 8 sides; they leave the beam forward and up and curve upward.
  - **A pale band along the jaw read as teeth** (and a shiny lip as a highlight): the jaw is dark like the muzzle,
    only the chin's front pale, smoothness 0.14. With a matte coat the eyes need a painted catchlight.
  - `deer_body._relax_creases` smooths decimation creases sharper than 55 degrees (a slit down the back).
  - **Clips:** grazing needs the chest lowered (trunk pitch -13, 0.10 down) as well as the three neck bones, or the
    muzzle stops 0.3 m above the grass; the head is tilted so the antlers stay clear. Lying, a folded foreleg's
    cannon goes back along the ground (flex -95; at -150 the forearm went into the ground) and the hooves curl
    little. Dead on its left side, the head rolls +45 so the antlers stand up (rolled with the trunk, one antler
    went 0.4 m into the ground). Running, the neck goes level and the head pitches up 50 to keep the face forward.

- **Dungeon ooze (2026-10-12):**
  - It was started as its own `Oozes/` project the same day. Daniel suggested moving it into Beasts, so it lives here
    now: scene **Ooze**, `ooze_*` modules.
  - These are my design calls, not reviewed by him yet:
    - green acid-ooze colours;
    - an adventurer's remains inside, with the sword sticking out of its back;
    - a dark-red nucleus as the weak spot;
    - hip-high, 3 m across.
  - **Everything the Ooze scene adds is prefixed `OOZ_`** (cameras, floor, rim light, the scale human). It reuses the
    shared KEY, FILL and world without changing them, and hides its cameras and lights in its own view layer only.
  - **No faces in the floor's plane, and none facing down near it.** A flat sole shadow-acned into dark wedges seen
    through the jelly, and so did tilted slivers along its rim. `ooze_body._clean` deletes them in passes.
  - **No undercut at the floor.** Floor pods curving back in below their equator rendered dark; a spreading "foot"
    flare decimated into a ragged paper edge. Below `FOOT[1]` the field takes that height's cross-section and leans
    out.
  - **Don't spare the pods in the decimation:** once they were fat, a sparing vertex group gave one pod a third of
    the triangles and left the dome faceted.
  - **UVs:**
    - A UV slit must start on its chart's border; an inner slit is a hole that `fill_holes` closes again.
    - A single ABF island over the whole top gave a 20x density spread.
    - Painted images need `img.update()`, or renders keep the stale GPU copy.
  - **Through the jelly, colours mix layer by layer**: two or three shell layers turn the red nucleus green-brown.
  - **Rim on the floor:** weight smoothing spread Dome and the raised pods down to the rim, which rose 15 cm in Crawl.
    `ooze_rig._pin_floor` hands their weight below 16 cm to Body.
  - **Non-uniform scale only on leaf bones** (Dome, the tips, Nucleus, Vac*), so Unity never inherits a shear. Body
    has children and is never scaled that way. Pods stretch by sliding their child bones along the chain.
  - **Sinking things must use their real lowest point, not the centroid:** a rotated helm sank through the floor
    (`_sink_z` reads it from the mesh).
  - **The containment check votes over three rays:** one ray grazing an edge called a skull vertex 34 cm deep
    "outside".
  - **The sheet cameras must not follow Motion:** the mesh plays in place, so following it walked Crawl out of the
    frame.
  - **Rebuild from clean:** `build_model` deletes the old meshes first, or the Armature modifier left on the shell
    would be applied together with the decimation, in whatever pose the rig holds.

## State (2026-09-26)

- **Grey wolf:** model, rig, three coats and 12 clips.
- **Giant rat (2026-09-27):** model, rig, three coats and 10 clips.
- **Woolly rhino (2026-10-07):** the woods' boss: model, rig, one coat, the `Spear` object and 13 clips; in
  MedievalSetting with one rhino in `Beasts_Test`. Root motion traced over 3 loops (Walk, Run, Charge): exact
  travel, head steady within 1 cm. The game side (fight, lair) is not built yet; the design doc still says boar.
- **Cave bear (2026-10-07):** model, rig, two coats (`T_Bear`, `T_Bear_Old`) and 13 clips; in MedievalSetting with
  two bears in `Beasts_Test`. Root motion traced over 3 loops (Walk 1.10 m, Run 2.30 m per loop, head steady, no
  snap). Not yet in the itch.io Creatures pack (waiting for a batch, with the rhino). No game side yet.
- **Woolly mammoth (2026-10-08):** model (6.3k tris, a six-bone trunk, spiralling tusks), two coats and 12 clips; in
  MedievalSetting with one mammoth in `Beasts_Test`. Root motion traced over 3 loops (Walk 2.20 m, Run 3.60 m,
  Charge 4.20 m per loop, head steady). Not in the itch.io pack yet; no game side yet.
- **Red deer stag (2026-10-11):** prey for the hunting grounds: model (5.4k tris), rig (3 neck bones), one coat
  (`T_Deer`) and 11 clips (Idle, Graze, Alert, Walk, Trot, Run, Attack, Hit, Death, Sleep, Wake); sheets in
  `renders/deer_clip_*.png`. Exported (`deer_build.export()`: 38 bones incl. Root/Motion/5 sockets, one skinned mesh, Motion
  travels 3.8 m a Run loop, 1.3 m a Walk loop). Installed in MedievalSetting 2026-10-11 (`DeerSetup.cs`, Tools > Beasts >
  Rebuild Deer: avatar valid, Run 8.14 m/s, Walk 1.08, Trot 2.93 root speed; 3 deer in `Beasts_Test`); the game's
  `red_deer` (prey: skittish, flees) in the hunting grounds.
- **Dungeon ooze (2026-10-12):**
  - model: shell 2.8k + contents 1.85k tris, `T_Ooze` 1024² (A = opacity), `T_OozeContents` 512²;
  - rig: 41 bones, 3 sockets;
  - 10 clips (Idle, Crawl, Lash, Grab, Engulf, Spit, Hit, Death, Puddle, Rise), all passing `ooze_anim.report()`;
    sheets in `renders/ooze_clip_*.png`, plus `ooze_clip_Engulf_victim.png` with the scale human in front.
  - Exported: checked in a background Blender (41 bones, 2 skinned meshes with 21 and 14 groups, one UV layer each;
    Motion travels 1.2 m per Crawl loop).
  - Installed in MedievalSetting on 2026-10-12, not checked in:
    - `OozeSetup.cs`, the `Beasts/OozeJelly` shader, M_Ooze and M_OozeContents, `Prefabs/Ooze`, `OozeAnims`;
    - two oozes in `Beasts_Test`;
    - `Logs/OozeSetup`: avatar valid, Crawl 0.60 m/s `dir=(0, 0, 1)`, 1.200 m per loop over 3 loops, no snap.
  - Gotchas from that install:
    - **The first render after an import can skip a transparent shader** whose variants are still compiling
      asynchronously; only the contents and the shadows showed. Set `ShaderUtil.allowAsyncCompilation = false`
      around verification renders.
    - **Other sessions work in the same editor.** This means:
      - don't switch scenes: `BeastsTestScene.Build` now fills the scene additively and restores the active scene,
        and the ooze's renders use a preview scene;
      - compile-check the scripts offline first (the editor `.rsp` with the new files swapped in);
      - copy the assets before the scripts, so there is one compile;
      - check `GetState` before every write;
      - don't enter play mode for a check.
    - **`EditorApplication.delayCall` doesn't tick while Unity is in the background,** so `AutoBuild` never ran. Run
      `OozeSetup.Build()` with RunCommand. The RunCommand sandbox rejects `using System.Reflection`; write
      `(System.Reflection.BindingFlags)40` inline.
  - **The extras (2026-10-12, same day), installed too:**
    - colour by shader (T_Ooze is masks now) with five presets;
    - Giant and Small prefabs;
    - Split and Reform clips, with the rig's halves, waist and twin nucleus (47 bones);
    - `OozeLook`, `OozeFx`, `OozeGlob` and `OozeSplit`.

    The 10 older clips came through the rig change within a few cm (99% of vertices within 3 cm; up to 10 cm in
    Lash's lean: the 4-influence cap in the middle band). All 12 pass `ooze_anim.report()`.
  - Gotchas from the extras:
    - **`Mathf.SmoothStep(a, b, t)` interpolates from a to b;** it is not GLSL's smoothstep. Used as one, the effect
      textures came out nearly opaque everywhere (`OozeSetup.Smooth` is the real one).
    - **URP Particles/Lit's "preserve specular" (`_BlendModePreserveSpecular`, on by default)** keeps reflections at
      full strength on clear texels, so every puddle and drop quad showed whole. It is off on the ooze's effect
      materials.
    - **Testing the effects without play mode:**
      - build them in a temporary additive scene (active only during the call) via reflection on Awake/Start, simulate
        the particle systems, render, then close the scene unsaved;
      - place it far from the open scene's creatures, since the camera renders every loaded scene;
      - `Destroy` logs an error in edit mode, which is harmless there;
      - a TrailRenderer builds no geometry in edit mode. It also folded over itself on turns (1.5 m wide), and a ribbon
        of my own that couldn't fold still showed its fresh end through the see-through jelly (Daniel, in play,
        2026-10-12). The trail is now splats merged in a wetness field (`OozeTrail` + `Beasts/OozeSlick`), laid behind
        the body. Its `Step(now)` takes a clock, so an edit-mode test drives it along a path and renders it.
    - **Split leaves a sharp V-shaped fold in the middle just before the snap** (seen from the front; from above the
      hourglass reads well). The splash covers the swap.

- **Warg (2026-10-12):** the goblin raiders' mount, from Daniel's reference (a goblin on a huge, shaggy, dark
  brown-grey wolf with a bone war-mask). Blender scene **Warg** (`WRG_*`, a wolf beside it for scale).
  - Body: the wolf's recipe ×1.35 (`warg_body.S`, folded into `hw()` with the head warp and a shortened, heavier
    muzzle `_mz`), so masks, painter and rig work in wolf units through `hw_inv`. Heavier legs (`LEG_K`, thicker
    toward the paws), bigger paws, short laid-back ears. 7,072 tris: fur 4.3k, mouth and eyes 0.9k, hair shells 1.9k.
  - The shag is separate hair (beast_coat clumps): `TIERS` of locks round the neck (the mane, poll to shoulders,
    stopping before the saddle), a bib under the throat, a belly fringe, `TAIL_RINGS` (a brush), forearm fringes
    (`LEG_STRIPS`), `LOCKS` (cheeks, elbows, breeches). Skinned from their roots.
  - Eyes (reworked at Daniel's ask): slanted almonds (`EYE_SLANT`, `EYE_SHAPE`) low at the stop, in a deeper
    socket under a heavy brow, laid onto a quadric fitted to the socket (the decimated socket is faceted, so a flat
    cap came out ragged); painted with a round pupil, a lid line and a dark brow.
  - Coats `T_Warg` (dark), `T_Warg_Ash`, `T_Warg_Black` + `T_Warg_Normal` (the painter's relief: clumps on the
    coat, strands down each lock — each lock's texels know its root, `bake_data(roots=True)`).
  - Tack (`warg_tack`, only for the ridden ones): `WargTack` 1,564 tris (felt blanket, leather seat with pommel
    and cantle, girth, breast collar, stirrups, bridle, bit rings, reins) and `WargMask` 304 tris (the bone
    war-mask, notched clear of the eyes, two horns, red war paint), one texture `T_WargTack` 512² + normal map.
    Fitted by ray casts onto the fur; weights copied from the skin there, the bridle and mask on Head, the reins
    Head → Neck1 → Spine2. Dressed total 8,940 tris.
  - 12 clips (`warg_anim`: the wolf's, distances ×1.35, slower cadences).
  - In MedievalSetting (`WargSetup.cs`, Tools > Beasts > Rebuild Warg): `Prefabs/Warg` (wild: tack and mask off)
    and `Prefabs/WargRidden` (`WargTack` component: saddled, masked; `Seat` = `Socket_Saddle`), `WargAnims`;
    2 + 2 in `Beasts_Test`. Report: avatar valid, Walk 1.16, Trot 2.48, Run 6.36 m/s root speed, `dir=(0, 0, 1)`.
    Not checked in (another thread does Plastic). No game side yet; no rider clips for the goblins yet.
  - Gotchas from it:
    - **`beast_scene.shot` renders Workbench by default:** textured studio light with its own plastic specular, no
      normal map, no smoothness. Judge materials in EEVEE (`warg_build.review` does now).
    - **`beast_paint._tame_islands` ran after the region scales** (fixed 2026-10-12): with many small hair islands
      scaled down, the median dropped and the eyes, head and jaw were "tamed" to hair density. It runs before the
      scales now. The other beasts' eyes and heads were affected the same way (their teeth and claws are many
      small islands too); rebuilding them would sharpen their faces.
    - **`BeastsTestScene.RenderLineup` used `NewScene(Single)`** (a scene switch in the shared editor); it renders
      in a preview scene now, and the lineup camera renders twice (the first render of fresh skinned meshes came
      out as shadows only).

- **Riders (2026-10-18):** Daniel: "goblin warg riders and orc mammoth riders, complete with animations"; his picks:
  one orc driver on the mammoth's neck (no howdah crew), every rider clip made by us, art + a test scene first.
  - Warg: the stirrup leathers end at `warg_tack.STIRRUP_PHI` 66 (were 88: the irons hung at the belly line and a
    goblin's legs came out straight); tack rebuilt and re-exported. The rider clips are Goblins `gob_ride.py`.
  - Mammoth: `mammoth_tack.py` = `MammothTack` (664 tris, `T_MammothTack` 512 + normal): a felt rug in the dip
    behind the head's dome, a foot rope behind the ears (the driver's feet tuck under it), a rope round the neck
    behind the rug, a rope grip for the left fist. UVs laid from the stored (along, across) coordinates, not smart UV
    (that cut the rug into odd islands and gave the 5 m ropes most of the sheet). New bone `Socket_Driver` on Neck1 at
    `mammoth_body.DRIVER_SEAT` (added to the live rig in edit mode, no body rebuild). `warg_tack` gained a `rope`
    part in its painter. `mammoth_build.export()` takes MammothTack when it exists. The driver clips are Humans
    `hum_ride.py`.
  - Unity: `MountedRider` (runtime): the rider's root is a child of the seat bone (pose from the mount's bind pose),
    it plays `<prefix><mount clip>` at the mount's own clip time through its own graph (manual, evaluated in
    LateUpdate), mirroring the mount's crossfade (`BeastRandomAnimator.PreviousClip/PreviousTime/Fade/CurrentLoops`);
    own clips (`PlayAction`) over an upper-body mask; `Fall()` lets go of the seat. `MammothTack` (like `WargTack`).
    `MammothSetup` makes `Prefabs/Mammoth` (tack off; coat target set to MammothBody) and `Prefabs/MammothRidden`.
    The rider prefabs and `Riders_Test` scene are game-side (MedievalSetting `Assets/Game/Riders`, `RiderSetup.cs`:
    they join three packs).
  - Gotchas:
    - **Blender 4.4 action slots:** an action keyed on one object (the rider copies) doesn't animate another
      (GoblinRig/HumanRig at export) until its slot is assigned; the export baked the rest pose, every rider clip
      came out a T-pose. `gob_anim.use` / `hum_anim.use` assign the slot now.
    - **`beast_export.export_model` exported with the last clip still assigned** (after `build_clips`): Warg.fbx's
      default pose was GetUp's. It clears the action while exporting now.
    - Unity preview-scene checks of Humanoid riders need `cullingMode = AlwaysAnimate` + `Rebind()` before a graph
      evaluates (nothing sees a preview scene).

- **Farm animals (2026-10-20):** Daniel decided the farm animals leave the Medieval Village Kit (its blocky static
  `SM_VK_Animal_*` looked like toys next to the beasts) and come here: goat, sheep, cow, horse, pig, chicken. His rule
  applies: a creature like an approved one starts from its finished parts, so the five hoofed ones are the red deer.
  - **Built headless, one file each:** the live Blender had the kit's unsaved diorama open, so every farm animal is
    built in a background Blender into its own `blender/farm_<name>.blend` (scene named after it; a background
    Blender has no window and can't switch scenes):
    `blender.exe -b --factory-startup --python tools/farm_run.py -- goat build review coats clips lowest sheets export`
    (or `-b blender/farm_goat.blend ... -- goat clips sheets export` for the clips alone). About a minute an animal.
  - **`farm_body.Hoofed`** is `deer_body` as a class. Every table and mask is in *deer units* (D); a species
    (`farm_goat.Goat`, `farm_sheep`, `farm_cow`, `farm_horse`, `farm_pig`) overrides the deer's tables there and
    sets the warp to its real size (R): `W()` scales x by KX, y by KY, the legs below `ZB` by KL and the body by KB
    (blended), applied at the very end of the build and to the bones; `W_inv()` takes positions back for the rig's
    masks, the UV cuts and the painter. The head is modelled in head space and scaled by `KH` before it is hung. Hooks:
    `extra_parts` (fused volumes), `extra_head_parts`, `extra_pieces` (shells), `skin_extra`, `coat_pattern`,
    `face_pattern`, `paint_pieces`, `wool_mask`; settings for horns (`HORN_BASE_H`, `HORN`), a clean tail tube
    (`TAIL_TUBE`), solid hooves, the fleece riding on the spine (`COAT_ON_TRUNK`), clip shapes (`GRAZE`, `RUN`, ...).
  - `farm_rig` (deer_rig's skinning; `copy_nearest_skin` for shells lying on the skin), `farm_paint` (deer_paint's
    painter with palettes per coat, bar / oval / round pupils, sleek / wool / bristle coats, `horns`, `patches`, and
    `uv_png`: a UV layout drawn without the GPU, since `uv.export_layout` fails headless), `farm_anim` (deer_anim's
    clips scaled: trunk by KB, feet and strides by KL, cadence by sqrt(KL); `Call` added; `Attack` only for the goat's
    butt), `farm_build` (scene, cameras sized to the animal, renders, sheets, `lowest`, export, `coat_shots`).
  - **The hen** is new (no approved bird): `chicken_body` (fused body + shells: beak, comb and wattles as part
    `whisker`, wings `hair`, tail, shanks and toes `claw`; 23 bones with the beasts' Root / Motion / sockets and leg
    names), `chicken_anim` (its own small pose system on `beast_rig.apply_pose`: the foot is placed, the shank tilted,
    thigh and drumstick reach the ankle by two-bone IK with the knee forward; the walk's head holds still and thrusts),
    `chicken_paint` (feather scallops, red comb and face), `chicken_build` (farm_run picks it for `chicken`).
  - **Results** (tris; coats; clips; root speeds in Unity):
    - goat 4.6k; chamois / white / pied; 12 clips (with Attack); walk 0.84, run 6.0 m/s;
    - sheep 4.6k (a fused fleece with staple lumps and curls); white / black / grey; 11; walk 0.75, run 5.5;
    - cow 5.6k (dewlap, hook and pin bones, horns, udder shell, tail tube with a switch); brown / red / pied; 11;
      walk 0.84, run 5.1;
    - horse 5.1k (mane blade from the neck's crest line, forelock, hair tail tube, solid hooves); bay / chestnut /
      grey / black; 11; walk 1.19, run 9.0;
    - pig 4.7k (snout disc, bristle crest seated by rays, curled tail tube); pink / saddleback / black / brown; 11;
      walk 0.78, run 4.8;
    - hen 2.1k; brown / white / black; 12 (Idle, Peck, Scratch, Alert, Call, Walk, Run, Flap, Hit, Death, Sleep,
      Wake); walk 0.30, run 1.65.
    Lowest vertex per clip within 3 cm, except the dead cow's ear and hooves (5 cm) and the lying sheep's fleece.
  - **Unity:** `FarmSetup.cs` (Tools > Beasts > Rebuild Farm Animals: every imported farm animal, `FarmSetup.All`
    lists their coats, pools for BeastRandomAnimator, mostly grazing) and `FarmTestScene.cs` (`Scenes/Farm_Test`,
    small groups on their own patches, goblins for scale). Installed in MedievalSetting on 2026-10-20 (assets, then
    scripts; setup run with RunCommand; reports and renders in `Logs/FarmSetup`): avatars valid, every moving clip
    `dir=(0,0,1)`. Not checked in to Plastic, not placed in the game yet.
  - **Gotchas:**
    - **Never build an existing beast in a scratch file:** a test deer build in an empty file rewrote
      `textures/T_Deer.png` at 512; it was restored from `export/Textures` (identical to the Unity copy).
    - **The leg graft left holes** where cutting the stump opened a second boundary loop or the zip doubled a face
      onto an edge (the goat had 9 open edges at the hind legs, the cow 26 round its udder). `Hoofed._rim` follows
      whole loops and fills the stray ones; doubled faces are dropped and refilled. `deer_body._graft_legs` has the
      same weakness and was left alone (the deer is approved; check its boundary edges before rebuilding it).
    - **`beast_body.ellipsoid` shells break the heat solve** (the poles are made for the voxel fuse): an udder shell
      left 1,264 vertices unweighted. Separate shells are lofts.
    - **A shallow decimation crease** survived the deer's 55 degree relax on the cow's back and the warp opened it into
      a crack: `CREASE_DEG` per species (cow 35, horse and pig 40).
    - **Thin tails decimate into strips** (the mammoth's trunk lesson): the cow, horse and pig tails are `TAIL_TUBE`s
      skinned along the tail bones.
    - **The neck's crest is not z + radius:** its rings tilt with the rising neck, so a mane placed that way sat
      inside the neck. `crest_line()` walks the loft's own ring tops.
    - **Hanging tails turn with the trunk:** a grazing horse's tail swung up behind it. `TAIL_HANGS` adds the trunk's
      pitch back on Tail1; `TAIL_FLOOR` drags tails lying on the ground.
    - A fleece over the leg tops must ride on the spine (`COAT_ON_TRUNK`), but only near the legs' axes and never the
      grafted lower legs (they stretched into boots, and the belly sagged with the stride).

- **Zombie wolf (2026-10-23):** a unit from Daniel's card game ("zombie wolf"), in the undead batch (zombies,
  skeletons and the ghoul are Humans). Daniel: "don't bother with adding them to the game, build the creatures" - so
  model, paint and export, no game wiring, nothing copied into MedievalSetting. Built headless into its own
  `blender/zombie_wolf.blend` (the live Blender had humans.blend open for another session): `tools/zwolf_run.py`.
  - **The wolf's skeleton exactly** (`wolf_body.rest_bones`, landmarks, head warp) and the rig is named `WolfRig`:
    the export's bind pose matches Wolf.fbx bone for bone (checked: max rest-matrix difference 0.0), so the wolf's clips
    bind to it in Unity too. `zwolf_anim` keys `wolf_anim.CLIPS` onto it (`ZombieWolf_<clip>` actions, exported as
    `ZombieWolf@<clip>.fbx`, so `ZombieWolfSetup` stands alone).
  - Built: 5,076 tris (fur 3,891, jaw 392, tongue 108, teeth 256, eyes 120, rib bars 300), 41 bones, one mesh with
    35 groups, one UV layer; three coats `T_ZombieWolf` (grey), `_Dark`, `_Pale` at 1024², no normal map (the wolf
    has none). Geometry: the starved body (narrow ribcage, tucked-up belly, wasted thighs/shoulders/neck, thin legs,
    knobby joints, thin tail), the spine's processes, hip points, pin bones, shoulder-blade ridges, the torn right
    flank (a 3.4 cm cavity, raised torn rim, five rib bars, one snapped), a shallow torn patch on the left haunch, the
    torn right ear, the drawn-back upper lip with the upper teeth hanging outside the jaw, deep sockets, gaunt cheeks,
    bald patches sunk 2.5 mm. Paint: the rot, bruises, veins, the painted ribs, the cavity, blood, milky eyes, gums,
    yellow teeth, the mud and grime. Coats and the second wound are my calls, not reviewed.
  - Checked: `weights` unweighted 0, over4 0; non-manifold edges 0 after `tidy`; lowest vertex per clip (standing
    clips 0.0, Lunge -0.008, Death and GetUp -0.025); EEVEE frames of Walk, Run, Bite, Lunge and Death round the wound
    and the face (no tearing; the ribs stay seated); the stress-test pose; the UV layout and the textures; the game
    camera (22 m, 50°, fov 30) against the wolf's (a one-off render of beasts.blend's wolf at the same cameras,
    `renders/zwolf_vs_wolf_game.png`: thin and dark, the broken pale spine and the red flank read; the eyes are a
    pixel). Dead, the thinner trunk lies 5.9 cm up at its lowest, the
    wolf's 4.8 cm: no clip change needed. `ZombieWolfSetup.cs` compiled offline against MedievalSetting's editor
    assembly (output in a temp folder).
  - Gotchas:
    - **One degenerate face fails the heat map for every bone.** Tufts at 0.62 of the wolf's radius collapsed in the
      decimation into "pillows" (two faces on three vertices) and fins: 2,098 of 2,619 vertices came out unweighted
      with only "Bone Heat Weighting: failed to find solution for one or more bones" in the log. The tufts are 0.85
      now, the centre-line ones dropped, and `zwolf_body.tidy` drops pillows and degenerate faces after the
      decimation and reports the non-manifold edges. Check `weights.unweighted` after every build.
    - **One-sided sculpts** (the wound, the ear) run after `fuse_body`'s symmetrize, and the collapse is not
      symmetric: `beast_body.fuse_body(dec_symmetry=False)` (new parameter, default True: the others are unchanged).
      `PART['bone']` = 17 is new too.
    - **Paint "inside the hole" from the outline alone** painted a red face where the sculpt had not dented (skin
      facing up at the top of the outline). Each vertex's real depth under the old surface goes into `info.b`
      (`wound_dent`) and gates the painter.
    - **What read wrong:** round Gaussian bald patches looked like stickers with a dark outline; a patch ringing a
      leg looked like a bandage; the continuous spine strip like a zipper; the first coat came out near-black (the
      wolf's layout lost). Now the patches are domain-warped and frayed, the fur thins into them in strands, the leg
      patches sit on the outside, the spine strip is broken, the coat is lighter.
    - **Headless:** `uv.export_layout` fails, so `farm_paint.uv_png` draws the layout. Open .blend files with
      `--factory-startup` too: without it the user's add-ons load (MPFB, the Blender MCP add-on).
  - Unity install (Daniel runs it): copy `export/ZombieWolf.fbx`, `export/Anims/ZombieWolf@*.fbx` +
    `zombiewolf_clips.json`, `textures/T_ZombieWolf*.png`, then `unity/Beasts/Editor/ZombieWolfSetup.cs` (commands in
    the README), then Tools > Beasts > Rebuild Zombie Wolf; check `Logs/ZombieWolfSetup/setup_report.txt` (avatar
    valid, moving clips `dir=(0,0,1)`). It makes the materials, `Prefabs/ZombieWolf`, `Animation/ZombieWolfAnims` and
    lineup renders; it does not touch Beasts_Test or any scene.

- **Giant bat (2026-10-23):** a unit from Daniel's card game, the first of three (bat, giant turtle, leech). Daniel:
  "Keep moving on the creatures" and "don't bother with adding them to the game, build the creatures" - model, paint,
  clips and export; no game wiring, nothing copied into MedievalSetting. Built headless into `blender/bat.blend`
  (the live Blender is another session's): `tools/creature_run.py -- bat <steps>` runs `bat_build`'s steps.
  - My calls (Daniel gave no details): wolf-sized body (0.80 m nose to rump), 2.9 m span, big upright ears, a pug
    snout with an upturned nose pad and a nose leaf, two long upper fangs outside the lower jaw, red eyes, dark
    brown-black fur with a rusty mantle, dark leather wings thinning and reddening toward the trailing edge; no tail,
    no tail membrane; always in the air: the bind pose flies with the body 1.6 m over the Root (`bat_body.H`), so the
    game moves it on the ground and only Death comes down. Idle is a lazy hover (no roost: a hanging idle needs a
    ceiling at a known height).
  - **The dragon's wing code takes a `WingSpec`** (`dragon_body`: `finger_pts`, `wing_chain`, the new `wing_bones`,
    `arm_panel`, `_mem_frames`, `_mem_weights`, `membrane_pose`, `build_membranes` take `ws`; the dragon's is
    `DRAGON_WING`, every default its old constant). Checked against a snapshot taken before the change: the dragon's
    rest bones, arm panels, membranes (positions and weights) and the matrices of 8 clips at 18 frames are
    bit-identical. The bat's spec: 4 fingers (2, 3, 3, 2 bones), a flank edge down the body to the knee and the ankle
    (`flank`, weighted Chest, Spine1, Thigh, Shin), the ankle's weight on Shin (`att_w`), smaller scallops.
  - Built: 4,120 tris (`BatBody` 3,160: fur 1,896, arm/finger/leg lofts 632, claws 88, ears 156, eyes 100, fangs 68,
    jaw 220; `BatWing` 960), 74 bones (24 of them the arm panels' helpers), `T_Bat` 1024² for both meshes,
    `M_BatWing` two-sided. Weights: unweighted 0, over4 0; the fur's heat solve runs on a copy of the fur alone
    (`bat_body.heat_weights`), the pieces carry their own weights (a `dragon_body.Acc`).
  - Clips (`bat_anim`, its own pose system in the hen's style with the dragon's wing strokes and fold): Idle 1.6 s,
    Hover 1.07 s, Fly 0.67 s (4.5 m/s), Dive 1.5 s (`Bite` 0.73 s), Screech 1.8 s (`Screech` 0.5 s), Hit 0.5 s, Death
    2.0 s (`Dead` 1.3 s). Lowest vertex: flying clips above 0.6 m, Dive 0.19 m, Death -0.012 at the landing. Fly
    traced over 3 loops (`beast_review.motion_trace`): 3.0 m a loop along -Y, Motion's turn 0, the head's step at the
    seam 2 mm (inside the loop up to 3 mm). Export re-imported in a background Blender: 74 bones (Motion a root,
    sibling of Root), two meshes with one UV layer each, Fly's Motion -3.0 m with the head steady.
  - Checked by eye: EEVEE close-ups of the face, the wing from above and below, every clip's frames from two sides,
    the UV layout and texture, the game camera beside the wolf (appended from `blender/beasts.blend`,
    `renders/bat_vs_wolf_game.png`: the red-brown wings carry it, the body is a dark dot between them).
    `BatSetup.cs` compiled offline against MedievalSetting's editor assembly (output in a temp folder).
  - Gotchas:
    - **A crashed headless run writes the textures but not the .blend.** The next run on the old file painted a new
      `T_Bat` layout over old UVs: scrambled wings (an eye on the membrane). Rebuild in one run (`build ... export`).
    - **`n.startswith("WingF")` also matches WingForearm**: finger tests need `n[5].isdigit()` (the dragon's way).
    - **The depth cap by the shoulder's height was not enough lying down** (roll, yaw and curl lower the tips too):
      `bat_anim._wings` bisects the stroke's 'Y' until every wing joint and finger tip clears `Pose.floor` by 2 cm.
    - The ground disc hides an underside shot (`review` hides it for `Below`).

- **Giant turtle (2026-10-23):** the second unit of the round (Daniel's words as for the bat). Built headless into
  `blender/turtle.blend`: `tools/creature_run.py -- turtle <steps>`.
  - My calls: after the alligator snapping turtle, made huge and slow: a 2.6 m carapace 1.6 m high, domed, three keels
    of pointed knobs, a saw-toothed back rim, moss, lichen and barnacles; a small plastron with bridges; a big wedge
    head with a hooked beak, amber star-pupilled eyes, the pink tongue lure (Idle gapes to show it); a thick wrinkled
    neck; columnar elephantine legs on round feet; a short crested tail. One texture (1024 was enough for the shell).
  - Built: 5,832 tris (skin 2,796, shell 2,208, lower beak 312, eyes 120, claws 396), 35 bones, `T_Turtle` 1024²;
    weights unweighted 0, over4 0; UV overlap 0.
  - Clips (beast_anim, `Species(extra=_retract)`): Idle 4.0 s, Walk 1.6 s (0.34 m/s), Bite 1.1 s (`Bite` 0.53 s),
    Withdraw 1.2 s (holds), Emerge 1.4 s, Hit 0.5 s, Death 2.5 s (`Dead` 2.0 s). Lowest vertex: standing clips 1.6 cm,
    Withdraw/Emerge 3.1 cm (a hind foot's pad on the way in), Death 1.9 cm. Walk traced over 3 loops: 0.55 m a loop,
    Motion's turn 0, head step at the seam 1.7 mm (inside 2.5 mm). Export re-imported: 35 bones, one mesh, one UV
    layer.
  - Checked by eye: the face and head from the side and 3/4, the shell from above (scute layout), the texture and UV
    layout, every clip from two sides, Bite/Withdraw/Death close-ups, the game camera beside the wolf (it reads as a
    big mossy knobbed shell; the head is ~10 px). `TurtleSetup.cs` compiled offline.
  - Gotchas:
    - **Shared code, additive:** `beast_rig.heat_weights` / `skin_with_pieces` (the bat's heat-on-the-fused-part-alone
      moved there; the bat rebuilt with the same report) and `beast_paint.unwrap(island_scale=)` (default None: the
      others unchanged). The carapace's hidden inner dome and the plastron are tagged in `info.b` and packed small.
    - **The withdraw drops the shell after the legs fold** (`ease(k) ** 1.6`): dropping it first pushed the feet 6 cm
      into the ground; the hind toes curl up when tucked, not down.
    - **Death's head:** with the shell 0.4 m lower, the standing neck bends put the head 45 cm under the ground; the
      neck barely bends now and the head slides out (`retract` -0.3).
    - **A separate lower beak reads as a tube under the head** (the wolf's jaw lesson again): it is deep and as wide as
      the head's underside, skin-coloured behind its horn tip, its top tucked inside the upper beak's edge; from the
      side it still reads as a lip.

- **Leech (2026-10-23):** the third unit of the round (Daniel's words as for the bat). Built headless into
  `blender/leech.blend`: `tools/creature_run.py -- leech <steps>`.
  - My calls: a medicinal leech made big and swampy: 1.8 m, flattened, ringed, dark olive-black with two rows of rusty
    spots and a broken pale stripe, a mottled yellow belly; a round oral sucker with three rows of teeth (a lamprey's
    mouth: it reads at the game camera), eye spots, a broad rear disc; glossy wet. 1024² (the brief allowed 512).
  - Built: 2,376 tris (tube 2,128, teeth 120, disc 128), 26 bones (Sucker, Body1-10, Head, Swell1-10, sockets),
    `T_Leech`; weights unweighted 0, over4 0 (by arc length, no heat map); non-manifold 0; UV overlap 0.
  - Clips (`leech_anim`, a pose = a curve): Idle 3.0 s, Crawl 2.0 s (inchworm, 0.33 m/s), Lunge 2.2 s (`Bite` 0.6 s,
    `Drain` 1.1 s, `Drain2` 1.5 s: the hydra's numbering for repeated events), Hit 0.5 s, Death 2.0 s (`Dead` 1.6 s).
    Lowest vertex 2 mm except Death -1.8 cm. Crawl traced over 3 loops (0.65 m a loop, Motion's turn 0, seam step
    0.1 mm). The export keeps the Swell bones' scale keys (checked on a re-import).
  - Checked by eye: the 3/4, top, side and mouth views, the texture and UV layout, every clip from two sides, the
    crawl, lunge and death close-ups, the game camera beside the wolf (a dark stick with orange dots, about the wolf's
    length). `LeechSetup.cs` compiled offline.
  - Gotchas:
    - **`recalc_face_normals` turned the tube inside out** (the cup folding inward fools the outside test): the
      painter's back/belly masks swapped (spots on the belly). `build_body` orients the tube by a test on its middle
      rings and builds with `recalc=False`.
    - **Seams the builder marks are kept only outside `n_fur`:** `beast_paint.mark_seams` redraws seams on the fused
      part, so the leech sets `n_fur = 0` (all of it is "pieces") and keeps its own cuts.
    - **A Bezier arch peaks into a V:** the crawl's loop is a bell (`sin^1.4`) fitted to the length; the lunge's
      latched body needs slack (1.24x) or it hangs straight as a stick.
    - **Rolling onto its side needs the centre line lifted** by the section's half-width (`_clip_death`).
    - `beast_rig.apply_pose(scale_bones=())`: new, default off (every other creature keys as before).

- **Golden eagle (2026-10-24):** Daniel: "You know, one of the models we need is an eagle or a falcon, can you model
  us one of those? Dont use the chicken as base, that model is bad". His rule: model first, then animate. This step is
  the model: shape, feathers, paint and a rig that poses it perched and spread. No clips, export, Unity setup or game
  wiring; Daniel sees the renders before the next step. Built headless into `blender/eagle.blend`:
  `tools/creature_run.py -- eagle build check review closeups game presets` (about 30 s). Nothing comes from the hen;
  the code reused is `dragon_body.Acc`, `_bone`/`_frame`, chain weights, `beast_body`, `beast_rig.skin_with_pieces`,
  `beast_paint` and `beast_review`, plus the bat's two-layer underside.
  - My calls (unreviewed; listed in the README):
    - a golden eagle at natural size: 0.85 m beak to tail tip, 2.05 m span, ~0.6 m perched;
    - the hooked beak with its cere, a brow shelf, amber-brown eyes, the golden crown and nape;
    - feathered trousers and tarsus, yellow toes, black talons;
    - six slotted fingers (P5-P10) and a 12-feather fan tail;
    - two presets, golden and bald;
    - the bind pose is the flight posture on its feet (the body level, the wings spread, the tail closed). Perched and
      spread are pose functions (`eagle_pose.perched()`, `spread()`; `folded()` is the bind pose with the wings folded).
  - Built: 5,224 tris. The fused body 2,000, the upper beak 192, the lower mandible 108, the eyes 100, the tarsi and
    toes 568, the talons 176, the wing's flesh 336, the cards 872 plus their undersides 872. 84 bones; `T_Eagle` and
    `T_Eagle_Bald` at 1024² (84% coverage, UV overlap 0); `M_Eagle` and `M_Eagle_Bald` cull back faces. Weights: 0
    unweighted, 0 over 4.
  - Feather bones:
    - one bone per primary (its covert rides it) and per tail feather;
    - the secondaries and greater coverts ride `WingSecA/B`, the tertials `WingTertA/B` (all children of the forearm),
      each card's weight fixed from its root's place between the two heads;
    - two bones turned the same way move every card between them rigidly about its own root (an LBS blend of equal
      rotations is a rotation); `eagle_pose.RIGID_PAIR` derives A's turn from B's;
    - 28 cards a wing fold on 4 bones; one rigid bone could not fold them (they would point out sideways).
  - Layers: one order for both poses, P10, P9, PC9 … P1, PC1, S1..S12, T1..T4, G1..G12, A2, A1. In the open wing the
    proximal feather lies over the distal one; folded, the order runs inside to outside.
  - The fold (`eagle_pose.FOLD` / `FOLD_ANG`, in the body's rest axes) is one stack in a plane against the flank,
    leaning in at the top:
    - the humerus aims at `elbow`; the forearm runs forward to `wrist`, projected into the plane;
    - the secondaries angle 32° down-back;
    - the hand and the primaries turn 2° in about the vertical together.
  - Checks (`eagle_build.check`; bind / perched / spread):
    - card through the body: 0 / 0 / 0;
    - card through card: 0 / 0 / 0;
    - card vertices inside the body: 0 / 0 / 0;
    - cards against the wing's own flesh: 0 / 292 / 0 (folded, the remiges' bases run along the forearm slab under the
      secondaries; not visible in the renders);
    - lowest vertex: 0.2 mm, -4 mm (gripping talon tips) and 1.13 m.
  - Gotchas:
    - **A stack crosses itself at 1 mm layer steps** if its cards' curve, drop or camber differ. The curve is a
      fraction of the card's own length, so a short covert's tip dips more than its long primary (PC5 crossed P5).
      Match them per stack and keep the camber at 1.5%.
    - **Root offsets must run along the fold plane's normal.** A forearm tilted out of the plane reversed the
      secondaries' order along its length (S1 ended up outside S12). Turning the primaries in without the hand put
      P10's root above P1's.
    - **The tertials on the humerus dived into the body** when it folded. They ride the forearm now and land behind
      the elbow.
    - **Two mirrored stacks leaning in can't overlap without cutting each other:** their planes cross at the midline.
      The wingtips meet over the tail instead of crossing (the brief asked for crossing).
    - **A per-face filter for the quills lies.** A long card face whose root end sits under the tail coverts counted
      along its whole length; `overlap_report` estimates the card's own t at each hit (`_t_on_card`). The nearest-face
      normal sign was no inside test either (it flagged the tail tip 20 cm from the body); ray parity is.
    - **No hand slab:** folded, the primaries lie along the hand and went through it. The primary coverts and the alula
      cover the hand.
    - **A gap between the folded wing and the body:** a flat stack meets a round body on one line. Leaning out at the
      top tucked the bottom in but opened the top, which the game camera sees. It leans in now, the trunk section is
      boxier (`loft(shape=0.82)`), and scapular, shoulder and flank volumes fill the sides.
    - Workbench colours from a colour attribute: `color_type='VERTEX'` in 4.4 (`'ATTRIBUTE'` errors). `quick` shows the
      debug colours of a `model` build (no paint).
    - A material on no object is dropped at save: `M_Eagle_Bald` has a fake user.

- **Golden eagle, revision (2026-10-24):** Daniel saw `eagle_presets.png` and `eagle_game_spread_x2.5.png` and answered
  my review of the first pass: "Yes, fix them", and "the head looks like a vulture structure, needs a pass too". Still
  the model only (no clips, no Unity, not committed). The first pass's renders are in `renders/eagle_before/`. The new
  `compare` step renders the same fixed views (`eagle_cmp_*.png`), and `tools/before_after.py` (system Python,
  Pillow) makes the sheets `renders/eagle_ba_<head|spread|fold|legs|game|presets>.png`.
  - The head:
    - a short, broad, flat-topped skull: a boxy `HEAD` loft, 6.8 cm across, 7.9 cm across the brows; poll to beak
      tip 12.5 cm, was 14.2;
    - brow shelves over the eyes, the outer edge and front end down and the front turned in;
    - an eyeball (`dome`, r 9.4 mm, 5 mm high) in a socket sculpted round its axis (`_socket`), looking 45° forward;
    - a short, thick neck and a nape ruff;
    - the beak built by `_mandible` from side profiles (`BEAK_UP`, `BEAK_LOW`): 4.7 cm from the cere, 2.9 cm deep at
      it. Its (h, t) are in `root`, and the painter colours the cere, nostril, cutting edge and hook by them. The lower
      mandible is in the beak's colours; a soft gape;
    - the landmarks moved: `POLL`, `BEAK`, `HINGE`, `CHIN`, the sockets.
  - The spread wing:
    - P1 62° to P10 4°, lengths 0.40-0.46 m, laid on a near-rectangular outline;
    - fingers 5-7° apart, separated over their outer 34-42% (`P_EMARG`);
    - secondaries 0.33-0.40 m, fanned 72-97°: chord ~0.44 m; span 2.03 m;
    - the flesh slabs painted as coverts; the alula flat along the hand.
  - The fold:
    - `FOLD` leans 32°, the forearm lower; S1 at −16°;
    - `FOLD_CLOSE` closes the secondaries' 25° fan: A is turned toward B about the fold's normal. The cards between
      blend two rotations about one axis, a rotation scaled by cos 12.5° at most;
    - P −3°, tertials −4°, the alula −12° and lifted 1.6 cm (`FOLD_LIFT`: a translation of the bone along the fold's
      normal);
    - scapulars: `SC1-4` per side on `ScapL/R` (children of the chest). Rest: on the back, 10° outward slope. Folded:
      rolled 20.5° and turned 3° out (`FOLD_SCAP`);
    - rounded tips (`CHEV` 0.45, last row 0.70; fingers 1.0);
    - 12 greater coverts, 7.5 cm wide, with three rows, angled 74-86°;
    - no undersides on the greater and primary coverts and the scapulars (`NO_UNDERSIDE`, never seen): 280 tris saved.
  - The legs: tarsus 9.2 cm (`ANKLE` at z 0.110), a feathered sock over the top 44% (`TARSUS_SOCK`) with a slimmer
    lower half; the shin 16.3 cm; the trousers fuller, past the ankle, flaring; the trouser paint mask now round the
    thigh-shin line only (`_trousers`).
  - Golden paint: the hackles `#9a7a3c`/`#563c20` on the hind crown, nape and hindneck; subtler bars (`bar_k`,
    `tail_bar_k`); darker coverts; the iris `#5a3210`/`#76481b`.
  - Built: 5,356 tris (was 5,224):
    - the fused body 2,000; beak 260, lower mandible 180, eyes 100; tarsi and toes 624, talons 176; wing flesh 280;
    - cards 1,032 plus undersides 704: primaries 288, primary coverts 72, secondaries 192, greater coverts 192,
      tertials 64, alula 16, scapulars 64, tail 144;
    - 86 bones; 83% texture coverage, UV overlap 0; weights 0 unweighted, 0 over 4;
    - perched 0.60 m tall (0.62), 0.84 m long (0.87).
  - Checks (bind / perched / spread): card through the body 0 / 0 / 0, card through card 0 / 0 / 0, card vertices
    inside 0 / 0 / 0, cards against the wing's flesh 0 / 296 / 0 (the remiges' bases along the forearm slab and the
    scapulars' roots over the humerus slab, under the cards), lowest vertex 0.2 mm, −4 mm, 1.13 m.
  - Gotchas:
    - **The secondaries at 32° down made the planks:** each card's lower edge steps 1 cm from the next. At 16° with
      the fan closed, the steps are millimetres.
    - **The folded wing's top edge is the remiges' inner vanes** (5-6 cm above the forearm: the trailing vanes face up
      when folded). Only cards rooted on the body can cover it, hence the scapulars. A cape of flat cards can't follow
      a round back: at 18° outward slope they cut the back (spread), at 5° they stand off it. The bone's roll does
      both (10° rest, 30.5° folded).
    - **Reverse-overlapped greater coverts** (the distal one on top, as on a real upper wing) give a row of tips when
      folded. Over a secondaries' stack that climbs 12 mm toward the elbow, they float 1-2.5 cm in the open wing
      (tried, dropped). Rolling each card about its shaft (louvres) crossed them as the fan closed. Rigid on the
      forearm, folded, they hang down as one board. They overlap the usual way: 12 narrow ones, so the folded steps
      are small.
    - **The wingtips don't meet over the tail:** turned further in (4-6°) they cut the rump; tilted up (2-8°) they cut
      the outer tail feathers and the scapulars. They reach the tail's middle beside it.
    - **The sculpted feather clumps were one-sided** (noise on the symmetrized body), so the right side's cards hit
      where the left's cleared. `_fur` mirrors them.
    - **The old trouser mask** (all below z 0.30) painted the whole belly and breast tawny.
    - **Euler Y on a mirrored blob:** −Y raised the brow's outer edge. The first pass's "horns" at the brow came from it.

- **Golden eagle: the third fold pass reverted (2026-10-24).** Daniel, comparing `renders/eagle_ba_fold3.png`: "Lets accept the issue and animate it... wait. The before actually looks better than the after, can we go back?" The second pass's eagle sources (`src/eagle_body.py`, `eagle_pose.py`, `eagle_build.py`, `eagle_paint.py`, saved by the third pass before it started) are back and the model rebuilt from them (`build check review closeups game presets`): 5,356 tris, 86 bones, all card checks 0 in bind / perched / spread, the hidden card-vs-flesh 296 when perched, lowest vertex 0.2 mm. The README describes the second pass again; the entry below is the reverted attempt's record (its approach, numbers and open points), kept for the next try. Daniel accepts the folded wing as it is ("accept the issue and animate it"): next are the clips and the Unity setup.
- **Golden eagle, the folded wing's third pass (2026-10-24):** Daniel looked at `renders/eagle_ba_fold.png` and asked:
  "Do another pass on the folded wing first: curve it around the body so it doesn't read as flat boards from behind
  and above." Still the model only (no clips, no Unity, not committed). The second pass's renders are in
  `renders/eagle_before_fold/` (and the fold views, game shots and measurements of that model, made with the new
  steps); the sheets are `renders/eagle_ba_fold3.png` (golden), `eagle_ba_fold3_bald.png`, `eagle_ba_fold3_game.png`,
  `eagle_ba_spread3.png`; the sections `renders/eagle_fold_sections.png`.
  - What it is now (`eagle_pose`, "the folded wing"):
    - the flat stack (`fold_stack`): one plane, `FOLD_PLANE` leaning in 35°, its back end turned 6° in toward the
      midline and raised 7° (the wings converge on the tail); the forearm along the plane's long axis (`FOLD['wrist']`
      None), so the secondaries' roots and top edges are level; the fans closed (`FAN`, by each card's open-wing angle);
      the primaries 3° down and dropped 2.4 cm under S1's top edge (`FOLD_DROP_AUTO`: their band is the folded wing's
      lower edge); the coverts' and the tertials' top edges set 3 and 4.8-6 cm above the secondaries' (`FOLD_TOPS`);
      the tertials lifted 1.2 cm outside the coverts, the alula 6 mm (`FOLD_LIFT`);
    - the wrap (`_wrap`): a convex profile along the body (`WRAP`: 12 cm radius over the back, 14.5 cm down the side),
      starting in the plane at the secondaries' top edge; each unit (a card's bone or the coverts' pair) is turned
      about its own top edge by the profile's turn at its arc and hung there, tangent to it. Tertials 23-29° over the
      back (meeting the other wing's over the rump), coverts 14° over the shoulder, the secondaries the plane (they
      ride S12: one facet), the primaries 10° in toward the flank and the tail's sides;
    - why it can't make cards cut each other: of two tangents to a convex curve, the one further round stays inside
      the other past its tangent point, so a card hung further round stays inside every card outside it as long as its
      top edge is no higher; the drop and `FOLD_TOPS` keep that order;
    - the scapulars: `FOLD_SCAP` (30.5° roll, 1° in); the perched tail: `PERCHED_TAIL` (3° up, was 6; 10° closed past
      shut, so the wingtips lie at its sides).
  - Bones: one per secondary (`WingS1..12`) and per tertial (`WingT1..4`), the greater coverts on `WingCovA/B`; 114
    bones (was 86). The rest frames are the cards' own, so the bind and spread poses are unchanged (the spread renders
    differ by under 0.3/255 on average, from the UV islands packed in another order).
  - Built: 5,356 tris, unchanged (the fused body 2,000; beak 260, lower mandible 180, eyes 100; tarsi and toes 624,
    talons 176; wing flesh 280; cards 1,032 plus undersides 704); weights 0 unweighted, 0 over 4; UV overlap 0, 82%
    coverage.
  - Checks (bind / perched / spread): card through the body 0 / 0 / 0, card through card 0 / 0 / 0, card vertices
    inside 0 / 0 / 0, cards against the wing's flesh 0 / 278 / 0 (under the cards), lowest vertex 0.2 mm, −4 mm,
    1.13 m.
  - Measured (`eagle_build.foldmetrics`, perched, in the body's axes; before → after): the wing's inner side off the
    body 47 / 189 → 41 / 103 mm (mean / max); its lower edge off the body 109 / 189 → 54 / 103 mm; the shell index (the
    outer face's turn over the section against the angle it spans) 0.04 → 0.46; the lower edge's flare 61° / 66° →
    58° / 60°; sky between wing and trunk or tail behind / above / low 3/4 back 29 / 48 / 14 → 10 / 32 / 13 cm²; the
    wingtips 22.4 → 14.4 cm apart (each 7.2 cm out of the middle, the closed tail 5.0 cm half wide); the wing's half
    width from above at the shoulder / mid-back / rump / tail 16 / 18 / 20 / 19 → 15 / 14 / 13 / 12 cm.
  - New steps (`eagle_build`): `foldviews`, `foldgame`, `foldmetrics` (see the README's renders list).
  - Gotchas:
    - **Flat cards can't be bent round a curve by turning each a little more than the one outside it** when they
      overlap almost wholly (the secondaries, 1-9 mm apart): turned about their own top edges they fan out like
      louvres from one line; turned about their middles they cut each other. Hung from their top edges on a convex
      profile they stay clear, but only groups whose top edges stand apart turn apart (a facet per group).
    - **The primaries are inner cards with wider inner vanes:** near the wrist their top edges stood 2.5-4.5 cm above
      S1's, so any wrap clamped the secondaries flat (or the primaries came out through them). Dropped under S1, their
      band becomes the wing's lower edge, as on the bird.
    - **The primaries sit on the trousers:** every way of lowering or turning them in (secondaries staggered down so
      the wrap fans them, the primaries turned 2° in, a 2° steeper plane) put their lower edges into the thighs. The
      wingtips stay beside the tail; they don't meet over it.
    - **The tertials' natural top edges are 2 cm apart** (rooted up the humerus), so the wrap fanned them 8° apart and
      from a low 3/4 back the far wing's showed as separate blades with sky between. `FOLD_TOPS` sets them 4 mm apart.
    - **A tight profile over the back stands the caps off:** a flat card hung from its top on a radius r stands off
      w²/2r at its lower edge (8 cm on 12 cm: 2.7 cm before the next card's own lean).
    - **The wrap is per unit, the clearance proof per card pair:** the coverts' pair is one rigid unit; they must stay
      outside S12 behind the elbow (G9-G12) and inside the tertials (hence the tertials' lift).
    - **The UV pack follows the dominant bone per vertex** (`beast_paint.mark_seams`): new bones re-pack the islands;
      the textures on disk then belong to the new layout. To re-render the old model, run its own `paint` first.

- **Golden eagle clips + Unity setup (2026-10-24):** Daniel: "Lets accept the issue and animate it" (the folded wing
  stays as the second pass left it; nothing in `eagle_body`, `eagle_pose` or `eagle_paint` changed). New
  `src/eagle_anim.py` (pose system + ten clips), clip steps in `eagle_build` (`clips cards lowest trace chains feet sheets
  gameclips gifs export reimport`), `unity/Beasts/Editor/EagleSetup.cs`. Run on the saved `blender/eagle.blend`:
  `creature_run.py -- eagle clips cards lowest trace chains feet sheets gameclips gifs export` (~2.5 min), then
  `creature_run.py -- eagle reimport nosave` without a file.
  - Clips (30 fps): Idle 6.0 s loop (perched, breathing, head turns and tilts, a rouse at 4.6 s), Walk 1.33 s loop
    (0.195 m/s), TakeOff 2.0 s (5.0 m, rising 1.5 m), Fly 0.8 s loop (6 m/s), Glide 3.0 s loop (9 m/s), Dive 2.6 s
    (16.3 m, `Strike` 1.27 s), Land 2.2 s (4.6 m, touchdown 1.47 s), Screech 2.0 s (`Screech` 0.53 s), Hit 0.6 s, Death
    2.5 s (`Dead` 1.0 s). Root motion on Motion, horizontal only.
  - My calls (the brief left them open): the height lives in the skeleton like the bat's (`FLY_H` 1.5 m: the
    GameObject stays on the ground, no pool is `vertical`); flight speeds 6 / 9 m/s at natural size; a 24-frame
    wingbeat; the stoop climbs to 2.0 m first and strikes a spot on the ground 16 cm ahead of the root (the talons stop
    7 cm up); Land brakes upright with two flaps; Death lies on the breast, legs folded back; the Unity pools chain
    TakeOff -> Flight (Fly, Glide, Fly, Dive, Fly, Glide) -> Land -> Idle, Flight and Land at weight 0; skins golden and
    bald equally likely.
  - Checks: every frame (701) through `overlap_report`: card-body 0, card-card 0, card vertices inside 0 in all ten
    clips (card-vs-wing-flesh peaks at the perched 296). Lowest vertex: the ground clips -3.2 mm (perched talons), Land
    -5.3 mm, Death -6.8 mm, Dive 7 cm. Traces: Fly 4.8 m a loop, Glide 27 m, Walk 0.26 m, Motion's turn 0, seam steps
    no bigger than inside. Hand-overs TakeOff/Dive/Land <-> Fly and Land -> Idle: 0 mm at matching speeds. Walk's feet
    drift <= 1.9 mm a frame. Export re-imported: 86 bones (Motion and Root roots), EagleBody 5,356 tris, one UV layer,
    79 groups, `M_Eagle`; Fly's Motion -4.8 m with the head steady at 1.9 m. `EagleSetup.cs` compiled offline against
    MedievalSetting's editor assembly (the `.rsp` with absolute paths, out in a temp folder): 0 errors, 0 warnings.
  - Looked at: every clip's strip from the side and above, the unfold and fold close-ups, the screech head, GIF frames,
    the game camera on Fly/Glide/Dive/TakeOff at x1 and x2.5 beside the wolf (it reads: dark broad wings, the golden
    nape, the barred tail, yellow feet at the strike).
  - Gotchas:
    - **eagle_pose's fold crosses cards on the way.** Its per-bone slerp is clean at fold 0 and 1 but crossed 500-1,500
      card pairs between (a fan's cards twist against each other at 1.1-1.4 mm layer steps; the right side was worse).
      `_place_wing` splits each bone's turn into a rigid lay of the wing's plane (G, one for the wing) and an in-plane
      twist plus the small swing left (R = G^-1 F S^-1): 0 crossings. Laying first and folding in-plane after, or the
      other way round, crossed the primaries with the scapulars; all three together is clean (the alula's lift is done
      by half the lay, or A1 touched G1 at fold 0.4).
    - **Mirror the left's basis, don't build the right's from mirrored vectors:** `a x n` of two mirrored vectors is
      minus the mirror of the cross product, so the right wing's plane turn came out improper (garbage quaternions).
    - **The back's skin rides the thighs** (up to 0.67 heat weight under the scapulars): any leg IK that turned the thigh
      (the walk, the crouch, the dive's throw, the death's fall) pushed it through the scapulars or the folded
      primaries. The thigh is held to the trunk at its perched or tucked frame (`Pose.thigh`), the knee and ankle do
      the work. Folding the legs while the scapulars are still rolled (Death) still touched: they unroll with it and lift
      3 deg (`DEATH_SCAP`).
    - **Stroke limits:** raised past ~-30 deg, or swept back (Z+) or supinated (X-) at the top, the innermost tertial
      slides over the back into the scapulars; downstrokes forward (Z-) are clean to +42 deg. The top of the beat keeps
      the wrist 0.2 flexed.
    - **Catmull-Rom keys overshoot next to a plateau:** the dive's leg throw went negative and lifted the feet onto the
      back. Envelopes use eased segments (`eagle_anim.E`).
    - **Flat feet on a turning tarsus sink:** the toes' bases sit round the ball, so the hallux's talon went 1.5 cm in
      as the ankle bent. `_leg` re-aims the ball (three passes) so the bases' middle stays put and none goes below its rest
      height.
    - Git Bash rewrites `/noconfig` into a path for `dotnet csc`: run it with `MSYS_NO_PATHCONV=1`.

Both are installed in MedievalSetting (`Assets/Beasts`, `Scenes/Beasts_Test`: 7 wolves, 10 rats, 8 goblins). Root
motion is traced over 3 loops for both: steady head offset, no loop snap.

Repo: github.com/danielgruginski/Beasts (`main`; public since 2026-10-06, CC0, for the itch.io packs). It holds the scripts and docs only; the .blend, the
exports, the textures and the renders are regenerated (see `.gitignore`). Commit and push each piece of work as soon as it is finished and checked (Daniel, 2026-10-12).

## Open / next

- **Farm animals:**
  - **In the game (2026-10-21, the user: "place those on the game and remove the placeholder animal props"; the
    user picked ambient in place, the game's layouts placing them).** MedievalSetting `Assets/Game/Farm/`: `Animal_Goat/
    Sheep/Cow/Horse/Pig.prefab` (the Beasts prefab unpacked, an `AC_<Animal>_AmbientA/B` controller, no root motion,
    cull-update, a BoxCollider at 85% of the mesh so the sheep stay shearable through `GatherDef.prop`
    "Animal_Sheep") and `Animal_Chickens.prefab` (five hens, A/B alternating, no collider). The controllers chain
    Idle/Graze/Call/Alert/Sleep/Wake (hens: Peck/Scratch/Call/Idle/Alert/Flap) by exit time; every other instance
    runs B so neighbours drift apart. 40 animals placed: Hamlet 12, Saltmere_Farms 10, ShepherdDowns 9, Greywall 3,
    MonasteryRoad 1, OrcHold 5 (the 19 loose kit props swapped in place, 21 where the kit's pens and yards held them),
    and the 21 pen ones written into the layouts (Tools~ `*_layout.py` + JSON, "z" = the old floor height) so a level
    rebuild keeps them. Game-side builder: MedievalSetting `Assets/Game/Farm/Editor/FarmLivestock.cs` (Game > Farm >
    Rebuild Livestock; refills the controllers and updates the prefabs in place, so the placed instances keep their
    overrides; re-run it after Rebuild Farm Animals to pick up new coats). The kit lost its animals in MedievalVillageKit d89bbb0 (HANDOFF 138). Not play-tested.
  - Daniel's first look (2026-10-20, in Farm_Test): "Goat is awesome actually"; the pig's snout too long, the cow's
    and the horse's snouts weird. Reshaped the same day: the deer's tapering muzzle with its thin separate jaw read as
    a beak with a bar under it on the bigger heads. Now the cow has a broad, deep, blunt muzzle (`HEAD_CAP`, a muzzle
    box, a heavy jaw), the horse a wedge-shaped face with facial crests, a soft muzzle and a tucked chin, the pig a
    much shorter snout (`KH` y 0.85), and all three a **jawline** volume that wraps the jaw's back half in skin, so
    only the mouth at the front shows. `farm_run ... body heads nosave` renders the bare head fast for such work.
    Then "the horse still needs serious improvements": rebuilt on horse proportions instead of the deer's tables (a
    plain 1.2x warp, KY 1.08: body length = withers height; the girth at half the height, knee 0.28, hock 0.32,
    fetlock 0.12 of it): high withers, a deep girth tucking up into the flank, round croup and buttocks, breast
    muscles, a deep crested neck, muscled forearms and gaskins, flat knees, thick cannons, knobby fetlocks, short
    pasterns, vertical flared hooves (`HOOF_UP`, `HOOF_CAPS`, `Horse.hoof_rows`). The mane is now a fused crest
    painted as hair falling right (`Horse.mane_mask`) with a painted forelock: the separate blade floated over the crest
    from behind. Grazing reaches down from the neck's base with the neck nearly straight (`GRAZE` searched on the
    mesh's lowest point: the deer's bends folded the thick neck into a U); the croup rides on the spine
    (`COAT_ON_TRUNK`; the thigh heaved it up in the stride). Hind stump rows must line up with the lower leg's first
    row (a 3 cm offset made a step at the gaskin). 5.2k tris.
    Then "Keep working on the head, it has to look like a horse": the head is a wedge (`HEAD_PROFILE`: top, bottom
    and width per row): deepest at a big flat round cheek, a straight face line, a smaller soft muzzle, the bottom
    line climbing from the cheek's edge to the lips, a narrow throatlatch, a flat forehead with the eyes high at the
    widest point. **No nose pad** (the deer's and wolf's glossy black pad read as a dog's nose): `NOSE_R` tiny and
    hidden, comma-shaped nostril dents in `Horse.sculpt_face`, the nostrils and lips painted dark in `face_pattern`.
    A strong brow ridge read as a visor over the eye; it is soft now.
    Then "keep working on this head": the lower jaw is **fused** for the horse (`JAW_PIECE = False`: `JAW_H` lofted into
    the head, moved by `Horse.jaw_weight` below `MOUTH_LINE`), since the separate jaw still showed as a dark plank
    along the bottom; `JAW_SCALE` 0.35 in the clips (opened wider, the fused lips stretched into a curtain). The eye
    is bigger and set in (`EYE_INSET`, `EYE_DOME`), with a thin lid line (`EYE_RING`) instead of the deer's dark ring;
    the cheek plate sits back and low as the jowl, the throat under the poll is narrow (the throatlatch). Close-ups:
    `farm_run ... closeups` (`farm_build.head_closeups`: side, front, 3/4, below; painted and bare).
    Then Daniel sent a reference (an Arabian-type horse head and neck): the neck is now **arched** (its centre line
    curves forward over the poll, the throat coming in high and thin), the head hangs nearly upright (`HEAD_PITCH`
    66) and is a short wedge (`HEAD_LEN` 0.39, a deep jowl, a small muzzle, flared nostril rims); the jowl is a big
    disc standing out sideways from a narrower head body, with a painted shadow round its edge; the throatlatch notch
    survives because the horse fuses with less fillet (`FILLET` 35); small upright ears; the brow volume made a fin
    at the eye's corner and is gone. **With the head upright the jowl sits behind the poll**, so the neck's last rings
    must stay high and thin or they swallow it. **The fused jaw's weight mask (head space) needs bounds on every side:**
    with the head steeper, belly skin between the forelegs fell inside it and was pulled down with the head while
    grazing (`Horse.jaw_weight` is bounded below the mouth line and behind the chin now). Grazing re-searched on the
    mesh's lowest point (`GRAZE` (-55, -12, -10), 68).
    Then a **normal map** (Daniel: "give the horse a normal map ... like the warg's"): `Hoofed.relief(ctx)` returns a
    per-texel height that `farm_paint.build_texture` turns into `T_<Name>_Normal` (`beast_paint.write_normal_map`,
    `RELIEF_STRENGTH`); FarmSetup adds it to every coat when the file exists. `Horse.relief`: the jowl's raised disc
    and soft rim (`JOWL`, shared with its volume and painted shadow), the nostrils' hollows and rims, the eyelids and
    brow, the jugular groove and the muscle above it, the crest's muscle, the shoulder blade, the triceps line, the
    neck-shoulder groove, the chest's division, the hamstring line (the body's forms doubled: fewer texels there).
    Gotchas: a relief mask that switches on with a hard step draws a crack (smoothstep everything); URP shows the
    relief harder than EEVEE (a hard jowl rim read as an ear-muff in Unity: check there, e.g. a preview-scene render
    to `Logs/FarmSetup/Horse/unity_head_*.png`). Daniel also noticed the **ears floating**: `EAR_BASE_H` was set for
    the old head angle and sat 2.5 cm above the skull; it is on the poll's top sides now, its base just inside.
    Then "reduce the horse face a tad": the face in front of the eyes is 15% shorter (`farm_horse._face`, `FACE_K`
    0.85 from `FACE_FROM` -0.11: the head rows, nostrils, lip, jaw and mouth line go through it; `HEAD_LEN` follows).
    Grazing re-searched on the head's own lowest point (the whole mesh's lowest is a pastern at 4.5 cm, which hid
    that the muzzle stopped 15 cm short): `GRAZE` (-74, -12, -10), 88.
    Still my calls, not reviewed: the coats, the horned cow, the leggy half-wild pig, a hen (no rooster).
  - The horse has no saddle socket or rider clips (`Socket_Back` sits over the saddle's place).
  - Young ones (lamb, kid, calf, foal, piglet, chicks) would be scaled copies with a bigger head (`KH`).

- **Gameplay:** nothing listens to the events yet (Bite damage, Howl sound). The wolves don't turn toward a
  target before biting.
- **Clips:** no turn-in-place, no sit or lie idle. The trot and gallop don't blend with each other (they are
  separate pools).
- **Look:**
  - the eyes are small domes (fine at the colony camera);
  - the lower jaw is a plain tube;
  - some tuft roots fold (about 200 sharp edges, mostly tuft tips and toes);
  - the ears are thin from the side.
- **Rat:**
  - its ears still have slightly ragged edges up close;
  - it has no swim or climb clips;
  - a rat swarm would want a cheaper variant (~1.5k tris).
- **Warg:**
  - goblin rider clips: done 2026-10-18 (Goblins `gob_ride.py`, see "Riders" above);
  - the lower jaw shows as a flat bar under the lip (the wolf's design);
  - up close the hair clumps still read a little like blades; the coat's relief is only the normal map;
  - in Death it lies on its left side: the stirrup on that side goes into the ground;
  - game side: a `Creature` definition (wild packs; ridden by goblin raiders), the Bite/Howl events.
- **Zombie wolf (2026-10-23):**
  - not installed in Unity yet, not seen by Daniel; no game side (a creature definition, sounds), by his call;
  - suggestion, not built: a lower head carriage and a slower, dragging walk would sell "undead" in motion. It is
    cheap in `zwolf_anim`: wrap the wolf's clip functions and add neck pitch (Neck1 -8, Head +4) to every pose, and
    scale Walk's cadence; the leg IK and events stay the wolf's;
  - the teeth are thin cones: from the side, up close, they read as needles with gaps; the lower teeth hide behind
    the uppers;
  - the wolf's own limits remain: the lower jaw is a plain tube (a dark plank when open), the ears are thin edge-on;
  - not in the itch.io Creatures pack.
- **Giant bat (2026-10-23):**
  - not installed in Unity, not seen by Daniel; no game side (a creature definition, the `Bite`/`Screech` events,
    sounds), by his call. The game moves it on the ground: it must not collide as a ground creature would (its body is
    1.6 m up);
  - the underside lit like the top: fixed 2026-10-23 (below, "Bat wing underside");
  - the arms and fingers are thin tubes (4-6 sides), fine at the game camera, faceted up close; the head is a smooth
    fused shape with painted fur;
  - maybe: a roost (hanging) idle with a drop into flight, a glide, a hit while diving.
- **Giant turtle (2026-10-23):**
  - not installed in Unity, not seen by Daniel; no game side (a creature definition, Withdraw as a defence state);
  - the lower beak is a separate tube (from the side it reads as a lip); the forelegs fold beside the head when
    withdrawn rather than closing over the opening; the neck slides in rather than folding into an S;
  - maybe: a Swim clip, a tower or howdah on `Socket_Back`.
- **Leech (2026-10-23):**
  - not installed in Unity, not seen by Daniel; no game side (latching: the game would hold the leech's mouth on the
    victim between `Bite` and the end of Lunge; `Drain` / `Drain2` for damage over time);
  - Lunge latches onto a point 0.4 m up in front of it, not onto a victim's real position (no IK);
  - maybe: a Swim clip (vertical undulation), a turn in place, a smaller swarm variant.
- **Golden eagle (2026-10-24):**
  - Status: the model is accepted with the folded wing as the second pass left it (86 bones); ten clips, the export and
    `EagleSetup.cs` are done (offline-compiled) and pushed. Not installed in Unity, not seen by Daniel; no game side (a
    creature definition, `Strike`/`Screech` hooks, sounds), as for the card-game units.
  - The fold's own limits remain (README, "The fold"): from a 3/4 back the near wing reads as a board; the wingtips lie
    beside the closed tail; the remiges' bases and the scapulars' roots run through the wing's flesh slabs when folded
    (296 face pairs, under the cards). Mid-fold (TakeOff, Land, Death) the in-plane-folded wing shows for a few frames
    as a narrow blade with the humerus as a stick.
  - The open wing from above still shows the greater coverts as blocks (the model's look).
  - Clips, rough: the beak opens on a plain gap (no mouth inside); Fly <-> Glide and Idle <-> Walk rely on the
    crossfade; the strike's spot is 16 cm ahead of the root, not a target (no IK to prey); Death -6.8 mm (a primary's
    tip in the first jerk); the take-off's spring straightens the legs into stilts for a few frames.
  - Not done: carrying prey on `Socket_Grip`, a perch on a branch or a cliff (Idle stands on flat ground), turning
    clips, a flight Hit/Death (both are perched).
  - 5,356 tris against the brief's ~5,000 (the beak +140, the tarsi +56, the scapulars +64, the 12 three-row
    greater coverts +96, less 280 for the coverts' and scapulars' dropped undersides).
- **More beasts:** a howdah on the mammoth's `Socket_Back` (the driver on the neck is done, "Riders"), giant elk, boar and dire variants can reuse the
  pipeline: parts, tufts, fuse, heat weights, and the painter's flow strokes.
- **Ooze, Unity side:**
  - The pending `OozeFx.cs` / `OozeSetup.cs` fixes went in with the warg's install (2026-10-12).
  - Look at the effects in play (`Beasts_Test`): the splat trail is checked in edit mode only so far.
  - Maybe a puddle decal under a resting ooze.
- **Ooze, game side:**
  - In the game since 2026-10-16 (MedievalSetting, Daniel's design; see its README "Oozes and wasps"): creatures
    `ooze`, `ooze_small` and `giant_ooze` (Ooze, SmallOoze and GiantOoze prefabs, colour by `OozeLook.Apply`) under
    the hamlet's well and deep in Greywall's sewers. The spit is hooked on the `BeastEvents` "Spit" event: the game
    points `OozeFx.spitTarget` at a mark that follows its target and times the hit itself (the glob's 0.7 s flight),
    so `OozeGlob.Landed` is not used. Lash and Grab are its blows; Crawl stands in for Walk and Run.
  - Still unused: Engulf hands the victim from `Socket_Mouth` to `Socket_Gut`. A 1.7 m person doesn't fit in a
    1.1 m dome, so hide them or crouch them inside.
  - Still unused: Puddle + Rise make an ambush.
  - Split: hook `OozeSplit.SplitInto` to make the two halves real creatures. Splitting again (halves of halves) is
    up to the game.
  - Sounds (squelch, splat, spit) via the game's SoundBank; the SFX pack has none.
- **Ooze, later:**
  - a ceiling Drop, a Squeeze (under doors and grates), a turn in place;
  - a softer neck in Split (it folds into a V just before the snap);
  - more colours: add one to both `ooze_paint.PRESETS` and `OozeLook.Presets`.
- **Dragon (started 2026-10-17, Daniel's "big test"):** a six-limbed fire dragon from his two references (perched
  on a rock; in flight). These are his calls:
  - six limbs (front legs plus a separate pair of wings);
  - about 12 m nose to tail, 2.8 m at the shoulder, 16 m wingspan;
  - "dragons will come in many colors", so the paint will be masks plus colour presets; the first is rusty red with
    a golden belly, dark horns and spikes, amber eyes;
  - a higher budget than the other beasts (one on screen, usually alone);
  - the wings attach on top of the shoulders, right above the front legs (after the first blockout: "a tad up, to
    the shoulders"; the whole wing moved 0.3 m forward and 0.2 m up, while the flank attachment `att` stayed).

  It lives in its own file, `blender/dragon.blend` (scene Dragon): `dragon_body` / `dragon_pose` / `dragon_build`.
  - **Stage 1, the blockout (done):** `dragon_build.build_blockout()` makes the 78-bone rig (`DragonRig`; the
    beasts' leg, spine and tail names, plus `WingScap/Arm/Forearm/Hand/Thumb` and `WingF{1-4}_{k}` per side, in a
    Wings bone collection) and two skinned meshes:
    - `DragonBlockout`: one loft for neck, trunk and tail with chain weights; rigid per-bone segments for the legs,
      wing arms and fingers;
    - `DragonMembrane`: Coons patches between arm, fingers and flank, with Coons-blended weights.

    `dragon_build.pose_sheet()` renders the test poses (folded, spread, downstroke, fire) into
    `renders/dragon_blockout_poses.png`. Wing poses aim each bone (direction plus membrane normal) in the chest's
    frame (`dragon_pose.solve`). The fold works: humerus back, wrist up front, fingers swept back along the flank.
  - **Daniel on the blockout:** "I actually love the horns, but the face will need a lot of work. Since the dragon
    is large, the face will actually be visible on the game." So the face gets real modelling and a bigger share of
    the budget.
  - **Stage 2, the face (2026-10-17):** `dragon_head.py`, from the perched reference.
    - **First pass:** separate skull and jaw fields with spikes as separate shells. Daniel: "an organic pass ...
      that takes primitives and smoothes them out, creating a single piece"; "the jaw is a straight line, it should
      have a proper jaw line"; "the snout is also flat, it should have some curves"; and no nose horn.
    - **Second pass (Daniel: "the jaw looks much better"; done):** ONE distance field in head space, meshed with
      ooze_body's `sdf_mesh` at 1 cm and decimated to 7.5k tris. Every primitive melts into the next with a fillet
      (smin): cranium, jowls, brow and cheek ridges, paired nose ridges, the swell over the fangs, nostril rims, and
      the lids (a ring round each almond eye).
    - **Spikes are not melted in.** Daniel: "the spikes fused with the skull made things look weird". They are crisp
      cones, seated by `seat_spike`: a ray from the tip back along the axis finds where the spike leaves the skin, and
      the base sinks in by most of its radius. Each spike rides on Head or Jaw by `jaw_weight` at its seat. This
      covers the brow, cheek, jaw and chin hooks, and the crown behind the horns.
    - **Frill ribs separate too** (Daniel picked the separate version over melted; `FRILL_FUSED = False`;
      `dragon_build.frill_compare()` renders both).
    - **Jaw fixes** after Daniel's "uv issues in the lower jaw" (there are no UVs yet; it was the blockout colours and
      faceting) and "you can use more polygons for the jaw, it is ok":
      - The gold band follows the jaw's bottom contour; picked from the decimated normals it made staircase blotches.
      - The head skin is 12k tris, the jaw kept more by `_dec_weight`. The head with its shells is 16.5k.
      - The upper lip hangs `LIP_HANG` (3.2 cm) over the outside of the narrower jaw, clear of it by `LIP_CLEAR`, so
        the slit no longer shows the inner teeth as a dashed line. The jaw swings down inside the lip.
      - In front of the corner, upper and lower meet hard (`k_ul`). A 3 cm blend there webbed the channel between
        the lip and the jaw side, and the web stretched into a curtain on opening.
      - `_dec_weight` never collapses the slit's ends (one triangle there made a strand).
      - `FANG_SWELL` stays above the slit (its sliver below the slit took jaw weights and became a rod).
      - Check: `bridges` 0. Only the mouth corners' edges stretch more than 3x when the jaw opens 34°; that is the
        lip corners.
    - **Masseter** (Daniel: "pieces of the upper skull being pushed by the bones of the lower jaw ... the masseter
      muscle is being pushed down in a weird way"):
      - The jowl reached 14 cm in front of the mouth corner. Below the mouth line its front was joined to the jaw
        inside and the upper cheek outside, so it tore between them whatever its weights. `JOWL` now ends at the
        corner.
      - `jaw_weight` in front of the corner takes the half of the field a point lies on (`parts`: up vs lo), so the
        weights follow the cut. Behind the corner the cheek blends from no jaw at the mouth line to all of it at the
        jaw's lower edge, and fades out toward the hinge. Behind the hinge the jaw's turn swung skin up into the
        skull.
      - Spikes take the skin's blended weight at their seat; a pinned hook floated off the cheek.
      - Edges stretched more than 3x on a 34° opening: 128 down to 29, all at the lip corners.
      - `CHEEK_RIDGE` tapers into the snout; its blunt end folded into a dark notch.
    - The snout and jaw are swept profiles keyed along y and Gaussian-smoothed (`MUZZLE_KEYS`, `JAW_KEYS`). That
      gives a dip at the brow, a waist and a flare round the fangs, and a lip line curling up to the corner. The jaw
      line drops to a deep angle and rises to a chin.
    - The mouth is a slit carved into the field (`Y_CORNER`, `GAP`), so the head is one skin. `jaw_weight` splits it
      along the slit and blends behind the corners, which stretch when the jaw opens.
    - `_dec_weight` keeps the lip edges (the collapse otherwise bridged the slit with a sheet from snout to chin);
      `bridges()` counts any left (0). `unfold()` runs after the decimate (a fold at the chin took the belly colour).
    - Shells: teeth (four upper per side hang outside the narrower jaw, the rest bite into it), tongue, eyeballs
      with a slit pupil, frill membranes. Horns stay `dragon_body.HORN`.
    - `dragon_body.build_blockout()` uses it (`old_head=True` brings back the lofted head). The Jaw bone and
      `Socket_Mouth` come from `dragon_head.HINGE / CHIN_TIP / MOUTH`. `dragon_build.face_sheet()` renders the head
      shut and open (`renders/dragon_face_sheet.png`).
  - **Stage 3, the real body (2026-10-17):** `dragon_skin.py`, `dragon_build.build_body()`. Daniel OK'd about 32k
    tris for the whole dragon. One skin, snout to tail tip:
    - **Body field:** like the head, melted primitives on a 2.5 cm grid (`Grid`, each primitive evaluated only
      inside its own box plus its melting margin, `pad`). It holds:
      - the spine chain: ~150 overlapping ellipsoids along `BODY_ROWS`, each hanging below the spine like the
        loft's section;
      - muscles: shoulders, upper arms, forearms, haunches, calves, wing roots, the wings' biceps. No pectoral:
        Daniel saw the round chest muscle as "this bulge ... does not feel right", and a flat sheet stuck out like
        a shelf. The chest is the spine chain's own deep section, widened a little at the front;
      - legs and wing arms as round cones per bone with joint knobs;
      - toes, four per foot, raised at the knuckle.
    - **Seam:** the body is meshed and decimated to 12.5k, the head as before (12k). They meet at a plane square to
      the neck's spine, `CUT_ARC` = 45 cm down from the poll.
      - Both fields hold the neck chain and the head near it (`head_field_with_neck`; the body grid unions
        `DH.head_field` in `head_region`), so the two cut loops lie on one surface. `zipper()` stitches them.
      - A plane square to the head's axis sliced the curving neck from the throat almost to the chest: the head's
        grid edge became a flat cap and the zip a 39 cm skirt (a box corner under the throat).
    - **Weights:** Blender's heat map on the skin (`heat`: deform bones minus Root/Motion/Jaw/sockets/wing
      fingers). The head's own weights (`DH.head_weights`) fade into it over the last 30 cm before the seam. Empty
      vertices fall back to `chain_weights` (none so far), then smoothing and 4 influences.
    - **Shells** (`build_shells`): the head's (`DH.head_shells`); the horns; dorsal spikes from behind the crown to
      the tail tip; claws on the toes and thumbs, seated on the skin and weighted from the nearest skin vertex; the
      wing fingers (lofts, chain weights). The membranes are `dragon_body.build_membranes` (Coons, unchanged).
    - **Objects:** `DragonBody` (skin + shells, 29.6k tris) and `DragonWingMembrane` (1.2k) in `DRG_Body`. The
      blockout's collection is excluded from the view layer.
    - **Checks:**
      - `rep["loops"]` is (1, 1, ...): exactly one cut loop on each side;
      - no non-manifold edges except the frill and membrane sheets;
      - `body.unweighted == 0`;
      - the head's `bridges == 0`;
      - renders: `pose_sheet(out="dragon_body_poses")`, `face_sheet(out="dragon_face_on_body")`.
    - **Decimation lessons** (`DH._decimate`, shared by head and body):
      - the collapse must triangulate itself (`use_collapse_triangulate`): bmesh triangulating its leftover quads
        made non-manifold edges;
      - no symmetric collapse: it left "pillows" on the centre line (two triangles on the same three vertices,
        hanging off the surface), which broke the skin's copy;
      - `_drop_pillows` still runs first, before the edge flips (beautify_fill turned them into cracks);
      - mirroring the dense mesh first (`symmetrize`) made it worse.
    - **Not done:**
      - Colours are still blockout vertex colours; the gold blotches up the neck and legs go when the paint is
        per-texel.
      - Dorsal spikes poke through the folded membrane.
      - Raising the wings (fire pose) tents the shoulder skin with a fold down the flank.
      - The membranes' flank edge was laid out for the blockout's body.
      - Shells are about 7.5k of the total: eyes at 24x14 and teeth at 6 sides could be cheaper.
  - **Stage 4, the paint (2026-10-17):** `dragon_paint.py`, `dragon_build.paint()`. Daniel: normal maps are worth it
    on a creature this big; other material properties are optional.
    - The build writes a part id per vertex into the `info` attribute (`dragon_skin.PART`), which
      `beast_paint.bake_data` bakes with position, normal and AO.
    - **UVs:** smart project on `DragonBody` (one closed skin: no natural seams), one density, then the head x1.7,
      the eyes x2.5, teeth and mouth smaller; packed (about 1,400 islands, 69% coverage). The membranes are a
      planar projection from above in the bind pose (left wing on top, right below).
    - **Relief, from 3D positions** (so it is continuous across islands); `RELIEF` is 2.6:
      - pebbled scales: 3D Voronoi cells in four sizes, blended by region, grooved at the borders and raised
        toward the tail-ward edge;
      - belly plates: the pitch follows the section's depth; plates across the jaw's underside too. The underside
        is measured within the cross-section; with the full offset the chest's front failed;
      - horn rings; grain on spikes and claws; tongue papillae; frill veins; radial and fine veins on the wings.
    - **Presets:** `PRESETS` holds rust (Daniel's), ash and bronze (mine). Each is its own albedo over one normal
      map: `T_Dragon`, `T_Dragon_Ash`, `T_Dragon_Bronze`, `T_Dragon_Normal`, and the `T_DragonWing*` equivalents.
      - The materials are `M_Dragon` and `M_DragonWing`; `dragon_paint.use_preset(name)` swaps them in Blender.
      - The scale shading fades out where the plates take over; the plates showed scales in the colour otherwise.
    - **Not done:**
      - a few stray texels where island margins meet (part interpolates to "mouth");
      - the pupil is still a slit of vertex resolution on the eyeball (the iris paint is per texel);
      - no export to Unity yet.
  - **Stage 4b, paint at 4096 (2026-10-17)**, after Daniel's "we need more pixels for the texture, I can see it is
    pixelated", "specifically, the wings texture isn't that good" and the nostrils note:
    - **Sizes:** body 4096 (66% coverage, ~2.4 mm a texel), wings 4096 with both wings on one mirrored planar layout
      (~2 mm a texel; 29% coverage, the wing's outline in its square). `RELIEF` 5.0 / `RELIEF_WING` 4.0
      (`height_normals` works per texel, so the strength doubles with the size). Textures: four 4096 body maps, four
      4096 wing maps.
    - **What "pixelated" turned out to be** (look at the height and normal maps at texel scale before raising the
      size again):
      - every plate's and scute's free edge dropped in one texel, so the edges drew stair-steps. `EDGE` now ramps
        each cliff over 8 mm;
      - the plates' phase came from the nearest spine row plus a projection, and jumped wherever that row changed,
        all over the chest (teeth along every plate edge). `_spine` now blends the ~10 nearest rows, each weighted by
        how close the point is to the row's plane;
      - measured from the spine, the chest's plates fanned out to 40 cm (it sits far out on the outside of the
        neck's bend). The plates' phase now runs along the belly's own line (each section's lowest point).
    - **Plates:** no fine parallel lines (they read as corduroy); a firm edge against the flank scales, each plate
      ending a little further in or out (a wide blend ran the grooves through the scales); pitch = 0.3 x the
      section's half-width (neck ~10 cm, trunk 20 cm).
    - **Nostrils:** a dark matte cavity (a gloss there read as an eye), a smooth lip, then two staggered rows of
      small scales (`ring_cells`: log-polar Voronoi, each row 1.4x further out), ending in a groove where the face's
      own scales take over.
    - **Scales:** size and direction blend over the shoulders and hips (they switched at a line), finer down to the
      toes, trunk scales at most 9 cm.
    - **Wings:** capillaries only at the ridged noise's crests (a wide threshold made blotches like map borders);
      broken, softer elastic fibres; a broad thick-to-thin gradient from the bones and a darker band along the edges
      (at a distance the wing was one flat orange); fine creases drawn out along the span (round ones read as a maze).
    - **Iterating:** `bake_data` and `body_fields` take ~3.5 min at 4096. In Blender, keep `dragon_paint._D` (the
      bake) and rerun `body_fields`, then `paint_body` per preset (~10 s each). The wings: bake once, `wing_fields`
      ~85 s. Calls over ~3 min drop the MCP connection, but Blender finishes the work.
    - **Geometry fixes in the same round:** Daniel saw the decimation starve the wing thumb and a "strangulation" on
      the tail. `dragon_skin._dec_weight` now keeps more around the wrist and thumb, and more the thinner the tail's
      section; the thumb cone is thicker.
  - **Stage 5, clips (2026-10-17, ground set first):** Daniel: "You can do things in small parts, so ground set
    first" (flight waits on the membrane fit and the shoulder tenting). He was on his phone, so each part is shown
    as GIFs: `dragon_build.clip_frames(clip, cam="34"|"side"|"front")` renders the frames into
    `renders/clip_<Clip>_<cam>/`, then `py tools/frames_to_gif.py renders/clip_Walk_34 renders/dragon_Walk.gif --step 2`.
    - `dragon_anim.py` on `beast_anim`. The rig already uses the quadrupeds' bone names. beast_anim gained
      `Species(ears=False)` and an `extra` hook; the dragon's `_wings` uses it to keep the wings folded on the
      chest (`dragon_pose.FOLD`), opened toward another wing pose by `p.wing_open` / `p.wing_to`, lifted by
      `p.wing_lift`.
    - Neck (7 bones) and tail (14) move as waves (`_neck_wave`, `_tail_wave`): each bone a little after the one
      before.
    - Clips so far: Idle (4 s loop), Walk (1.6 s loop, 1.25 m/s), Run (0.8 s loop, rotary gallop, 5.5 m/s), Bite
      (1.4 s), Claw (1.2 s), TailSweep (1.8 s), Fire (2.5 s), Roar (2.2 s), Hit (0.6 s), Death (3 s): the
      ground set is complete. The attacks fire event 'Bite' at impact, as the other beasts' do. Fire has 'Fire'
      (0.9 s) and 'FireEnd' (2.0 s) for the flames at Socket_Mouth; Roar has 'Roar'; Death has 'Dead' (2.0 s).
      `dragon_build.build_clips()`; `dragon_anim.report()` gives the lowest vertex per clip (all within 4.4 cm:
      the claw tips).
    - Death collapses onto the belly, not onto a side: rolling would drive the folded wing into the ground. With
      the shoulders that low, the forefeet stay close in (`DEATH_FORE`): further forward, the leg IK put the
      elbows into the ground.
    - **Flight set (2026-10-17, after Daniel's "Start the flight clips"):** Takeoff (2.2 s, event 'TakeOff' at
      0.63 s), Fly (1.2 s wingbeat loop, 10 m/s), Glide (2 s loop, 14 m/s), Land (2.4 s, event 'Land' at 1.4 s).
      - Flight plays at the Root's height like the rest. The Motion bone carries the travel: forward, and in
        Takeoff (+7 m) and Land (-7 m) up and down. The game must let root motion move the dragon vertically.
        Fly and Glide are in-air loops (the Root is in the air); `report()` skips them.
      - Wings in flight: `p.wing = dict(turns, curl, fold)`, the spread wing turned about the shoulder (`_turned`:
        'Y' up/down, 'Z' sweep, 'X' pitch), drawn part way back to the fold. Every wing pose blends bone by bone
        along the shortest rotation (slerp); a straight blend of directions folded the forearm through itself.
        The beat is `STROKE`/`SWEEP`/`PITCH`/`FOLD_UP`/`CURL` keyed over `FLY_N`, down fast, up slower with the hand
        drawn in.
      - `_depth_cap` limits a downstroke near the ground to what the 7.5 m wing can reach without touching it (the
        first takeoff beats dug the tips in; after touchdown the braking stroke hung the wings through the ground).
      - Previews: `clip_frames(..., travel=True)` moves the rig along its root motion with the camera following;
        `end_home=True` lands it in the middle of the ground; `lift=5` raises Fly and Glide.
    - **Not done:** no turn-in-place, no banking turns or hover in flight (the Unity export is done: see "Dragon and
      hydra in Unity" below); the shoulder tenting with the wings raised (seen on the
      blockout) not looked at again since the helper bones: check the shoulders in Roar and at the top of a beat.
      The slerped wing blend also changed how the standing clips open their wings (Fire, Roar, Hit, Death).
    - The tail's floor is per bone, measured from the mesh (`dragon_anim.tail_floor`): a flat 10 cm let the 30 cm
      thick tail root sink 18 cm into the ground when it reared.
    - **The folded wing** (Daniel: "Something is wrong with the folded wing, it has a bad geometry"):
      - The panel between the wing arm and the flank was skinned straight to those bones. In the fold the arm
        turns ~150 degrees from the flank, and linear blend skinning swung the panel's middle out from the side like
        a saddlebag.
      - Now 12 helper bones per wing (`WingMem<i><j>L/R`, children of WingScap) sit on that panel. Each pose places
        them on the Coons surface spanned by the panel's posed edges (`dragon_body.membrane_pose`, called by
        `dragon_anim._wings` and `dragon_pose.solve`). The inside and the trailing edge are weighted to them;
        arm, flank and last finger keep their own bones.
      - `dragon_build.membrane_helpers()` adds the bones to a built rig and re-weights DragonWingMembrane in place
        (same vertices: the UVs and paint stay). `rest_bones()` includes them, and `_exclude` keeps them out of the
        body's heat weights.
      - The fold's fingers are a tighter bundle (`dragon_pose.FOLD`): the last finger pointing down hung its panel
        over the thigh like a plate.
  - **Head to-do, for a later pass** (Daniel 2026-10-17: "It is not perfect, but it is good enough"; body first, head
    later). The head is code, so a change is a rebuild plus re-export:
    - Teeth: open, from the side, they form one perfectly straight, even row. Vary size, spacing, lean and height
      along a curved gum line; leave a gap or a broken tooth here and there.
    - Eye position: Daniel isn't sure it is right. Judge it with the whole body built, against the perched
      reference (eye about 55% back from the snout tip, under the brow).
    - Canine: the front fang pokes out through the side of the upper lip. It should come out from under the lip's
      edge (root inside the hanging lip, further in and down).
    - Mine: the pupil is a vertex-colour blob. The eye's detail and the scales come with the paint and normal map.
  - **Next:**
    - the real body: done (stage 3); the paint: done (stages 4 and 4b: scales, plates, presets, normal maps);
    - Unity export: done 2026-10-18 (below); clips: done;
    - the head to-do above; membrane fit to the bulkier body; shoulder tenting with raised wings.
  - **Gotcha:** `dragon_body.Acc` builds each piece in its own bmesh. `create_uvsphere` deletes vertices, and the
    freed slots let later vertices sort ahead of the per-vertex lists (the horn bases took the eye's colour).
    Budget proposal (mine, unreviewed): about 20k tris, 2048² body texture, 1024² membranes.
- **Hydra (started 2026-10-17):** Daniel: "how about an hydra monster? Like the dragon, but more aquatic like, no
  spikes, no wings, two or three heads". Its own file, `blender/hydra.blend` (scene Hydra): `hydra_body` (skeleton,
  blockout) and `hydra_build`; the dragon's pieces are reused (dragon_body's Acc, lofts, chain weights; later the
  dragon's melted head/body, paint and clip machinery).
  - **Stage 1, the blockout:** a low, long-bodied water beast (a giant newt more than a dragon), ~11 m from the
    middle snout to the tail tip, 1.8 m at the shoulder, heads up at 3.4-3.9 m.
    - Four short, sprawled legs with webbed feet; a flat paddle tail with a smooth dorsal fin and a smaller keel;
      eel-like heads with no horns, rounded gill fins behind the jaws. No spikes anywhere.
    - `HEADS` = 3 or 2: the middle neck is Neck1..7 + Head + Jaw (beast_anim's chain), the side necks
      Neck1L..7L + HeadL + JawL and the R mirror. 63 bones with three heads.
    - `hydra_build.build_blockout(heads)`; `hydra_build.heads_sheet()` renders three heads against two
      (`renders/hydra_heads.png`), leaving the three-headed one built.
    - **Gotcha:** `hydra_build.new_file()` renames the empty file's scene to Hydra. Removing it instead crashed
      Blender 4.4 (EXCEPTION_ACCESS_VIOLATION in ED_space_image: the window still referenced it). Right after
      `read_homefile` the MCP call's context is stale (no `selected_objects`): build in the next call. Blender's
      MCP add-on restarts its server by itself when Blender is relaunched (`D:\Program Files\Blender
      Foundation\Blender 4.4\blender.exe`); add Beasts/src to sys.path again.
  - **Daniel's pick (2026-10-17):** "Three heads is better, I think. The proportions are good." HEADS = 3.
  - **Stage 2, the heads:** `hydra_head.py`, one design shared by all three necks (meshed once, cached in
    `_SKIN`, placed by `hydra_body.head_matrix`; weights go to Head<nid> / Jaw<nid>).
    - It is the dragon's finished head: `dragon_head`'s melted field and mesh (jaw line, curved snout, hanging lip,
      lids, masseter weights), decimated to 8k triangles a head, without the horns, spikes, hooks
      and frill (separate pieces on the dragon). A first head built from fresh profiles brought back every problem
      the dragon's face had been through; Daniel: "The hydra head has the very same issues that existed on the
      dragon head. I was expecting you to base the mesh on the finished dragon head."
    - Scale per axis, `SCALE` = (0.66, 0.86, 0.70) of the dragon's: Daniel, on a plain 0.8, "Can the heads be
      sleaner?" -> narrower, shallower and a little longer (1.22 m), the same face.
    - Hydra additions: pleated gill fans (shells in HydraFins, sea green to coral), its palette, and its own teeth
      (`hydra_head.build_teeth`): the dragon's layout varied in length, spacing and lean, with a gap and a broken
      tooth a side, and the showing front teeth rooted inside the hanging lip so they come out from under its edge.
      Those are two of the dragon's parked head notes; the dragon itself is unchanged.
    - `hydra_build.head_sheet()` -> `renders/hydra_head_sheet.png`: the left head (the middle one is hidden from
      the side by its neighbours), shut and open.
    - The necks are still the blockout's lofts, thinned to 0.19 m at the head; the real body comes next.
  - Daniel on the sleeker head: move on.
  - **Stage 3, the real body:** `hydra_skin.py`, `hydra_build.build_body()`, after dragon_skin's recipe:
    - Field on a 2.5 cm grid: a chain of ellipsoids along the trunk/tail rows and one per neck (from inside the
      chest to the poll), muscles, sprawled legs, webbed feet's toes; each head's back melted in near its neck.
    - Heads: meshed per neck at 1 cm in the dragon's head space (the dragon head scaled the hydra's way, its neck
      melted in near the seam), 7k triangles each, moved onto the body.
    - Seams: a plane square to each neck 0.40 m down from its poll. The body is bisected only round that neck (the
      dragon's one infinite plane would slice the other necks); the rough heads beyond fall off as loose pieces
      and are dropped (`_keep_largest`); each head's loop is zipped to its neck's.
    - Weights: heat map (Jaw* excluded), each head's Head/Jaw weights fading in over 30 cm before its seam.
    - Colours: back / belly per axis (trunk, each neck), measured within the cross-section and blended by
      distance. Taking only the nearest axis flipped at the neck roots (dark patches on the chest).
    - Shells: teeth, tongues, eyes (`hydra_head.build_eye`, 16 x 10: six eyeballs at 24 x 14 cost 4k), seated
      claws. HydraFins: gill fans, toe webs (reaching most of the way to the tips; a third-sag hid them), tail fin
      and keel.
    - Body skin 14k (10k left the necks faceted), totals: HydraBody 40.4k (skin 34k: three heads 21k + body;
      shells 6.4k), HydraFins 2.5k. More than the dragon's ~32k; the heads (7k) and body (14k) can come down.
  - Daniel on the budget: "I think trimming more is dangerous, lets keep the current polygons" (~43k stays).
  - **Stage 4, the paint (2026-10-17):** `hydra_paint.py`, dragon_paint's machinery reused (scales, plates with
    anti-aliased edges, the nostrils' ring, the bake, the texture writing). dragon_paint gained two hooks, the
    dragon's defaults unchanged: `_spine(rows=...)` for any loft, `unwrap_body(head_groups=...)`.
    - Four axes (trunk + three necks): each texel takes its coordinates from the axis it is nearest to; the
      belly's share blends over them (`body_fields`).
    - Each head's texels get the dragon's head treatment in the dragon's head space (`hydra_skin.to_head` / SCALE):
      eye rings, the nostrils' ring, the lips' shade, the jaw's plates.
    - Aquatic: smaller scales (trunk 3.2-6.5 cm), sparse dark spots on the back and flanks (Voronoi cells), a
      wetter shine (`SMOOTH`).
    - Fins (`fin_fields`, `paint_fins`, 2048): gill fans ray along their pleats with a coral rim, toe webs vein
      from the paw, the tail's fin and keel ray slanting back every ~26 cm (13 cm read as corrugated card).
    - Presets: sea (default), swamp, abyss (cyan gills and eyes). `T_Hydra*`, `T_HydraFins*` with one normal map
      each; materials M_Hydra, M_HydraFins; `hydra_paint.use_preset(name)`.
    - The belly stays off the legs: Daniel, "We have the same issue as the belly texture bleeding into the members"
      (the dragon's gold once lit up its knee). `limb_weight` (near a leg bone, past the first stretch of the upper
      bones so the belly between the legs stays) takes the limbs out of the belly's share and plates, and the
      trunk's band is tighter (lim 1.35; the necks keep 1.6).
    - The breast where the necks part is belly (`breast`: forward-facing by the baked normal, in front of the chest,
      below the necks' split). No axis owned it -- in front of the trunk's first section, on the necks' inner
      sides -- and it came out as an X of back scales (Daniel: "fix that chest area where scales show up but
      should be a belly texture").
    - Where two axes' plates meet (the necks' roots on the chest) the plates' relief and grooves fade out: their
      runs don't line up, and the edge between them stepped into a dashed line.
    - Iterating: `hydra_paint.build()` does it all (~8 min; the body fields alone ~5 min). The bake and fields stay
      in `hydra_paint._CACHE`, so a colour change is `paint_body(_CACHE["F"], preset)` (~15 s).
  - Daniel: "now it is working, we can move on to animations".
  - **Stage 5, clips:** `hydra_anim.py` on beast_anim with dragon_anim's patterns. The middle neck is beast_anim's
    chain; `_side_necks` (the `extra` hook) poses Neck1L..7L/HeadL/JawL and R from `p.side[nid]` (+ yaw turns
    outward; the right chain mirrors itself). `wave`, `tail_wave`, `chain/head/set_jaw` work on any neck.
    `hydra_build.build_clips()`, `hydra_build.clip_frames(clip, cam, travel=...)` -> renders/clip_hydra_*,
    GIFs via tools/frames_to_gif.py; `hydra_anim.report()` (lowest point, root motion counted).
    - Part 1: Idle (4 s loop: each head on its own beat, a yawn, a snap), Walk (1.33 s loop, sprawling, 1 m/s).
    - Parts 2-3: Run (0.67 s loop, trot, 3.9 m/s), Bite (middle head; 'Bite' 0.6 s), TripleBite (left, middle,
      right; 'Bite' 0.6 s, 'Bite2' 1.2 s, 'Bite3' 1.8 s -- the game needs to listen for all three), TailSweep
      ('Bite' 0.8 s). `strike()` gives any neck its draw-back, strike and snap.
    - The tail floor counts the keel fin too: it dug 12 cm into the ground in Bite.
    - Part 4: Roar (2.2 s, three heads a beat apart, 'Roar' 0.6 s), Hit (0.6 s), Death (3 s, onto the belly, the
      necks falling one by one, 'Dead' 2.3 s; DEATH_DROP 0.64: the belly's lowest point stands 0.68 m up).
    - All nine clips stay within 2.5 cm of the ground (`hydra_anim.report()`).
  - **Next:** maybe a Swim clip for water (the Unity export is done: below).
- **Dragon and hydra in Unity (2026-10-18):** Daniel: "you know the beast test scene? Can you make one for dragon /
  hydra?"
  - **Export:**
    - `dragon_build.export()` and `hydra_build.export()` rebuild the clips and write `Dragon.fbx` (DragonBody +
      DragonWingMembrane, 102 bones with the WingMem helpers) and `Hydra.fbx` (HydraBody + HydraFins, 63 bones), the
      clips and the JSON into export/. Both anim modules now have the module-level `action_name` beast_export wants.
    - Run them in a **headless Blender** when the live one is busy (another session had an unsaved harbour scene
      open): `blender.exe -b blender/dragon.blend --python <script>` with src on sys.path, then `dragon_build.export()`.
      About a minute each.
    - Then `tools/install_to_unity.ps1`, or copy only the new files (assets first, then the scripts).
  - **Unity side** (`unity/Beasts`):
    - `DragonSetup.cs` / `HydraSetup.cs` (Tools > Beasts > Rebuild Dragon / Hydra). Three skins each: dragon base, Ash,
      Bronze; hydra sea, Swamp, Abyss. Normal maps; wings and fins drawn from both sides (`MakeTwoSided`: URP Lit
      `_Cull` 0).
    - Textures are imported at 2048 (`TexSize`; painted at 4096). Raise it there if Daniel wants the full size.
    - `BeastAppearance.pairedTarget` / `pairedSkins` give the wings (or fins) the same preset as the hide.
    - `ConfigureClips(..., vertical)` keeps the root height of Takeoff and Land: they climb and sink 7.00 m. Every
      other clip still bakes it.
    - `BeastAnimationSet.Pool.vertical` lets root motion lift the creature. `BeastRandomAnimator` keeps it no lower
      than where it took off, and settles it back down (6 m/s) once a ground pool plays. Creatures up in the air
      (`Aloft`) skip the separation pushes.
    - The dragon's `Flight` pool is a sequence: Takeoff, Fly, Glide, Fly, Land (`PoolDef.sequence` now reaches
      MakeSet).
    - `BeastBreath` (dragon prefab): a flame cone from `Socket_Mouth` between the Fire clip's events (`Fire` 0.9 s,
      `FireEnd` 2.0 s, never longer than 1.6 s).
      - Parts: flame body, additive core, smoke and an orange light.
      - It uses the game's `Resources/FX` flame materials when the project has them, and a soft blob otherwise.
      - It is built in Awake, aimed by the bind pose: `offset` puts it between the jaws, `aimDown` 12 degrees.
      - It collides with the world (the ground).
    - `DragonsTestScene.cs` -> `Scenes/Dragons_Test.unity` (Tools > Beasts > Build Dragons Test Scene; both setups
      rebuild it):
      - 2 dragons and 2 hydras on random pools, plus 6 goblins for scale, on a 320 m field;
      - the dragons wander 45 m and the hydras 30 m;
      - the viewer has `presetScale` 2.5 and a "Follow next" button (new in `BeastTestUI`).
    - `BeastsTestScene.BuildScene(path, fill, log)` is the shared additive build. `AddGoblins` is public (radius,
      wander), and `RenderLineup` takes a `camScale`.
  - **Checked:**
    - offline compile;
    - setup reports: avatars valid, every moving clip `dir=(0,0,1)`, Takeoff climb 7.00 m, Land -7.00 m;
    - a PlayableGraph trace in a preview scene: Takeoff ends at (0, 7, 10) with the head still ~3 m over the root
      (the skeleton isn't lifted twice), Fly holds 7 m at 10 m/s, Land comes down to 0 with at most a 17 cm undershoot
      (the animator's floor clamp catches it);
    - renders in `Logs/DragonSetup` and `Logs/HydraSetup`: lineups, close-ups, and the fire posed and simulated.
  - **Not played** (Daniel's no-play-test rule): the random animator's flight path, the settle after Land, the flame
    hitting the ground and the follow camera are untested in play mode.
  - Gotcha: `delayCall` didn't tick with Unity in the background again, so the setups were run with RunCommand.

## Checks

- `wolf_build.build_all()` report: `weights.unweighted == 0`, `over4 == 0`, `bad_group_names == []`, triangle
  total.
- Look at `textures/T_Wolf.png` and `renders/uv_layout_wolf.png`, not only renders.
- To stress-test the rig, run `wolf_rig.test_pose(rig)` and render (jaw open, head turned, a stride, tail swept,
  ears back), then `wolf_rig.reset_pose(rig)` before exporting.
- After changing clips: `wolf_anim.build_clips()`, render sheets with `beast_scene.render_sheet`, and check the
  lowest vertex per clip (nothing under -0.03).
- **Unity:** in `Logs/WolfSetup/setup_report.txt`, check `avatar valid=True` and the moving clips'
  `dir=(0.00, 0.00, 1.00)`. Trace the moving clips with a manual PlayableGraph (AlwaysAnimate): the head's offset
  from the GameObject must stay steady across loops.
- To check the export, import `export/Wolf.fbx` in a background Blender: 41 bones including Root/Motion/sockets,
  one mesh with 35 groups, one UV layer.
- **Ooze:**
  - `ooze_build.build_model()` report: `contents.outside == []`, `weights` with `unweighted == 0` and `over4 == 0`,
    and the alpha range (about 0.18–0.51).
  - After changing clips: `ooze_anim.report()` per clip:
    - `rim_high` within a few cm (the open bottom stays on the floor);
    - `lowest` no lower than -0.05;
    - `contents_out == 0`;
    - `contents_low >= 0`.
  - Then `ooze_build.clip_sheets()`, and check `renders/check_tex_*.png` (the UV layout over the texture).

- 2026-10-23 (later): **turtle shell openings** (Daniel: "The turtle cask is not right. The head and limbs emerge right
  from the cask wall, there should be some space where they are inserted"). The rim sat at a fixed height (0.62 m at the
  sides, 0.90 at the front) under the tops of what leaves the shell (front leg 0.86 m where it crosses the rim, hind 0.82,
  neck 1.05, tail 0.80), so they came out through the carapace's wall. `turtle_body.ARCHES` lifts the rim in a cos^2 arch
  over each opening (neck +0.30, front legs +0.26, hind legs +0.24, tail +0.12), so the neck and legs leave through a gap
  between the carapace's edge and the plastron, the skin going in under it. The painter reads only the outline, so the
  scutes still fit. Lowest-vertex and the Walk trace unchanged; Withdraw now pulls the head in under the front arch.
  Re-exported (model, clips, texture) and reinstalled in MedievalSetting (Rebuild Turtle: OK).
- 2026-10-23 (later): **Bat wing underside** (Daniel: "Do these tasks you mentioned", from the polish list). In URP the
  membrane was drawn from both sides (`MakeTwoSided`, `_Cull` 0), and URP Lit does not flip the normal on back faces,
  so the underside was lit like the top: bright from below. URP Lit and URP Shader Graph have no back-face flip (only
  SpeedTree uses `FRONT_FACE_SEMANTIC`); the dragon and hydra use the same `MakeTwoSided`, so nothing to reuse. Fix in
  the mesh: `bat_build._two_layers` copies the wing's faces onto new vertices (UVs, weights, info kept), flips them
  and tags them (`back` face attribute); `M_BatWing` culls back faces in Blender, and `BatSetup` sets `_Cull` 2 and
  `doubleSidedGI` false (the old material asset kept `_Cull` 0 otherwise) and logs the wing's triangles (1920).
  BatWing 960 -> 1,920 tris, the bat 4,120 -> 5,080. `paint` bakes one sheet (`_one_layer`: the layers share UVs, and
  Cycles would bake both) and puts the underside back. Applied with `creature_run.py -- bat paint lowest export` on the
  saved file (same mesh and UVs; lowest unchanged). Export re-imported: BatWing 1,232 verts, 1,920 tris, every back
  face on its front face with the opposite normal, 0 unweighted. `renders/bat_underside_before_after.png` (EEVEE; the
  old look emulated with the back faces' normal flipped back to the front one). Not run in Unity. The dragon's wings
  and the hydra's fins have the same issue (`MakeTwoSided`), not changed.
- 2026-10-23 (later): **Zombie wolf spine** (Daniel: "Do these tasks you mentioned", from the polish list): at the game
  camera the pale bald strip down the back (`zwolf_body.SPINE_BALD`, grey-green skin + bone-pale processes) read as a
  racing stripe. Paint only (`zwolf_paint`; the mesh, the strip's sunk skin and the processes' bumps unchanged): inside
  `_spine_strip` the skin is dark grey-green mixed 40% toward the coat's saddle colour (so the pale coat doesn't get a
  dark stripe instead), matted fur crosses it in stretches (fbm along the back, seed 91), the processes are stained dark
  except `PALE_KNOBS` (1, 2, 6, 10, 11, 15: six of seventeen, bone x0.75), the gaps between them a little lighter than
  before. `zwolf_run.py -- paint coats game export` (same UVs; FBX and clips re-exported unchanged). Checked at full
  res: the game sheet, `renders/zwolf_vs_wolf_game.png` (redone from the saved `zwolf_ref_wolf_game*.png`),
  `renders/zwolf_spine_game_before_after.png`, top/above/34/34r and the three coats: no stripe, a dotted knobbly line
  with a few pale knobs. `docs/images/zwolf_game.png` and `zwolf_34r.png` updated.

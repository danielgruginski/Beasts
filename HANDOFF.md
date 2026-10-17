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

Both are installed in MedievalSetting (`Assets/Beasts`, `Scenes/Beasts_Test`: 7 wolves, 10 rats, 8 goblins). Root
motion is traced over 3 loops for both: steady head offset, no loop snap.

Repo: github.com/danielgruginski/Beasts (`main`; public since 2026-10-06, CC0, for the itch.io packs). It holds the scripts and docs only; the .blend, the
exports, the textures and the renders are regenerated (see `.gitignore`). Commit and push each piece of work as soon as it is finished and checked (Daniel, 2026-10-12).

## Open / next

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
  - goblin rider clips (sitting on `Socket_Saddle`, holding the reins) belong to the Goblins repo;
  - the lower jaw shows as a flat bar under the lip (the wolf's design);
  - up close the hair clumps still read a little like blades; the coat's relief is only the normal map;
  - in Death it lies on its left side: the stirrup on that side goes into the ground;
  - game side: a `Creature` definition (wild packs; ridden by goblin raiders), the Bite/Howl events.
- **More beasts:** a war mammoth (howdah on `Socket_Back`), giant elk, boar and dire variants can reuse the
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
    - the real body: done (stage 3); next its paint (masks + presets, normal map with scales);
    - scales: brow plates, face scales and the belly plates in the normal map;
    - paint masks plus presets;
    - clips;
    - Unity.
  - **Gotcha:** `dragon_body.Acc` builds each piece in its own bmesh. `create_uvsphere` deletes vertices, and the
    freed slots let later vertices sort ahead of the per-vertex lists (the horn bases took the eye's colour).
    Budget proposal (mine, unreviewed): about 20k tris, 2048² body texture, 1024² membranes.

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

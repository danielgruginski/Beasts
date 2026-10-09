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

Both are installed in MedievalSetting (`Assets/Beasts`, `Scenes/Beasts_Test`: 7 wolves, 10 rats, 8 goblins). Root
motion is traced over 3 loops for both: steady head offset, no loop snap.

Repo: github.com/danielgruginski/Beasts (private, `main`). It holds the scripts and docs only; the .blend, the
exports, the textures and the renders are regenerated (see `.gitignore`). Commit in batches when Daniel asks.

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
- **Warg** (goblin raider mount): scale about 1.4x, heavier ruff, saddle prop on `Socket_Saddle`, darker coat.
- **More beasts:** a war mammoth (howdah on `Socket_Back`), warg, giant elk, boar and dire variants can reuse the pipeline: parts, tufts, fuse, heat weights, and the
  painter's flow strokes.

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

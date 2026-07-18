# Asset library — entropy

The SceneCreationDirector's reference: what EXISTS before the
Asset Creator is asked for anything new (`13 library` rebuilds
this file + the contact sheets in `work/game/entropy/library/`).
Sizes are given in FIGURES (the 96px character — the scale
contract): a door is ≥1 figure, a house ≈3.

## Families

### bench — generator `genlab`; blocks `base`

| variant | px | figures (w×h) | frames | style |
|---|---|---|---|---|
| marble_0 | 96×64 | 1.0×0.7 | 1 | gen1 |
| marble_1 | 96×64 | 1.0×0.7 | 1 | gen1 |
| picnic_0 | 128×96 | 1.3×1.0 | 1 | gen1 |
| picnic_1 | 128×96 | 1.3×1.0 | 1 | gen1 |

### brazier — generator `genlab`; animates `flame_flicker`; blocks `base`

| variant | px | figures (w×h) | frames | style |
|---|---|---|---|---|
| lantern_0 | 64×128 | 0.7×1.3 | 2 | gen1 |
| standing_0 | 64×128 | 0.7×1.3 | 2 | gen1 |

### building — generator `buildings2d`; lighting `ambient`; blocks `rect`

| variant | px | figures (w×h) | frames | style |
|---|---|---|---|---|
| house_0 | 160×256 | 1.7×2.7 | 1 | bld1 |
| house_1 | 128×256 | 1.3×2.7 | 1 | bld1 |
| house_2 | 192×256 | 2.0×2.7 | 1 | bld1 |
| house_3 | 192×256 | 2.0×2.7 | 1 | bld1 |
| house_4 | 128×256 | 1.3×2.7 | 1 | bld1 |
| house_5 | 192×256 | 2.0×2.7 | 1 | bld1 |
| house_6 | 160×256 | 1.7×2.7 | 1 | bld1 |
| inn_0 | 224×352 | 2.3×3.7 | 1 | bld1 |
| inn_1 | 256×352 | 2.7×3.7 | 1 | bld1 |
| kiosk_0 | 96×192 | 1.0×2.0 | 1 | bld1 |
| kiosk_1 | 96×192 | 1.0×2.0 | 1 | bld1 |
| pavilion_0 | 224×224 | 2.3×2.3 | 1 | bld1 |
| pavilion_1 | 192×224 | 2.0×2.3 | 1 | bld1 |
| shop_0 | 192×256 | 2.0×2.7 | 1 | bld1 |
| shop_1 | 160×256 | 1.7×2.7 | 1 | bld1 |
| shop_2 | 192×256 | 2.0×2.7 | 1 | bld1 |
| shop_3 | 224×256 | 2.3×2.7 | 1 | bld1 |

### clutter — generator `genlab`; blocks `base`

| variant | px | figures (w×h) | frames | style |
|---|---|---|---|---|
| barrel_0 | 64×96 | 0.7×1.0 | 1 | gen1 |
| barrel_1 | 64×96 | 0.7×1.0 | 1 | gen1 |
| crates_0 | 96×96 | 1.0×1.0 | 1 | gen1 |
| crates_1 | 96×96 | 1.0×1.0 | 1 | gen1 |
| crates_2 | 96×96 | 1.0×1.0 | 1 | gen1 |

### column — generator `genlab`; blocks `base`

| variant | px | figures (w×h) | frames | style |
|---|---|---|---|---|
| broken_0 | 64×128 | 0.7×1.3 | 1 | gen1 |
| broken_1 | 64×128 | 0.7×1.3 | 1 | gen1 |
| broken_2 | 64×128 | 0.7×1.3 | 1 | gen1 |
| intact_0 | 64×192 | 0.7×2.0 | 1 | gen1 |
| intact_1 | 64×192 | 0.7×2.0 | 1 | gen1 |
| intact_2 | 64×192 | 0.7×2.0 | 1 | gen1 |
| piped_0 | 64×192 | 0.7×2.0 | 1 | gen1 |
| piped_1 | 64×192 | 0.7×2.0 | 1 | gen1 |
| piped_2 | 64×192 | 0.7×2.0 | 1 | gen1 |

### fountain — generator `genlab`; animates `water_spray`; blocks `base`

| variant | px | figures (w×h) | frames | style |
|---|---|---|---|---|
| tiered_0 | 128×128 | 1.3×1.3 | 2 | gen1 |
| tiered_1 | 128×128 | 1.3×1.3 | 2 | gen1 |

### machine — generator `genlab`; animates `heat_shimmer` (static: cart, winch); lighting `ambient`; blocks `base`

| variant | px | figures (w×h) | frames | style |
|---|---|---|---|---|
| boiler_0 | 128×128 | 1.3×1.3 | 2 | gen1 |
| boiler_1 | 128×128 | 1.3×1.3 | 2 | gen1 |
| cart_0 | 64×96 | 0.7×1.0 | 1 | gen1 |
| cart_1 | 64×96 | 0.7×1.0 | 1 | gen1 |
| gearstack_0 | 128×128 | 1.3×1.3 | 2 | gen1 |
| gearstack_1 | 128×128 | 1.3×1.3 | 2 | gen1 |
| winch_0 | 128×128 | 1.3×1.3 | 1 | gen1 |
| winch_1 | 128×128 | 1.3×1.3 | 1 | gen1 |

### portal — generator `genlab`; blocks `base`

| variant | px | figures (w×h) | frames | style |
|---|---|---|---|---|
| arch_0 | 160×160 | 1.7×1.7 | 1 | gen1 |
| arch_1 | 160×160 | 1.7×1.7 | 1 | gen1 |
| bricked_0 | 160×160 | 1.7×1.7 | 1 | gen1 |
| bricked_1 | 160×160 | 1.7×1.7 | 1 | gen1 |
| shaftmouth_0 | 160×160 | 1.7×1.7 | 1 | gen1 |
| shaftmouth_1 | 160×160 | 1.7×1.7 | 1 | gen1 |

### ride — generator `genlab`; blocks `base`

| variant | px | figures (w×h) | frames | style |
|---|---|---|---|---|
| carousel_0 | 224×224 | 2.3×2.3 | 1 | gen1 |
| carousel_1 | 224×224 | 2.3×2.3 | 1 | gen1 |
| ferris_0 | 288×384 | 3.0×4.0 | 1 | gen1 |

### rock — generator `genlab`; blocks `base`

| variant | px | figures (w×h) | frames | style |
|---|---|---|---|---|
| boulder_0 | 64×64 | 0.7×0.7 | 1 | gen1 |
| boulder_1 | 64×64 | 0.7×0.7 | 1 | gen1 |
| boulder_2 | 64×64 | 0.7×0.7 | 1 | gen1 |
| ore_0 | 64×64 | 0.7×0.7 | 1 | gen1 |
| ore_1 | 64×64 | 0.7×0.7 | 1 | gen1 |
| ore_2 | 64×64 | 0.7×0.7 | 1 | gen1 |
| rock_0 | 32×32 | 0.3×0.3 | 1 | gen1 |

### shopsign — generator `genlab`; lighting `ambient`; blocks `base`

| variant | px | figures (w×h) | frames | style |
|---|---|---|---|---|
| apothecary_0 | 64×128 | 0.7×1.3 | 1 | gen1 |
| apothecary_1 | 64×128 | 0.7×1.3 | 1 | gen1 |
| garments_0 | 64×128 | 0.7×1.3 | 1 | gen1 |
| garments_1 | 64×128 | 0.7×1.3 | 1 | gen1 |
| general_0 | 64×128 | 0.7×1.3 | 1 | gen1 |
| inn_2 | 64×128 | 0.7×1.3 | 1 | gen1 |
| smith_0 | 64×128 | 0.7×1.3 | 1 | gen1 |
| smith_1 | 64×128 | 0.7×1.3 | 1 | gen1 |

### stall — generator `genlab`; blocks `base`

| variant | px | figures (w×h) | frames | style |
|---|---|---|---|---|
| booth_0 | 128×96 | 1.3×1.0 | 1 | gen1 |
| booth_1 | 128×96 | 1.3×1.0 | 1 | gen1 |
| bunting_0 | 192×192 | 2.0×2.0 | 1 | gen1 |
| flagpole_0 | 64×160 | 0.7×1.7 | 1 | gen1 |
| highstriker_0 | 64×192 | 0.7×2.0 | 1 | gen1 |
| highstriker_1 | 64×192 | 0.7×2.0 | 1 | gen1 |
| marquee_0 | 256×256 | 2.7×2.7 | 1 | gen1 |
| marquee_1 | 256×256 | 2.7×2.7 | 1 | gen1 |
| sign_0 | 128×96 | 1.3×1.0 | 1 | gen1 |
| tent_0 | 192×192 | 2.0×2.0 | 1 | gen1 |
| tent_1 | 192×192 | 2.0×2.0 | 1 | gen1 |

### statue — generator `genlab`; lighting `ambient`; blocks `base`

| variant | px | figures (w×h) | frames | style |
|---|---|---|---|---|
| founder_0 | 64×160 | 0.7×1.7 | 1 | gen1 |
| founder_1 | 64×160 | 0.7×1.7 | 1 | gen1 |
| robed_0 | 64×128 | 0.7×1.3 | 1 | gen1 |
| robed_1 | 64×128 | 0.7×1.3 | 1 | gen1 |

### stump — generator `genlab`; blocks `base`

| variant | px | figures (w×h) | frames | style |
|---|---|---|---|---|
| log_0 | 64×32 | 0.7×0.3 | 1 | gen1 |
| stump_0 | 32×32 | 0.3×0.3 | 1 | gen1 |
| stump_1 | 32×32 | 0.3×0.3 | 1 | gen1 |

### support — generator `genlab`; blocks `base`

| variant | px | figures (w×h) | frames | style |
|---|---|---|---|---|
| timber_0 | 128×192 | 1.3×2.0 | 1 | gen1 |
| timber_1 | 128×192 | 1.3×2.0 | 1 | gen1 |

### topiary — generator `genlab`; animates `foliage_sway`; blocks `base`

| variant | px | figures (w×h) | frames | style |
|---|---|---|---|---|
| sphere_0 | 64×96 | 0.7×1.0 | 2 | gen1 |
| sphere_1 | 64×96 | 0.7×1.0 | 2 | gen1 |
| spiral_0 | 64×96 | 0.7×1.0 | 2 | gen1 |

### tree — generator `trees_px`; animates `foliage_sway`; blocks `trunk_base`

| variant | px | figures (w×h) | frames | style |
|---|---|---|---|---|
| dead_0 | 96×128 | 1.0×1.3 | 1 | px3 |
| dead_1 | 64×96 | 0.7×1.0 | 1 | px3 |
| deciduous_0 | 96×128 | 1.0×1.3 | 2 | px3 |
| deciduous_1 | 64×96 | 0.7×1.0 | 2 | px3 |
| deciduous_10 | 96×128 | 1.0×1.3 | 2 | gen1 |
| deciduous_11 | 96×128 | 1.0×1.3 | 2 | gen1 |
| deciduous_12 | 96×128 | 1.0×1.3 | 2 | gen1 |
| deciduous_13 | 96×128 | 1.0×1.3 | 2 | gen1 |
| deciduous_2 | 96×128 | 1.0×1.3 | 2 | px3 |
| deciduous_3 | 64×96 | 0.7×1.0 | 2 | px3 |
| deciduous_4 | 32×64 | 0.3×0.7 | 2 | px3 |
| deciduous_5 | 96×128 | 1.0×1.3 | 2 | px3 |
| deciduous_6 | 96×128 | 1.0×1.3 | 2 | px3 |
| deciduous_7 | 64×96 | 0.7×1.0 | 2 | px3 |
| deciduous_8 | 96×128 | 1.0×1.3 | 2 | px3 |
| deciduous_9 | 64×96 | 0.7×1.0 | 2 | px3 |
| pine_0 | 96×128 | 1.0×1.3 | 2 | px3 |
| pine_1 | 64×96 | 0.7×1.0 | 2 | px3 |
| pine_2 | 96×128 | 1.0×1.3 | 2 | px3 |
| pine_3 | 64×96 | 0.7×1.0 | 2 | px3 |
| pine_4 | 32×64 | 0.3×0.7 | 2 | px3 |

## Terrain vocabularies (atlas specs)

- **vaporis_expo** (`atlases/vaporis_expo.spec.json`): lawn, flag, terrace, upper, stairs, midway, water, hedge, canopy, flowers, bush
- **vaporis_fair** (`atlases/vaporis_fair.spec.json`): lawn, flag, terrace, stairs, midway, water, hedge, canopy, flowers, bush
- **vaporis_mine** (`atlases/vaporis_mine.spec.json`): earth, wall, water, moss, rail_v, rail_h
- **vaporis_town** (`atlases/vaporis_town.spec.json`): lawn, street, lane, water, hedge, bush

## Scenes (regional filing: levels/<region>/<id>/)

- `originals` / **castle_outside** — backdrop, 0 sockets
- `originals` / **classroom_start** — backdrop, 1 sockets
- `originals` / **ecole** — backdrop, 0 sockets
- `originals` / **forest_buit** — backdrop, 0 sockets
- `originals` / **witch_cottage** — backdrop, 0 sockets
- `originals` / **witch_cottage_inside** — backdrop, 0 sockets
- `vaporis` / **vaporis_fair** — tilemap, 20 sockets

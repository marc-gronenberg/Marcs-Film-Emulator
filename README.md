# Marcs Film Emulator (v0.8.0)

Film looks for **PhotoCraft** as a WebAssembly filter plug-in (plug-in ABI v1). Twenty films in
one dropdown – eight colour negatives, five cine stocks, two slide films, five black-and-white –
each simulated from the curves of its manufacturer datasheet, with push/pull processing, halation
(switchable) and film grain. The halation is also available as a plug-in of its own, for stacking
it separately.

## Download

**[⬇ marcs-film-emulator.wasm](https://github.com/marc-gronenberg/Marcs-Film-Emulator/releases/latest/download/marcs-film-emulator.wasm)** (28 MB) – that one file is
the whole plug-in. In PhotoCraft: **Filter › Plug-ins › Install Plug-in…**, then **Filter › Plug-ins ›
Marcs Film Emulator…**. All versions: [Releases](https://github.com/marc-gronenberg/Marcs-Film-Emulator/releases).

## The plug-ins

| File | Menu entry | What it does |
|---|---|---|
| `marcs-film-emulator.wasm` | Filter › Plug-ins › Marcs Film Emulator… | Halation (switch) → film colour and tone (dropdown) → grain |
| `marcs-film-emulator-halation.wasm` | Filter › Plug-ins › Marcs Film Emulator – Halation… | The same glow alone, for stacking it as a separate smart filter (optional) |

Install via **Filter › Plug-ins › Install Plug-in…**. The film plug-in is all you need; with its
Halation switch on, the glow is added before the film, so it goes through the film's colour like
the rest of the light. The separate halation plug-in gives the same result when applied first (below
the film in the smart filter list), and lets you toggle or restack it on its own.

## The films

| Dropdown | Built from (Kodak publication) | Output route | Character |
|---|---|---|---|
| Portrait 400 | PORTRA 400 (E-4050) | lab scan | soft contrast, natural warm skin, muted cyan skies |
| Portrait 800 | PORTRA 800 (E-4040; EI 800, 1600 and 3200 curves) | lab scan | like Portrait 400, a bit warmer and richer, coarser grain |
| Everyday 200 | GOLD 200 (E-7022) | lab scan | warm, saturated, punchy reds and greens |
| Street 400 | ULTRAMAX 400 (E-7023) | lab scan | warm consumer look, strong colour, visible grain |
| Vivid 100 | EKTAR 100 (E-4046) | lab scan | highest saturation, crisp contrast, finest colour grain |
| Cine 500T | VISION3 500T 5219 (H-1-5219t) on VISION Color Print Film 2383 (H-1-2383t) | cinema print | contrasty, deep shadows, cool |
| Cine 250D | VISION3 250D 5207 (H-1-5207t) on 2383 | cinema print | the daylight cinema stock, neutral, deep shadows |
| Mono 400 | TRI-X 400 (F-4017; T-MAX Developer, 7 min) | b/w scan | punchy, classic coarse grain |
| Mono 100 | T-MAX 100 (F-4016; D-76, 7.5 min) | b/w scan | smoother tones, very fine grain |
| **v0.8** | | | |
| Portrait 160 | PORTRA 160 (E-4051) | lab scan | the finest Portra, pastel |
| Soft 400 | FUJICOLOR PRO 400H (AF3-176E) | lab scan | airy, low contrast, cool greens; the wedding look |
| Snapshot 400 | FUJICOLOR SUPERIA X-TRA 400 (AF3-0217E) | lab scan | Fuji's consumer look, cooler than Gold |
| Cine 50D | VISION3 50D 5203 (TI-2657) on 2383 | cinema print | the finest cinema stock, daylight |
| Cine 200T | VISION3 200T 5213 (H-1-5213t) on 2383 | cinema print | between 500T and 250D |
| Tungsten 800 | VISION3 500T 5219 in daylight, no filter, C-41 scan | lab scan | the "CineStill 800T" way: the same emulsion without its anti-halation layer; switch Halation on |
| Chrome 100 | EKTACHROME E100 (E-4000) | slide | neutral slide film, clean whites |
| Vivid Chrome 100 | FUJICHROME Velvia 100 (AF3-202E) | slide | the landscape slide, saturated, deep shadows |
| Mono 125 | ILFORD FP4 PLUS (fact sheet 4/2004; ILFOTEC HC 1+31, 8 min) | b/w scan | classic medium speed, fine grain |
| Mono 400 T | T-MAX 400 (F-4016; D-76, 8 min) | b/w scan | tabular 400, finer than Tri-X |
| Mono 3200 | T-MAX P3200 (F-4016; T-MAX Developer, EI 3200) | b/w scan | the available-light film, coarse |

Names in the menu are neutral on purpose (trademarks); the table says which film each is built
from. Velvia 100 stands in for Velvia 50 because Fujifilm's Velvia 50 sheets (both the 2020 US and
the 2019 EU edition) carry their curves as raster images, which the digitizer cannot read; the
Velvia 100 sheet is vector. The Ilford sheet is the April 2004 one for the same reason: the current
(2018) sheet has no curves at all. The v0.8 films' look parameters (grey, contrast, saturation,
tint, interlayer) are set by analogy to the first nine and not yet judged against real scans.

## Parameters

| Parameter | Range | Default | What it does |
|---|---|---|---|
| Film | the nine above | Portrait 400 | The film |
| Input Space | sRGB / Display P3 / Adobe RGB | sRGB | The document's colour space (see below) |
| Push | Pull 1 / Normal / Push 1 / Push 2 | Normal | Exposure index and development: pushed = underexposed by that many stops and developed longer, pulled = the opposite (see below) |
| Strength | 0 … 100 | 100 | How much of the film (colour and tonality alike) replaces the original; 0 returns the original exactly, grain aside |
| Halation | Off / On | Off | The red-orange glow around bright highlights, before the film (off: no cost) |
| Halation Amount | 0 … 100 | 40 | Strength of the glow |
| Halation Radius | 2 … 36 px | 14 | Width of the glow |
| Halation Threshold | 0 … 100 | 55 | Linear luminance above which a pixel glows |
| Grain | 0 … 100 | 35 | Grain amount, scaled per film; grey (silver) grain for the Mono films |
| Grain Size | 0.5 … 4 px | 1 | Grain clump size (exactly 1 is the fastest) |
| Seed | 0 … 9999 | 1 | Grain pattern |

**Strength** mixes the film with the original in linear light, luminance and colour (rgb ÷
luminance) alike. It is v0.5's Color and Tone set to the same value (v0.5/0.6 settings with the two
apart cannot be reproduced; a Strength of 50 gives what Color 50 / Tone 50 gave, to the level).

**Push.** A pushed film is underexposed by that many stops (the camera set to a higher exposure
index) and developed longer, so the negative still reaches its density; the lab then prints or
scans it to normal mid-tones. The result is more contrast, coarser grain and less shadow detail;
pulling is the opposite. The plug-in has one LUT per film and level, each baked from the model
with the matching underexposure and development:

| Film | Pull 1 | Push 1 | Push 2 | Source |
|---|---|---|---|---|
| Mono 400 (Tri-X) | 6 min curve | 7 min (normal time; F-4017: 1-stop push needs no more time) | 8¾ min (F-4017: EI 1600, T-MAX Developer, 20 °C), between the plotted 7 and 9 min curves | the datasheet's 6 / 7 / 9 / 11 min curves |
| Mono 100 (T-MAX 100) | 6 min curve | 7.5 min (normal time; F-4016: no increase for 1 stop) | 10 min curve | the datasheet's D-76 6 / 7.5 / 10 min curves |
| Portrait 800 | development gain 0.84 | the EI 1600 curves | the EI 3200 curves | E-4040's push 1 and push 2 curves |
| other colour films | gain 0.84 | gain 1.19 | gain 1.31 | the gains measured on Portra 800 (pull: the inverse of push 1) |

"Development gain" scales the negative's density above base; for the films without published
push curves that is a model assumption, taken from the one Kodak C-41 film that publishes them
(Portra 800: mid-scale contrast × 1.19 at push 1, × 1.31 at push 2). Measured on the digitized
curves: Tri-X 6 / 9 / 11 min give × 0.92 / 1.18 / 1.40 of the 7 min contrast, T-MAX 100 6 / 10
min × 0.81 / 1.38 of 7.5 min. No pull time is published for either b/w film; Pull 1 takes the
shortest plotted time, so it is a mild pull. Grain is scaled × 0.85 / 1.25 / 1.5 for pull 1 / push
1 / push 2 (the datasheets describe the increase, no numbers). 18 % grey stays within a few levels
across the levels (the lab re-levels it); the mid-tone contrast of Portrait 400 goes 0.84 → 1 →
1.11 → 1.21, of Mono 400 0.93 → 1 → 0.99 → 1.15 (Push 1 on the Mono films is the exposure shift
alone, as Kodak processes it).

Tried first and dropped: push as an affine map of log exposure in front of the normal LUT (no
extra LUTs). Exact on the straight part of the curve, but the pushed colour films change their
colour rendering too (dye amounts, masking, hue damping), and the fit was off by 15–60 levels for
them (3–30 for the Mono films). So: real LUTs, stored as u16 instead of f32, which keeps the
plug-in at 18 MB for 36 LUTs instead of 11 MB for 9.

**Input Space.** PhotoCraft's plug-in ABI does not tell the plug-in the document's profile, so it
has to be set by hand. Display P3 and Adobe RGB documents are decoded with their own transfer
curve, converted to linear sRGB for the film (colours outside sRGB pulled towards their luminance
until they fit, for the film only) and converted back. Colour **from the film** therefore never
leaves sRGB; with Strength < 100 the original's share keeps its full gamut. Grayscale documents are
always taken as sRGB-encoded grey. Tested: a P3 or Adobe RGB copy of an image gives the same result
as the sRGB original within 2 levels (8-bit), Strength 0 returns it within 0.5.

**Halation.** Light that passes the emulsion reflects off the film base and re-exposes the red
(and a little of the green) layer around bright highlights. The stage takes the linear luminance
above the threshold, blurs it (Gaussian, sigma = radius / 2, computed at quarter resolution) and
adds it in linear light as red 1 / green 0.22 / blue 0.02 (its luminance on grayscale documents),
in the document's input space. Then the film sees it like any other light: on the Mono films the
glow is a neutral bloom, on the colour films it takes the film's colour. The switch off skips the
stage entirely; the band overlap it needs (96 px) stays, which costs a few percent on every run.

## How the looks are made

**Measured (digitized from the datasheets' vector graphics, `data/`):**

- spectral sensitivity of the three layers (b/w: of the one panchromatic layer, averaged from the
  two density levels the datasheet plots),
- characteristic curves (density over log exposure, B/G/R; b/w: diffuse visual density), for the
  b/w films at every plotted development time and for Portra 800 also pushed 1 and 2 stops,
- dye density spectra and minimum density (VISION3 and 2383 publish single dyes; for Portra, Gold,
  UltraMax and Ektar, which publish only the midscale-neutral spectrum, the VISION3 dyes are shifted
  and stretched to reproduce that spectrum: fit error 0.009–0.014 density),
- for 2383: sensitivities, characteristic curves and dyes of the print film.

**Modelled (assumptions, see `model/film_model_v2.py`):** turning RGB into smooth spectra, the
film's design light (5500 K daylight, 3200 K tungsten), a mild interlayer (DIR) effect, the
status M and A densitometers (ANSI curves in `data/films/status.json`, from python-colormath), the enlarger and projector lamps,
and the scan or viewing step: a lab scan (grey balance, tone curve, saturation setting per film),
the projected print (dark-surround compensation), or for b/w a scan of the negative. Part of each
colour film's hue shift is kept (75–85 %), the rest is pulled back towards the original hue.

**Fixed in v0.5:** the spectral upsampling fitted the brightest channel at reflectance 0.98. For
colours just off the grey axis whose largest channel was green, that forced a spectrum that fell to
zero at its ends – a film sensitive there saw a jump of up to 15 levels next to neutral grey. Now
fitted at 0.7, the model is smooth and the plug-in matches the model within 1–2 levels (p99) for
all nine films. This also shifts the v0.4 films slightly (mean 2–3 levels, strongest in saturated
colours).

**Fixed in v0.5.1:** with Tone below 100, a pixel at exactly black took the film's (lifted) black
while its neighbour at level 1 kept its own luminance: a step of about 12 levels at the black end of
every clipped shadow. Black now stays black at Tone 0. 32-bit documents keep values above 1.0
where Color and Tone fade the film out (before, the mix clipped them to white); with the film at
100 % the output is unchanged. Default settings give the same output as v0.5 at every depth
(checked pixel for pixel in the test host). `cube/` is re-exported from the same model as the
plug-in (it came from the older v0.3 model before).

**New in v0.7:** Push replaces Exposure, Strength replaces Color and Tone (smart filters saved
with v0.5/0.6 fall back to the defaults for these). The LUTs are u16 now (36 of them, 18 MB plug-in;
f32 would have been 30 MB). Normal / Strength 100 gives v0.6's output within one level on a handful
of pixels (the u16 arithmetic rounds differently); the price is 4–8 % more time per run, mostly the
bigger module every band copies in.

**New in v0.6:** halation is a switch in the film plug-in (default off). Switched on, the result is
the same, pixel for pixel, as the halation plug-in followed by the film plug-in (checked in the test
host at 8 and 32 bit); switched off, the same as v0.5.1. The halation stage now uses the film's
Input Space and works on grayscale documents too (both also in the separate plug-in, 0.4.2).

**New in v0.8: eleven more films.** Three new things in the model:

- *Slide route* (Chrome 100, Vivid Chrome 100): the descending Status A characteristic curves give
  the positive's dye amounts directly; the dye spectrum is projected with a 5000 K source (the
  sheets normalize their dyes for 5000 K viewing), seen with the CIE observer adapted to it, white
  is the clear film, dark-surround to dim-surround as for the prints. The exposure is set so 18 %
  grey lands at a visual density of 0.95 (Chrome 100) / 1.12 (Vivid Chrome 100): a choice, the
  ISO point is not a grey. Grey is balanced like a scanned slide (white and black neutral, a
  per-channel gamma pulls grey to neutral); the film's cast stays in between.
- *Scene light other than the film's balance* (Tungsten 800): VISION3 500T is given the scene
  under 5500 K daylight, developed and scanned with grey balance like the C-41 films. The glow is
  the plug-in's Halation switch; the film has no anti-halation layer in this guise.
- *Datasheets that publish less*: Fujifilm gives spectral sensitivity only relative (fine, the
  model normalizes it), Ilford a wedge spectrogram to 2850 K light (corrected to equal energy) and
  a *relative* exposure axis (anchored so the ISO 125 speed point, 0.1 above base, sits at
  log H = log10(0.8 / 125)). FP4 Plus has no other development times, so its push uses the gain
  measured on Tri-X. T-MAX 400 takes the plotted D-76 curves (6 / 8 / 10 / 12 min; 8 normal, pull
  6, push 1 at 8, push 2 at 11); T-MAX P3200 the T-MAX Developer curves (8 / 9 / 11 / 13 min)
  at the small-tank times for EI 1600 / 3200 / 6400 / 12 500 (10.5 / 12 / 13.5 / 15.5 min; the
  last two lie beyond the plotted 13 min and continue the density growth of the 11 → 13 min step).

Module size: PhotoCraft refuses plug-in modules above 32 MiB (33 554 432 bytes; the message appears
in yellow in the status bar). 80 LUTs on the old 41³ grid over 15 stops were 37 MB, so since v0.8
the grid is 37³ over 13 stops (−8 .. +5 around 18 % grey): the same cell size, so the same
accuracy, in 28 MB. Below −8 stops a film's toe is flat anyway (8-bit level 1 is −9.2 stops and
clamps to −8 without a visible difference); above +5 stops only 32-bit documents have values, and
every film has long since saturated there. Every band's fresh instance copies the module in, which
costs about 8 % on a 2 MP run compared with the 9-film v0.6 build (same per-pixel code). Against
the 41³ build the output differs by the moved grid nodes only: mean 0.06 levels on Portrait 400,
nothing above 2 levels; on the steepest films (Vivid Chrome 100, Cine 500T) 0.3–0.6 % of the
pixels move more, up to 26 levels in near-black shadows, where both grids approximate the model
about equally well.

**Black-and-white and blue skies:** both Mono films are, per their datasheets, as sensitive in the
blue (and near UV) as in the green, so an unfiltered blue sky comes out light, about 1–1.5 stops
brighter than the eye sees it, and foliage darker. That is the real look of unfiltered pan film;
a yellow/orange/red filter option would darken skies (not built yet).

## Speed

Measured in the test host (same interpreter and limits as PhotoCraft's), 24 MP photo, 2 slow cloud
cores (timings vary ±20 % between runs). PhotoCraft runs up to 4 bands at once, so a current Mac
should be faster still.

| | v0.4 | v0.5 |
|---|---|---|
| 8-bit, sRGB, Color/Tone 100, grain on (default) | 3.5 s | 3.5 s |
| 8-bit, Color or Tone < 100 | – | 5.8 s |
| 8-bit, Display P3 / Adobe RGB | – | 7.5 s |
| 16-bit, sRGB | 6.0 s | 6.1 s |
| 16-bit, Display P3 / Adobe RGB | – | 16.6 s |
| 32-bit, sRGB (linear) | 9.4 s | 10.6 s |
| 32-bit, Adobe RGB (linear) | – | 17.1 s |
| Halation, 8-bit | 2.5 s | 2.5 s |

The default settings run the same code as v0.4 (only the LUTs changed, see "Fixed in v0.5");
other input spaces and Color/Tone mixing take a general path with the colour conversion per pixel
(per cached colour in 8-bit). The plug-in file grew to 11 MB (nine LUTs stored as f32); v0.7 stores
36 LUTs as u16 in 18 MB.

v0.6 (measured on a 0.4 MP crop on this Mac, so only the ratios count): Halation off runs about
6 % slower than v0.5.1 (the 96 px band overlap the stage needs is copied whether it runs or not);
Halation on takes about as long as the two plug-ins did one after the other.

**Halation, profiled** (2 MP, 8-bit, default settings, glow reaching nearly every pixel): the
per-pixel write-back took two thirds of the stage, blur and highlight map a sixth each. Since then
the stage is specialised per depth and colour mode, 8-bit encodes through a clamp-free table and
the blur tests only the edges it must: a third of the wasm instructions, the same output to the
bit, but only about 20 % less wall time. The rest is memory traffic in the interpreter (about 16
loads and stores per pixel, like the film's cache hit), and that does not shrink without touching
fewer pixels.

**Tried and dropped: a colour cache for 16-bit documents.** Keyed by 12-bit levels it hardly ever
hits: in a 16-bit photo with ordinary sensor noise over 90 % of the pixels are distinct colours
(measured: 1.56 M distinct of 1.7 M pixels at σ = 0.4/255, against 0.46 M for the same photo as an
8-bit JPEG). Keyed by 8-bit levels, with the output's slope per input channel cached so a hit
interpolates to the exact 16-bit value, it hits about 70 % but is still 1.2–2.4× *slower* than the
per-pixel path, because a hit with the interpolation already costs about what the tetrahedral
lookup does; only grayscale 16-bit gained (5×), too rare to keep a path for. The interpreter is
the limit here, not the algorithm: the plug-in has no SIMD (PhotoCraft's wasmi is built without
the `simd` feature, a SIMD build is refused at load), no threads and no GPU; a JIT or SIMD on the
host side would help every plug-in without a change here.

## Limits

- Input space set by hand (no profile information in the plug-in ABI). 32-bit documents are taken
  as linear with the chosen primaries; the film itself saturates at +6 stops, so values above 1.0
  survive only in the share Color and Tone leave to the original.
- The separate halation plug-in takes the document as sRGB (the film plug-in's own stage knows the
  Input Space; the difference only moves the threshold a little).
- RGB and Grayscale only.
- Without measurements of real scans or prints, the look is the datasheets plus the stated
  model, not a copy of a specific lab's output.

## Layout

| Path | What |
|---|---|
| `dist/` | the built plug-ins (`./build.sh`; not in the repository, published as release downloads) |
| `plugin/`, `halation/` | Rust sources of the two plug-ins (`no_std`, no imports) |
| `common/` | what both share, compiled into each: ABI glue, parameter reader, table lookups, and the halation stage itself (`halation.rs`) |
| `data/pdf/` | the manufacturer datasheets – **not in the repository** (see Licence). `./build.sh --data` needs them here, under the file names in `data/tools/specs.py`; the publication numbers are in the film table above. The VISION3 200T and 50D sheets used are Kodak's Spanish editions (vector PDFs) |
| `data/tools/` | `pagesummary.py`/`pdfpaths.py` (inspect a page), `specs.py` (where each curve is), `digitize.py`, `film_data.py`, `check_specs.py` (plots into `data/check/`) |
| `data/films/*.json` | the digitized film data the model reads (`char_dev` / `char_push`: the other development times and push curves, `dev_for_push`: which time each push level uses); `status.json` the status M/A densitometer curves |
| `data/check/` | plots of every digitized curve over the datasheet page, for checking (`check_specs.py`; not in the repository, as they contain the pages) |
| `model/film_model_v2.py` | the film simulation → `lut/<film>.lut` and `_pull1` / `_push1` / `_push2` (`--push-only` bakes just those, `--preview` writes comparisons) |
| `model/make_tables.py` | decode tables (`tables.bin`, `srgb.bin`), Adobe RGB tables, grain texture |
| `model/export_cube.py` | the same look as standard `.cube` LUTs → `cube/` (Portrait 400 shipped; any film by its model key, named by its menu label) |
| `harness/` | test host mirroring PhotoCraft's plug-in host; `cargo test --release` there checks the plug-ins in `dist/` (Strength 0 is the identity, Strength 50 has no step at black, push/pull order the mid-tone contrast and keep 18 % grey, the slide films are neutral at grey, 32-bit headroom, every film and push level at every depth, halation idle without highlights, Halation switch = the two plug-ins in sequence) |
| `build.sh` | build and test (`--data` re-digitizes and re-bakes, `--test IMG` runs every film in the test host) |

## Licence

MIT (see `LICENSE`): the code, the digitized curves (`data/films/*.json`), the look tables computed
from them and the built plug-ins.

The manufacturer datasheets (© Kodak Alaris / Eastman Kodak Company, FUJIFILM Corporation, Harman
Technology / ILFORD) are **not** part of this repository, nor are page images or plots drawn over
them, and this licence grants no rights in them. Product names are trademarks of their owners; the
dropdown uses neutral names for that reason.

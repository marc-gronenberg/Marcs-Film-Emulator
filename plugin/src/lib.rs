//! Marcs Film Emulator: twenty film looks (colour negative, cine, slide, black-and-white) for PhotoCraft (plug-in
//! ABI v1, see PhotoCraft's `docs/plugins.md`), chosen in a dropdown.
//!
//! The colour and tone of each come from a spectral simulation of the film built on the curves of
//! the manufacturer's published datasheet (`model/film_model_v2.py`, data in `data/films/`): layer
//! sensitivities, characteristic curves, dye spectra, then a lab scan or a cinema print, baked into
//! a 37³ 3D LUT per film over 13 stops of log exposure (-8 .. +5 around 18 % grey). At run time the
//! plug-in only decodes each pixel to that log-exposure coordinate (static tables), interpolates
//! the LUT (tetrahedral; 8-bit colours are cached per band) and adds grain (a static, tileable
//! grain texture addressed in document coordinates, weighted to the mid-tones). Before the film,
//! a switchable halation stage (`common/src/halation.rs`) adds the glow around highlights; it
//! needs neighbouring pixels, so every band
//! comes with a 96 px overlap and the film runs on the inner area only.
//!
//! Documents in Display P3 or Adobe RGB are converted to linear sRGB for the film and back
//! ("Input Space"); "Color" and "Tone" mix the film's colour and its tonality with the original's
//! separately, in linear light.
//!
//! Built for the interpreter it runs in (wasmi, ~10–100× slower than native): no per-band set-up
//! work, no bounds checks in the pixel loop, one specialised loop per pixel layout, a colour cache.
//!
//! `no_std`, no imports, no allocator. The ABI glue, parameter reader and table lookups are in
//! `common/`.
#![no_std]

use emulsion_common::halation::{Glow, halation};
use emulsion_common::{Aligned, ERR_ARGS, ERR_MEMORY, ERR_MODE, HAS_ALPHA, TN, clamp01, json_num, json_str, lerp_tab};

#[panic_handler]
fn panic(_: &core::panic::PanicInfo) -> ! {
    core::arch::wasm32::unreachable()
}

// ----------------------------------------------------------------------------- manifest

const MANIFEST: &str = r#"{
  "id": "io.emulsion.film",
  "name": "Marcs Film Emulator…",
  "version": "0.8.0",
  "kind": "filter",
  "author": "Marc Gronenberg",
  "description": "Film looks simulated spectrally from published film datasheets (sensitivities, characteristic curves, dyes), with push/pull, halation and film grain. Colour and black-and-white. RGB and Grayscale.",
  "params": {
    "film":       {"type": "choice", "options": ["Portrait 160", "Portrait 400", "Portrait 800", "Everyday 200", "Street 400", "Vivid 100", "Soft 400", "Snapshot 400", "Cine 50D", "Cine 200T", "Cine 250D", "Cine 500T", "Tungsten 800", "Chrome 100", "Vivid Chrome 100", "Mono 100", "Mono 125", "Mono 400", "Mono 400 T", "Mono 3200"], "default": "Portrait 400"},
    "inputSpace": {"type": "choice", "options": ["sRGB", "Display P3", "Adobe RGB"], "default": "sRGB"},
    "push":       {"type": "choice", "options": ["Pull 1", "Normal", "Push 1", "Push 2"], "default": "Normal"},
    "strength":   {"type": "number", "min": 0, "max": 100, "default": 100},
    "halation":   {"type": "choice", "options": ["Off", "On"], "default": "Off"},
    "halationAmount":    {"type": "number", "min": 0, "max": 100, "default": 40},
    "halationRadius":    {"type": "number", "min": 2, "max": 36, "default": 14, "unit": "px"},
    "halationThreshold": {"type": "number", "min": 0, "max": 100, "default": 55},
    "grain":      {"type": "number", "min": 0, "max": 100, "default": 35},
    "grainSize":  {"type": "number", "min": 0.5, "max": 4, "default": 1, "unit": "px"},
    "seed":       {"type": "int", "min": 0, "max": 9999, "default": 1}
  },
  "overlap": 96,
  "area": "content"
}"#;

/// The manifest's overlap: the halation stage's reach; the film runs inside it.
const OVERLAP: usize = 96;

#[unsafe(no_mangle)]
pub extern "C" fn pc_abi_version() -> u32 {
    1
}

#[unsafe(no_mangle)]
pub extern "C" fn pc_manifest() -> u64 {
    emulsion_common::pack_manifest(MANIFEST)
}

#[unsafe(no_mangle)]
pub extern "C" fn pc_alloc(size: u32) -> u32 {
    emulsion_common::alloc(size)
}

// ----------------------------------------------------------------------------- static data

const N: usize = 37;
const STOPS_LO: f32 = -8.0;
const STOPS_HI: f32 = 5.0;
const INV_SPAN: f32 = 1.0 / (STOPS_HI - STOPS_LO);
const LUT_LEN: usize = N * N * N * 3;
const TABLES_LEN: usize = 256 + 2 * (TN + 1) + 257 + 65536;
const GT: usize = 1024; // grain tile size

/// The film LUTs as the model writes them: `u16` (little-endian), `[b][g][r][rgb]`, sRGB-encoded
/// output; per film one for each push level (`lut/<film>_pull1.lut`, `<film>.lut`, `_push1`,
/// `_push2`). u16 rather than f32 halves what every band's fresh instance copies in.
type Lut = Aligned<[u8; LUT_LEN * 2]>;
macro_rules! luts {
    ($film:literal) => {
        [
            &Aligned(*include_bytes!(concat!("../../lut/", $film, "_pull1.lut"))),
            &Aligned(*include_bytes!(concat!("../../lut/", $film, ".lut"))),
            &Aligned(*include_bytes!(concat!("../../lut/", $film, "_push1.lut"))),
            &Aligned(*include_bytes!(concat!("../../lut/", $film, "_push2.lut"))),
        ]
    };
}
/// Dropdown label, LUTs per push level (Pull 1, Normal, Push 1, Push 2), grain scale (relative
/// graininess of the stock), black-and-white (grey grain). Any order; the dropdown's is in the
/// manifest, the choice arrives by name.
const FILMS: [(&str, [&Lut; 4], f32, bool); 20] = [
    ("Portrait 160", luts!("portra160"), 0.8, false),
    ("Portrait 400", luts!("portra400"), 1.0, false),
    ("Portrait 800", luts!("portra800"), 1.3, false),
    ("Everyday 200", luts!("gold200"), 1.05, false),
    ("Street 400", luts!("ultramax400"), 1.25, false),
    ("Vivid 100", luts!("ektar100"), 0.75, false),
    ("Soft 400", luts!("pro400h"), 1.0, false),
    ("Snapshot 400", luts!("superia400"), 1.3, false),
    ("Cine 50D", luts!("vision50d"), 0.6, false),
    ("Cine 200T", luts!("vision200t"), 1.05, false),
    ("Cine 250D", luts!("vision250d"), 1.0, false),
    ("Cine 500T", luts!("vision500t"), 1.2, false),
    ("Tungsten 800", luts!("tungsten800"), 1.2, false),
    ("Chrome 100", luts!("ektachrome100"), 0.6, false),
    ("Vivid Chrome 100", luts!("velvia100"), 0.55, false),
    ("Mono 100", luts!("tmax100"), 0.65, true),
    ("Mono 125", luts!("fp4plus"), 0.8, true),
    ("Mono 400", luts!("trix400"), 1.35, true),
    ("Mono 400 T", luts!("tmax400"), 0.9, true),
    ("Mono 3200", luts!("tmaxp3200"), 2.0, true),
];
/// Grain scale per push level: more development, coarser grain (a model assumption; the
/// datasheets describe the increase but give no numbers).
const PUSH_GRAIN: [f32; 4] = [0.85, 1.0, 1.25, 1.5];
/// `adec[TN+1] | aenc[TN+1]`: Adobe RGB (1998) transfer curve (gamma 563/256) and its inverse.
static ADOBE_BYTES: &Aligned<[u8; 2 * (TN + 1) * 4]> = &Aligned(*include_bytes!("../../lut/adobe.bin"));
/// Linear Display P3 / Adobe RGB (D65) -> linear sRGB and back (rows sum to 1: white stays white).
const P3_IN: [f32; 9] = [1.2249402, -0.2249402, 0.0, -0.0420571, 1.0420571, 0.0, -0.0196375, -0.0786360, 1.0982736];
const P3_OUT: [f32; 9] = [0.8224620, 0.1775380, 0.0, 0.0331943, 0.9668057, 0.0, 0.0170826, 0.0723974, 0.9105200];
const ADOBE_IN: [f32; 9] = [1.3983558, -0.3983558, 0.0, 0.0, 1.0, 0.0, 0.0, -0.0429290, 1.0429290];
const ADOBE_OUT: [f32; 9] = [0.7151256, 0.2848744, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0411619, 0.9588381];
/// `u8base[256] | odec[TN+1] | enc[TN+1] | log2m[257] | u16base[65536]` as `f32`
/// (see `model/make_tables.py`).
static TABLE_BYTES: &Aligned<[u8; TABLES_LEN * 4]> = &Aligned(*include_bytes!("../../lut/tables.bin"));
/// Tileable grain, `[y][x][rgb]` signed bytes, unit spread = 32.
static GRAIN_BYTES: &Aligned<[u8; GT * GT * 3]> = &Aligned(*include_bytes!("../../lut/grain1024.bin"));

const U8BASE: usize = 0;
const ODEC: usize = 256;
const ENC: usize = 256 + (TN + 1);
const LOG2M: usize = 256 + 2 * (TN + 1);
const U16BASE: usize = LOG2M + 257;
const LOG2_018: f32 = -2.473_931_2;
/// `log2(linear) * INV_SPAN + LOG_OFF` is the shaper coordinate.
const LOG_OFF: f32 = -(LOG2_018 + STOPS_LO) * INV_SPAN;

#[inline(always)]
fn tables() -> *const f32 {
    TABLE_BYTES.0.as_ptr() as *const f32
}

const DR: usize = 3;
const DG: usize = N * 3;
const DB: usize = N * N * 3;

/// Tetrahedral interpolation in the cell at `p0` with fractions (fr, fg, fb); sRGB-encoded rgb.
///
/// # Safety
/// `p0` is a cell's first corner, so that all 8 corners lie inside the LUT.
#[inline(always)]
unsafe fn tetra(p0: *const u16, fr: f32, fg: f32, fb: f32) -> (f32, f32, f32) {
    let (a, b, w1, w2, w3) = if fr > fg {
        if fg > fb {
            (DR, DR + DG, fr - fg, fg - fb, fb)
        } else if fr > fb {
            (DR, DR + DB, fr - fb, fb - fg, fg)
        } else {
            (DB, DR + DB, fb - fr, fr - fg, fg)
        }
    } else if fb > fg {
        (DB, DG + DB, fb - fg, fg - fr, fr)
    } else if fb > fr {
        (DG, DG + DB, fg - fb, fb - fr, fr)
    } else {
        (DG, DR + DG, fg - fr, fr - fb, fb)
    };
    // the u16 scale folded into the weights
    const S: f32 = 1.0 / 65535.0;
    let (w1, w2, w3) = (w1 * S, w2 * S, w3 * S);
    let w0 = S - (w1 + w2 + w3);
    unsafe {
        let (pa, pb, pc) = (p0.add(a), p0.add(b), p0.add(DR + DG + DB));
        let c = |k: usize| w0 * *p0.add(k) as f32 + w1 * *pa.add(k) as f32 + w2 * *pb.add(k) as f32 + w3 * *pc.add(k) as f32;
        (c(0), c(1), c(2))
    }
}

/// The LUT cell and fraction along one axis for a shaper coordinate (clamped to 0..1).
#[inline(always)]
fn cell(u: f32) -> (usize, f32) {
    const S: f32 = (N - 1) as f32;
    let p = clamp01(u) * S;
    let i = p as usize;
    let i = if i < N - 1 { i } else { N - 2 };
    (i, p - i as f32)
}

/// Tetrahedral interpolation at shaper coordinates (each clamped to 0..1); sRGB-encoded rgb.
#[inline(always)]
fn sample_lut(lut: *const u16, ur: f32, ug: f32, ub: f32) -> (f32, f32, f32) {
    let ((ir, fr), (ig, fg), (ib, fb)) = (cell(ur), cell(ug), cell(ub));
    // SAFETY: ir, ig, ib <= N-2, so every corner index stays below LUT_LEN.
    unsafe { tetra(lut.add(ib * DB + ig * DG + ir * DR), fr, fg, fb) }
}

#[inline(always)]
fn floor_i(x: f32) -> i32 {
    let i = x as i32;
    if (i as f32) > x { i - 1 } else { i }
}

// ----------------------------------------------------------------------------- the pixel loop

/// Everything the loop needs, decided once per band.
struct Ctx {
    /// the chosen film's LUT at the chosen push level
    lut: *const u16,
    /// the inner area (the band without its overlap): size, document position of its first pixel,
    /// and the band's row stride in samples
    w: usize,
    h: usize,
    x0: i32,
    y0: i32,
    stride: usize,
    /// black-and-white film: one grain value for all channels
    mono: bool,
    /// general path: input space is sRGB (no matrices); mix with the original (color or tone < 1)
    ident: bool,
    mix: bool,
    color: f32,
    tone: f32,
    m_in: [f32; 9],
    m_out: [f32; 9],
    /// decode (16-bit) and encode tables of the document's transfer curve (TN + 1 floats)
    dec: *const f32,
    enc: *const f32,
    /// grain amplitude in output (sRGB-encoded) units per tile unit (0 = off)
    grain: f32,
    /// grain sampling: tile pixels per document pixel; `nearest` when it is ~1
    gscale: f32,
    nearest: bool,
    /// tile offset from the seed
    ox: u32,
    oy: u32,
}

/// Grain at document pixel (x, y): three values, unit spread × 32.
///
/// # Safety
/// Reads the static grain tile only (indices are wrapped to the tile).
#[inline(always)]
unsafe fn grain_at(c: &Ctx, x: i32, y: i32) -> (f32, f32, f32) {
    let g = GRAIN_BYTES.0.as_ptr() as *const i8;
    const M: u32 = (GT - 1) as u32;
    unsafe {
        if c.nearest {
            let i = (((y as u32).wrapping_add(c.oy) & M) as usize * GT + ((x as u32).wrapping_add(c.ox) & M) as usize) * 3;
            (*g.add(i) as f32, *g.add(i + 1) as f32, *g.add(i + 2) as f32)
        } else {
            let gx = x as f32 * c.gscale;
            let gy = y as f32 * c.gscale;
            let (ix, iy) = (floor_i(gx), floor_i(gy));
            let (fx, fy) = (gx - ix as f32, gy - iy as f32);
            let (x0, x1) = ((ix as u32).wrapping_add(c.ox) & M, (ix as u32).wrapping_add(c.ox + 1) & M);
            let (y0, y1) = ((iy as u32).wrapping_add(c.oy) & M, (iy as u32).wrapping_add(c.oy + 1) & M);
            let (a, b) = (g.add((y0 as usize * GT + x0 as usize) * 3), g.add((y0 as usize * GT + x1 as usize) * 3));
            let (cc, d) = (g.add((y1 as usize * GT + x0 as usize) * 3), g.add((y1 as usize * GT + x1 as usize) * 3));
            // Bilinear interpolation shrinks the spread; 1.3 brings it back roughly.
            let s = |k: usize| {
                let top = *a.add(k) as f32 + (*b.add(k) as f32 - *a.add(k) as f32) * fx;
                let bot = *cc.add(k) as f32 + (*d.add(k) as f32 - *cc.add(k) as f32) * fx;
                (top + (bot - top) * fy) * 1.3
            };
            (s(0), s(1), s(2))
        }
    }
}

/// One slot of the per-band colour cache (8-bit documents): the input levels and the film output,
/// plus the pixel's grain weight. 32 bytes, so a slot address is a shift.
#[repr(C)]
struct Slot {
    key: u32,
    r: f32,
    g: f32,
    b: f32,
    k: f32,
    _pad: [u32; 3],
}

const CACHE_BITS: u32 = 16;

/// Grain weight of an output (sRGB-encoded): strongest in the mid-tones, as grain shows in a print.
#[inline(always)]
fn grain_weight(c: &Ctx, l: f32) -> f32 {
    c.grain * (0.3 + 2.8 * l * (1.0 - l))
}

/// A row of grain: the tile row for document row `y`, and the tile column of the band's first pixel.
#[inline(always)]
fn grain_row(c: &Ctx, y: i32) -> (*const i8, u32) {
    const M: u32 = (GT - 1) as u32;
    let row = ((y as u32).wrapping_add(c.oy) & M) as usize;
    let g = unsafe { (GRAIN_BYTES.0.as_ptr() as *const i8).add(row * GT * 3) };
    (g, (c.x0 as u32).wrapping_add(c.ox) & M)
}

/// Grain at a scaled size (bilinear from the tile), prepared per band so the per-pixel work is one
/// horizontal interpolation: per column the tile column and fraction, per row the two tile rows
/// blended vertically into `row`.
struct Scaled {
    col: *mut u32,
    frac: *mut f32,
    row: *mut f32,
    span: usize,
    i0: i32,
}

impl Scaled {
    /// None if out of memory.
    fn new(c: &Ctx) -> Option<Scaled> {
        let x0 = c.x0 as f32 * c.gscale;
        let i0 = floor_i(x0);
        let i1 = floor_i((c.x0 + c.w as i32) as f32 * c.gscale) + 1;
        let span = (i1 - i0 + 2) as usize;
        let mem = pc_alloc((c.w * 8 + span * 12) as u32) as usize;
        if mem == 0 {
            return None;
        }
        let s = Scaled { col: mem as *mut u32, frac: (mem + c.w * 4) as *mut f32, row: (mem + c.w * 8) as *mut f32, span, i0 };
        for x in 0..c.w {
            let gx = (c.x0 + x as i32) as f32 * c.gscale;
            let i = floor_i(gx);
            unsafe {
                *s.col.add(x) = ((i - i0) * 3) as u32;
                *s.frac.add(x) = gx - i as f32;
            }
        }
        Some(s)
    }

    /// Blends the two tile rows around document row `y` into `row` (scaled by 1.3, which brings
    /// back the spread bilinear interpolation takes away).
    fn prepare_row(&self, c: &Ctx, y: i32) {
        const M: u32 = (GT - 1) as u32;
        let gy = y as f32 * c.gscale;
        let iy = floor_i(gy);
        let fy = gy - iy as f32;
        let g = GRAIN_BYTES.0.as_ptr() as *const i8;
        let r0 = ((iy as u32).wrapping_add(c.oy) & M) as usize * GT;
        let r1 = ((iy as u32).wrapping_add(c.oy + 1) & M) as usize * GT;
        for j in 0..self.span {
            let tx = ((self.i0 + j as i32) as u32).wrapping_add(c.ox) & M;
            unsafe {
                let a = g.add((r0 + tx as usize) * 3);
                let b = g.add((r1 + tx as usize) * 3);
                for k in 0..3 {
                    let v0 = *a.add(k) as f32;
                    *self.row.add(j * 3 + k) = (v0 + (*b.add(k) as f32 - v0) * fy) * 1.3;
                }
            }
        }
    }

    /// Grain at band column `x` of the prepared row.
    #[inline(always)]
    fn at(&self, x: usize) -> (f32, f32, f32) {
        unsafe {
            let i = *self.col.add(x) as usize;
            let f = *self.frac.add(x);
            let a = self.row.add(i);
            let l = |k: usize| *a.add(k) + (*a.add(k + 3) - *a.add(k)) * f;
            (l(0), l(1), l(2))
        }
    }
}

/// Writes (r, g, b) to the pixel at `p`.
///
/// # Safety
/// `p` points at a pixel with at least 3 (1 if GREY) samples.
#[inline(always)]
unsafe fn store<const GREY: bool>(p: *mut f32, r: f32, g: f32, b: f32) {
    unsafe {
        *p = r;
        if !GREY {
            *p.add(1) = g;
            *p.add(2) = b;
        }
    }
}

/// Adds grain (gr, gg, gb) × k to an output; black-and-white films and grey documents get one
/// grey value (the mean, scaled back to the per-channel spread).
#[inline(always)]
fn add_grain<const GREY: bool>(c: &Ctx, o: (f32, f32, f32), gr: f32, gg: f32, gb: f32, k: f32) -> (f32, f32, f32) {
    if GREY || c.mono {
        let v = (gr + gg + gb) * (1.25 / 3.0) * k;
        (o.0 + v, o.1 + v, o.2 + v)
    } else {
        (o.0 + gr * k, o.1 + gg * k, o.2 + gb * k)
    }
}

#[inline(always)]
fn mat(m: &[f32; 9], r: f32, g: f32, b: f32) -> (f32, f32, f32) {
    (m[0] * r + m[1] * g + m[2] * b, m[3] * r + m[4] * g + m[5] * b, m[6] * r + m[7] * g + m[8] * b)
}

#[inline(always)]
fn luma(r: f32, g: f32, b: f32) -> f32 {
    0.2126 * r + 0.7152 * g + 0.0722 * b
}

/// The general path, for any input space and Strength setting: linear document values in,
/// output encoded with the document's transfer curve, or linear if `LIN` (32-bit documents, whose
/// values above 1.0 then survive the mix).
///
/// Linear sRGB of the original (colours outside sRGB pulled towards their luminance until they
/// fit, for the film only) -> film -> mixed with the original in linear light: the luminance by
/// `tone`, the colour (rgb / luminance) by `color` -> back to the document's space.
#[inline(always)]
fn general<const GREY: bool, const LIN: bool>(c: &Ctx, r: f32, g: f32, b: f32) -> (f32, f32, f32) {
    let (or, og, ob) = if c.ident { (r, g, b) } else { mat(&c.m_in, r, g, b) };
    let yo = luma(or, og, ob);
    let mn = if or < og { if or < ob { or } else { ob } } else if og < ob { og } else { ob };
    let (sr, sg, sb) = if mn >= 0.0 {
        (or, og, ob)
    } else if yo > 0.0 {
        let t = yo / (yo - mn);
        (yo + (or - yo) * t, yo + (og - yo) * t, yo + (ob - yo) * t)
    } else {
        (0.0, 0.0, 0.0)
    };
    let f = sample_lut(c.lut, log2_fast(sr) * INV_SPAN + LOG_OFF, log2_fast(sg) * INV_SPAN + LOG_OFF, log2_fast(sb) * INV_SPAN + LOG_OFF);
    finish::<GREY, LIN>(c, (or, og, ob), yo, f)
}

/// The rest of the general path: film output `f` (sRGB-encoded) mixed with the original `o`
/// (linear sRGB, luminance `yo`), converted to the document's space and encoded (linear if `LIN`).
#[inline(always)]
fn finish<const GREY: bool, const LIN: bool>(c: &Ctx, o: (f32, f32, f32), yo: f32, f: (f32, f32, f32)) -> (f32, f32, f32) {
    let (or, og, ob) = o;
    let odec = unsafe { tables().add(ODEC) };
    let (mut xr, mut xg, mut xb) = unsafe { (lerp_tab(odec, f.0), lerp_tab(odec, f.1), lerp_tab(odec, f.2)) };
    if c.mix {
        let yf = luma(xr, xg, xb);
        let yt = yo + (yf - yo) * c.tone;
        let (a, d) = match (yo > 1e-7, yf > 1e-7) {
            (true, true) => ((1.0 - c.color) * yt / yo, c.color * yt / yf),
            // one side is black and has no colour of its own: the other carries the target
            // luminance alone (so Tone 0 keeps a black pixel black)
            (false, true) => (0.0, yt / yf),
            (true, false) => (yt / yo, 0.0),
            (false, false) => (0.0, 0.0),
        };
        (xr, xg, xb) = (or * a + xr * d, og * a + xg * d, ob * a + xb * d);
    }
    unsafe {
        if GREY {
            let l = luma(xr, xg, xb);
            let e = if LIN { l } else { lerp_tab(c.enc, l) };
            return (e, e, e);
        }
        let (xr, xg, xb) = if c.ident { (xr, xg, xb) } else { mat(&c.m_out, xr, xg, xb) };
        if LIN { (xr, xg, xb) } else { (lerp_tab(c.enc, xr), lerp_tab(c.enc, xg), lerp_tab(c.enc, xb)) }
    }
}

/// Film output (sRGB-encoded) for shaper coordinates; grey documents get the output's luminance.
#[inline(always)]
fn film<const GREY: bool>(c: &Ctx, ur: f32, ug: f32, ub: f32) -> (f32, f32, f32) {
    let (r, g, b) = sample_lut(c.lut, ur, ug, ub);
    if GREY {
        unsafe {
            let t = tables();
            let odec = t.add(ODEC);
            let l = 0.2126 * lerp_tab(odec, r) + 0.7152 * lerp_tab(odec, g) + 0.0722 * lerp_tab(odec, b);
            let e = lerp_tab(t.add(ENC), l);
            (e, e, e)
        }
    } else {
        (r, g, b)
    }
}

/// Per band, for each 8-bit level: its LUT cell offset along each axis and its fraction (push
/// included), so a cache miss goes straight to the tetrahedral interpolation, and its linear value
/// in the document's transfer curve.
struct Pre {
    off: *mut u32, // [3][256]: r, g, b offsets into the LUT
    frac: *mut f32, // [256]
    lin: *mut f32, // [256]
}

impl Pre {
    fn new(c: &Ctx) -> Option<Pre> {
        let mem = pc_alloc(256 * 20) as usize;
        if mem == 0 {
            return None;
        }
        let p = Pre { off: mem as *mut u32, frac: (mem + 256 * 12) as *mut f32, lin: (mem + 256 * 16) as *mut f32 };
        let u8b = tables();
        for l in 0..256 {
            let (i, f) = cell(unsafe { *u8b.add(U8BASE + l) });
            unsafe {
                *p.off.add(l) = (i * DR) as u32;
                *p.off.add(256 + l) = (i * DG) as u32;
                *p.off.add(512 + l) = (i * DB) as u32;
                *p.frac.add(l) = f;
                *p.lin.add(l) = lerp_tab(c.dec, l as f32 * (1.0 / 255.0));
            }
        }
        Some(p)
    }

    #[inline(always)]
    fn film<const GREY: bool>(&self, c: &Ctx, lr: usize, lg: usize, lb: usize) -> (f32, f32, f32) {
        unsafe {
            let base = *self.off.add(lr) + *self.off.add(256 + lg) + *self.off.add(512 + lb);
            let (r, g, b) = tetra(c.lut.add(base as usize), *self.frac.add(lr), *self.frac.add(lg), *self.frac.add(lb));
            if GREY {
                let t = tables();
                let odec = t.add(ODEC);
                let l = 0.2126 * lerp_tab(odec, r) + 0.7152 * lerp_tab(odec, g) + 0.0722 * lerp_tab(odec, b);
                let e = lerp_tab(t.add(ENC), l);
                (e, e, e)
            } else {
                (r, g, b)
            }
        }
    }
}

/// 8-bit documents: a direct-mapped colour cache in front of the LUT (photos repeat 8-bit colours
/// a lot; a hit is a few loads), grain from the tile with the weight cached alongside.
///
/// (Tried for 16-bit documents too, keyed by the 8-bit levels with the output's slope per input
/// channel cached so a hit interpolates to the exact value: slower than the per-pixel path below,
/// because a hit with the interpolation already costs about what the tetrahedral lookup does, and
/// noisy 16-bit photos miss a third of the time. Only grayscale gained.)
///
/// # Safety
/// `px` holds `w × h × CH` samples; `cache` holds 2^CACHE_BITS zeroed slots.
#[inline(always)]
unsafe fn run8<const CH: usize, const ALPHA: bool, const GREY: bool, const GRAIN: u8, const GEN: bool>(px: *mut f32, c: &Ctx, cache: *mut Slot, pre: &Pre, sc: Option<&Scaled>) {
    // GRAIN: 0 off, 1 native size (straight from the tile row), 2 scaled (prepared rows in `sc`)
    // GEN: the general path (input space, Strength) on a cache miss
    const M: u32 = (GT - 1) as u32;
    let mut row = px;
    for y in 0..c.h {
        let (grow, mut gx) = grain_row(c, c.y0 + y as i32);
        if GRAIN == 2 {
            if let Some(sc) = sc {
                sc.prepare_row(c, c.y0 + y as i32);
            }
        }
        let mut p = row;
        for x in 0..c.w {
            unsafe {
                if !(ALPHA && *p.add(CH - 1) <= 0.0) {
                    // 8-bit samples are exactly i/255, so rounding gives the level (saturating cast)
                    let (lr, lg, lb) = if GREY {
                        let l = (*p * 255.0 + 0.5) as u32;
                        (l, l, l)
                    } else {
                        ((*p * 255.0 + 0.5) as u32, (*p.add(1) * 255.0 + 0.5) as u32, (*p.add(2) * 255.0 + 0.5) as u32)
                    };
                    let key = lr | (lg << 8) | (lb << 16) | (1 << 24);
                    let slot = cache.add((key.wrapping_mul(0x9e37_79b1) >> (32 - CACHE_BITS)) as usize);
                    if (*slot).key != key {
                        let (lr, lg, lb) = ((lr & 255) as usize, (lg & 255) as usize, (lb & 255) as usize);
                        let o = if GEN && c.ident {
                            // sRGB document, Strength mix: the film through the per-level tables
                            let f = pre.film::<false>(c, lr, lg, lb);
                            let (or, og, ob) = (*pre.lin.add(lr), *pre.lin.add(lg), *pre.lin.add(lb));
                            finish::<GREY, false>(c, (or, og, ob), luma(or, og, ob), f)
                        } else if GEN {
                            general::<GREY, false>(c, *pre.lin.add(lr), *pre.lin.add(lg), *pre.lin.add(lb))
                        } else {
                            pre.film::<GREY>(c, lr, lg, lb)
                        };
                        let k = if GRAIN > 0 { grain_weight(c, if GREY { o.0 } else { 0.2126 * o.0 + 0.7152 * o.1 + 0.0722 * o.2 }) } else { 0.0 };
                        *slot = Slot { key, r: o.0, g: o.1, b: o.2, k, _pad: [0; 3] };
                    }
                    let s = &*slot;
                    if GRAIN > 0 {
                        let (gr, gg, gb) = if GRAIN == 1 {
                            let gp = grow.add(gx as usize * 3);
                            (*gp as f32, *gp.add(1) as f32, *gp.add(2) as f32)
                        } else {
                            match sc {
                                Some(sc) => sc.at(x),
                                None => (0.0, 0.0, 0.0),
                            }
                        };
                        let (r, g, b) = add_grain::<GREY>(c, (s.r, s.g, s.b), gr, gg, gb, s.k);
                        store::<GREY>(p, r, g, b);
                    } else {
                        store::<GREY>(p, s.r, s.g, s.b);
                    }
                }
                gx = (gx + 1) & M;
                p = p.add(CH);
            }
        }
        row = unsafe { row.add(c.stride) };
    }
}

/// log2(v) for v > 0 from the float's exponent and a 257-entry mantissa table (|error| < 2e-6).
#[inline(always)]
fn log2_fast(v: f32) -> f32 {
    let v = if v > 1e-30 { v } else { 1e-30 };
    let bits = v.to_bits();
    let e = ((bits >> 23) & 0xff) as i32 - 127;
    let m = bits & 0x007f_ffff;
    let i = (m >> 15) as usize; // top 8 mantissa bits
    let f = (m & 0x7fff) as f32 * (1.0 / 32768.0);
    unsafe {
        let t = tables().add(LOG2M);
        let a = *t.add(i);
        e as f32 + a + (*t.add(i + 1) - a) * f
    }
}

/// 16- and 32-bit documents: every pixel through the LUT (no cache: few repeats at these depths).
/// 32-bit documents are linear: the general path mixes in linear light without an encode step, so
/// values above 1.0 survive where the film is faded out; the film's own output is decoded.
///
/// # Safety
/// `px` holds `w × h × CH` samples.
#[inline(always)]
unsafe fn run_hi<const CH: usize, const ALPHA: bool, const GREY: bool, const DEPTH: u32, const GEN: bool>(px: *mut f32, c: &Ctx) {
    let t = tables();
    let (u16b, odec, enc) = unsafe { (t.add(U16BASE), t.add(ODEC), t.add(ENC)) };
    // 16-bit samples are exactly i/65535: the level indexes the table directly (saturating cast)
    let to_u = |v: f32| -> f32 {
        if DEPTH == 16 { unsafe { *u16b.add(((v * 65535.0 + 0.5) as u32 & 0xffff) as usize) } } else { log2_fast(v) * INV_SPAN + LOG_OFF }
    };
    let grain_on = c.grain > 0.0;
    // 32-bit: grain is added through the sRGB curve as for the other depths; above white (where
    // only a faded-out film leaves values) with the curve's slope at white, so it stays continuous
    let slope1 = unsafe { (lerp_tab(odec, 1.0) - lerp_tab(odec, 1.0 - 1.0 / TN as f32)) * TN as f32 };
    let mut row = px;
    for y in 0..c.h {
        let dy = c.y0 + y as i32;
        let mut p = row;
        for x in 0..c.w {
            unsafe {
                if !(ALPHA && *p.add(CH - 1) <= 0.0) {
                    let lin = |v: f32| if DEPTH == 16 { lerp_tab(c.dec, v) } else { v };
                    // `e` is the sRGB-encoded result, kept for the grain of 32-bit documents (the
                    // film's own output is encoded already; the mixed one is encoded on demand)
                    let (mut r, mut g, mut b, e) = if GEN {
                        let (pr, pg, pb) = if GREY {
                            let l = lin(*p);
                            (l, l, l)
                        } else {
                            (lin(*p), lin(*p.add(1)), lin(*p.add(2)))
                        };
                        if DEPTH == 32 {
                            let (r, g, b) = general::<GREY, true>(c, pr, pg, pb);
                            let e = if grain_on { (lerp_tab(enc, r), lerp_tab(enc, g), lerp_tab(enc, b)) } else { (0.0, 0.0, 0.0) };
                            (r, g, b, e)
                        } else {
                            let (r, g, b) = general::<GREY, false>(c, pr, pg, pb);
                            (r, g, b, (0.0, 0.0, 0.0))
                        }
                    } else {
                        let f = if GREY {
                            let u = to_u(*p);
                            film::<true>(c, u, u, u)
                        } else {
                            film::<false>(c, to_u(*p), to_u(*p.add(1)), to_u(*p.add(2)))
                        };
                        if DEPTH == 32 { (lerp_tab(odec, f.0), lerp_tab(odec, f.1), lerp_tab(odec, f.2), f) } else { (f.0, f.1, f.2, f) }
                    };
                    if grain_on {
                        let (gr, gg, gb) = grain_at(c, c.x0 + x as i32, dy);
                        if DEPTH == 32 {
                            let (er, eg, eb) = e;
                            let k = grain_weight(c, if GREY { er } else { luma(er, eg, eb) });
                            let (dr, dg, db) = add_grain::<GREY>(c, (0.0, 0.0, 0.0), gr, gg, gb, k);
                            let through = |v: f32, e: f32, d: f32| if v < 1.0 { lerp_tab(odec, e + d) } else { v + d * slope1 };
                            (r, g, b) = (through(r, er, dr), through(g, eg, dg), through(b, eb, db));
                        } else {
                            let k = grain_weight(c, if GREY { r } else { luma(r, g, b) });
                            (r, g, b) = add_grain::<GREY>(c, (r, g, b), gr, gg, gb, k);
                        }
                    }
                    store::<GREY>(p, r, g, b);
                }
                p = p.add(CH);
            }
        }
        row = unsafe { row.add(c.stride) };
    }
}

// ----------------------------------------------------------------------------- the filter

/// # Safety
/// The host passes `buf..buf+len` and `params..params+params_len` from `pc_alloc`.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn pc_filter(buf: *mut f32, len: u32, width: u32, height: u32, channels: u32, format: u32, params: *const u8, params_len: u32) -> i32 {
    let (w, h, n) = (width as usize, height as usize, channels as usize);
    if n == 0 || w == 0 || h == 0 || (len as usize) < w * h * n * 4 {
        return ERR_ARGS;
    }
    let alpha = format & HAS_ALPHA != 0;
    let colour = if alpha { n - 1 } else { n };
    let mode = (format >> 16) & 0xff;
    let depth = format & 0xff;
    let grey = colour == 1;
    if !(grey || (colour == 3 && mode == 3)) {
        return ERR_MODE;
    }
    // SAFETY: see the function's contract.
    let json = unsafe { core::slice::from_raw_parts(params, params_len as usize) };
    let g = |k: &str, d: f32| json_num(json, k).unwrap_or(d);
    let size = g("grainSize", 1.0).max(0.25);
    let seed = g("seed", 1.0) as u32;
    let mix = |s: u32| -> u32 {
        let mut h = s.wrapping_mul(0x9e37_79b9) ^ 0x85eb_ca6b;
        h ^= h >> 13;
        h = h.wrapping_mul(0xc2b2_ae35);
        h ^ (h >> 16)
    };
    // the manifest's default, Portrait 400, when the name is unknown
    let fi = json_str(json, "film").and_then(|v| FILMS.iter().position(|f| f.0.as_bytes() == v)).unwrap_or(1);
    let film = &FILMS[fi];
    let level = match json_str(json, "push") {
        Some(b"Pull 1") => 0,
        Some(b"Push 1") => 2,
        Some(b"Push 2") => 3,
        _ => 1,
    };
    // Grey documents: the grey value is taken as sRGB-encoded whatever the setting.
    let space = if grey { &b"sRGB"[..] } else { json_str(json, "inputSpace").unwrap_or(b"sRGB") };
    let (ident, m_in, m_out) = match space {
        b"Display P3" => (false, P3_IN, P3_OUT),
        b"Adobe RGB" => (false, ADOBE_IN, ADOBE_OUT),
        _ => (true, [0.0; 9], [0.0; 9]),
    };
    let adobe = space == b"Adobe RGB";
    let t = tables();
    let a = ADOBE_BYTES.0.as_ptr() as *const f32;
    // Strength mixes the film's colour and tonality with the original's, both alike
    let strength = clamp01(g("strength", 100.0) / 100.0);
    let (color, tone) = (strength, strength);
    // SAFETY: offsets inside the static tables
    let dec = unsafe { if adobe { a } else { t.add(ODEC) } };
    let enc = unsafe { if adobe && depth != 32 { a.add(TN + 1) } else { t.add(ENC) } };
    // The band comes with the manifest's overlap on every side (the host repeats edge pixels at
    // the document's border); the halation stage reads all of it, the film writes the inner area.
    let ov = (g("overlap", OVERLAP as f32) as usize).min(w / 2).min(h / 2);
    if json_str(json, "halation") == Some(b"On") {
        let glow = Glow { amount: g("halationAmount", 40.0), radius: g("halationRadius", 14.0), threshold: g("halationThreshold", 55.0) };
        // SAFETY: `buf` holds w × h × n samples (checked above); dec and enc are TN + 1 floats.
        let rc = unsafe { halation(buf, w, h, n, alpha, grey, depth, ov, dec, enc, &glow) };
        if rc != 0 {
            return rc;
        }
    }
    let (iw, ih) = (w - 2 * ov, h - 2 * ov);
    if iw == 0 || ih == 0 {
        return 0;
    }
    // SAFETY: the inner area's first pixel lies inside the band.
    let buf = unsafe { buf.add((ov * w + ov) * n) };
    let ctx = Ctx {
        lut: film.1[level].0.as_ptr() as *const u16,
        w: iw,
        h: ih,
        x0: g("x", 0.0) as i32 + ov as i32,
        y0: g("y", 0.0) as i32 + ov as i32,
        stride: w * n,
        mono: film.3,
        ident,
        mix: color < 1.0 || tone < 1.0,
        color,
        tone,
        m_in,
        m_out,
        dec,
        enc,
        // spread 0.045 (sRGB-encoded output) in the mid-tones at 100 %, per tile unit (spread 32)
        grain: clamp01(g("grain", 35.0) / 100.0) * film.2 * PUSH_GRAIN[level] * 0.045 / 32.0,
        gscale: 1.0 / size,
        nearest: size > 0.9 && size < 1.1,
        ox: mix(seed) % GT as u32,
        oy: mix(seed ^ 0x5bd1_e995) % GT as u32,
    };
    // 8-bit documents take the cached path (a colour cache in fresh, zeroed pages from memory.grow,
    // key 0 = empty; grain at the native size straight from the tile row, a scaled grain size
    // interpolated); 16- and 32-bit documents go pixel by pixel. The fast path (sRGB, full film
    // colour and tone) is v0.4's; anything else takes the general one.
    let general_path = !ident || ctx.mix;
    let grain = ctx.grain > 0.0;
    if depth == 8 {
        let at = pc_alloc((1u32 << CACHE_BITS) * core::mem::size_of::<Slot>() as u32);
        if at == 0 {
            return ERR_MEMORY;
        }
        let cache = at as *mut Slot;
        let Some(pre) = Pre::new(&ctx) else { return ERR_MEMORY };
        let sc = if grain && !ctx.nearest {
            match Scaled::new(&ctx) {
                Some(s) => Some(s),
                None => return ERR_MEMORY,
            }
        } else {
            None
        };
        macro_rules! go {
            ($ch:literal, $a:literal, $g:literal) => {
                match (if !grain { 0 } else if ctx.nearest { 1 } else { 2 }, general_path) {
                    (1, true) => run8::<$ch, $a, $g, 1, true>(buf, &ctx, cache, &pre, sc.as_ref()),
                    (1, false) => run8::<$ch, $a, $g, 1, false>(buf, &ctx, cache, &pre, sc.as_ref()),
                    (2, true) => run8::<$ch, $a, $g, 2, true>(buf, &ctx, cache, &pre, sc.as_ref()),
                    (2, false) => run8::<$ch, $a, $g, 2, false>(buf, &ctx, cache, &pre, sc.as_ref()),
                    (_, true) => run8::<$ch, $a, $g, 0, true>(buf, &ctx, cache, &pre, sc.as_ref()),
                    (_, false) => run8::<$ch, $a, $g, 0, false>(buf, &ctx, cache, &pre, sc.as_ref()),
                }
            };
        }
        unsafe {
            match (n, alpha, grey) {
                (4, true, false) => go!(4, true, false),
                (3, false, false) => go!(3, false, false),
                (2, true, true) => go!(2, true, true),
                (1, false, true) => go!(1, false, true),
                _ => return ERR_MODE,
            }
        }
        return 0;
    }
    macro_rules! hi {
        ($ch:literal, $a:literal, $g:literal, $d:literal) => {
            if general_path { run_hi::<$ch, $a, $g, $d, true>(buf, &ctx) } else { run_hi::<$ch, $a, $g, $d, false>(buf, &ctx) }
        };
    }
    unsafe {
        match (n, alpha, grey, depth) {
            (4, true, false, 32) => hi!(4, true, false, 32),
            (4, true, false, _) => hi!(4, true, false, 16),
            (3, false, false, 32) => hi!(3, false, false, 32),
            (3, false, false, _) => hi!(3, false, false, 16),
            (2, true, true, 32) => hi!(2, true, true, 32),
            (2, true, true, _) => hi!(2, true, true, 16),
            (1, false, true, 32) => hi!(1, false, true, 32),
            (1, false, true, _) => hi!(1, false, true, 16),
            _ => return ERR_MODE,
        }
    }
    0
}

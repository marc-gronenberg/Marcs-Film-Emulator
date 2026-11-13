//! The halation glow: the red-orange glow colour film gets around bright highlights, when light
//! passes the emulsion, reflects off the film base and re-exposes the red (and a little of the
//! green) layer. The film plug-in's switchable stage before the film.
//!
//! The glow is soft and wide, so it is computed at 1/4 resolution: a highlight map of the whole
//! band (including the overlap, sampling every other pixel), three box blurs (≈ Gaussian), then
//! sampled back bilinearly (rows prepared once). Pixels the glow does not reach are skipped.
//!
//! Profiled (2 MP, 8-bit, default settings, glow reaching nearly every pixel): the per-pixel
//! write-back was two thirds of the time, the blur and the highlight map a sixth each. So the
//! work is specialised per depth and colour mode (`run`), 8-bit documents encode through a table
//! that needs no clamping, and the blur's running sum only tests the edges it has to.

use crate::{ERR_MEMORY, TN, alloc, clamp01, lerp_tab};

const F: usize = 4; // the glow's resolution divisor

/// The glow's settings, as the parameters give them.
pub struct Glow {
    /// 0..100
    pub amount: f32,
    /// full-resolution pixels
    pub radius: f32,
    /// 0..100 (of linear luminance)
    pub threshold: f32,
}

// the glow's colour: red, a little green, almost no blue; its luminance for grey documents
const GLOW_G: f32 = 0.22;
const GLOW_B: f32 = 0.02;
const GLOW_Y: f32 = 0.2126 + 0.7152 * GLOW_G + 0.0722 * GLOW_B;

/// One running-sum box blur pass of half-width `r` (edges repeat), along rows (`stride` 1,
/// `line_step` = row length) or columns (`stride` = row length, `line_step` 1).
///
/// # Safety
/// `src` and `dst` hold `lines × len` values laid out as described.
unsafe fn box_pass(src: *const f32, dst: *mut f32, lines: usize, len: usize, line_step: usize, stride: usize, r: usize) {
    let inv = 1.0 / (2 * r + 1) as f32;
    let last = len - 1;
    for l in 0..lines {
        unsafe {
            let s = src.add(l * line_step);
            let d = dst.add(l * line_step);
            let mut acc = 0.0f32;
            for i in 0..=2 * r {
                let i = if i < r { 0 } else if i - r > last { last } else { i - r };
                acc += *s.add(i * stride);
            }
            for i in 0..len {
                *d.add(i * stride) = acc * inv;
                let next = if i + r < last { *s.add((i + r + 1) * stride) } else { *s.add(last * stride) };
                let prev = if i >= r { *s.add((i - r) * stride) } else { *s };
                acc += next - prev;
            }
        }
    }
}

/// Adds the glow to the inner area (`ov` pixels in from each edge) of a band of `w × h` pixels
/// with `n` channels (`grey`: one colour channel, which gets the glow's luminance). `dec` and
/// `enc` are the document's transfer curve and its inverse as `TN + 1` tables (unused for 32-bit
/// documents, which are linear). Returns 0, or `ERR_MEMORY`.
///
/// # Safety
/// `buf` holds `w × h × n` samples.
pub unsafe fn halation(buf: *mut f32, w: usize, h: usize, n: usize, alpha: bool, grey: bool, depth: u32, ov: usize, dec: *const f32, enc: *const f32, g: &Glow) -> i32 {
    let amount = clamp01(g.amount / 100.0) * 2.2;
    let radius = if g.radius > 0.0 { g.radius } else { 0.0 };
    let thr = clamp01(g.threshold / 100.0);
    let ov = ov.min(w / 2).min(h / 2);
    if amount <= 0.0 || radius <= 0.0 {
        return 0;
    }
    unsafe {
        match (depth, grey) {
            (8, false) => run::<8, false>(buf, w, h, n, alpha, ov, dec, enc, amount, radius, thr),
            (8, true) => run::<8, true>(buf, w, h, n, alpha, ov, dec, enc, amount, radius, thr),
            (32, false) => run::<32, false>(buf, w, h, n, alpha, ov, dec, enc, amount, radius, thr),
            (32, true) => run::<32, true>(buf, w, h, n, alpha, ov, dec, enc, amount, radius, thr),
            (_, false) => run::<16, false>(buf, w, h, n, alpha, ov, dec, enc, amount, radius, thr),
            (_, true) => run::<16, true>(buf, w, h, n, alpha, ov, dec, enc, amount, radius, thr),
        }
    }
}

/// The stage for one pixel layout: `DEPTH` 8 (levels, exact tables), 16 (interpolated tables) or
/// 32 (linear already); `GREY` one colour channel.
///
/// # Safety
/// As `halation`; `amount` is the glow's gain, `thr` the linear threshold.
#[inline(always)]
unsafe fn run<const DEPTH: u32, const GREY: bool>(buf: *mut f32, w: usize, h: usize, n: usize, alpha: bool, ov: usize, dec: *const f32, enc: *const f32, amount: f32, radius: f32, thr: f32) -> i32 {
    // 8-bit documents: decode by level (exact); encode by the nearest table entry, rounded to the
    // 8-bit level it stands for and written as the host writes a level (i / 255): the film rounds
    // to levels anyway, and its colour cache, keyed by the samples' bits, then finds a glowing
    // pixel's colour under the same key as everywhere else. The table covers 0..4 and so needs no
    // clamping (a value is never negative, and never above 1 + the glow's maximum of 2.2)
    const ENC8: usize = 4 * TN + 2;
    let (lin8, enc8) = if DEPTH == 8 {
        let mem = alloc((256 * 4 + ENC8 * 4) as u32) as usize;
        if mem == 0 {
            return ERR_MEMORY;
        }
        let (lin8, enc8) = (mem as *mut f32, (mem + 256 * 4) as *mut f32);
        unsafe {
            for i in 0..256 {
                *lin8.add(i) = lerp_tab(dec, i as f32 / 255.0);
            }
            for i in 0..ENC8 {
                *enc8.add(i) = (*enc.add(i.min(TN)) * 255.0 + 0.5) as u32 as f32 / 255.0;
            }
        }
        (lin8 as *const f32, enc8 as *const f32)
    } else {
        (core::ptr::null(), core::ptr::null())
    };
    let to_lin = |v: f32| -> f32 {
        unsafe {
            if DEPTH == 32 {
                if v > 0.0 { v } else { 0.0 }
            } else if DEPTH == 8 {
                *lin8.add(((v * 255.0 + 0.5) as u32 & 255) as usize)
            } else {
                lerp_tab(dec, v)
            }
        }
    };
    let to_doc = |v: f32| -> f32 {
        unsafe {
            if DEPTH == 32 {
                v
            } else if DEPTH == 8 {
                *enc8.add(((v * TN as f32 + 0.5) as usize).min(ENC8 - 1))
            } else {
                lerp_tab(enc, v)
            }
        }
    };

    // Highlight map at 1/F resolution over the whole band (margins included).
    let (lw, lh) = (w.div_ceil(F), h.div_ceil(F));
    let area = lw * lh;
    let mem = alloc((area * 4 * 2) as u32) as usize;
    if mem == 0 {
        return ERR_MEMORY;
    }
    let (a, b) = (mem as *mut f32, (mem + area * 4) as *mut f32); // zeroed by memory.grow
    // the threshold on the encoded luminance, so most pixels are rejected before any decoding
    let thr_doc = if DEPTH == 32 { thr } else { unsafe { lerp_tab(enc, thr) } } * 0.98;
    unsafe {
        // Every other pixel in each direction (4 samples per 4x4 cell); luminance taken from the
        // encoded values and decoded once (close enough for a glow source).
        for y in (0..h).step_by(2) {
            let row = a.add((y / F) * lw);
            let mut p = (buf as *const f32).add(y * w * n);
            for x in (0..w).step_by(2) {
                if !(alpha && *p.add(n - 1) <= 0.0) {
                    let le = if GREY { *p } else { 0.2126 * *p + 0.7152 * *p.add(1) + 0.0722 * *p.add(2) };
                    if le > thr_doc {
                        let e = (if DEPTH == 32 { le } else { lerp_tab(dec, le) }) - thr;
                        if e > 0.0 {
                            *row.add(x / F) += e;
                        }
                    }
                }
                p = p.add(2 * n);
            }
        }
        let inv_cell = 4.0 / (F * F) as f32;
        for i in 0..area {
            *a.add(i) *= inv_cell;
        }
        // Gaussian of sigma = radius / 2 (full-res px); its reach (3 r low-res) stays in the overlap.
        let sigma = radius * 0.5 / F as f32;
        let r_max = (ov / F / 3).max(1);
        let r = ((sigma * 1.732 + 0.5) as usize).clamp(1, r_max);
        for _ in 0..3 {
            box_pass(a, b, lh, lw, lw, 1, r);
            box_pass(b, a, lw, lh, 1, lw, r);
        }
    }

    // Sampling the low-res glow back: per column its cell and fraction (once per band), per row
    // the two cell rows blended vertically into `vrow` (once per row), so a pixel is one lerp.
    let cols = alloc((w * 8 + (lw + 1) * 4) as u32) as usize;
    if cols == 0 {
        return ERR_MEMORY;
    }
    let (cix, ctx_, vrow) = (cols as *mut u32, (cols + w * 4) as *mut f32, (cols + w * 8) as *mut f32);
    for x in 0..w {
        let fx = (x as f32 + 0.5) / F as f32 - 0.5;
        let fx = if fx < 0.0 { 0.0 } else { fx };
        let ix = (fx as usize).min(lw - 1);
        unsafe {
            *cix.add(x) = ix as u32;
            *ctx_.add(x) = if ix + 1 < lw { fx - ix as f32 } else { 0.0 };
        }
    }
    let eps = 2e-4 / amount;
    for y in ov..h - ov {
        let fy = (y as f32 + 0.5) / F as f32 - 0.5;
        let fy = if fy < 0.0 { 0.0 } else { fy };
        let iy = (fy as usize).min(lh - 1);
        let jy = (iy + 1).min(lh - 1);
        let ty = fy - iy as f32;
        let mut any = false;
        unsafe {
            for i in 0..lw {
                let (p, q) = (*a.add(iy * lw + i), *a.add(jy * lw + i));
                let v = p + (q - p) * ty;
                *vrow.add(i) = v;
                any |= v >= eps;
            }
            *vrow.add(lw) = *vrow.add(lw - 1);
        }
        if !any {
            continue; // nothing glows on this row
        }
        let mut p = unsafe { buf.add((y * w + ov) * n) };
        for x in ov..w - ov {
            unsafe {
                let ix = *cix.add(x) as usize;
                let (g0, g1) = (*vrow.add(ix), *vrow.add(ix + 1));
                if (g0 >= eps || g1 >= eps) && !(alpha && *p.add(n - 1) <= 0.0) {
                    let hv = (g0 + (g1 - g0) * *ctx_.add(x)) * amount;
                    if GREY {
                        *p = to_doc(to_lin(*p) + hv * GLOW_Y);
                    } else {
                        *p = to_doc(to_lin(*p) + hv);
                        *p.add(1) = to_doc(to_lin(*p.add(1)) + hv * GLOW_G);
                        *p.add(2) = to_doc(to_lin(*p.add(2)) + hv * GLOW_B);
                    }
                }
                p = p.add(n);
            }
        }
    }
    0
}

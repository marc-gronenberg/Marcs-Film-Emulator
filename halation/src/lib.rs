//! Marcs Film Emulator – Halation as a plug-in of its own (PhotoCraft plug-in ABI v1): the same glow the
//! film plug-in has as a switchable stage (`common/src/halation.rs`), for stacking it separately.
//!
//! Use it *before* the film look (below "Marcs Film Emulator" in the smart filter list), so the glow
//! goes through the film's colour and tone like the rest of the light. Takes the document as sRGB
//! (the film plug-in's own stage knows the input space).
//!
//! `no_std`, no imports, no allocator.
#![no_std]

use emulsion_common::halation::{Glow, halation};
use emulsion_common::{Aligned, ERR_ARGS, ERR_MODE, HAS_ALPHA, TN, json_num};

#[panic_handler]
fn panic(_: &core::panic::PanicInfo) -> ! {
    core::arch::wasm32::unreachable()
}

const MANIFEST: &str = r#"{
  "id": "io.emulsion.halation",
  "name": "Marcs Film Emulator – Halation…",
  "version": "0.4.2",
  "kind": "filter",
  "author": "Marc Gronenberg",
  "description": "Red-orange glow around bright highlights, as on colour film. Apply before the film look (or use the Halation switch in Marcs Film Emulator). RGB and Grayscale.",
  "params": {
    "amount":    {"type": "number", "min": 0, "max": 100, "default": 40},
    "radius":    {"type": "number", "min": 2, "max": 36, "default": 14, "unit": "px"},
    "threshold": {"type": "number", "min": 0, "max": 100, "default": 55}
  },
  "overlap": 96,
  "area": "content"
}"#;

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

/// `odec[TN+1] | enc[TN+1]`: sRGB -> linear and back (see `model/make_tables.py`).
static TABLE_BYTES: &Aligned<[u8; 2 * (TN + 1) * 4]> = &Aligned(*include_bytes!("../../lut/srgb.bin"));

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
    let grey = colour == 1;
    if !(grey || (colour == 3 && (format >> 16) & 0xff == 3)) {
        return ERR_MODE;
    }
    // SAFETY: see the function's contract.
    let json = unsafe { core::slice::from_raw_parts(params, params_len as usize) };
    let g = |k: &str, d: f32| json_num(json, k).unwrap_or(d);
    let glow = Glow { amount: g("amount", 40.0), radius: g("radius", 14.0), threshold: g("threshold", 55.0) };
    let ov = g("overlap", OVERLAP as f32) as usize;
    let tables = TABLE_BYTES.0.as_ptr() as *const f32;
    // SAFETY: `buf` holds w × h × n samples (checked above); the tables are TN + 1 floats each.
    unsafe { halation(buf, w, h, n, alpha, grey, format & 0xff, ov, tables, tables.add(TN + 1), &glow) }
}

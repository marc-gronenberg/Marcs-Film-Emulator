//! Test host for PhotoCraft filter plug-ins, mirroring PhotoCraft's `crates/plugins` host:
//! wasmi 2.0 with fuel metering and strict limits, no imports, a fresh instance per band,
//! tile-row bands (256 px) as wide as fit in 4 MiB, the manifest's overlap with edge pixels
//! repeated, `_image` geometry in the params, fuel = 50 M + 4,000 per sample, 60 s wall clock.
//!
//! harness <plugin.wasm> <in.png|jpg> <out.png> [params-json] [depth 8|16|32] [--grey] [--threads N]
use std::time::{Duration, Instant};

use wasmi::{Config, EnforcedLimits, Engine, Linker, Module, Store, StoreLimits, StoreLimitsBuilder, TypedFunc};

const TILE: i32 = 256;
const FUEL_BASE: u64 = 50_000_000;
const FUEL_PER_SAMPLE: u64 = 4_000;
const MAX_MEM: usize = 512 << 20;
const BAND_BYTES: usize = 4 << 20;

struct Host {
    engine: Engine,
    module: Module,
}

impl Host {
    /// Compiles the plug-in with PhotoCraft's engine settings; panics if it imports anything.
    fn load(bytes: &[u8]) -> Host {
        let mut cfg = Config::default();
        cfg.consume_fuel(true).enforced_limits(EnforcedLimits::strict()).set_max_recursion_depth(1024);
        let engine = Engine::new(&cfg);
        let module = Module::new(&engine, bytes).expect("module");
        if let Some(i) = module.imports().next() {
            panic!("module imports {}.{} (not allowed)", i.module(), i.name());
        }
        Host { engine, module }
    }

    fn store(&self) -> (Store<StoreLimits>, wasmi::Instance, wasmi::Memory) {
        let limits = StoreLimitsBuilder::new().memory_size(MAX_MEM).memories(1).tables(4).table_elements(100_000).instances(1).build();
        let mut store = Store::new(&self.engine, limits);
        store.limiter(|l| l);
        store.set_fuel(20_000_000).unwrap();
        let inst = Linker::<StoreLimits>::new(&self.engine).instantiate_and_start(&mut store, &self.module).expect("instantiate");
        let mem = inst.get_memory(&store, "memory").expect("memory export");
        (store, inst, mem)
    }

    /// Returns fuel used.
    fn filter(&self, data: &mut [f32], w: u32, h: u32, ch: u32, fmt: u32, params: &[u8]) -> Result<u64, String> {
        let (mut store, inst, mem) = self.store();
        let alloc: TypedFunc<i32, i32> = inst.get_typed_func(&store, "pc_alloc").map_err(|e| e.to_string())?;
        type Args = (i32, i32, i32, i32, i32, i32, i32, i32);
        let filter: TypedFunc<Args, i32> = inst.get_typed_func(&store, "pc_filter").map_err(|e| e.to_string())?;
        store.set_fuel(FUEL_BASE).unwrap();
        let bytes = data.len() * 4;
        let ptr = alloc.call(&mut store, bytes as i32).map_err(|e| e.to_string())? as usize;
        let pptr = alloc.call(&mut store, params.len().max(1) as i32).map_err(|e| e.to_string())? as usize;
        if ptr == 0 || pptr == 0 {
            return Err("pc_alloc returned 0".into());
        }
        {
            let m = mem.data_mut(&mut store);
            for (d, v) in m[ptr..ptr + bytes].chunks_exact_mut(4).zip(data.iter()) {
                d.copy_from_slice(&v.to_le_bytes());
            }
            m[pptr..pptr + params.len()].copy_from_slice(params);
        }
        let budget = FUEL_BASE + data.len() as u64 * FUEL_PER_SAMPLE;
        store.set_fuel(budget).unwrap();
        let rc = filter
            .call(&mut store, (ptr as i32, bytes as i32, w as i32, h as i32, ch as i32, fmt as i32, pptr as i32, params.len() as i32))
            .map_err(|e| format!("trap: {e}"))?;
        if rc != 0 {
            return Err(format!("pc_filter returned error code {rc}"));
        }
        let used = budget - store.get_fuel().unwrap();
        let m = mem.data(&store);
        for (v, s) in data.iter_mut().zip(m[ptr..ptr + bytes].chunks_exact(4)) {
            *v = f32::from_le_bytes([s[0], s[1], s[2], s[3]]);
        }
        Ok(used)
    }
}

fn main() {
    let a: Vec<String> = std::env::args().collect();
    let threads: usize = a.iter().position(|s| s == "--threads").and_then(|i| a.get(i + 1)).and_then(|s| s.parse().ok()).unwrap_or(2);
    let grey = a.iter().any(|s| s == "--grey");
    let depth: u32 = a.get(5).and_then(|s| s.parse().ok()).unwrap_or(8);
    let user: serde_json::Value = serde_json::from_str(a.get(4).map(String::as_str).unwrap_or("{}")).expect("params json");

    let bytes = std::fs::read(&a[1]).expect("wasm");
    let t = Instant::now();
    let host = Host::load(&bytes);
    let (mut store, inst, mem) = host.store();
    let ver: TypedFunc<(), i32> = inst.get_typed_func(&store, "pc_abi_version").unwrap();
    assert_eq!(ver.call(&mut store, ()).unwrap(), 1, "abi version");
    let man: TypedFunc<(), i64> = inst.get_typed_func(&store, "pc_manifest").unwrap();
    let packed = man.call(&mut store, ()).unwrap() as u64;
    let (mp, ml) = ((packed & 0xffff_ffff) as usize, (packed >> 32) as usize);
    let manifest: serde_json::Value = serde_json::from_slice(&mem.data(&store)[mp..mp + ml]).expect("manifest json");
    println!("loaded {:?} v{} ({} bytes, {:?})", manifest["name"].as_str().unwrap(), manifest["version"].as_str().unwrap(), bytes.len(), t.elapsed());
    let ov = manifest["overlap"].as_i64().unwrap_or(0) as i32;

    // Resolve params like Manifest::resolve_params: defaults, clamp numbers, round ints.
    let mut params = serde_json::Map::new();
    for (k, spec) in manifest["params"].as_object().unwrap() {
        let v = user.get(k).cloned().unwrap_or_else(|| spec["default"].clone());
        let v = match spec["type"].as_str().unwrap() {
            "number" => serde_json::json!(v.as_f64().unwrap().clamp(spec["min"].as_f64().unwrap(), spec["max"].as_f64().unwrap())),
            "int" => serde_json::json!((v.as_f64().unwrap().round() as i64).clamp(spec["min"].as_i64().unwrap(), spec["max"].as_i64().unwrap())),
            _ => v,
        };
        params.insert(k.clone(), v);
    }
    println!("params {}", serde_json::Value::Object(params.clone()));

    // Image -> f32 surface (sRGB for 8/16-bit, linear for 32-bit), RGBA or GA.
    let img = image::open(&a[2]).expect("image").to_rgba32f();
    let (w, h) = (img.width() as i32, img.height() as i32);
    let n: usize = if grey { 2 } else { 4 };
    let lin = |v: f32| if v <= 0.04045 { v / 12.92 } else { ((v + 0.055) / 1.055).powf(2.4) };
    let q = |v: f32| match depth {
        8 => (v * 255.0).round() / 255.0,
        16 => (v * 65535.0).round() / 65535.0,
        _ => lin(v),
    };
    let mut surf = Vec::with_capacity((w * h) as usize * n);
    for p in img.pixels() {
        let [r, g, b, al] = p.0;
        if grey {
            surf.extend_from_slice(&[q(0.2126 * r + 0.7152 * g + 0.0722 * b), al]);
        } else {
            surf.extend_from_slice(&[q(r), q(g), q(b), al]);
        }
    }
    let fmt = depth | (1 << 8) | ((if grey { 1 } else { 3 }) << 16);

    // Bands: one tile row tall, as many tiles across as fit in BAND_BYTES.
    let tile_bytes = (TILE * TILE) as usize * n * 4;
    let across = (BAND_BYTES.min(MAX_MEM / 2) / tile_bytes).clamp(1, 1024) as i32;
    let mut bands = vec![];
    let mut ty = 0;
    while ty < h {
        let mut tx = 0;
        while tx < w {
            bands.push((tx, ty, (tx + across * TILE).min(w), (ty + TILE).min(h)));
            tx += across * TILE;
        }
        ty += TILE;
    }
    let deadline = Instant::now() + Duration::from_secs(60);
    let t = Instant::now();
    let surf_ref = &surf;
    let params_ref = &params;
    let host_ref = &host;
    let results: Vec<(usize, Vec<f32>, u64)> = std::thread::scope(|s| {
        let mut hs = vec![];
        for tid in 0..threads {
            let bands = &bands;
            hs.push(s.spawn(move || {
                let mut out = vec![];
                for (bi, &(x0, y0, x1, y1)) in bands.iter().enumerate().filter(|(i, _)| i % threads == tid) {
                    assert!(Instant::now() < deadline, "time budget exceeded");
                    let (ix0, iy0, ix1, iy1) = (x0 - ov, y0 - ov, x1 + ov, y1 + ov);
                    let (iw, ih) = ((ix1 - ix0) as usize, (iy1 - iy0) as usize);
                    let mut data = Vec::with_capacity(iw * ih * n);
                    for y in iy0..iy1 {
                        let sy = y.clamp(0, h - 1);
                        for x in ix0..ix1 {
                            let sx = x.clamp(0, w - 1);
                            let i = (sy * w + sx) as usize * n;
                            data.extend_from_slice(&surf_ref[i..i + n]);
                        }
                    }
                    let mut p = params_ref.clone();
                    p.insert(
                        "_image".into(),
                        serde_json::json!({"x": ix0, "y": iy0, "width": iw, "height": ih, "overlap": ov,
                            "canvasWidth": w, "canvasHeight": h, "mode": if grey {"grayscale"} else {"rgb"},
                            "depth": depth, "alpha": true, "channels": n}),
                    );
                    let pb = serde_json::to_vec(&serde_json::Value::Object(p)).unwrap();
                    let used = host_ref.filter(&mut data, iw as u32, ih as u32, n as u32, fmt, &pb).unwrap_or_else(|e| panic!("band {bi}: {e}"));
                    out.push((bi, data, used / (iw * ih * n) as u64));
                }
                out
            }));
        }
        hs.into_iter().flat_map(|h| h.join().unwrap()).collect()
    });
    let dt = t.elapsed();
    let max_fuel = results.iter().map(|r| r.2).max().unwrap_or(0);
    let avg_fuel = results.iter().map(|r| r.2).sum::<u64>() as f64 / results.len().max(1) as f64;
    println!(
        "{w}x{h} ({:.1} MP), {} bands, {threads} threads: {:?}  (~{:.1} s per 24 MP on {threads} cores); fuel/sample avg {avg_fuel:.0} max {max_fuel} of {FUEL_PER_SAMPLE}",
        (w * h) as f64 / 1e6,
        bands.len(),
        dt,
        dt.as_secs_f64() * 24e6 / (w * h) as f64
    );

    // Write back the inner rectangles, clamp like the host, save as 8-bit sRGB PNG.
    let mut res = surf.clone();
    for (bi, data, _) in results {
        let (x0, y0, x1, y1) = bands[bi];
        let iw = (x1 - x0 + 2 * ov) as usize;
        for y in y0..y1 {
            for x in x0..x1 {
                let si = ((y - y0 + ov) as usize * iw + (x - x0 + ov) as usize) * n;
                let di = (y * w + x) as usize * n;
                for c in 0..n {
                    let mut v = data[si + c];
                    if !v.is_finite() {
                        v = surf[di + c];
                    }
                    if depth != 32 {
                        v = v.clamp(0.0, 1.0);
                    }
                    res[di + c] = v;
                }
            }
        }
    }
    let enc = |v: f32| if v <= 0.0031308 { v * 12.92 } else { 1.055 * v.max(0.0).powf(1.0 / 2.4) - 0.055 };
    let c8 = |v: f32| ((if depth == 32 { enc(v) } else { v }).clamp(0.0, 1.0) * 255.0 + 0.5) as u8;
    let mut o = image::RgbaImage::new(w as u32, h as u32);
    for (i, p) in o.pixels_mut().enumerate() {
        let s = &res[i * n..i * n + n];
        p.0 = if grey { [c8(s[0]), c8(s[0]), c8(s[0]), 255] } else { [c8(s[0]), c8(s[1]), c8(s[2]), 255] };
    }
    o.save(&a[3]).expect("save");
}

/// Checks on the shipped plug-ins (`dist/`), run by `build.sh`: `cd harness && cargo test --release`.
#[cfg(test)]
mod tests {
    use super::*;

    const W: usize = 256;
    const H: usize = 4;
    const RGBA: u32 = (1 << 8) | (3 << 16);
    // The ramp tests run the film without overlap (`_image.overlap` 0), so every pixel counts.

    fn host(name: &str) -> Host {
        let path = concat!(env!("CARGO_MANIFEST_DIR"), "/../dist/");
        Host::load(&std::fs::read(format!("{path}{name}")).expect("plug-in in dist/ (run build.sh first)"))
    }

    /// A grey ramp, one level per column, `top` at the right edge; RGBA, opaque.
    fn ramp(top: f32) -> Vec<f32> {
        let mut v = Vec::with_capacity(W * H * 4);
        for _ in 0..H {
            for x in 0..W {
                let l = x as f32 / (W - 1) as f32 * top;
                v.extend_from_slice(&[l, l, l, 1.0]);
            }
        }
        v
    }

    /// Runs a band of `w × h` RGBA pixels whose outer `ov` pixels are overlap, with the host's
    /// `_image` geometry added to `params` (a JSON object).
    fn run_band(host: &Host, data: &mut [f32], w: usize, h: usize, ov: usize, depth: u32, params: &str) {
        let p = format!(r#"{{"_image":{{"x":0,"y":0,"width":{w},"height":{h},"overlap":{ov}}}{}{}"#, if params.len() > 2 { "," } else { "" }, &params[1..]);
        host.filter(data, w as u32, h as u32, 4, depth | RGBA, p.as_bytes()).expect("filter");
    }

    /// The ramp band, no overlap.
    fn run(host: &Host, data: &mut [f32], depth: u32, params: &str) {
        run_band(host, data, W, H, 0, depth, params);
    }

    /// A band of `w × h` with `ov` overlap: dark grey with a white disc in the middle (a highlight
    /// for the halation to glow around), 8-bit levels.
    fn disc(w: usize, h: usize) -> Vec<f32> {
        let mut v = Vec::with_capacity(w * h * 4);
        for y in 0..h {
            for x in 0..w {
                let (dx, dy) = (x as f32 - w as f32 / 2.0, y as f32 - h as f32 / 2.0);
                let l = if dx * dx + dy * dy < 400.0 { 1.0 } else { 51.0 / 255.0 };
                v.extend_from_slice(&[l, l * 0.9, l * 0.8, 1.0]);
            }
        }
        v.iter().map(|v: &f32| (v * 255.0).round() / 255.0).collect()
    }

    fn inner(data: &[f32], w: usize, h: usize, ov: usize) -> Vec<f32> {
        let mut out = vec![];
        for y in ov..h - ov {
            out.extend_from_slice(&data[(y * w + ov) * 4..(y * w + w - ov) * 4]);
        }
        out
    }

    #[test]
    fn halation_glows_red_around_highlights() {
        let film = host("marcs-film-emulator.wasm");
        let (w, h, ov) = (448, 256, 96);
        for depth in [8, 32] {
            let orig: Vec<f32> = disc(w, h).iter().map(|v| if depth == 32 { v.powf(2.2) } else { *v }).collect();
            let (mut on, mut off) = (orig.clone(), orig.clone());
            run_band(&film, &mut on, w, h, ov, depth, r#"{"halation":"On","grain":0}"#);
            run_band(&film, &mut off, w, h, ov, depth, r#"{"halation":"Off","grain":0}"#);
            let (on, off) = (inner(&on, w, h, ov), inner(&off, w, h, ov));
            let glow = on.iter().zip(&off).filter(|(a, b)| (*a - *b).abs() > 1.0 / 255.0).count();
            assert!(glow > 1000, "{depth}-bit: the glow changed only {glow} samples");
            // the glow is red-orange: red rises more than blue around the disc
            let gain = |k: usize| on.chunks(4).zip(off.chunks(4)).map(|(a, b)| a[k] - b[k]).sum::<f32>();
            assert!(gain(0) > 2.0 * gain(2), "{depth}-bit: red +{} vs blue +{}", gain(0), gain(2));
        }
    }

    fn luma(p: &[f32]) -> f32 {
        0.2126 * p[0] + 0.7152 * p[1] + 0.0722 * p[2]
    }

    #[test]
    fn strength_0_returns_the_original() {
        let film = host("marcs-film-emulator.wasm");
        for depth in [8, 16] {
            let orig = ramp(1.0);
            let mut out = orig.clone();
            run(&film, &mut out, depth, r#"{"strength":0,"grain":0}"#);
            let worst = orig.iter().zip(&out).map(|(a, b)| (a - b).abs() * 255.0).fold(0.0f32, f32::max);
            assert!(worst <= 1.0, "{depth}-bit: original changed by {worst} levels");
        }
    }

    /// The mix once gave a pixel at exactly black the film's full lifted black while level 1 got
    /// the mixed value: a step at the black end of every clipped shadow.
    #[test]
    fn strength_50_has_no_step_at_black() {
        let film = host("marcs-film-emulator.wasm");
        let mut out = ramp(1.0);
        run(&film, &mut out, 8, r#"{"strength":50,"grain":0}"#);
        let row: Vec<f32> = out[..W * 4].chunks(4).map(luma).collect();
        assert!((row[1] - row[0]).abs() * 255.0 <= 1.5, "step at black: level 0 -> {}, level 1 -> {}", row[0] * 255.0, row[1] * 255.0);
        for x in 1..W {
            assert!(row[x] + 0.5 / 255.0 >= row[x - 1], "luminance falls at level {x}: {} -> {}", row[x - 1], row[x]);
        }
    }

    /// Push 2 steepens the mid-tones, pull flattens them; 18 % grey stays about where it was.
    /// Push 1 is at least as steep as normal for the colour films; for the Mono films Kodak's
    /// 1-stop push is the normal development time, so it only moves the scene down the toe.
    #[test]
    fn push_and_pull_change_contrast_in_order() {
        let film = host("marcs-film-emulator.wasm");
        for name in ["Portrait 400", "Mono 400"] {
            let mut contrast = vec![];
            let mut grey = vec![];
            for push in ["Pull 1", "Normal", "Push 1", "Push 2"] {
                let mut out = ramp(1.0);
                run(&film, &mut out, 8, &format!(r#"{{"film":"{name}","push":"{push}","grain":0}}"#));
                let row: Vec<f32> = out[..W * 4].chunks(4).map(luma).collect();
                contrast.push(row[180] - row[70]);
                grey.push(row[118]); // sRGB level of 18 % grey
            }
            assert!(contrast[0] < contrast[1] && contrast[2] >= contrast[1] * 0.98 && contrast[3] > contrast[1] * 1.05, "{name}: mid-tone contrast per level {contrast:?}");
            let spread = (grey.iter().cloned().fold(0.0f32, f32::max) - grey.iter().cloned().fold(1.0f32, f32::min)) * 255.0;
            assert!(spread <= 8.0, "{name}: 18 % grey moves by {spread} levels across the push levels: {grey:?}");
        }
    }

    /// The slide route balances grey and keeps the clear film white; its first version had a blue
    /// cast at grey and cream whites, which nothing caught.
    #[test]
    fn slide_films_are_neutral_at_grey_and_white() {
        let film = host("marcs-film-emulator.wasm");
        for name in ["Chrome 100", "Vivid Chrome 100"] {
            let mut out = ramp(1.0);
            run(&film, &mut out, 8, &format!(r#"{{"film":"{name}","grain":0}}"#));
            let grey = &out[118 * 4..118 * 4 + 3]; // sRGB level of 18 % grey
            let spread = (grey.iter().cloned().fold(0.0f32, f32::max) - grey.iter().cloned().fold(1.0f32, f32::min)) * 255.0;
            assert!(spread <= 1.5, "{name}: grey has a cast of {spread} levels: {grey:?}");
            // diffuse white (sRGB 255, +2.5 stops) is not the clear film (+5 stops): a slide
            // renders it around 0.9, and the film's own cast may remain there (Velvia: 6 levels);
            // the first, unbalanced version had 27 levels
            let white = &out[(W - 1) * 4..(W - 1) * 4 + 3];
            let spread = (white.iter().cloned().fold(0.0f32, f32::max) - white.iter().cloned().fold(1.0f32, f32::min)) * 255.0;
            assert!(white.iter().all(|v| *v * 255.0 > 215.0) && spread <= 8.0, "{name}: white is {white:?} (cast {spread} levels)");
        }
    }

    #[test]
    fn faded_out_film_keeps_32_bit_highlights_above_one() {
        let film = host("marcs-film-emulator.wasm");
        let orig = ramp(2.0);
        let mut out = orig.clone();
        run(&film, &mut out, 32, r#"{"strength":0,"grain":0}"#);
        let worst = orig.iter().zip(&out).map(|(a, b)| (a - b).abs()).fold(0.0f32, f32::max);
        assert!(worst <= 1e-3, "32-bit original changed by {worst} (linear)");
        assert!(out[(W - 1) * 4] > 1.9, "white above 1.0 was clipped to {}", out[(W - 1) * 4]);
    }

    #[test]
    fn every_film_and_push_runs_at_every_depth() {
        let film = host("marcs-film-emulator.wasm");
        for name in ["Portrait 160", "Portrait 400", "Portrait 800", "Everyday 200", "Street 400", "Vivid 100", "Soft 400", "Snapshot 400", "Cine 50D", "Cine 200T", "Cine 250D", "Cine 500T", "Tungsten 800", "Chrome 100", "Vivid Chrome 100", "Mono 100", "Mono 125", "Mono 400", "Mono 400 T", "Mono 3200"] {
            for push in ["Pull 1", "Normal", "Push 1", "Push 2"] {
                for depth in [8, 16, 32] {
                    let mut out = ramp(1.0);
                    run(&film, &mut out, depth, &format!(r#"{{"film":"{name}","push":"{push}","grainSize":1.7}}"#));
                    assert!(out.iter().all(|v| v.is_finite()), "{name} {push} {depth}-bit: non-finite output");
                    assert!(luma(&out[(W - 1) * 4..]) > luma(&out[W * 2..]), "{name} {push} {depth}-bit: white not brighter than mid-grey");
                }
            }
        }
    }

    /// 8-bit documents go through a per-band colour cache (direct-mapped, keyed by the samples'
    /// bits), 16-bit documents take every pixel through the LUT. The same colours must come out
    /// the same either way: here with more distinct colours than the cache has slots (so slots
    /// get replaced), every colour a second time later in the band (hits and replaced slots), and
    /// black first (a zeroed slot must not pass for it).
    #[test]
    fn cached_colours_match_the_uncached_path() {
        let film = host("marcs-film-emulator.wasm");
        let (w, h) = (512, 256);
        let mut s = 0x2545_f491u32;
        let mut level = || {
            s ^= s << 13;
            s ^= s >> 17;
            s ^= s << 5;
            (s >> 8 & 255) as f32 / 255.0
        };
        let mut half: Vec<[f32; 4]> = vec![[0.0, 0.0, 0.0, 1.0], [1.0, 1.0, 1.0, 1.0]];
        while half.len() < w * h / 2 {
            half.push([level(), level(), level(), 1.0]);
        }
        let orig: Vec<f32> = half.iter().chain(half.iter().rev()).flatten().copied().collect();
        for params in [r#"{"grain":0}"#, r#"{"strength":60,"grain":0}"#, r#"{"film":"Mono 400","inputSpace":"Display P3","grain":0}"#] {
            let (mut cached, mut direct) = (orig.clone(), orig.clone());
            run_band(&film, &mut cached, w, h, 0, 8, params);
            run_band(&film, &mut direct, w, h, 0, 16, params);
            let worst = cached.iter().zip(&direct).map(|(a, b)| (a - b).abs() * 255.0).fold(0.0f32, f32::max);
            assert!(worst <= 0.25, "{params}: 8-bit (cached) and 16-bit differ by {worst} levels");
            let n = w * h;
            let mirrored = (0..n / 2).all(|i| cached[i * 4..i * 4 + 4] == cached[(n - 1 - i) * 4..(n - i) * 4]);
            assert!(mirrored, "{params}: a colour came out differently the second time");
        }
    }

    #[test]
    fn halation_leaves_an_image_without_highlights_alone() {
        let film = host("marcs-film-emulator.wasm");
        let (mut on, mut off) = (ramp(0.5), ramp(0.5));
        run(&film, &mut on, 8, r#"{"halation":"On","grain":0}"#);
        run(&film, &mut off, 8, r#"{"halation":"Off","grain":0}"#);
        assert_eq!(on, off);
    }
}

"""Exports a film look as standard .cube 3D LUTs (sRGB in, sRGB out), the same look the plug-in
ships (film_model_v2, without grain).

Every grid point is run through the full spectral film model (not resampled from the plug-in's
LUT). Works in Photoshop (Color Lookup), Premiere/After Effects (Lumetri), DaVinci Resolve,
Final Cut Pro, Capture One and anything else that reads .cube.

Run:  python3 export_cube.py [film ...]   -> ../cube/MarcsFilmEmulator_<Film>_33.cube and _65.cube
      (default: portra400)
"""

import os
import sys

import numpy as np

import film_model_v2 as m

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "cube")
def bake_srgb(film, size, chunk=12000):
    v = np.linspace(0.0, 1.0, size)
    # .cube order: red changes fastest, then green, then blue
    bb, gg, rr = np.meshgrid(v, v, v, indexing="ij")
    rgb = np.stack([rr.ravel(), gg.ravel(), bb.ravel()], axis=1)
    lin = m.srgb_decode(rgb)
    out = np.empty_like(lin)
    for i in range(0, len(lin), chunk):
        out[i : i + chunk] = film.simulate(lin[i : i + chunk])
        print(f"\r  {size}^3: {min(i + chunk, len(lin)) / len(lin) * 100:5.1f} %", end="", file=sys.stderr)
    print(file=sys.stderr)
    return m.srgb_encode(out)


def write_cube(path, title, size, data):
    with open(path, "w", newline="\n") as f:
        f.write(f'TITLE "Marcs Film Emulator {title}"\n')
        f.write("# Spectral film look simulated from the manufacturer's datasheet (Marcs Film Emulator, film_model_v2).\n")
        f.write("# Input and output: sRGB / Rec.709 display-referred, 0..1. No grain or halation.\n")
        f.write(f"LUT_3D_SIZE {size}\n")
        f.write("DOMAIN_MIN 0.0 0.0 0.0\nDOMAIN_MAX 1.0 1.0 1.0\n")
        for r, g, b in np.clip(data, 0.0, 1.0):
            f.write(f"{r:.6f} {g:.6f} {b:.6f}\n")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for key in sys.argv[1:] or ["portra400"]:
        film = m.make_film(key)
        name = m.FILMS[key]["label"].replace(" ", "")
        for size in (33, 65):
            data = bake_srgb(film, size)
            path = os.path.join(OUT, f"MarcsFilmEmulator_{name}_{size}.cube")
            write_cube(path, name, size, data)
            print("wrote", path, os.path.getsize(path), "bytes")

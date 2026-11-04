"""Static data for the plug-ins (so no instance has to compute it per band):

  lut/tables.bin    little-endian f32 (the film plug-in):
                      u8base[256]   shaper coordinate of each 8-bit sRGB level (exposure 0)
                      odec[4097]    sRGB -> linear (v = i/4096)
                      enc[4097]     linear -> sRGB (v = i/4096)
                      log2m[257]    log2(1 + i/256), for log2 from a float's exponent and mantissa
                      u16base[65536] shaper coordinate of each 16-bit sRGB level (exposure 0)
  lut/srgb.bin      little-endian f32: odec[4097] | enc[4097] (the halation plug-in)
  lut/adobe.bin     little-endian f32: adec[4097] (Adobe RGB (1998) -> linear, v = i/4096),
                    aenc[4097] (linear -> Adobe RGB); gamma 563/256
  lut/grain1024.bin 1024 x 1024 x 3 signed bytes: tileable colour-negative grain (unit spread
                    = 32), a shared part plus a smaller per-layer part, slightly clumped.

Run:  python3 make_tables.py
"""

import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "lut")
STOPS_LO, STOPS_HI = -8.0, 5.0  # must match film_model_v2.py and the plug-in
GRAIN_SCALE = 32.0


def srgb_decode(v):
    return np.where(v <= 0.04045, v / 12.92, ((v + 0.055) / 1.055) ** 2.4)


def srgb_encode(v):
    v = np.clip(v, 0, 1)
    return np.where(v <= 0.0031308, v * 12.92, 1.055 * v ** (1 / 2.4) - 0.055)


def shaper(lin):
    return (np.log2(np.maximum(lin, 1e-12) / 0.18) - STOPS_LO) / (STOPS_HI - STOPS_LO)


def tables():
    v8 = np.arange(256) / 255.0
    v = np.arange(4097) / 4096.0
    srgb = [srgb_decode(v), srgb_encode(v)]
    np.concatenate(srgb).astype("<f4").tofile(os.path.join(OUT, "srgb.bin"))
    parts = [shaper(srgb_decode(v8))] + srgb + [np.log2(1 + np.arange(257) / 256), shaper(srgb_decode(np.arange(65536) / 65535.0))]
    data = np.concatenate(parts).astype("<f4")
    path = os.path.join(OUT, "tables.bin")
    data.tofile(path)
    return path, data.size


def adobe():
    v = np.arange(4097) / 4096.0
    g = 563.0 / 256.0
    data = np.concatenate([v**g, v ** (1 / g)]).astype("<f4")
    path = os.path.join(OUT, "adobe.bin")
    data.tofile(path)
    return path


def grain():
    rng = np.random.default_rng(400)
    n = 1024
    mono = rng.standard_normal((n, n))
    chans = rng.standard_normal((3, n, n))
    g = np.stack([0.82 * mono + 0.42 * c for c in chans])
    # slight clumping: cyclic Gaussian blur (sigma 0.55 px) via FFT, keeps the tile seamless
    f = np.fft.fftfreq(n)
    kx, ky = np.meshgrid(f, f)
    kern = np.exp(-2 * (np.pi**2) * (0.55**2) * (kx**2 + ky**2))
    g = np.real(np.fft.ifft2(np.fft.fft2(g, axes=(1, 2)) * kern, axes=(1, 2)))
    g /= g.std()
    q = np.clip(np.round(g * GRAIN_SCALE), -127, 127).astype(np.int8)
    path = os.path.join(OUT, "grain1024.bin")
    np.ascontiguousarray(q.transpose(1, 2, 0)).tofile(path)  # [y][x][rgb]
    return path


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    p, n = tables()
    print("wrote", p, n, "floats")
    print("wrote", adobe())
    print("wrote", grain())

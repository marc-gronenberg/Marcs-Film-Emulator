"""Film looks from measured datasheet data (data/films/*.json, see data/tools/film_data.py).

Per film:

  scene linear sRGB
    -> smooth, non-negative scene spectrum (sigmoid-polynomial reflectance x the film's design
       illuminant: daylight films 5500 K, tungsten films 3200 K)
    -> exposure of the three layers through their MEASURED spectral sensitivities
    -> layer dye amounts from the MEASURED characteristic curves (status densities converted to
       dye amounts with the status densitometer and the dye spectra), plus a mild interlayer
       (DIR) term that leaves neutrals unchanged
    -> negative density spectrum = sum of MEASURED (or fitted, see film_data.py) dye spectra
       + MEASURED minimum density
  then one of four outputs:
    "scan":  status M densities of the negative, inverted per channel along the grey axis onto a
             lab-scan tone curve (how most people see Portra or Gold today)
    "print": printed onto KODAK VISION 2383 (MEASURED sensitivities, characteristic curves and
             dyes) with a 3200 K enlarger lamp, projected with a xenon-like source, seen with the
             CIE 1931 observer (the cinema-print look)
    "slide": reversal film: the MEASURED (descending) characteristic curves give the dye amounts
             of the positive directly, its density spectrum is projected with a 5000 K source and
             seen with the CIE 1931 observer; white at the film's minimum density
    "mono":  black-and-white: one panchromatic layer (MEASURED sensitivity and characteristic
             curve), scanned like the colour negatives, output grey

Not measured (model assumptions, stated): the spectral upsampling, the DIR strength, the scan tone
curve, the enlarger and projector spectra, and how much of the film's hue shift is kept.

Run:  python3 film_model_v2.py [--preview]   -> ../lut/<film>.lut and previews
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np
from scipy.optimize import brentq, least_squares

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data", "films")
OUT = os.path.join(HERE, "..", "lut")

FILMS = {
    # name: menu label (as in the plug-in's dropdown), negative json, route, interlayer strength,
    # hue kept, grey brightness (sRGB), scan contrast and saturation. Grain is set in the plug-in
    # (plugin/src/lib.rs, FILMS), not here.
    # `scene_k` lights the scene with another colour temperature than the film is balanced for.
    "portra400": dict(label="Portrait 400", neg="portra400", route="scan", dir=0.18, hue_keep=0.75, grey=0.48, contrast=0.85, sat=1.05),
    "gold200": dict(label="Everyday 200", neg="gold200", route="scan", dir=0.12, hue_keep=0.85, grey=0.48, contrast=1.0, sat=1.25),
    "vision500t": dict(label="Cine 500T", neg="vision500t", route="print", dir=0.2, hue_keep=0.85, grey=0.45, contrast=1.0),
    "portra800": dict(label="Portrait 800", neg="portra800", route="scan", dir=0.18, hue_keep=0.75, grey=0.48, contrast=0.9, sat=1.12),
    "ultramax400": dict(label="Street 400", neg="ultramax400", route="scan", dir=0.12, hue_keep=0.85, grey=0.48, contrast=1.0, sat=1.22),
    "ektar100": dict(label="Vivid 100", neg="ektar100", route="scan", dir=0.22, hue_keep=0.85, grey=0.47, contrast=1.08, sat=1.3),
    "vision250d": dict(label="Cine 250D", neg="vision250d", route="print", dir=0.2, hue_keep=0.85, grey=0.45, contrast=1.0),
    # black-and-white: one panchromatic layer, scanned like a negative, output grey
    "trix400": dict(label="Mono 400", neg="trix400", route="mono", grey=0.47, contrast=1.12),
    "tmax100": dict(label="Mono 100", neg="tmax100", route="mono", grey=0.47, contrast=1.0),
    # ---- v0.8: look parameters set by analogy to the films above, to be judged on previews
    "portra160": dict(label="Portrait 160", neg="portra160", route="scan", dir=0.18, hue_keep=0.75, grey=0.48, contrast=0.85, sat=1.0),
    "vision200t": dict(label="Cine 200T", neg="vision200t", route="print", dir=0.2, hue_keep=0.85, grey=0.45, contrast=1.0),
    "vision50d": dict(label="Cine 50D", neg="vision50d", route="print", dir=0.2, hue_keep=0.85, grey=0.45, contrast=1.0),
    # VISION3 500T without its anti-halation layer (the CineStill way): shot in daylight with no
    # filter, developed C-41 and scanned with grey balance; the plug-in's halation gives the glow
    "tungsten800": dict(label="Tungsten 800", neg="vision500t", route="scan", scene_k=5500, dir=0.2, hue_keep=0.85, grey=0.47, contrast=1.0, sat=1.15),
    "pro400h": dict(label="Soft 400", neg="pro400h", route="scan", dir=0.15, hue_keep=0.8, grey=0.5, contrast=0.85, sat=1.05),
    "superia400": dict(label="Snapshot 400", neg="superia400", route="scan", dir=0.12, hue_keep=0.85, grey=0.48, contrast=1.02, sat=1.18),
    # reversal (slide) films: the film is the picture; `grey` is the density of 18 % grey on it
    "ektachrome100": dict(label="Chrome 100", neg="ektachrome100", route="slide", dir=0.15, hue_keep=0.85, grey_density=0.95),
    "velvia100": dict(label="Vivid Chrome 100", neg="velvia100", route="slide", dir=0.25, hue_keep=0.9, grey_density=1.12),
    "tmax400": dict(label="Mono 400 T", neg="tmax400", route="mono", grey=0.47, contrast=1.05),
    "tmaxp3200": dict(label="Mono 3200", neg="tmaxp3200", route="mono", grey=0.47, contrast=1.15),
    "fp4plus": dict(label="Mono 125", neg="fp4plus", route="mono", grey=0.47, contrast=1.0),
}

TINT = {"portra400": [1.02, 1.0, 0.965], "gold200": [1.05, 1.0, 0.89], "vision500t": [0.985, 1.0, 1.015],
        "portra800": [1.03, 1.0, 0.955], "ultramax400": [1.04, 1.0, 0.91], "ektar100": [1.0, 1.0, 0.985],
        "vision250d": [1.03, 1.0, 0.965],
        "portra160": [1.015, 1.0, 0.975], "vision200t": [1.0, 1.0, 0.995], "vision50d": [1.02, 1.0, 0.975],
        "tungsten800": [1.0, 1.0, 1.0], "pro400h": [0.99, 1.0, 0.98], "superia400": [0.995, 1.0, 0.99],
        "ektachrome100": [1.0, 1.0, 1.0], "velvia100": [1.0, 1.0, 1.0]}


def load(name):
    with open(os.path.join(DATA, f"{name}.json")) as f:
        d = json.load(f)
    for k, v in d.items():
        if isinstance(v, list):
            d[k] = np.array(v, dtype=float)
    return d


PRINT = load("print2383")
LAM = PRINT["lam"]
DL = float(LAM[1] - LAM[0])


# ----------------------------------------------------------------------------- colour basics


def g2(lam, mu, s1, s2):
    s = np.where(lam < mu, s1, s2)
    return np.exp(-0.5 * ((lam - mu) / s) ** 2)


def planck(lam_nm, t):
    lam = lam_nm * 1e-9
    h, c, k = 6.62607015e-34, 2.99792458e8, 1.380649e-23
    return 1.0 / (lam**5 * (np.exp(h * c / (lam * k * t)) - 1.0))


# CIE 1931 2-degree observer, multi-lobe analytic fit (Wyman, Sloan & Shirley 2013)
XBAR = 1.056 * g2(LAM, 599.8, 37.9, 31.0) + 0.362 * g2(LAM, 442.0, 16.0, 26.7) - 0.065 * g2(LAM, 501.1, 20.4, 26.2)
YBAR = 0.821 * g2(LAM, 568.8, 46.9, 40.5) + 0.286 * g2(LAM, 530.9, 16.3, 31.1)
ZBAR = 1.217 * g2(LAM, 437.0, 11.8, 36.0) + 0.681 * g2(LAM, 459.0, 26.0, 13.8)
CMF = np.stack([XBAR, YBAR, ZBAR])

SRGB_TO_XYZ = np.array([[0.4124564, 0.3575761, 0.1804375], [0.2126729, 0.7151522, 0.0721750], [0.0193339, 0.1191920, 0.9503041]])
XYZ_TO_SRGB = np.linalg.inv(SRGB_TO_XYZ)
D65_WHITE = SRGB_TO_XYZ @ np.ones(3)
BRADFORD = np.array([[0.8951, 0.2664, -0.1614], [-0.7502, 1.7135, 0.0367], [0.0389, -0.0685, 1.0296]])


def bradford(src_white, dst_white):
    s, d = BRADFORD @ src_white, BRADFORD @ dst_white
    return np.linalg.inv(BRADFORD) @ np.diag(d / s) @ BRADFORD


def white_of(spd):
    return (CMF * spd).sum(axis=1) * DL


# ANSI status densitometer responsivities (data/films/status.json, from python-colormath, BSD)
def _status(name):
    with open(os.path.join(DATA, "status.json")) as f:
        ds = json.load(f)
    src = np.asarray(ds["lam"], float)
    out = []
    for ch in ("BLUE", "GREEN", "RED"):
        v = np.interp(LAM, src, np.asarray(ds[name][ch], float), left=0, right=0)
        out.append(v / v.sum())
    return np.stack(out)  # B, G, R


STATUS_M = _status("M")
STATUS_A = _status("A")


def status_density(dens_spectra, resp):
    """Status densities (N x 3, B G R) of density spectra (N x L)."""
    t = 10.0 ** (-dens_spectra)
    return -np.log10(np.maximum(t @ resp.T, 1e-12))


# ----------------------------------------------------------------------------- spectral upsampling


T_NORM = (LAM - LAM[0]) / (LAM[-1] - LAM[0])
T_POW = np.stack([np.ones_like(T_NORM), T_NORM, T_NORM**2])


def _sig(z):
    return 0.5 + 0.5 * z / np.sqrt(1.0 + z * z)


def _dsig(z):
    return 0.5 / (1.0 + z * z) ** 1.5


class Upsampler:
    """Smooth reflectance (sigmoid of a quadratic) x illuminant, matched exactly to each colour."""

    def __init__(self, illum_k):
        il = planck(LAM, illum_k)
        self.illum = il / ((CMF[1] * il).sum() * DL)
        self.cmf_w = (CMF * self.illum).T * DL
        self.rgb_to_xyz = bradford(D65_WHITE, white_of(self.illum)) @ SRGB_TO_XYZ

    def fit(self, rgb01, iters=200):
        n = rgb01.shape[0]
        target = rgb01 @ self.rgb_to_xyz.T
        c = np.zeros((n, 3))
        lam = np.full(n, 1e-3)

        def err(cc):
            z = cc @ T_POW
            return _sig(z) @ self.cmf_w - target, z

        e, z = err(c)
        cost = (e * e).sum(1)
        for _ in range(iters):
            ds = _dsig(z)
            jac = np.einsum("nl,il,lk->nki", ds, T_POW, self.cmf_w)
            jtj = np.einsum("nki,nkj->nij", jac, jac)
            jte = np.einsum("nki,nk->ni", jac, e)
            a = jtj + lam[:, None, None] * (np.einsum("nii->ni", jtj)[:, :, None] * np.eye(3)[None] + 1e-9 * np.eye(3)[None])
            step = np.linalg.solve(a, -jte[:, :, None])[:, :, 0]
            en, zn = err(c + step)
            cn = (en * en).sum(1)
            ok = cn < cost
            c[ok] += step[ok]
            e[ok], z[ok], cost[ok] = en[ok], zn[ok], cn[ok]
            lam = np.clip(np.where(ok, lam * 0.3, lam * 8.0), 1e-9, 1e9)
            if cost.max() < 1e-14:
                break
        return c

    # Reflectance level the brightest channel is fitted at. Well below 1, so near-neutral colours
    # get near-flat spectra: at 0.98 (v0.4) a colour whose largest channel was green needed a
    # reflectance bump that fell to zero at the ends of the spectrum, which a film sensitive there
    # (blue/UV of the black-and-white films) saw as a jump just off the grey axis.
    LEVEL = 0.7

    def spectra(self, rgb_lin):
        rgb = np.maximum(rgb_lin, 0.0)
        m = np.maximum(rgb.max(1, keepdims=True), 1e-12)
        c = self.fit(np.clip(rgb / m, 0, 1) * self.LEVEL)
        return (m / self.LEVEL) * _sig(c @ T_POW) * self.illum[None, :]


# ----------------------------------------------------------------------------- film stock


def extend_curve(x, d, lo=-12.0, hi=12.0, shoulder=1.2, reversal=False):
    """Characteristic curves beyond the plotted range: flat below (toe), the last slope continued
    above and rolled off over `shoulder` log units (film keeps going, then saturates). Reversal
    curves descend: flat at maximum density below, the minimum density continued above."""
    xs = np.arange(lo, hi + 1e-9, 0.01)
    out = []
    x = np.asarray(x, float)
    for row in d:
        row = np.asarray(row, float)
        y = np.interp(xs, x, row)
        if not reversal:
            slope = (row[-1] - row[-6]) / (x[-1] - x[-6])
            above = xs > x[-1]
            t = xs[above] - x[-1]
            y[above] = row[-1] + max(slope, 0) * shoulder * (1 - np.exp(-t / shoulder))
        out.append(y)
    return xs, np.stack(out)


# ----------------------------------------------------------------------------- push and pull

# The push levels the plug-in offers: stops of underexposure the lab makes up for in development
# (negative: overexposure and shorter development).
PUSH_LEVELS = (-1, 0, 1, 2)


def _gamma(x, y):
    """Mid-scale contrast of a characteristic curve: density per log exposure between 0.5 and 1.5
    above its base."""
    base = y.min()
    m = (y > base + 0.5) & (y < base + 1.5)
    return np.polyfit(x[m], y[m], 1)[0]


def _colour_push_gain():
    """Development gain per push level for the colour films without their own push curves, from
    the one that has them (Portra 800, C-41: EI 1600 and EI 3200 curves): the ratio of pushed to
    normal mid-scale contrast, averaged over the three layers. Pull 1 is taken as the inverse of
    push 1 (the same change of development time the other way)."""
    d = load("portra800")
    x, normal = d["char_logh"], d["char_density"]
    g0 = np.array([_gamma(x, row) for row in normal])
    gain = {0: 1.0}
    for k, rows in d["char_push"].items():
        gain[int(k)] = float(np.mean([_gamma(x, np.asarray(row)) / g for row, g in zip(rows, g0)]))
    gain[-1] = 1.0 / gain[1]
    return gain


COLOUR_PUSH_GAIN = _colour_push_gain()


def _mono_push_gain():
    """The same for black-and-white films without their own development curves, from Tri-X: the
    contrast at the development time each push level uses, relative to normal."""
    d = load("trix400")
    x = np.asarray(d["char_logh"])
    g0 = _gamma(x, np.asarray(d["char_density"][0]))
    return {p: _gamma(x, dev_curves(d, p)[0]) / g0 for p in PUSH_LEVELS}


def dev_curves(d, push):
    """The negative's characteristic curves (3 x X, or 1 x X for b/w) for a push level.

    Measured where the datasheet publishes them: Portra 800's push 1 and 2 curves; for the
    black-and-white films the curve at the development time the datasheet's tables give for that
    push, interpolated in time between the plotted times. For the other films the normal curves
    with the density above base scaled by a gain measured on a film that has the curves
    (`COLOUR_PUSH_GAIN` from Portra 800, `MONO_PUSH_GAIN` from Tri-X): a model assumption."""
    normal = np.asarray(d["char_density"], float)
    if push == 0:
        return normal
    if d.get("char_dev"):  # other development times plotted (an empty dict means none)
        curves = {float(k): np.asarray(v, float) for k, v in d["char_dev"].items()}
        curves[float(d["dev_for_push"]["0"])] = normal[0]
        times = sorted(curves)
        want = float(d["dev_for_push"][str(push)])
        # between two plotted times: interpolated; beyond the longest (P3200's EI 6400 and 12 500
        # times): the density above base continued at the rate of the last two plotted times
        if want > times[-1]:
            lo, hi = times[-2], times[-1]
        else:
            want = max(want, times[0])
            hi = next(t for t in times if t >= want)
            lo = max(t for t in times if t <= want)
        w = 0.0 if hi == lo else (want - lo) / (hi - lo)
        return ((1 - w) * curves[lo] + w * curves[hi])[None, :]
    if "char_push" in d and str(push) in d["char_push"]:
        return np.asarray(d["char_push"][str(push)], float)
    gain = (MONO_PUSH_GAIN if d.get("type") == "bw" else COLOUR_PUSH_GAIN)[push]
    if d.get("type") == "slide":
        # reversal: more first development clears more silver, the positive gets thinner and
        # contrastier; scaled about the film's maximum density
        top = normal.max(axis=1, keepdims=True)
        return top - (top - normal) * gain
    base = normal.min(axis=1, keepdims=True)
    return base + (normal - base) * gain


MONO_PUSH_GAIN = _mono_push_gain()


class Stock:
    """A negative or print stock: layer sensitivities, dye spectra and dye-amount curves."""

    def __init__(self, d, status, dmin=None, dens=None):
        self.sens = 10.0 ** d["sens_log"]  # 3 x L (B, G, R layers -> Y, M, C dyes)
        self.dyes = d["dyes"]  # 3 x L (Y, M, C)
        self.dmin = d["dmin"] if dmin is None else dmin
        reversal = d.get("type") == "slide"
        x, dens = extend_curve(d["char_logh"], d["char_density"] if dens is None else dens, reversal=reversal)
        # status density of one unit of each dye (columns) in each channel (rows) -> amounts
        m = np.stack([status_density(self.dyes[j][None, :], status)[0] for j in range(3)], axis=1)
        base = dens.min(axis=1, keepdims=True)
        amounts = np.linalg.solve(m, dens - base)  # 3 x X, dye amounts along the neutral series
        self.x, self.amounts = x, np.maximum(amounts, 0.0)
        self.logh_ref = d.get("logh_ref", 0.0)

    def amount(self, j, logh):
        return np.interp(logh, self.x, self.amounts[j])

    def density(self, logh3):
        """Density spectra (N x L) for layer log exposures (N x 3)."""
        a = np.stack([self.amount(j, logh3[:, j]) for j in range(3)], axis=1)
        return a @ self.dyes + self.dmin[None, :]


class Film:
    def __init__(self, key, push=0):
        cfg = FILMS[key]
        self.key, self.cfg, self.push = key, cfg, push
        d = load(cfg["neg"])
        slide = cfg["route"] == "slide"
        self.neg = Stock(d, STATUS_A if slide else STATUS_M, dens=dev_curves(d, push))
        self.up = Upsampler(cfg.get("scene_k", d["illuminant_k"]))
        self.e_grey = (self.up.spectra(np.full((1, 3), 0.18)) @ self.neg.sens.T)[0] * DL
        if slide:
            # projected with a 5000 K source (the dyes are published for 5000 K viewing), seen
            # adapted to it; the exposure is set so 18 % grey lands at `grey_density` (visual)
            proj = planck(LAM, 5000.0)
            self.proj = proj / ((CMF[1] * proj).sum() * DL)
            self.adapt = bradford(white_of(self.proj), D65_WHITE)
            self._fit_slide_exposure()
        if cfg["route"] == "print":
            self.prt = Stock(PRINT, STATUS_A, dmin=np.full_like(LAM, 0.0))
            lamp = planck(LAM, 3200.0) * (1.0 / (1.0 + np.exp((LAM - 700.0) / 12.0)))  # + heat-absorbing glass
            self.lamp = lamp / lamp.max()
            proj = planck(LAM, 5500.0)
            self.proj = proj / ((CMF[1] * proj).sum() * DL)
            self.adapt = bradford(white_of(self.proj), D65_WHITE)
            self.gain = np.zeros(3)
            self._fit_print_filtration()
        if cfg["route"] == "scan":
            m = np.stack([status_density(self.neg.dyes[j][None, :], STATUS_M)[0] for j in range(3)], axis=1)
            self.unmix = np.linalg.inv(m) * np.diag(m)[:, None]  # keep each channel's own scale
            self.scan_base = status_density(self.neg.dmin[None, :], STATUS_M)[0]
        self.nx = self.ny = None
        self._fit_neutral()

    # negative --------------------------------------------------------------
    def logh(self, rgb_lin):
        spec = self.up.spectra(rgb_lin)
        e = np.maximum((spec @ self.neg.sens.T) * DL, self.e_grey * 1e-6)
        # pushed: underexposed by that many stops (the lab's development makes up for it)
        x = self.neg.logh_ref + np.log10(e / self.e_grey) - self.push * 0.30103
        # interlayer (DIR) effect: each layer pushed away from the other two, neutrals unchanged
        k = self.cfg["dir"]
        if k:
            mean_other = (x.sum(1, keepdims=True) - x) / 2.0
            x = x + k * np.tanh(x - mean_other)
        return x

    def negative(self, rgb_lin):
        return self.neg.density(self.logh(rgb_lin))

    # outputs ---------------------------------------------------------------
    def _print_raw(self, neg_dens, gain=None):
        g = self.gain if gain is None else gain
        t = 10.0 ** (-neg_dens)
        h = np.log10(np.maximum((t * self.lamp) @ self.prt.sens.T * DL, 1e-20)) + g
        pd = self.prt.density(h)
        xyz = (10.0 ** (-pd) * self.proj) @ CMF.T * DL
        return np.maximum(xyz @ self.adapt.T @ XYZ_TO_SRGB.T, 0.0), pd

    def _fit_print_filtration(self):
        """Enlarger filtration (a log gain per layer) so 18 % grey prints at the aim densities."""
        neg = self.negative(np.full((1, 3), 0.18))
        aim = np.array([1.03, 1.06, 1.09])  # status A B, G, R: a Kodak LAD-like print aim for 18 % grey
        t = 10.0 ** (-neg)
        h0 = np.log10((t * self.lamp) @ self.prt.sens.T * DL)[0]
        # start: the log exposure at which each layer's own curve reaches the aim
        start = []
        for j in range(3):
            d = status_density(self.prt.density(np.repeat(self.prt.x[:, None], 3, 1)), STATUS_A)[:, j]
            start.append(np.interp(aim[j], d, self.prt.x) - h0[j])
        g = np.array(start)
        for _ in range(60):  # damped Newton on the 3 x 3 system
            _, pd = self._print_raw(neg, g)
            r = status_density(pd, STATUS_A)[0] - aim
            if np.abs(r).max() < 1e-6:
                break
            jac = np.zeros((3, 3))
            for j in range(3):
                gg = g.copy()
                gg[j] += 1e-4
                jac[:, j] = (status_density(self._print_raw(neg, gg)[1], STATUS_A)[0] - aim - r) / 1e-4
            g = g - 0.7 * np.linalg.solve(jac, r)
        self.gain = g

    def _fit_slide_exposure(self):
        """Moves the film's log exposure reference so that 18 % grey comes out at the configured
        visual density (a lab's or photographer's exposure choice; the ISO point is not a grey)."""
        want = self.cfg["grey_density"]
        self.neg.logh_ref = 0.0
        grey = np.full((1, 3), 0.18)

        def visual(ref):
            self.neg.logh_ref = ref
            t = 10.0 ** (-self.negative(grey))
            return -np.log10(max(float(((t * self.proj) @ CMF[1] * DL)[0]), 1e-9))

        self.neg.logh_ref = brentq(lambda r: visual(r) - want, -6.0, 6.0)

    def _slide_raw(self, dens):
        xyz = (10.0 ** (-dens) * self.proj) @ CMF.T * DL
        return np.maximum(xyz @ self.adapt.T @ XYZ_TO_SRGB.T, 0.0)

    def raw(self, rgb_lin):
        """Per-channel raw output, monotonic in exposure along the grey axis."""
        neg = self.negative(rgb_lin)
        if self.cfg["route"] == "print":
            return self._print_raw(neg)[0]
        if self.cfg["route"] == "slide":
            return self._slide_raw(neg)
        d = status_density(neg, STATUS_M)  # B, G, R
        # lab scanners unmix the dyes' overlap (colour masking): status densities -> dye amounts,
        # blended by the scan's masking strength
        a = (d - self.scan_base) @ self.unmix.T
        u = self.cfg.get("unmix", 0.8)
        d = (1 - u) * (d - self.scan_base) + u * a
        return d[:, ::-1]  # R, G, B: a denser negative is a brighter scene

    # tone and balance --------------------------------------------------------
    def scan_curve(self, eq, eq_base):
        """Lab-scan tone curve over equivalent stops (0 = 18 % grey): a power curve (display
        contrast) with a soft shoulder reaching `top` at diffuse white, and the film base (the
        unexposed negative) as black, as a scanner operator sets it."""
        black, top = 0.004, 0.86  # top: output (linear) at diffuse white, +2.47 stops
        g = float(srgb_decode(np.array(self.cfg["grey"])))
        gamma = 1.0 * self.cfg["contrast"]

        def shape(x, n):
            t = g * 2.0 ** (gamma * x)
            return t / (1.0 + t**n) ** (1.0 / n)

        def y(x, n):
            y0, yb = shape(0.0, n), shape(eq_base, n)
            return black + (g - black) * (shape(x, n) - yb) / (y0 - yb)

        n = brentq(lambda n: y(np.log2(1 / 0.18), n) - top, 0.3, 40.0)
        return y(eq, n)

    def _fit_neutral(self):
        """Per-channel curves along the grey axis: a lab scan (inverting the negative) or the
        print's own curve, levelled; then the look's tint, fading towards the highlights."""
        stops = np.linspace(-16.0, 10.0, 1300)
        greys = np.repeat((0.18 * 2.0**stops)[:, None], 3, axis=1)
        raw = self.raw(greys)
        if self.cfg["route"] == "scan":
            d = status_density(self.negative(greys[[np.argmin(abs(stops + 1))], :].repeat(1, 0)), STATUS_M)
            d2 = status_density(self.negative(greys[[np.argmin(abs(stops - 1))], :]), STATUS_M)
            self.mean_slope = float(np.mean(d2 - d) / 2.0)
        tint = np.array(TINT[self.key])
        w = np.clip(1.0 - stops / 4.0, 0.35, 1.0)
        if self.cfg["route"] == "slide":
            # grey-balanced like a scanned slide: white is the clear film in every channel, and a
            # per-channel gamma pulls each channel's 18 % grey to the three channels' mean (the
            # film's cast stays between those points)
            grey_rel = np.array([np.interp(0.0, stops, raw[:, c]) / raw[-1, c] for c in range(3)])
            balance = np.log(np.exp(np.log(grey_rel).mean())) / np.log(grey_rel)
        self.nx, self.ny = [], []
        for c in range(3):
            r = np.maximum.accumulate(raw[:, c])
            if self.cfg["route"] == "scan":
                # equivalent stops from the channel's own density: linear on the straight line,
                # compressed in the film's toe (where the negative stops recording shadows)
                # each channel levelled to its own grey, scaled by the film's mean contrast against a
                # reference negative (gamma 0.6), so a contrastier film scans contrastier
                r0 = np.interp(0.0, stops, r)
                slope = (np.interp(1.0, stops, r) - np.interp(-1.0, stops, r)) / 2.0
                eq = (r - r0) / slope * (self.mean_slope / (0.6 * 0.30103))
                lev = self.scan_curve(eq, eq[0])
                lev = np.where(lev > 0.93, 1.0 - 0.07 * np.exp(-(lev - 0.93) / 0.07), lev)
            elif self.cfg["route"] == "slide":
                # the projected slide: white is the film's minimum density (the clear film), seen
                # dark-surround -> dim-surround (power 0.82); the slide's own black stays
                white = r[-1]
                rel = np.clip(r / white, 0, None) ** (0.82 * balance[c])
                lev = np.where(rel > 0.94, 1.0 - 0.06 * np.exp(-(rel - 0.94) / 0.06), rel)
            else:
                # the projected print, white at diffuse white, dark-surround -> dim-surround
                # compensation (power 0.82), blacks lifted to the display's
                white = np.interp(np.log2(1 / 0.18), stops, r)
                rel = np.clip(r / white, 0, None) ** 0.82
                lev = 0.0055 + (0.94 - 0.0055) * rel
                lev = np.where(lev > 0.94, 1.0 - 0.06 * np.exp(-(lev - 0.94) / 0.06), lev)
            self.nx.append(r + np.arange(len(stops)) * 1e-10)
            self.ny.append(np.clip(lev * tint[c] ** w, 0, 1))

    def neutralise(self, raw):
        out = np.empty_like(raw)
        for c in range(3):
            out[:, c] = np.interp(raw[:, c], self.nx[c], self.ny[c])
        return out

    def simulate(self, rgb_lin, chunk=20000):
        out = np.empty((len(rgb_lin), 3))
        for i in range(0, len(rgb_lin), chunk):
            sl = slice(i, i + chunk)
            film = self.neutralise(self.raw(rgb_lin[sl]))
            out[sl] = damp_hue(film, rgb_lin[sl], self.cfg["hue_keep"], self.cfg.get("sat", 1.0))
        return out


class MonoFilm(Film):
    """Black-and-white negative: one panchromatic layer (MEASURED spectral sensitivity and
    characteristic curve, diffuse visual density), scanned like the colour negatives (the film's
    own contrast against a reference gamma of 0.6, base as black), output neutral grey."""

    def __init__(self, key, push=0):
        cfg = FILMS[key]
        self.key, self.cfg, self.push = key, cfg, push
        d = load(cfg["neg"])
        self.sens = 10.0 ** d["sens_log"][0]
        self.x, dens = extend_curve(d["char_logh"], dev_curves(d, push))
        self.dens = dens[0]
        self.logh_ref = d["logh_ref"]
        self.up = Upsampler(cfg.get("scene_k", d["illuminant_k"]))
        self.e_grey = float((self.up.spectra(np.full((1, 3), 0.18)) @ self.sens)[0] * DL)
        stops = np.linspace(-16.0, 10.0, 1300)
        dn = np.maximum.accumulate(self.density(np.repeat((0.18 * 2.0**stops)[:, None], 3, 1)))
        d0 = np.interp(0.0, stops, dn)
        slope = (np.interp(1.0, stops, dn) - np.interp(-1.0, stops, dn)) / 2.0  # density per stop
        eq = (dn - d0) / slope * (slope / (0.6 * 0.30103))
        lev = self.scan_curve(eq, eq[0])
        lev = np.where(lev > 0.93, 1.0 - 0.07 * np.exp(-(lev - 0.93) / 0.07), lev)
        self.nx, self.ny = dn + np.arange(len(stops)) * 1e-10, np.clip(lev, 0, 1)

    def density(self, rgb_lin):
        e = np.maximum((self.up.spectra(rgb_lin) @ self.sens) * DL, self.e_grey * 1e-6)
        x = self.logh_ref + np.log10(e / self.e_grey) - self.push * 0.30103
        return np.interp(x, self.x, self.dens)

    def simulate(self, rgb_lin, chunk=20000):
        out = np.empty((len(rgb_lin), 3))
        for i in range(0, len(rgb_lin), chunk):
            sl = slice(i, i + chunk)
            out[sl] = np.interp(self.density(rgb_lin[sl]), self.nx, self.ny)[:, None]
        return out


def make_film(key, push=0):
    return MonoFilm(key, push) if FILMS[key]["route"] == "mono" else Film(key, push)


# ----------------------------------------------------------------------------- hue

_M1 = np.array([[0.4122214708, 0.5363325363, 0.0514459929], [0.2119034982, 0.6806995451, 0.1073969566], [0.0883024619, 0.2817188376, 0.6299787005]])
_M2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468], [1.9779984951, -2.4285922050, 0.4505937099], [0.0259040371, 0.7827717662, -0.8086757660]])


def oklab(c):
    return np.cbrt(np.maximum(c @ _M1.T, 0.0)) @ _M2.T


def oklab_inv(lab):
    return ((lab @ np.linalg.inv(_M2).T) ** 3) @ np.linalg.inv(_M1).T


def damp_hue(film, src, keep, sat=1.0):
    """Keeps `keep` of the film's hue shift (against the source) and scales chroma by `sat`
    (the scan's saturation setting), smoothly limited so it cannot leave the display gamut much."""
    lf, ls = oklab(film), oklab(np.clip(src, 0, None))
    hf, hs = np.arctan2(lf[:, 2], lf[:, 1]), np.arctan2(ls[:, 2], ls[:, 1])
    dh = (hf - hs + np.pi) % (2 * np.pi) - np.pi
    w = np.clip(np.hypot(ls[:, 1], ls[:, 2]) / 0.06, 0, 1)
    w = w * w * (3 - 2 * w)
    h = hf - (1 - keep) * w * dh
    cf = np.hypot(lf[:, 1], lf[:, 2])
    if sat != 1.0:
        lim = 0.32
        c2 = cf * sat
        cf = np.where(c2 > cf, lim * np.tanh(c2 / lim) * np.maximum(cf, 1e-9) / np.maximum(lim * np.tanh(cf / lim), 1e-9), c2)
    return np.clip(oklab_inv(np.stack([lf[:, 0], cf * np.cos(h), cf * np.sin(h)], 1)), 0, 1)


# ----------------------------------------------------------------------------- LUT

LUT_N = 37
STOPS_LO, STOPS_HI = -8.0, 5.0  # 13 stops on 37 points: the cell size of the old 15 stops on 41


def srgb_decode(v):
    return np.where(v <= 0.04045, v / 12.92, ((v + 0.055) / 1.055) ** 2.4)


def srgb_encode(v):
    v = np.clip(v, 0, 1)
    return np.where(v <= 0.0031308, v * 12.92, 1.055 * v ** (1 / 2.4) - 0.055)


def shaper_inv(u):
    return 0.18 * 2.0 ** (STOPS_LO + u * (STOPS_HI - STOPS_LO))


def bake(film):
    v = shaper_inv(np.linspace(0, 1, LUT_N))
    bb, gg, rr = np.meshgrid(v, v, v, indexing="ij")
    rgb = np.stack([rr.ravel(), gg.ravel(), bb.ravel()], 1)
    return film.simulate(rgb).reshape(LUT_N, LUT_N, LUT_N, 3)


def write_lut(lut, path):
    """u16 little-endian, [b][g][r][rgb], sRGB-encoded."""
    np.round(srgb_encode(lut) * 65535).astype("<u2").tofile(path)


def apply_lut_np(lut, rgb_lin):
    n = lut.shape[0]
    u = (np.log2(np.maximum(rgb_lin, 1e-9) / 0.18) - STOPS_LO) / (STOPS_HI - STOPS_LO)
    p = np.clip(u, 0, 1) * (n - 1)
    i0 = np.clip(np.floor(p).astype(int), 0, n - 2)
    f = p - i0
    r, g, b = i0[..., 0], i0[..., 1], i0[..., 2]
    fr, fg, fb = f[..., 0:1], f[..., 1:2], f[..., 2:3]
    out = 0
    for db in (0, 1):
        for dg in (0, 1):
            for dr in (0, 1):
                w = (fr if dr else 1 - fr) * (fg if dg else 1 - fg) * (fb if db else 1 - fb)
                out = out + w * lut[b + db, g + dg, r + dr]
    return out


def report(film):
    stops = np.arange(-8, 7)
    out = srgb_encode(film.simulate(np.repeat((0.18 * 2.0**stops)[:, None], 3, 1)))
    print(f"{film.key}: grey scale (sRGB)")
    for s, o in zip(stops, out):
        print(f"  {s:+3d}  {o[0]:.3f} {o[1]:.3f} {o[2]:.3f}")


def lut_name(key, push):
    """`<film>.lut` for normal development, `<film>_pull1.lut`, `_push1`, `_push2` otherwise."""
    return key + ("" if push == 0 else f"_pull{-push}" if push < 0 else f"_push{push}") + ".lut"


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    keys = [a for a in sys.argv[1:] if not a.startswith("--")] or list(FILMS)
    levels = [p for p in PUSH_LEVELS if p != 0] if "--push-only" in sys.argv else PUSH_LEVELS
    luts = {}
    for key in keys:
        for push in levels:
            film = make_film(key, push)
            if push == 0:
                report(film)
            lut = bake(film)
            if push == 0:
                luts[key] = lut
            write_lut(lut, os.path.join(OUT, lut_name(key, push)))
            print("wrote", lut_name(key, push), flush=True)
    if "--preview" in sys.argv:
        import imageio.v3 as iio
        import skimage.data as sd
        from skimage.transform import resize

        pv = os.path.join(HERE, "..", "preview")
        os.makedirs(pv, exist_ok=True)
        imgs = [sd.astronaut()[..., :3], sd.coffee()[..., :3], sd.chelsea()[..., :3]]
        extra = os.path.join(HERE, "..", "test")
        for f in ("street.jpg", "portrait.jpg", "landscape.jpg"):
            if os.path.exists(os.path.join(extra, f)):
                imgs.append(iio.imread(os.path.join(extra, f))[..., :3])
        rows = []
        for img in imgs:
            w = 360
            h = int(img.shape[0] * w / img.shape[1])
            small = resize(img / 255.0, (h, w), anti_aliasing=True)
            row = [small] + [srgb_encode(apply_lut_np(luts[k], srgb_decode(small))) for k in keys]
            rows.append(np.concatenate(row, 1))
        iio.imwrite(os.path.join(pv, "films.jpg"), (np.concatenate(rows, 0) * 255 + 0.5).astype(np.uint8), quality=90)
        print("preview written")

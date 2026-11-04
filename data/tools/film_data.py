"""Turns the digitized datasheet curves into film data on a common wavelength grid and saves them
as JSON (../films/*.json), the only film input the model reads.

Per negative film: three layer sensitivities (log), three characteristic curves (status density
over log exposure, B/G/R), dye density spectra (yellow, magenta, cyan) and the minimum density
spectrum. Per print film: the same, with print dyes. Where the datasheet publishes them, also the
curves for other development: Portra 800 pushed 1 and 2 stops ("char_push"), the black-and-white
films at their other development times ("char_dev", minutes -> densities).

Portra 400 and Gold 200 datasheets publish only the midscale-neutral and minimum density spectra,
not the single dyes. Their dyes are taken as the VISION3 dye shapes (Kodak dyes of the same
chemistry family), each shifted and stretched, fitted so that their sum reproduces the film's own
measured (midscale neutral - minimum density) spectrum.
"""

import json
import os
import sys

import numpy as np
from scipy.optimize import least_squares

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, HERE)
from digitize import curves  # noqa: E402
from specs import SPECS  # noqa: E402

LAM = np.arange(360.0, 781.0, 5.0)


def get(name):
    s = SPECS[name]
    return curves(os.path.join(ROOT, "pdf", s["pdf"]), s)


def resample(c, x, fill=None):
    """Curve c (N x 2, any order) at x; outside its range: `fill` or the edge value."""
    c = c[np.argsort(c[:, 0])]
    _, idx = np.unique(c[:, 0], return_index=True)
    c = c[idx]
    y = np.interp(x, c[:, 0], c[:, 1])
    if fill is not None:
        y = np.where((x < c[0, 0]) | (x > c[-1, 0]), fill, y)
    return y


def peak(c):
    return c[np.argmax(c[:, 1]), 0]


def by_peak(cs, n=3):
    """The n longest curves, ordered by the wavelength of their maximum (blue, green, red)."""
    return sorted(cs[:n], key=peak)


def by_level(cs):
    """Characteristic curves ordered B, G, R (B the densest, R the least dense on a negative)."""
    return sorted(cs[:3], key=lambda c: -np.mean(c[:, 1]))


def sens_on_grid(c):
    """Log sensitivity on LAM; outside the measured range it falls off (-6 = effectively zero)."""
    return resample(c, LAM, fill=-6.0)


def warp(shape_lam, shape, shift, stretch, centre):
    x = centre + (LAM - centre - shift) / stretch
    return np.interp(x, shape_lam, shape, left=0.0, right=0.0)


def fit_dyes(neutral, vis_dyes):
    """Fits 3 warped VISION3 dye shapes (amplitude, shift, stretch each) to `neutral` on 400-700."""
    centres = [peak(np.stack([LAM, d], 1)) for d in vis_dyes]
    m = (LAM >= 400) & (LAM <= 700)

    def model(p):
        return [p[3 * j] * warp(LAM, vis_dyes[j], p[3 * j + 1], p[3 * j + 2], centres[j]) for j in range(3)]

    def resid(p):
        return (sum(model(p)) - neutral)[m]

    p0 = [0.8, 0, 1, 0.8, 0, 1, 0.9, 0, 1]
    lo = [0.1, -20, 0.8, 0.1, -20, 0.8, 0.1, -25, 0.8]
    hi = [3.0, 20, 1.25, 3.0, 20, 1.25, 3.0, 25, 1.25]
    r = least_squares(resid, p0, bounds=(lo, hi))
    dyes = model(r.x)
    rms = float(np.sqrt(np.mean(resid(r.x) ** 2)))
    # peak-normalize; the amplitudes come back through the characteristic curves
    return [d / d.max() for d in dyes], r.x, rms


def char_curves(cs):
    b, g, r = by_level(cs)
    x = np.linspace(max(c[:, 0].min() for c in (b, g, r)), min(c[:, 0].max() for c in (b, g, r)), 81)
    return x, np.stack([resample(c, x) for c in (b, g, r)])


def main():
    out = {}
    # ------------------------------------------------------------- VISION3 500T (reference dyes)
    vd = get("vision500t_dye")
    # five curves: midscale neutral (highest), minimum density (dashed, drawn last), 3 dyes
    vd_sorted = sorted(vd, key=lambda c: -c[:, 1].max())
    neutral_v = vd_sorted[0]
    dmin_v = [c for c in vd if c is not neutral_v and abs(c[:, 1].max() - 0.87) < 0.05][0]
    dyes_v = by_peak([c for c in vd if c is not neutral_v and c is not dmin_v])
    vis_dyes = [resample(c, LAM, fill=None) for c in dyes_v]
    vis_dyes = [np.clip(d, 0, None) for d in vis_dyes]

    def negative(name, sens_key, char_key, dye_key, logh_ref, illum_k, dyes=None, dmin=None, note="", push=()):
        s = by_peak(get(sens_key))
        sens = [sens_on_grid(c) for c in s]
        x, d = char_curves(get(char_key))
        entry = {"lam": LAM.tolist(), "sens_log": [v.tolist() for v in sens], "char_logh": x.tolist(),
                 "char_density": d.tolist(), "logh_ref": logh_ref, "illuminant_k": illum_k, "note": note}
        if push:  # the pushed curves (1, 2, ... stops) resampled on the normal curves' grid
            entry["char_push"] = {str(i + 1): np.stack([resample(c, x) for c in by_level(get(k))]).tolist() for i, k in enumerate(push)}
        if dyes is None:
            dd = get(dye_key)
            mid, mn = max(dd, key=lambda c: c[:, 1].mean()), min(dd, key=lambda c: c[:, 1].mean())
            midv, mnv = resample(mid, LAM), resample(mn, LAM)
            dyes, params, rms = fit_dyes(np.clip(midv - mnv, 0, None), vis_dyes)
            dmin = mnv
            entry["dye_fit"] = {"params": [round(float(p), 4) for p in params], "rms": round(rms, 4)}
        entry["dyes"] = [np.clip(v, 0, None).tolist() for v in dyes]
        entry["dmin"] = np.clip(dmin, 0, None).tolist()
        out[name] = entry

    negative("portra400", "portra400_sens", "portra400_char", "portra400_dye", -1.44, 5500,
             note="KODAK PROFESSIONAL PORTRA 400, publication E-4050 (rev. 1-25); daylight, C-41, Status M")
    negative("gold200", "gold200_sens", "gold200_char", "gold200_dye", -1.14, 5500,
             note="KODAK GOLD 200, publication E-7022 (rev. 06-23); daylight, C-41, Status M")
    # VISION3: sensitometry is over camera stops (0 = normal exposure), so logh_ref = 0
    negative("vision500t", "vision500t_sens", "vision500t_char", None, 0.0, 3200,
             dyes=vis_dyes, dmin=resample(dmin_v, LAM),
             note="KODAK VISION3 500T 5219/7219, publication H-1-5219t (rev. 7-15); 3200 K, ECN-2. "
                  "Dye and Dmin curves have D-min subtracted / are peak-normalized")

    negative("ektar100", "ektar100_sens", "ektar100_char", "ektar100_dye", -0.84, 5500,
             note="KODAK PROFESSIONAL EKTAR 100, publication E-4046; daylight, C-41, Status M")
    negative("portra800", "portra800_sens", "portra800_char", "portra800_dye", -1.74, 5500,
             note="KODAK PROFESSIONAL PORTRA 800, publication E-4040; daylight, C-41, Status M, EI 800; "
                  "char_push: EI 1600 (1 stop push) and EI 3200 (2 stop push)",
             push=("portra800_char_push1", "portra800_char_push2"))
    negative("ultramax400", "ultramax400_sens", "ultramax400_char", "ultramax400_dye", -1.44, 5500,
             note="KODAK ULTRAMAX 400, publication E-7023; daylight, C-41, Status M")
    dyes_250 = by_peak(get("vision250d_dye"))
    negative("vision250d", "vision250d_sens", "vision250d_char", None, 0.0, 5500,
             dyes=[np.clip(resample(c, LAM), 0, None) for c in dyes_250],
             dmin=resample(get("vision250d_dmin")[0], LAM),
             note="KODAK VISION3 250D 5207/7207, publication H-1-5207t; 5500 K, ECN-2. "
                  "Dye curves peak-normalized, D-min subtracted")

    # ------------------------------------------------------------- black-and-white: one layer
    def mono(name, sens_key, char_key, logh_ref, note, dev, dev_for_push):
        cs = get(sens_key)
        rows = []
        for c in cs:  # curves for two density levels: same shape, offset; average the shapes
            c = c[np.argsort(c[:, 0])]
            rows.append(resample(np.stack([c[:, 0], c[:, 1] - c[:, 1].max()], 1), LAM, fill=np.nan))
        sens = np.nanmean(np.stack(rows), 0)
        sens = np.where(np.isnan(sens), -6.0, sens)
        c = get(char_key)[0]
        x = np.linspace(c[:, 0].min(), c[:, 0].max(), 81)
        out[name] = {"type": "bw", "lam": LAM.tolist(), "sens_log": [sens.tolist()], "char_logh": x.tolist(),
                     "char_density": [resample(c, x).tolist()], "logh_ref": logh_ref, "illuminant_k": 5500,
                     "note": note,
                     # the same plot's other development times (minutes -> density on the same grid)
                     "char_dev": {str(minutes): resample(get(key)[0], x).tolist() for minutes, key in dev.items()},
                     # the development time (minutes) the model uses per push level, from the
                     # datasheet's processing tables (see the notes at the calls below)
                     "dev_for_push": {str(k): v for k, v in dev_for_push.items()}}

    mono("trix400", "trix400_sens", "trix400_char", -1.44,
         "KODAK PROFESSIONAL TRI-X 400, publication F-4017; T-MAX Developer 7 min 20 C, diffuse visual density; "
         "char_dev: 6, 9, 11 min",
         dev={6: "trix400_char_6", 9: "trix400_char_9", 11: "trix400_char_11"},
         # F-4017: 1-stop push at the normal time; EI 1600 (2-stop push) 8 3/4 min in T-MAX Developer,
         # small tank, 20 C. No pull time is published: pull 1 takes the shortest plotted time, 6 min.
         dev_for_push={-1: 6.0, 0: 7.0, 1: 7.0, 2: 8.75})
    mono("tmax100", "tmax100_sens", "tmax100_char", -0.84,
         "KODAK PROFESSIONAL T-MAX 100, publication F-4016; D-76 7.5 min 20 C, diffuse visual density; "
         "char_dev: 6, 10 min",
         dev={6: "tmax100_char_6", 10: "tmax100_char_10"},
         # F-4016: no time increase for a 1-stop push; 2-stop push takes the plot's longest D-76 time,
         # 10 min (the push table lists other developers). Pull 1: the shortest plotted time, 6 min.
         dev_for_push={-1: 6.0, 0: 7.5, 1: 7.5, 2: 10.0})

    # ------------------------------------------------------------- VISION Color Print Film 2383
    ps = get("print2383_sens")
    main3 = by_peak(sorted(ps, key=lambda c: -len(c))[:3])  # yellow, magenta, cyan layers
    frag = sorted([c for c in ps if len(c) < 50], key=lambda c: -c[:, 1].max())  # blue-region tails
    psens = []
    for j, c in enumerate(main3):
        v = sens_on_grid(c)
        if j == 1 and frag:  # magenta: higher blue tail
            v = np.maximum(v, sens_on_grid(frag[0]))
        if j == 2 and len(frag) > 1:  # cyan: lower blue tail
            v = np.maximum(v, sens_on_grid(frag[1]))
        psens.append(v)
    pd = get("print2383_dye")
    pneutral = max(pd, key=lambda c: c[:, 1].mean())
    pdyes = by_peak([c for c in pd if c is not pneutral])
    pdyes = [np.clip(resample(c, LAM), 0, None) for c in pdyes]
    # print char curves: B is the leftmost (most sensitive), not the densest; order by position
    cs = sorted(get("print2383_char")[:3], key=lambda c: np.interp(2.0, np.sort(c[:, 1]), c[np.argsort(c[:, 1]), 0]))
    x = np.linspace(max(c[:, 0].min() for c in cs), min(c[:, 0].max() for c in cs), 121)
    d = np.stack([resample(c, x) for c in cs])  # B, G, R
    out["print2383"] = {"lam": LAM.tolist(), "sens_log": [v.tolist() for v in psens], "char_logh": x.tolist(),
                        "char_density": d.tolist(), "dyes": [(v / v.max()).tolist() for v in pdyes],
                        "dye_peak": [float(v.max()) for v in pdyes],
                        "note": "KODAK VISION Color Print Film 2383, publication H-1-2383t; ECP-2D, Status A"}

    # ============================================================= v0.8 films
    negative("portra160", "portra160_sens", "portra160_char", "portra160_dye", -1.051, 5500,
             note="KODAK PROFESSIONAL PORTRA 160, publication E-4051 (rev. 1-25); daylight, C-41, Status M")
    for name, k, note in (("vision200t", 3200, "KODAK VISION3 200T 5213/7213, publication H-1-5213t (Spanish edition); 3200 K, ECN-2. "
                                              "Dye curves peak-normalized, D-min subtracted"),
                          ("vision50d", 5500, "KODAK VISION3 50D 5203/7203, publication TI-2657 / H-1-5203t (Spanish edition); 5500 K, "
                                              "ECN-2. Dye curves peak-normalized, D-min subtracted")):
        negative(name, f"{name}_sens", f"{name}_char", None, 0.0, k,
                 dyes=[np.clip(resample(c, LAM), 0, None) for c in by_peak(get(f"{name}_dye"))],
                 dmin=resample(get(f"{name}_dmin")[0], LAM), note=note)
    # Fujifilm: spectral sensitivity is published relative (log), which is all the model uses
    negative("pro400h", "pro400h_sens", "pro400h_char", "pro400h_dye", -1.44, 5500,
             note="FUJICOLOR PRO 400H PROFESSIONAL, bulletin AF3-176E; daylight, C-41, Status M; sensitivity relative")
    negative("superia400", "superia400_sens", "superia400_char", "superia400_dye", -1.44, 5500,
             note="FUJICOLOR SUPERIA X-TRA 400, bulletin AF3-0217E; daylight, CN-16 (C-41), Status M; sensitivity relative")

    # ------------------------------------------------------------- reversal (slide) films
    def reversal(name, note):
        """Sensitivities, the descending characteristic curves (Status A, B/G/R by density) and the
        single dyes (peak-normalized; the base density is not published and taken as clear)."""
        sens = [sens_on_grid(c) for c in by_peak(get(f"{name}_sens"))]
        x, d = char_curves(get(f"{name}_char"))
        dyes = [np.clip(resample(c, LAM), 0, None) for c in by_peak(get(f"{name}_dye"))]
        out[name] = {"type": "slide", "lam": LAM.tolist(), "sens_log": [v.tolist() for v in sens], "char_logh": x.tolist(),
                     "char_density": d.tolist(), "illuminant_k": 5500,  # the exposure is fitted by the model
                     "dyes": [(v / v.max()).tolist() for v in dyes], "dmin": np.zeros_like(LAM).tolist(), "note": note}

    reversal("ektachrome100", "KODAK PROFESSIONAL EKTACHROME E100, publication E-4000 (rev. 8-18); daylight, E-6, Status A")
    reversal("velvia100", "FUJICHROME Velvia 100 Professional, bulletin AF3-202E; daylight, E-6/CR-56, Status A; sensitivity relative")

    # ------------------------------------------------------------- black-and-white, second style
    def mono_times(name, sens_key, char_key, logh_ref, note, times, dev_for_push, tungsten_wedge=False, iso=None):
        """A b/w film whose characteristic-curve plot holds several development times in one spec
        (`times`, ascending; the curves are told apart by density). `tungsten_wedge`: the
        sensitivity is a wedge spectrogram to 2850 K light and is corrected to equal energy.
        `iso`: the exposure axis is relative; it is anchored so that the ISO speed point (0.1
        above base) lies at log H = log10(0.8 / ISO)."""
        rows = []
        for c in get(sens_key):
            c = c[np.argsort(c[:, 0])]
            rows.append(resample(np.stack([c[:, 0], c[:, 1] - c[:, 1].max()], 1), LAM, fill=np.nan))
        sens = np.nanmean(np.stack(rows), 0)
        if tungsten_wedge:
            lam = LAM * 1e-9
            planck = 1.0 / (lam**5 * (np.exp(6.62607015e-34 * 2.99792458e8 / (lam * 1.380649e-23 * 2850.0)) - 1.0))
            sens = sens - np.log10(planck / planck[np.argmin(abs(LAM - 560))])
        sens = np.where(np.isnan(sens), -6.0, sens)
        cs = sorted(get(char_key), key=lambda c: c[:, 1].mean())
        assert len(cs) == len(times), (name, len(cs), times)
        x = np.linspace(max(c[:, 0].min() for c in cs), min(c[:, 0].max() for c in cs), 81)
        curves = {t: resample(c, x) for t, c in zip(times, cs)}
        if iso is not None:  # relative log exposure: anchor at the ISO speed point of the normal curve
            y = curves[dev_for_push[0]] if dev_for_push[0] in curves else list(curves.values())[0]
            x_speed = float(np.interp(y.min() + 0.1, y, x))
            x = x - x_speed + np.log10(0.8 / iso)
        normal_t = dev_for_push[0]
        ts = sorted(curves)
        if normal_t in curves:
            normal = curves[normal_t]
        else:  # the normal time lies between two plotted ones
            lo = max(t for t in ts if t <= normal_t); hi = min(t for t in ts if t >= normal_t)
            w = (normal_t - lo) / (hi - lo)
            normal = (1 - w) * curves[lo] + w * curves[hi]
        out[name] = {"type": "bw", "lam": LAM.tolist(), "sens_log": [sens.tolist()], "char_logh": x.tolist(),
                     "char_density": [normal.tolist()], "logh_ref": logh_ref, "illuminant_k": 5500, "note": note,
                     "char_dev": {str(t): c.tolist() for t, c in curves.items() if t != normal_t},
                     "dev_for_push": {str(k): v for k, v in dev_for_push.items()}}

    mono_times("tmax400", "tmax400_sens", "tmax400_char", -1.44,
               "KODAK PROFESSIONAL T-MAX 400, publication F-4016; D-76 small tank 20 C, diffuse visual density; curves 6, 8, 10, 12 min",
               times=[6, 8, 10, 12],
               # F-4016: 8 min normal in D-76; no time increase for a 1-stop push; 2-stop push about
               # +40 % as for T-MAX Developer (7 -> 10 min), here 11 min; pull 1 the shortest plotted
               dev_for_push={-1: 6.0, 0: 8.0, 1: 8.0, 2: 11.0})
    mono_times("tmaxp3200", "tmaxp3200_sens", "tmaxp3200_char", round(-(np.log10(3200) - 1.162), 3),
               "KODAK PROFESSIONAL T-MAX P3200, publication F-4016; T-MAX Developer small tank 20 C, diffuse visual density; "
               "curves 8, 9, 11, 13 min; normal = EI 3200",
               times=[8, 9, 11, 13],
               # F-4016 small-tank table, 20 C: EI 1600 10.5, EI 3200 12, EI 6400 13.5, EI 12500 15.5 min
               # (the last two beyond the plotted 13 min are taken at 13)
               dev_for_push={-1: 10.5, 0: 12.0, 1: 13.5, 2: 15.5})
    mono_times("fp4plus", "fp4plus_sens", "fp4plus_char", round(-(np.log10(125) - 1.162), 3),
               "ILFORD FP4 PLUS, fact sheet April 2004; ILFOTEC HC 1+31 8 min 20 C; wedge spectrogram to 2850 K corrected to "
               "equal energy; relative log exposure anchored at the ISO 125 speed point",
               times=[8], dev_for_push={-1: 8.0, 0: 8.0, 1: 8.0, 2: 8.0}, tungsten_wedge=True, iso=125)

    os.makedirs(os.path.join(ROOT, "films"), exist_ok=True)
    for k, v in out.items():
        with open(os.path.join(ROOT, "films", f"{k}.json"), "w") as f:
            json.dump(v, f)
        extra = f" dye fit rms {v['dye_fit']['rms']}" if "dye_fit" in v else ""
        print(k, "ok", extra)


if __name__ == "__main__":
    main()

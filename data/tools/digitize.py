"""Digitizes curves from the vector graphics of Kodak datasheet PDFs.

Each graph is described by: page, the plot's rectangle on the page (PDF points), two calibration
points per axis (page coordinate -> data value, linear or log), and which strokes to take (by
colour, width, or a list of drawing indices). Strokes are broken into polylines (Bezier curves
sampled), polylines that touch end to end are joined, and every joined curve is returned in data
units, sorted by x.

Library use: curves(pdf, spec) -> list of (x, y) arrays.
"""

import numpy as np
import pymupdf


def _bez(p0, p1, p2, p3, n=10):
    t = np.linspace(0, 1, n)[:, None]
    p0, p1, p2, p3 = (np.array([p.x, p.y]) for p in (p0, p1, p2, p3))
    return (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t**2 * p2 + t**3 * p3


def _polylines(drawing):
    """Splits a drawing's items into polylines (lists of points), new one at each jump."""
    out, cur = [], []
    for it in drawing["items"]:
        kind = it[0]
        if kind == "l":
            seg = np.array([[it[1].x, it[1].y], [it[2].x, it[2].y]])
        elif kind == "c":
            seg = _bez(it[1], it[2], it[3], it[4])
        else:
            continue
        if cur and np.hypot(*(cur[-1][-1] - seg[0])) > 0.05:
            out.append(np.concatenate(cur))
            cur = []
        cur.append(seg if not cur else seg[1:])
    if cur:
        out.append(np.concatenate(cur))
    return out


def _join(lines, tol=0.6):
    """Joins polylines whose ends touch (reversing where needed)."""
    lines = [l for l in lines if len(l) >= 2]
    changed = True
    while changed:
        changed = False
        for i in range(len(lines)):
            for j in range(len(lines)):
                if i == j:
                    continue
                a, b = lines[i], lines[j]
                for ra in (False, True):
                    for rb in (False, True):
                        aa = a[::-1] if ra else a
                        bb = b[::-1] if rb else b
                        if np.hypot(*(aa[-1] - bb[0])) < tol:
                            lines[i] = np.concatenate([aa, bb[1:]])
                            del lines[j]
                            changed = True
                            break
                    if changed:
                        break
                if changed:
                    break
            if changed:
                break
    return lines


def _axis(cal, log=False):
    (p0, v0), (p1, v1) = cal
    if log:
        v0, v1 = np.log10(v0), np.log10(v1)

    def f(p):
        v = v0 + (np.asarray(p) - p0) * (v1 - v0) / (p1 - p0)
        return 10**v if log else v

    return f


def curves(pdf, spec):
    page = pymupdf.open(pdf)[spec["page"]]
    x0, y0, x1, y1 = spec["rect"]
    lines = []
    for i, d in enumerate(page.get_drawings()):
        if "drawings" in spec:
            if i not in spec["drawings"]:
                continue
        else:
            if d.get("color") is None or d["type"] not in ("s", "fs"):
                continue
            r = d["rect"]
            if r.x1 < x0 or r.x0 > x1 or r.y1 < y0 or r.y0 > y1:
                continue
            if "stroke" in spec and not np.allclose(d["color"], spec["stroke"], atol=0.02):
                continue
            if "width" in spec and abs((d.get("width") or 0) - spec["width"]) > 0.02:
                continue
            if spec.get("dashed") is not None and bool(d.get("dashes") not in (None, "[] 0")) != spec["dashed"]:
                continue
        for pl in _polylines(d):
            # drop axis lines, ticks and grid (straight horizontal or vertical strokes)
            if np.ptp(pl[:, 0]) < 0.3 or np.ptp(pl[:, 1]) < 0.3:
                continue
            # keep only what lies inside the plot
            inside = (pl[:, 0] >= x0 - 0.5) & (pl[:, 0] <= x1 + 0.5) & (pl[:, 1] >= y0 - 0.5) & (pl[:, 1] <= y1 + 0.5)
            if inside.mean() < 0.5:
                continue
            lines.append(pl)
    joined = _join(lines) if spec.get("join", True) else lines
    fx = _axis(spec["xcal"], spec.get("xlog", False))
    fy = _axis(spec["ycal"], spec.get("ylog", False))
    out = []
    for l in joined:
        if np.ptp(l[:, 0]) < spec.get("min_span", 5.0):
            continue
        xy = np.stack([fx(l[:, 0]), fy(l[:, 1])], axis=1)
        out.append(xy)
    out.sort(key=lambda c: -len(c))
    return out

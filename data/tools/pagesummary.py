"""Compact view of a page for writing digitizer specs: curve-like strokes, ticks/grid lines and
numeric labels (PDF points)."""
import re, sys, pymupdf
f, page = sys.argv[1], int(sys.argv[2])
p = pymupdf.open(f)[page]
for i, d in enumerate(p.get_drawings()):
    if d.get("color") is None:
        continue
    r = d["rect"]; n = len(d["items"])
    kinds = "".join(sorted(set(it[0] for it in d["items"])))
    curve = n >= 6 and ("c" in kinds or n >= 10)
    line = n <= 2 and (r.width < 0.3 or r.height < 0.3)
    if curve:
        print(f"CURVE D{i} ({r.x0:.1f},{r.y0:.1f},{r.x1:.1f},{r.y1:.1f}) n={n} k={kinds} w={d.get('width'):.2f} dash={d.get('dashes')}")
    elif line:
        print(f"LINE  D{i} ({r.x0:.1f},{r.y0:.1f},{r.x1:.1f},{r.y1:.1f})")
    elif n <= 8:
        print(f"SMALL D{i} ({r.x0:.1f},{r.y0:.1f},{r.x1:.1f},{r.y1:.1f}) n={n} k={kinds} dash={d.get('dashes')}")
for b in p.get_text("dict")["blocks"]:
    for l in b.get("lines", []):
        for s in l["spans"]:
            t = s["text"].strip()
            if re.fullmatch(r"[-–]?\d+(\.\d+)?|[BGR]|.{0,40}(min|D-min|Fog|Neutral|Density|Layer).{0,10}", t):
                bb = s["bbox"]; print(f"TEXT ({(bb[0]+bb[2])/2:.1f},{(bb[1]+bb[3])/2:.1f}) {t!r}")

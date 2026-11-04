"""List vector paths and text spans of a PDF page (to digitize datasheet curves)."""
import sys, pymupdf
f, page = sys.argv[1], int(sys.argv[2])
p = pymupdf.open(f)[page]
print("page size", p.rect)
for i, d in enumerate(p.get_drawings()):
    pts = sum(len(it) - 1 for it in d["items"])
    r = d["rect"]
    print(f"D{i:3d} rect=({r.x0:6.1f},{r.y0:6.1f},{r.x1:6.1f},{r.y1:6.1f}) items={len(d['items']):4d} kinds={''.join(sorted(set(it[0] for it in d['items'])))} "
          f"stroke={d.get('color')} fill={d.get('fill')} w={d.get('width')} dash={d.get('dashes')}")
if len(sys.argv) > 3:
    for b in p.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            for s in l["spans"]:
                bb = s["bbox"]
                print(f"T ({bb[0]:6.1f},{bb[1]:6.1f},{bb[2]:6.1f},{bb[3]:6.1f}) {s['text']!r}")

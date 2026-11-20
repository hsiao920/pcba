# Adapter that presents SCH_KunLunV1.3.pdf pages in the same geometry / colour / text conventions as KUNLUNV1.5.pdf,
# so extract_cad.extract_page() can be reused.  Text is Type3-encoded in V1.3; the character map is learned per font
# by aligning each V1.3 page with the matching V1.5 page.
import pymupdf, collections, math, json, os, sys

V13 = os.path.join(os.path.dirname(__file__), "..", "SCH_KunLunV1.3.pdf")
V15 = os.path.join(os.path.dirname(__file__), "..", "KUNLUNV1.5.pdf")

def C(c): return tuple(round(x, 3) for x in c) if c else None

COLMAP = {(0.258, 0.0, 1.0): (0.5, 0.0, 0.25),      # wire
          (0.668, 0.535, 0.266): (1.0, 0.0, 0.0),   # pin
          (0.801, 0.5, 0.023): (0.0, 0.0, 1.0),     # body
          (0.0, 0.0, 0.0): (1.0, 0.0, 0.0),         # power / gnd / offpage graphics are black in V1.3
          }
TXTMAP = {0x0000cc: 0x004080}                        # pin names


class Item:
    pass


def spans_raw(page):
    out = []
    for bl in page.get_text("rawdict")["blocks"]:
        for l in bl.get("lines", []):
            for s in l["spans"]:
                t = "".join(ch["c"] for ch in s["chars"])
                if not t.strip(): continue
                out.append(dict(t=t, origin=s["origin"], size=s["size"], color=s["color"], font=s["font"], dir=l["dir"], flags=s["flags"]))
    return out


class Fake:
    def __init__(self, p13, p15=None, cmap=None, pno=0):
        self.p = p13; self.pno = pno
        H = p13.mediabox.height
        self.H = H
        # scale so that pin-number font size matches V1.5 convention (6.2349 at full scale)
        sizes = collections.Counter(round(s["size"], 2) for s in spans_raw(p13) if s["color"] == 0)
        base = sizes.most_common(1)[0][0]
        cands = [6.2349, 6.2349 * 0.7, 6.2349 * 0.5]
        # V1.3 is uniformly ~0.942 of V1.5; pick scale from known ratio
        self.s = 6.2349 / 5.87
        self.dx = self.dy = 0.0
        xs, ys = [], []
        for d in p13.get_drawings():
            r = d["rect"]
            a = self.T(r.x0, r.y0); b = self.T(r.x1, r.y1)
            xs += [a[0], b[0]]; ys += [a[1], b[1]]
        if xs:
            self.dx, self.dy = min(xs), min(ys)
            self.rect = pymupdf.Rect(0, 0, max(xs) - self.dx, max(ys) - self.dy)
        else:
            self.rect = pymupdf.Rect(0, 0, H * self.s, p13.mediabox.width * self.s)
        self.cmap = cmap or {}

    def T(self, x, y):
        return ((self.H - y) * self.s - getattr(self, "dx", 0.0), x * self.s - getattr(self, "dy", 0.0))

    def get_drawings(self):
        out = []
        for d in self.p.get_drawings():
            c = C(d.get("color")); f = C(d.get("fill"))
            nd = {}
            nd["color"] = COLMAP.get(c, (0.3, 0.3, 0.3)) if c else None
            if c == (1.0, 0.0, 0.0): nd["color"] = (0.9, 0.9, 0.0)        # red note boxes: ignore
            nd["fill"] = None
            if f == (1.0, 0.0, 0.0): nd["fill"] = (1.0, 0.0, 1.0); nd["color"] = None   # junction dots
            elif f: nd["fill"] = COLMAP.get(f, (0.3, 0.3, 0.3))
            items = []
            xs, ys = [], []
            for it in d["items"]:
                k = it[0]
                if k == "l":
                    a = self.T(it[1].x, it[1].y); b = self.T(it[2].x, it[2].y)
                    items.append(("l", pymupdf.Point(*a), pymupdf.Point(*b))); xs += [a[0], b[0]]; ys += [a[1], b[1]]
                elif k == "c":
                    pts = [self.T(q.x, q.y) for q in it[1:5]]
                    items.append(("c",) + tuple(pymupdf.Point(*q) for q in pts)); xs += [q[0] for q in pts]; ys += [q[1] for q in pts]
                elif k == "re":
                    r = it[1]
                    a = self.T(r.x0, r.y0); b = self.T(r.x1, r.y1)
                    rr = pymupdf.Rect(min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1]))
                    items.append(("re", rr)); xs += [rr.x0, rr.x1]; ys += [rr.y0, rr.y1]
                elif k == "qu":
                    q = it[1]
                    pts = [self.T(p.x, p.y) for p in (q.ul, q.ur, q.lr, q.ll, q.ul)]
                    for a, b in zip(pts, pts[1:]):
                        items.append(("l", pymupdf.Point(*a), pymupdf.Point(*b)))
                    xs += [p[0] for p in pts]; ys += [p[1] for p in pts]
            if not items: continue
            nd["items"] = items
            nd["rect"] = pymupdf.Rect(min(xs), min(ys), max(xs), max(ys))
            nd["closePath"] = d.get("closePath")
            out.append(nd)
        return out

    def text_spans(self):
        out = []
        for idx, s in enumerate(spans_raw(self.p)):
            o = self.T(*s["origin"])
            dx, dy = s["dir"]
            nd = (round(-dy), round(dx))
            size = s["size"] * self.s
            out.append(dict(raw=s["t"], font=s["font"], origin=o, dir=nd, size=size, color=s["color"], idx=idx))
        return out

    def get_text(self, kind="dict"):
        blocks = []
        attrs = self.cmap.get("@attrs", {})
        for s in self.text_spans():
            t = decode_span(s["font"], s["raw"], self.cmap)
            if not t.strip(): continue
            at = attrs.get("%d:%d" % (self.pno, s["idx"]))
            if at and (len(at) > 3 and at[3] == "tt" or re.search(r"[㐀-鿿-]", at[2])):
                t = at[2]
            if at:
                s["dir"] = tuple(at[0])
            if at and len(at) > 2 and (at[2] == t):
                s["color"] = at[1]
            else:
                if REF.match(t) and s["color"] == 0: s["color"] = 0x80
                s["color"] = TXTMAP.get(s["color"], s["color"])
            n = len(t); size = s["size"]
            adv = 0.578 * size * n
            ox, oy = s["origin"]
            if s["dir"] == (1, 0):
                bbox = (ox, oy - 0.64 * size, ox + adv, oy + 0.19 * size)
            elif s["dir"] == (0, -1):
                bbox = (ox - 0.64 * size, oy - adv, ox + 0.19 * size, oy)
            elif s["dir"] == (0, 1):
                bbox = (ox - 0.19 * size, oy, ox + 0.64 * size, oy + adv)
            else:
                bbox = (ox - adv, oy - 0.19 * size, ox, oy + 0.64 * size)
            col = s["color"]
            blocks.append({"lines": [{"dir": s["dir"], "spans": [{"text": t, "bbox": bbox, "color": col, "size": size, "font": "CourierNew"}]}]})
        return {"blocks": blocks}


import re
REF = re.compile(r"^(?![RCL](?:0201|0402|0603|0805|1206|1210)$)(?:(?:R|C|L|D|U|Q|Y|X|J|P|FB|TP|ED)\d{3,6}[A-Z]?|ESD\d{3,6}|(?:SW|LED|FPC|TYPE_C)\d{1,3})$")


HEADING_FIX = {"êeeU": "eMMC"}


def decode_span(font, raw, cmap):
    return HEADING_FIX.get(_decode(font, raw, cmap), _decode(font, raw, cmap))


def _decode(font, raw, cmap):
    if not font.startswith("Type3"): return raw       # real TrueType text (e.g. the Chinese notes) is already Unicode
    return _decode_span(font, raw, cmap)


def _decode_span(font, raw, cmap):
    m = cmap.get(font, {}); g = cmap.get("*", {})
    if not raw.strip(chr(0)): return ""
    extra = {"#": "#"}
    return "".join(g.get(ch) or m.get(ch) or extra.get(ch) or "?" for ch in raw)


def learn():
    """learn per-font char maps by aligning V1.3 pages with V1.5 pages"""
    a, b = pymupdf.open(V13), pymupdf.open(V15)
    votes = collections.defaultdict(collections.Counter)
    attrs = {}
    for i in range(min(len(a), len(b))):
        fk = Fake(a[i])
        A = fk.text_spans()
        B = []
        for bl in b[i].get_text("dict")["blocks"]:
            for l in bl.get("lines", []):
                for s in l["spans"]:
                    if s["text"].strip(): B.append(dict(t=s["text"], origin=s["origin"], dir=(round(l["dir"][0]), round(l["dir"][1])), size=s["size"], color=s["color"]))
        # junction-based affine (V1.3-transformed -> V1.5)
        def juncs(dr):
            return [((d["rect"].x0 + d["rect"].x1) / 2, (d["rect"].y0 + d["rect"].y1) / 2) for d in dr
                    if d.get("fill") and C(d["fill"]) in ((1.0, 0.0, 1.0),)]
        ja = juncs(fk.get_drawings()); jb = juncs(b[i].get_drawings())
        if len(ja) < 3 or len(jb) < 3:
            # fall back to text extents
            ja = [s["origin"] for s in A]; jb = [s["origin"] for s in B]
        def ext(v): return min(v), max(v)
        ax0, ax1 = ext([p[0] for p in ja]); bx0, bx1 = ext([p[0] for p in jb])
        ay0, ay1 = ext([p[1] for p in ja]); by0, by1 = ext([p[1] for p in jb])
        sx = (bx1 - bx0) / (ax1 - ax0) if ax1 > ax0 else 1; sy = (by1 - by0) / (ay1 - ay0) if ay1 > ay0 else 1
        off = [0.0, 0.0]
        def M(p): return (bx0 + (p[0] - ax0) * sx + off[0], by0 + (p[1] - ay0) * sy + off[1])
        # refine offset from unambiguous matches (same text length, nearest)
        gridB = collections.defaultdict(list)
        for j, t in enumerate(B): gridB[(int(t["origin"][0] // 10), int(t["origin"][1] // 10))].append(j)
        for it in range(2):
            ds = []
            for s in A:
                if len(s["raw"]) < 4: continue
                o = M(s["origin"])
                c = [B[j] for gx in range(int(o[0] // 10) - 1, int(o[0] // 10) + 2) for gy in range(int(o[1] // 10) - 1, int(o[1] // 10) + 2)
                     for j in gridB.get((gx, gy), []) if len(B[j]["t"]) == len(s["raw"])]
                c = [(math.dist(o, t["origin"]), t) for t in c]
                c.sort(key=lambda x: x[0])
                if c and c[0][0] < 8 and (len(c) == 1 or c[1][0] > c[0][0] + 4):
                    ds.append((c[0][1]["origin"][0] - o[0], c[0][1]["origin"][1] - o[1]))
            if ds:
                ds.sort(key=lambda d: d[0]); off[0] += ds[len(ds) // 2][0]
                ds.sort(key=lambda d: d[1]); off[1] += ds[len(ds) // 2][1]
        # match spans
        grid = collections.defaultdict(list)
        for j, s in enumerate(B): grid[(int(s["origin"][0] // 6), int(s["origin"][1] // 6))].append(j)
        for s in A:
            o = M(s["origin"])
            best = None
            for gx in range(int(o[0] // 6) - 1, int(o[0] // 6) + 2):
                for gy in range(int(o[1] // 6) - 1, int(o[1] // 6) + 2):
                    for j in grid.get((gx, gy), []):
                        t = B[j]
                        if len(t["t"]) != len(s["raw"]): continue
                        d = math.dist(o, t["origin"])
                        if d < 1.6 and (best is None or d < best[0]): best = (d, t)
            if best is None and not s["font"].startswith("Type3"):
                # TrueType span (Chinese note): take the V1.5 text sitting at the same place, whatever its length
                for gx in range(int(o[0] // 6) - 2, int(o[0] // 6) + 3):
                    for gy in range(int(o[1] // 6) - 2, int(o[1] // 6) + 3):
                        for j in grid.get((gx, gy), []):
                            t = B[j]; d = math.dist(o, t["origin"])
                            if d < 6 and (best is None or d < best[0]): best = (d, t)
                if best:
                    attrs["%d:%d" % (i, s["idx"])] = [best[1]["dir"], best[1]["color"], best[1]["t"], "tt"]
                continue
            if best:
                for ca, cb in zip(s["raw"], best[1]["t"]):
                    votes[(s["font"], ca)][cb] += 1
                attrs["%d:%d" % (i, s["idx"])] = [best[1]["dir"], best[1]["color"], best[1]["t"]]
    cmap = collections.defaultdict(dict)
    glob = collections.defaultdict(collections.Counter)
    for (font, ca), cnt in votes.items():
        cb, n = cnt.most_common(1)[0]
        cmap[font][ca] = cb
        glob[ca][cb] += n
    cmap["*"] = {ca: c.most_common(1)[0][0] for ca, c in glob.items()}
    cmap["@attrs"] = attrs
    return cmap


CMAP_FILE = os.path.join(os.path.dirname(__file__), "v13_cmap.json")


def get_cmap():
    if os.path.exists(CMAP_FILE):
        return json.load(open(CMAP_FILE, encoding="utf-8"))
    cm = learn()
    json.dump(cm, open(CMAP_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    return cm


def open_pages():
    cm = get_cmap()
    a = pymupdf.open(V13)
    return [Fake(a[i], cmap=cm, pno=i) for i in range(len(a))]


if __name__ == "__main__":
    if os.path.exists(CMAP_FILE): os.remove(CMAP_FILE)
    cm = get_cmap()
    print("fonts", len(cm) - 1, "global map", "".join(sorted(cm["*"].values())))
    pages = open_pages()
    for i in (0, 10):
        txt = [l["spans"][0]["text"] for b in pages[i].get_text()["blocks"] for l in b["lines"]]
        print(i + 1, txt[:60])
        print("unknown chars:", sum(t.count("?") for t in txt), "of", sum(len(t) for t in txt))

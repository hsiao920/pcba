# Adapter: present JLC/EasyEDA-exported schematic PDF pages in the Cadence-like conventions extract_cad expects.
#   wires red -> WIRE colour, junction dots -> JUNC, symbol geometry (green / grey) is split into
#   pins (red), part bodies (blue) and port symbols (red); text roles are recoloured.
import pymupdf, collections, math, re, os
from extract_cad import PROPRE

PDF = os.path.join(os.path.dirname(__file__), "..", "SCH_0.5青春版主板v1.0_2024-10-24.pdf")

GREEN = (0.0, 0.5, 0.0); GREY = (0.6, 0.6, 0.6); NCX = (0.2, 0.8, 0.2)
RED = (1.0, 0.0, 0.0); BLUEDOT = (0.0, 0.0, 1.0)
W_OUT = (0.5, 0.0, 0.25); PIN_OUT = (1.0, 0.0, 0.0); BODY_OUT = (0.0, 0.0, 1.0); JUNC_OUT = (1.0, 0.0, 1.0)
TOL = 0.3
REF = re.compile(r"^(?:R|C|L|D|U|Q|Y|X|J|FB|TP|SW|LED|FPC|USB|CN|CON|BT|F|MIC|SPK|ANT|VR|RT|TH|ZD|BZ|RN|ED|ESD|TVS|IR|NTC|KEY|MOTOR|LS|BUZ)\d{1,4}(?:\.\d{1,2})?$")
NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_+\-./#]{0,40}$")
POWERLIKE = re.compile(r"^(?:\+|[AD]?V(?:CC|DD|SS|BAT|BUS|IN|SYS|REF)|VBAT|VSYS|VIN|VBUS|GND|AGND|DGND|PGND|[0-9]+V[0-9]*|BAT|SYS_)", re.I)


def C(c): return tuple(round(x, 2) for x in c) if c else None


def bez(p0, p1, p2, p3, n=6):
    out = []
    for i in range(n + 1):
        t = i / n; m = 1 - t
        out.append((m**3*p0[0]+3*m*m*t*p1[0]+3*m*t*t*p2[0]+t**3*p3[0], m**3*p0[1]+3*m*m*t*p1[1]+3*m*t*t*p2[1]+t**3*p3[1]))
    return out


def on_seg(p, a, b, eps=TOL):
    (x, y), (x1, y1), (x2, y2) = p, a, b
    dx, dy = x2 - x1, y2 - y1; L2 = dx * dx + dy * dy
    if L2 < 1e-9: return math.hypot(x - x1, y - y1) <= eps
    t = max(0, min(1, ((x - x1) * dx + (y - y1) * dy) / L2))
    return math.hypot(x - (x1 + t * dx), y - (y1 + t * dy)) <= eps


def bbox_dist(a, b):
    dx = max(a[0] - b[2], 0, b[0] - a[2]); dy = max(a[1] - b[3], 0, b[1] - a[3])
    return math.hypot(dx, dy)


class Seg:
    __slots__ = ("a", "b", "straight", "src", "grey", "role", "comp")
    def __init__(s, a, b, straight, src, grey):
        s.a, s.b, s.straight, s.src, s.grey = a, b, straight, src, grey; s.role = None; s.comp = None


class Grid:
    def __init__(s, segs, cell=8.0):
        s.c = cell; s.h = collections.defaultdict(list)
        for i, sg in enumerate(segs):
            x0, x1 = sorted((sg.a[0], sg.b[0])); y0, y1 = sorted((sg.a[1], sg.b[1]))
            for gx in range(int((x0 - 1) // cell), int((x1 + 1) // cell) + 1):
                for gy in range(int((y0 - 1) // cell), int((y1 + 1) // cell) + 1):
                    s.h[(gx, gy)].append(i)
    def near(s, p): return s.h.get((int(p[0] // s.c), int(p[1] // s.c)), [])


class Fake:
    def __init__(self, page):
        self.p = page; self.rect = page.rect
        self._build()

    def _build(self):
        dr = self.p.get_drawings()
        wires, juncs, ncs, dots, segs = [], [], [], [], []
        self.polysrc = set()
        for di, d in enumerate(dr):
            c, f = C(d.get("color")), C(d.get("fill"))
            if f == RED and d["items"][0][0] == "c":
                r = d["rect"]; juncs.append(((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2)); continue
            if f == BLUEDOT and d["items"][0][0] == "c":
                r = d["rect"]; dots.append(((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2)); continue
            if c == NCX:
                r = d["rect"]; ncs.append(((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2)); continue
            if c == RED:
                for it in d["items"]:
                    if it[0] == "l": wires.append(((it[1].x, it[1].y), (it[2].x, it[2].y)))
                continue
            if c in (GREEN, GREY):
                grey = c == GREY
                ls = [it for it in d["items"] if it[0] == "l"]
                if 5 <= len(ls) <= 8 and len(ls) == len(d["items"]) and all(math.dist((it[1].x, it[1].y), (it[2].x, it[2].y)) > 1.5 for it in ls)                         and math.dist((ls[0][1].x, ls[0][1].y), (ls[-1][2].x, ls[-1][2].y)) < 0.3:
                    self.polysrc.add(di)
                for it in d["items"]:
                    k = it[0]
                    if k == "l":
                        segs.append(Seg((it[1].x, it[1].y), (it[2].x, it[2].y), True, di, grey))
                    elif k == "re":
                        r = it[1]; pts = [(r.x0, r.y0), (r.x1, r.y0), (r.x1, r.y1), (r.x0, r.y1), (r.x0, r.y0)]
                        for a, b in zip(pts, pts[1:]): segs.append(Seg(a, b, False, di, grey))
                    elif k == "qu":
                        q = it[1]; pts = [(q.ul.x, q.ul.y), (q.ur.x, q.ur.y), (q.lr.x, q.lr.y), (q.ll.x, q.ll.y), (q.ul.x, q.ul.y)]
                        for a, b in zip(pts, pts[1:]): segs.append(Seg(a, b, False, di, grey))
                    elif k == "c":
                        pts = bez(*[(q.x, q.y) for q in it[1:5]])
                        for a, b in zip(pts, pts[1:]): segs.append(Seg(a, b, False, di, grey))
        segs = [s for s in segs if math.hypot(s.a[0] - s.b[0], s.a[1] - s.b[1]) > 0.05]
        # drop exact duplicates, then merge collinear straight pieces that meet end-to-end with nothing else there
        seen = set(); uniq = []
        for s in segs:
            k = tuple(sorted([(round(s.a[0], 1), round(s.a[1], 1)), (round(s.b[0], 1), round(s.b[1], 1))])) + (s.straight,)
            if k in seen: continue
            seen.add(k); uniq.append(s)
        segs = uniq
        changed = True
        while changed:
            changed = False
            ends = collections.defaultdict(list)
            for i, s in enumerate(segs):
                for p in (s.a, s.b): ends[(round(p[0], 1), round(p[1], 1))].append(i)
            gtmp = Grid(segs)
            for key_, ids in ends.items():
                if len(ids) != 2: continue
                i, j = ids
                si, sj = segs[i], segs[j]
                if not (si.straight and sj.straight) or si.grey != sj.grey: continue
                hi = abs(si.a[1] - si.b[1]) < 0.05; hj = abs(sj.a[1] - sj.b[1]) < 0.05
                vi = abs(si.a[0] - si.b[0]) < 0.05; vj = abs(sj.a[0] - sj.b[0]) < 0.05
                if not ((hi and hj) or (vi and vj)): continue
                Li = math.dist(si.a, si.b); Lj = math.dist(sj.a, sj.b)
                if min(Li, Lj) > 4.0: continue          # two full-length leads meeting: different symbols
                p = key_
                # anything else touching this joint?
                if any(k not in (i, j) and on_seg(p, segs[k].a, segs[k].b) for k in gtmp.near(p)): continue
                pts = [q for q in (si.a, si.b, sj.a, sj.b) if (round(q[0], 1), round(q[1], 1)) != p]
                if len(pts) != 2: continue
                segs[i] = Seg(pts[0], pts[1], True, si.src, si.grey)
                segs.pop(j)
                changed = True
                break
        self.wires, self.juncs, self.ncs, self.dots = wires, juncs, ncs, dots
        g = Grid(segs)
        # components
        par = list(range(len(segs)))
        def fnd(i):
            while par[i] != i: par[i] = par[par[i]]; i = par[i]
            return i
        touch = collections.defaultdict(set)   # (seg, end) -> segs touching that endpoint
        for i, s in enumerate(segs):
            for e, p in ((0, s.a), (1, s.b)):
                for j in g.near(p):
                    if j != i and on_seg(p, segs[j].a, segs[j].b):
                        sj = segs[j]
                        if s.straight and sj.straight and (math.dist(p, sj.a) < 0.3 or math.dist(p, sj.b) < 0.3):
                            hi = abs(s.a[1] - s.b[1]) < 0.05; hj = abs(sj.a[1] - sj.b[1]) < 0.05
                            vi = abs(s.a[0] - s.b[0]) < 0.05; vj = abs(sj.a[0] - sj.b[0]) < 0.05
                            if (hi and hj) or (vi and vj): continue      # end-to-end collinear: two different symbols' leads
                        touch[(i, e)].add(j)
                        a, b = fnd(i), fnd(j)
                        if a != b: par[a] = b
        comps = collections.defaultdict(list)
        for i in range(len(segs)): comps[fnd(i)].append(i)
        wg = Grid([Seg(a, b, True, -1, False) for a, b in wires])
        wsegs = wires
        def wire_hit(p):
            for j in wg.near(p):
                a, b = wsegs[j]
                if on_seg(p, a, b, 0.4): return True
            return False
        def nc_hit(p): return any(math.hypot(p[0] - q[0], p[1] - q[1]) < 2.5 for q in ncs)
        # pin candidates
        numboxes = []
        for b in self.p.get_text("dict")["blocks"]:
            for l in b.get("lines", []):
                for sp in l["spans"]:
                    if sp["color"] in (0x0000ff, 0x999999) and re.match(r"^[A-Z]{0,2}\d{1,3}$", sp["text"].strip()): numboxes.append(sp["bbox"])
        info = {}
        for cid, ids in comps.items():
            pins = []
            for i in ids:
                s = segs[i]
                if not s.straight: continue
                horiz = abs(s.a[1] - s.b[1]) < 0.05; vert = abs(s.a[0] - s.b[0]) < 0.05
                if not (horiz or vert): continue
                L = math.hypot(s.a[0] - s.b[0], s.a[1] - s.b[1])
                if L < 2.0: continue
                ta, tb = set(touch.get((i, 0), set())), set(touch.get((i, 1), set()))
                # a collinear lead meeting this one end-to-end is another part's pin (pin-to-pin contact): ignore it
                def pinpin(p, T):
                    out = set()
                    for j in T:
                        sj = segs[j]
                        if not sj.straight: continue
                        hj = abs(sj.a[1] - sj.b[1]) < 0.05; vj = abs(sj.a[0] - sj.b[0]) < 0.05
                        if (hj and horiz or vj and vert) and (math.dist(p, sj.a) < 0.3 or math.dist(p, sj.b) < 0.3): out.add(j)
                    return out
                ta -= pinpin(s.a, ta); tb -= pinpin(s.b, tb)
                if bool(ta) == bool(tb): continue
                free = s.a if not ta else s.b
                # evidence that this is a real pin: wire / no-connect mark at the free end, a pin-number text beside it,
                # or a long lead
                hasbox = any(not segs[k].straight for k in ids)
                ev = wire_hit(free) or nc_hit(free) or (L >= 5.5 and hasbox) or any(
                    bbox_dist(nb, (min(s.a[0], s.b[0]) - 1, min(s.a[1], s.b[1]) - 1, max(s.a[0], s.b[0]) + 1, max(s.a[1], s.b[1]) + 1)) < 2.5
                    for nb in numboxes)
                if ev: pins.append((i, free))
            # free end must lie outside the body outline (rejects leads drawn inside a box, e.g. LED internals)
            pinids = {p[0] for p in pins}
            bx = [q for k in ids if k not in pinids for q in (segs[k].a, segs[k].b)]
            if bx:
                x0, y0, x1, y1 = min(q[0] for q in bx), min(q[1] for q in bx), max(q[0] for q in bx), max(q[1] for q in bx)
                pins = [(k, fr) for k, fr in pins if not (x0 + 0.4 < fr[0] < x1 - 0.4 and y0 + 0.4 < fr[1] < y1 - 0.4)]
            info[cid] = pins
        # classify components
        self.kind = {}
        portlike = {}
        for cid, ids in comps.items():
            pins = info[cid]
            others = [i for i in ids if i not in {p[0] for p in pins}]
            if len(pins) == 1 and len(others) == 1 and segs[others[0]].straight:
                pi, free = pins[0]; bar = segs[others[0]]; ps = segs[pi]
                ph = abs(ps.a[1] - ps.b[1]) < 0.05; bh = abs(bar.a[1] - bar.b[1]) < 0.05
                if ph != bh:
                    portlike[cid] = (pi, others[0]); continue
            if not pins:
                self.kind[cid] = "sym"
            else:
                self.kind[cid] = "part"
        # capacitor halves: two port-like comps with parallel, overlapping bars a few pt apart
        pl = list(portlike)
        paired = set()
        for x in range(len(pl)):
            for y in range(x + 1, len(pl)):
                a, b = segs[portlike[pl[x]][1]], segs[portlike[pl[y]][1]]
                ah = abs(a.a[1] - a.b[1]) < 0.05; bh = abs(b.a[1] - b.b[1]) < 0.05
                if ah != bh: continue
                if ah:
                    d = abs(a.a[1] - b.a[1]); ov = min(max(a.a[0], a.b[0]), max(b.a[0], b.b[0])) - max(min(a.a[0], a.b[0]), min(b.a[0], b.b[0]))
                    La = abs(a.a[0] - a.b[0])
                else:
                    d = abs(a.a[0] - b.a[0]); ov = min(max(a.a[1], a.b[1]), max(b.a[1], b.b[1])) - max(min(a.a[1], a.b[1]), min(b.a[1], b.b[1]))
                    La = abs(a.a[1] - a.b[1])
                # the two stems must point away from each other (cap) - not stacked like GND bars
                if 0.8 < d < 6.5 and ov > 0.6 * La:
                    pa, pb = segs[portlike[pl[x]][0]], segs[portlike[pl[y]][0]]
                    ca = ((pa.a[0] + pa.b[0]) / 2, (pa.a[1] + pa.b[1]) / 2); cb = ((pb.a[0] + pb.b[0]) / 2, (pb.a[1] + pb.b[1]) / 2)
                    if ah: away = (ca[1] - a.a[1]) * (cb[1] - b.a[1]) < 0
                    else: away = (ca[0] - a.a[0]) * (cb[0] - b.a[0]) < 0
                    if away: paired.add(pl[x]); paired.add(pl[y])
        for cid in portlike:
            self.kind[cid] = "part" if cid in paired else "port"
        # parts must have a refdes text nearby; otherwise they are net-port graphics
        reftexts = []; blacks = []
        for b in self.p.get_text("dict")["blocks"]:
            for l in b.get("lines", []):
                for sp in l["spans"]:
                    if sp["color"] in (0x0000ff, 0x999999) and REF.match(sp["text"].strip()): reftexts.append(sp["bbox"])
                    if sp["color"] == 0 and sp["text"].strip(): blacks.append(sp["bbox"])
        for cid, ids in comps.items():
            if self.kind[cid] != "part" or cid in paired: continue
            xs = [p[0] for i in ids for p in (segs[i].a, segs[i].b)]; ys = [p[1] for i in ids for p in (segs[i].a, segs[i].b)]
            box = [min(xs), min(ys), max(xs), max(ys)]
            if not any(bbox_dist(rb, box) < 40 for rb in reftexts):
                self.kind[cid] = "sym"; continue
            if any(segs[i].src in self.polysrc for i in ids) and all(segs[i].straight for i in ids):
                self.kind[cid] = "sym"; continue
            # net-flag polygons: only plain line segments, with a black net name right beside them
            if all(segs[i].straight for i in ids) and not any(bbox_dist(rb, box) < 12 for rb in reftexts) and                     any(bbox_dist(bb, box) < 4 and not (bb[0] >= box[0] and bb[2] <= box[2]) for bb in blacks):
                if not any(segs[i].straight and abs(segs[i].a[0] - segs[i].b[0]) > 0.05 and abs(segs[i].a[1] - segs[i].b[1]) > 0.05 for i in ids) is False:
                    self.kind[cid] = "sym"
        # roles
        self.comps = comps; self.segs = segs; self.pininfo = info; self.portlike = portlike
        for cid, ids in comps.items():
            k = self.kind[cid]
            pinset = {p[0] for p in info[cid]} if k == "part" else set()
            if k == "part" and cid in portlike: pinset = {portlike[cid][0]}
            for i in ids:
                segs[i].comp = cid
                segs[i].role = "pin" if i in pinset else ("body" if k == "part" else "sym")
        # body boxes of parts for text roles
        self.part_boxes = []
        self.port_boxes = []
        self.flag_boxes = []
        for cid, ids in comps.items():
            xs = [p[0] for i in ids for p in (segs[i].a, segs[i].b)]; ys = [p[1] for i in ids for p in (segs[i].a, segs[i].b)]
            box = [min(xs), min(ys), max(xs), max(ys)]
            if self.kind[cid] == "part":
                bx = [p for i in ids if segs[i].role == "body" for p in (segs[i].a, segs[i].b)]
                if bx:
                    self.part_boxes.append(([min(p[0] for p in bx), min(p[1] for p in bx), max(p[0] for p in bx), max(p[1] for p in bx)],
                                            any(segs[i].grey for i in ids)))
            elif self.kind[cid] == "port":
                self.port_boxes.append(box)
            elif self.kind[cid] == "sym":
                self.flag_boxes.append(box)
        self.pin_segs = [(segs[i].a, segs[i].b) for cid in comps for i in comps[cid] if segs[i].role == "pin"]

    def get_drawings(self):
        out = []
        for a, b in self.wires:
            out.append({"color": W_OUT, "fill": None, "items": [("l", pymupdf.Point(*a), pymupdf.Point(*b))],
                        "rect": pymupdf.Rect(min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1]))})
        for j in self.juncs:
            r = pymupdf.Rect(j[0] - 1.2, j[1] - 1.2, j[0] + 1.2, j[1] + 1.2)
            out.append({"color": None, "fill": JUNC_OUT, "items": [("c", pymupdf.Point(j[0] + 1.2, j[1]), pymupdf.Point(j[0] + 1.2, j[1] - 0.6), pymupdf.Point(j[0] + 0.6, j[1] - 1.2), pymupdf.Point(j[0], j[1] - 1.2))], "rect": r})
        for s in self.segs:
            col = {"pin": PIN_OUT, "body": BODY_OUT, "sym": PIN_OUT}[s.role]
            kind = "l"
            out.append({"color": col, "fill": None, "items": [("l", pymupdf.Point(*s.a), pymupdf.Point(*s.b))] if s.straight or s.role != "pin" else [],
                        "rect": pymupdf.Rect(min(s.a[0], s.b[0]), min(s.a[1], s.b[1]), max(s.a[0], s.b[0]), max(s.a[1], s.b[1]))})
            if not s.straight:
                # curves / rect edges: emit as 'c'-free polyline pieces; mark kind so extractor does not treat them as pins
                out[-1]["items"] = [("l", pymupdf.Point(*s.a), pymupdf.Point(*s.b))]
                out[-1]["_curve"] = True
        return out

    def get_text(self, kind="dict"):
        blocks = []
        # merge spans of the same line and colour
        lines = []
        for b in self.p.get_text("dict")["blocks"]:
            for l in b.get("lines", []):
                cur = None
                for sp in l["spans"]:
                    if not sp["text"].strip():
                        if cur: cur["text"] += sp["text"]
                        continue
                    if cur and sp["color"] == cur["color"] and sp["bbox"][0] - cur["bbox"][2] < 3.5 and abs(sp["origin"][1] - cur["origin"][1]) < 1.0:
                        cur["text"] += sp["text"]; bb = cur["bbox"]
                        cur["bbox"] = (min(bb[0], sp["bbox"][0]), min(bb[1], sp["bbox"][1]), max(bb[2], sp["bbox"][2]), max(bb[3], sp["bbox"][3]))
                    else:
                        if cur and cur["text"].strip(): lines.append((l["dir"], cur))
                        cur = dict(text=sp["text"], bbox=tuple(sp["bbox"]), color=sp["color"], size=sp["size"], font=sp["font"], origin=sp["origin"])
                if cur and cur["text"].strip(): lines.append((l["dir"], cur))
        split = []
        for d, sp in lines:
            tok = sp["text"].strip().split(" ", 1)
            if sp["color"] in (0x0000ff, 0x999999) and len(tok) == 2 and REF.match(tok[0]) and (d == (1.0, 0.0) or d == (1, 0)):
                n = len(sp["text"]); bb = sp["bbox"]; w = (bb[2] - bb[0]) / max(n, 1)
                k = sp["text"].index(tok[0]) + len(tok[0])
                a = dict(sp); a["text"] = tok[0]; a["bbox"] = (bb[0], bb[1], bb[0] + w * k, bb[3])
                b2 = dict(sp); b2["text"] = tok[1].strip(); b2["bbox"] = (bb[0] + w * (k + 1), bb[1], bb[2], bb[3])
                split += [(d, a), (d, b2)]
            else:
                split.append((d, sp))
        for d, sp in split:
            t = sp["text"].strip(); bb = sp["bbox"]; col = sp["color"]; extra = []
            # tighten bbox height (JLC text boxes include large ascent)
            h = bb[3] - bb[1]
            o = sp.get("origin")
            if o and (d == (1.0, 0.0) or d == (1, 0)):
                bb = (bb[0], o[1] - 0.72 * sp["size"], bb[2], o[1] + 0.12 * sp["size"])
            elif o and (d == (0.0, -1.0) or d == (0, -1)):
                bb = (o[0] - 0.72 * sp["size"], bb[1], o[0] + 0.12 * sp["size"], bb[3])
            if col in (0x0000ff, 0x999999):
                grey = col == 0x999999
                m = re.match(r"^([A-Z]+\d+)\.(\d+)$", t)
                if REF.match(t):
                    if m: t = m.group(1) + chr(64 + int(m.group(2)))
                    col = 0x80
                    if grey: extra.append(dict(text="DNP", bbox=(bb[0], bb[3] + 0.5, bb[0] + 10, bb[3] + 0.5 + sp["size"] * 0.8), color=0x00ff00, size=sp["size"]))
                elif re.match(r"^[A-Z]{0,2}\d{1,3}$|^[A-Z0-9]{1,4}$", t) and self._near_pin(bb):
                    col = 0x0
                elif PROPRE.search(t) or re.search(r"[Ωµ]|\d+(?:\.\d+)?\s*(?:[pnuµm]?F|[kKM]?Ω|[pnuµm]?H|[kM]?Hz|V|A|%)", t) or not NAME.match(t):
                    col = 0x80
                elif any(bbox_dist(bb, pb) < 8 for pb in self.port_boxes):
                    col = 0x0 if POWERLIKE.match(t) else 0xff0000
                elif any(bbox_dist(bb, pb) < 6 for pb in self.flag_boxes):
                    col = 0xff0000
                else:
                    col = 0x80
            elif col == 0x0:
                if any(bb[0] >= pb[0] - 1 and bb[2] <= pb[2] + 1 and bb[1] >= pb[1] - 1 and bb[3] <= pb[3] + 1 for pb, g in self.part_boxes):
                    col = 0x004080
                elif any(bbox_dist(bb, (q[0] - 1, q[1] - 1, q[0] + 1, q[1] + 1)) < 4 for q in self.dots):
                    col = 0xff0000
                elif not NAME.match(t):
                    col = 0x123456
                elif any(bbox_dist(bb, pb) < 6 for pb in self.flag_boxes):
                    col = 0xff0000
                elif any(bbox_dist(bb, pb) < 8 for pb in self.port_boxes):
                    col = 0x0 if POWERLIKE.match(t) else 0xff0000
            elif col == 0x008000 or col == 0x000080:
                col = 0x123456          # notes / headings: neutral
            blocks.append({"lines": [{"dir": (round(d[0]), round(d[1])), "spans": [dict(text=t, bbox=bb, color=col, size=sp["size"], font=sp["font"])]}]})
            for e in extra:
                blocks.append({"lines": [{"dir": (1, 0), "spans": [dict(text=e["text"], bbox=e["bbox"], color=e["color"], size=e["size"], font="x")]}]})
        return {"blocks": blocks}

    def _near_pin(self, bb):
        for a, b in self.pin_segs:
            sb = (min(a[0], b[0]) - 1, min(a[1], b[1]) - 1, max(a[0], b[0]) + 1, max(a[1], b[1]) + 1)
            if bbox_dist(bb, sb) < 3: return True
        return False


def open_pages():
    d = pymupdf.open(PDF)
    return [Fake(d[i]) for i in range(len(d))]


if __name__ == "__main__":
    import sys
    pages = open_pages()
    for i, f in enumerate(pages):
        k = collections.Counter(f.kind.values())
        print(i + 1, dict(k), "pins", len(f.pin_segs), "ports", len(f.port_boxes), "nc", len(f.ncs), "dots", len(f.dots))

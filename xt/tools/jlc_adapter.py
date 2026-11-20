# Adapter: present JLC/EasyEDA-exported schematic PDF pages in the Cadence-like conventions extract_cad expects.
# EasyEDA emits every schematic object as a contiguous run of drawing operators followed by its own texts
# (pins of an IC interleave their pin-name / pin-number texts; a part ends with its designator + value).
# We use that drawing order to segment objects, then:
#   part   (has a designator text)  -> pins red, body blue
#   port   (power / net port / GND) -> red symbol graphics; its name text black (power) or red (signal port)
#   wires red -> WIRE colour, junction dots -> JUNC, no-connect crosses dropped
import pymupdf, collections, math, re, os
from extract_cad import PROPRE

PDF = os.path.join(os.path.dirname(__file__), "..", "SCH_0.5青春版主板v1.0_2024-10-24.pdf")

GREEN = (0.0, 0.5, 0.0); GREY = (0.6, 0.6, 0.6); NCX = (0.2, 0.8, 0.2)
RED = (1.0, 0.0, 0.0); BLUEDOT = (0.0, 0.0, 1.0)
W_OUT = (0.5, 0.0, 0.25); PIN_OUT = (1.0, 0.0, 0.0); BODY_OUT = (0.0, 0.0, 1.0); JUNC_OUT = (1.0, 0.0, 1.0)
REF = re.compile(r"^(?:R|C|L|D|U|Q|Y|X|J|FB|TP|SW|LED|FPC|USB|CN|CON|BT|F|MIC|SPK|ANT|VR|RT|TH|ZD|BZ|RN|ED|ESD|TVS|IR|NTC|KEY|MOTOR|LS|BUZ|M)\d{1,4}(?:\.\d{1,2})?$")
NAME = re.compile(r"^[A-Za-z_+][A-Za-z0-9_+\-./#]{0,40}$")
POWERLIKE = re.compile(r"^(?:\+|[AD]?V(?:CC|DD|SS|BAT|BUS|IN|SYS|REF)|VBAT|VSYS|VIN|VBUS|GND|AGND|DGND|PGND|[0-9]+V[0-9]*$)", re.I)
PINNUM = re.compile(r"^[A-Z]{0,2}\d{1,3}$|^[A-Z]{1,3}$|^EP$")


def C(c): return tuple(round(x, 2) for x in c) if c else None


def bez(p0, p1, p2, p3, n=6):
    out = []
    for i in range(n + 1):
        t = i / n; m = 1 - t
        out.append((m**3*p0[0]+3*m*m*t*p1[0]+3*m*t*t*p2[0]+t**3*p3[0], m**3*p0[1]+3*m*m*t*p1[1]+3*m*t*t*p2[1]+t**3*p3[1]))
    return out


def on_seg(p, a, b, eps=0.3):
    (x, y), (x1, y1), (x2, y2) = p, a, b
    dx, dy = x2 - x1, y2 - y1; L2 = dx * dx + dy * dy
    if L2 < 1e-9: return math.hypot(x - x1, y - y1) <= eps
    t = max(0, min(1, ((x - x1) * dx + (y - y1) * dy) / L2))
    return math.hypot(x - (x1 + t * dx), y - (y1 + t * dy)) <= eps


def bbox_dist(a, b):
    dx = max(a[0] - b[2], 0, b[0] - a[2]); dy = max(a[1] - b[3], 0, b[1] - a[3])
    return math.hypot(dx, dy)


def seg_list(d):
    out = []
    for it in d["items"]:
        k = it[0]
        if k == "l":
            out.append(((it[1].x, it[1].y), (it[2].x, it[2].y), True))
        elif k == "re":
            r = it[1]; pts = [(r.x0, r.y0), (r.x1, r.y0), (r.x1, r.y1), (r.x0, r.y1), (r.x0, r.y0)]
            out += [(a, b, "rect") for a, b in zip(pts, pts[1:])]
        elif k == "qu":
            q = it[1]; pts = [(q.ul.x, q.ul.y), (q.ur.x, q.ur.y), (q.lr.x, q.lr.y), (q.ll.x, q.ll.y), (q.ul.x, q.ul.y)]
            out += [(a, b, "rect") for a, b in zip(pts, pts[1:])]
        elif k == "c":
            pts = bez(*[(q.x, q.y) for q in it[1:5]])
            out += [(a, b, False) for a, b in zip(pts, pts[1:])]
    if len(out) > 1:     # multi-segment polylines are graphics (arrows, coils), never pins; keep rect marker (0)
        out = [(a, b, ("rect" if s == "rect" else False)) for a, b, s in out]
    return [s for s in out if math.dist(s[0], s[1]) > 0.05]


def _hor(sg): return abs(sg[0][1] - sg[1][1]) < 0.05
def _ver(sg): return abs(sg[0][0] - sg[1][0]) < 0.05


def split_gnd(segs):
    """remove ground symbols (stem + >=3 shrinking parallel bars) from a segment list"""
    straight = [i for i, sg in enumerate(segs) if sg[2] is True]
    used = set()
    for orient in ("h", "v"):
        bars = [i for i in straight if (_hor(segs[i]) if orient == "h" else _ver(segs[i]))]
        # group by centre on the perpendicular axis
        def centre(i):
            a, b, _ = segs[i]
            return ((a[0] + b[0]) / 2) if orient == "h" else ((a[1] + b[1]) / 2)
        def pos(i):
            a, b, _ = segs[i]
            return a[1] if orient == "h" else a[0]
        def length(i): return math.dist(segs[i][0], segs[i][1])
        groups = collections.defaultdict(list)
        for i in bars: groups[round(centre(i), 0)].append(i)
        for c_, ids in groups.items():
            ids = sorted(ids, key=pos)
            # find runs of >=3 bars spaced <=3.5 with strictly shrinking length (either direction)
            for start in range(len(ids)):
                run = [ids[start]]
                for k in ids[start + 1:]:
                    if abs(pos(k) - pos(run[-1])) <= 3.5 and abs(pos(k) - pos(run[-1])) > 0.5: run.append(k)
                    else: break
                if len(run) < 3: continue
                L = [length(k) for k in run]
                if not (all(L[i] > L[i + 1] for i in range(len(L) - 1)) or all(L[i] < L[i + 1] for i in range(len(L) - 1))): continue
                top = run[0] if L[0] > L[-1] else run[-1]
                tb = segs[top]; mid = ((tb[0][0] + tb[1][0]) / 2, (tb[0][1] + tb[1][1]) / 2)
                stem = [i for i in straight if i not in run and (_ver(segs[i]) if orient == "h" else _hor(segs[i]))
                        and (math.dist(segs[i][0], mid) < 0.3 or math.dist(segs[i][1], mid) < 0.3)]
                if not stem: continue
                used.update(run); used.update(stem[:1])
                break
    keep = [sg for i, sg in enumerate(segs) if i not in used]
    gnd = [sg for i, sg in enumerate(segs) if i in used]
    return keep, gnd


def split_far(segs, refbox, gap=4.0):
    """cluster segments by proximity; keep the cluster(s) nearest the designator text"""
    n = len(segs)
    par = list(range(n))
    def f(i):
        while par[i] != i: par[i] = par[par[i]]; i = par[i]
        return i
    boxes = [(min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])) for a, b, _ in segs]
    for i in range(n):
        for j in range(i + 1, n):
            if bbox_dist(boxes[i], boxes[j]) <= gap: par[f(i)] = f(j)
    cl = collections.defaultdict(list)
    for i in range(n): cl[f(i)].append(i)
    if len(cl) <= 1: return segs, []
    def cbox(ids): return (min(boxes[i][0] for i in ids), min(boxes[i][1] for i in ids), max(boxes[i][2] for i in ids), max(boxes[i][3] for i in ids))
    dists = {k: bbox_dist(cbox(v), refbox) for k, v in cl.items()}
    best = min(dists.values())
    keep_k = {k for k, d in dists.items() if d <= best + 12}
    keep = [segs[i] for k in keep_k for i in cl[k]]
    far = [segs[i] for k in cl if k not in keep_k for i in cl[k]]
    return keep, far


class Fake:
    def __init__(self, page):
        self.p = page; self.rect = page.rect
        self._build()

    def _texts(self):
        groups = []
        for t in self.p.get_texttrace():
            s = "".join(chr(c[0]) for c in t["chars"])
            col = t["color"] or (0, 0, 0)
            rgb = (int(round(col[0] * 255)) << 16) | (int(round(col[1] * 255)) << 8) | int(round(col[2] * 255))
            if groups and groups[-1]["seq"] == t["seqno"] and groups[-1]["color"] == rgb:
                e = groups[-1]; e["text"] += s; bb = e["bbox"]
                e["bbox"] = (min(bb[0], t["bbox"][0]), min(bb[1], t["bbox"][1]), max(bb[2], t["bbox"][2]), max(bb[3], t["bbox"][3]))
            else:
                groups.append(dict(text=s, bbox=tuple(t["bbox"]), color=rgb, size=t["size"], dir=(round(t["dir"][0]), round(t["dir"][1])), seq=t["seqno"]))
        return [g for g in groups if g["text"].strip()]

    def _build(self):
        dr = self.p.get_drawings(extended=True)
        texts = self._texts()
        ev = [(d["seqno"], 0, i, d) for i, d in enumerate(dr)] + [(t["seq"], 1, i, t) for i, t in enumerate(texts)]
        ev.sort(key=lambda e: (e[0], e[1], e[2]))
        self.wires, self.juncs, self.ncs, self.dots = [], [], [], []
        objs = []
        state = dict(cur=None, last_text=None)
        def close():
            c = state["cur"]
            if c and (c["segs"] or c["texts"]): objs.append(c)
            state["cur"] = None
        for seq, kind, _, x in ev:
            cur = state["cur"]
            if kind == 0:
                d = x
                c, f = C(d.get("color")), C(d.get("fill"))
                items = d.get("items") or []
                if f == RED and items and items[0][0] == "c":
                    r = d["rect"]; self.juncs.append(((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2)); close(); continue
                if f == BLUEDOT and items and items[0][0] == "c":
                    r = d["rect"]; self.dots.append(((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2)); close()
                    state["cur"] = dict(segs=[], texts=[], grey=False, label=True); continue
                if c == NCX:
                    r = d["rect"]; self.ncs.append(((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2)); continue
                if c == RED:
                    for it in items:
                        if it[0] == "l": self.wires.append(((it[1].x, it[1].y), (it[2].x, it[2].y)))
                    close(); continue
                if c in (GREEN, GREY):
                    lt = state["last_text"]
                    r = d["rect"]; rb = (r.x0, r.y0, r.x1, r.y1)
                    far = lt is None and cur is not None and cur.get("lastbox") is not None and bbox_dist(rb, cur["lastbox"]) > 40
                    W_ = self.rect.width
                    if cur is not None and any(self._frame(sg) for sg in cur["segs"]):
                        far = True          # page frame / title block never continues into a symbol
                    if cur is None or cur.get("label") or far or (lt is not None and not self._continues(cur, lt)):
                        close(); state["cur"] = cur = dict(segs=[], texts=[], grey=c == GREY)
                    cur["segs"] += seg_list(d)
                    cur["lastbox"] = rb
                    state["last_text"] = None
                    continue
                # other colours: decorative parts of the current symbol (e.g. LED dies) - keep the object open
                continue
            else:
                t = x
                if cur is not None and t["color"] == 0x000000 and not cur.get("label"):
                    has_ref = any(REF.match(u["text"].strip()) and u["color"] in (0x0000ff, 0x999999) for u in cur["texts"])
                    named_port = cur["segs"] and not has_ref and any(u["color"] in (0x0000ff, 0x000000) for u in cur["texts"]) and                         not any(u["color"] == 0x000000 for u in cur["texts"]) is False
                    if has_ref or not cur["segs"]:
                        close(); cur = None
                if cur is None:
                    state["cur"] = cur = dict(segs=[], texts=[], grey=False)
                cur["texts"].append(t); state["last_text"] = t
        close()
        # fold reference-less fragments into a neighbouring part they touch (IC split by the far-jump rule)
        def has_ref(o): return any(REF.match(t["text"].strip()) and t["color"] in (0x0000ff, 0x999999) for t in o["texts"])
        def touches(o1, o2):
            # endpoints of one object lying on a rectangle edge (IC / resistor body) of the other
            for x, y in ((o1, o2), (o2, o1)):
                rects = [(c, d) for c, d, k in y["segs"] if k == "rect"]
                if not rects: continue
                xs = [q[0] for c, d in rects for q in (c, d)]; ys = [q[1] for c, d in rects for q in (c, d)]
                bx = (min(xs), min(ys), max(xs), max(ys))
                for a, b, _ in x["segs"]:
                    for p in (a, b):
                        if any(on_seg(p, c, d) for c, d in rects): return True
                        if bx[0] < p[0] < bx[2] and bx[1] < p[1] < bx[3] and has_ref(x): return True   # pin-1 dot etc. inside the body
            return False
        changed = True
        while changed:
            changed = False
            for i, o in enumerate(objs):
                if not o["segs"] or o.get("label") or has_ref(o): continue
                if any(self._frame(sg) for sg in o["segs"]): continue   # page frame
                for j in sorted(range(len(objs)), key=lambda j: abs(j - i)):
                    if j != i and has_ref(objs[j]) and touches(o, objs[j]):
                        objs[j]["segs"] += o["segs"]; objs[j]["texts"] = o["texts"] + objs[j]["texts"]
                        objs.pop(i); changed = True; break
                if changed: break
        self.objs = objs
        self._classify()

    def _frame(self, sg):
        a, b = sg[0], sg[1]
        W, H = self.rect.width, self.rect.height
        if math.dist(a, b) < 100: return False
        near = lambda p: p[0] < 14 or p[1] < 14 or p[0] > W - 14 or p[1] > H - 14
        return near(a) or near(b)

    def _continues(self, cur, t):
        """a drawing after text t continues the current object only inside an IC (pin texts interleaved)"""
        if any(REF.match(u["text"].strip()) and u["color"] in (0x0000ff, 0x999999) for u in cur["texts"]): return False
        s = t["text"].strip()
        if t["color"] == 0x000000: return True                    # pin name
        if t["color"] in (0x0000ff, 0x999999) and PINNUM.match(s): return True
        return False

    def _classify(self):
        segs_out = []
        self.textroles = {}
        self.rect_boxes = []
        for o in self.objs:
            if any(REF.match(t["text"].strip()) and t["color"] in (0x0000ff, 0x999999) for t in o["texts"]):
                rs = [sg for sg in o["segs"] if sg[2] == "rect"]
                if rs:
                    xs = [p_[0] for sg in rs for p_ in sg[:2]]; ys = [p_[1] for sg in rs for p_ in sg[:2]]
                    self.rect_boxes.append((min(xs), min(ys), max(xs), max(ys)))
        def in_rect(bb):
            return any(bb[0] >= r[0] - 2 and bb[2] <= r[2] + 2 and bb[1] >= r[1] - 2 and bb[3] <= r[3] + 2 for r in self.rect_boxes)
        self._in_rect = in_rect
        for o in self.objs:
            texts = o["texts"]; segs = o["segs"]
            refs = [t for t in texts if t["color"] in (0x0000ff, 0x999999) and REF.match(t["text"].strip())]
            if o.get("label"):
                for t in texts:
                    self.textroles[id(t)] = 0xff0000 if NAME.match(t["text"].strip()) else 0x123456
                continue
            if refs and segs:
                # (1) GND symbols drawn inside the part object: >=3 parallel bars, shrinking, centred on one axis
                segs, gsegs = split_gnd(segs)
                for a, b, st in gsegs: segs_out.append((a, b, "sym", id(o) + 2))
                # (2) keep only the spatial cluster(s) next to the designator
                far_ = []
                if not any(sg[2] == "rect" for sg in segs):
                    segs, far_ = split_far(segs, refs[-1]["bbox"])
                for a, b, st in far_: segs_out.append((a, b, "sym", id(o) + 3))
                o["segs"] = segs
                # graphics far outside the part's rectangle belong to other objects (net ports drawn in between)
                rects = [sg for sg in segs if sg[2] == "rect"]
                if rects:
                    xs = [p[0] for sg in rects for p in sg[:2]]; ys = [p[1] for sg in rects for p in sg[:2]]
                    rb = (min(xs), min(ys), max(xs), max(ys))
                    inside, outside = [], []
                    for sg in segs:
                        d_ = min(bbox_dist((p[0], p[1], p[0], p[1]), rb) for p in sg[:2])
                        (outside if d_ > 16 else inside).append(sg)
                    if outside:
                        for a, b, st in outside: segs_out.append((a, b, "sym", id(o) + 1))
                        segs = inside; o["segs"] = inside
                    o["_rb"] = rb
                # dedupe and join collinear straight pieces (a pin drawn as two strokes)
                seen = set(); ded = []
                for sg in segs:
                    k_ = tuple(sorted([(round(sg[0][0], 1), round(sg[0][1], 1)), (round(sg[1][0], 1), round(sg[1][1], 1))]))
                    if k_ in seen: continue
                    seen.add(k_); ded.append(sg)
                segs = ded
                merged = True
                while merged:
                    merged = False
                    for i in range(len(segs)):
                        a, b, st = segs[i]
                        if st is not True: continue
                        for j in range(len(segs)):
                            if i == j: continue
                            c, d_, st2 = segs[j]
                            if st2 is not True: continue
                            hor = abs(a[1] - b[1]) < 0.05 and abs(c[1] - d_[1]) < 0.05 and abs(a[1] - c[1]) < 0.05
                            ver = abs(a[0] - b[0]) < 0.05 and abs(c[0] - d_[0]) < 0.05 and abs(a[0] - c[0]) < 0.05
                            if not (hor or ver): continue
                            for p_, q_ in ((a, c), (a, d_), (b, c), (b, d_)):
                                if math.dist(p_, q_) < 0.1:
                                    others = [k for k in range(len(segs)) if k not in (i, j) and on_seg(p_, segs[k][0], segs[k][1])]
                                    if others: continue
                                    ends = [e for e in (a, b, c, d_) if math.dist(e, p_) >= 0.1]
                                    if len(ends) != 2: continue
                                    segs[i] = (ends[0], ends[1], True); segs.pop(j); merged = True; break
                            if merged: break
                        if merged: break
                o["segs"] = segs
                n = len(segs)
                deg = []
                for i, (a, b, st) in enumerate(segs):
                    ta = any(j != i and on_seg(a, segs[j][0], segs[j][1]) for j in range(n))
                    tb = any(j != i and on_seg(b, segs[j][0], segs[j][1]) for j in range(n))
                    deg.append((ta, tb))
                pins = set()
                for i, (a, b, st) in enumerate(segs):
                    if st is not True: continue
                    if not (abs(a[0] - b[0]) < 0.05 or abs(a[1] - b[1]) < 0.05): continue
                    if deg[i][0] == deg[i][1]: continue
                    pins.add(i)
                body = [segs[i] for i in range(n) if i not in pins]
                outline = [sg for sg in body if sg[2] == "rect"]
                if outline: body = outline
                if body:
                    xs = [p[0] for s_ in body for p in s_[:2]]; ys = [p[1] for s_ in body for p in s_[:2]]
                    x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
                    keep = set()
                    for i in pins:
                        a, b, _ = segs[i]; fr = a if not deg[i][0] else b
                        if x0 + 0.4 < fr[0] < x1 - 0.4 and y0 + 0.4 < fr[1] < y1 - 0.4: continue
                        keep.add(i)
                    pins = keep
                drop = set()
                if not pins:
                    # e.g. test points drawn as a curved hook: the piece touching a wire end is the pin
                    contact = None
                    for i, (a, b, st) in enumerate(segs):
                        for e in (a, b):
                            if any(math.dist(e, w[0]) < 0.5 or math.dist(e, w[1]) < 0.5 for w in self.wires):
                                contact = e; break
                        if contact: break
                    if contact:
                        J_ = [j for j, sg in enumerate(segs) if math.dist(sg[0], contact) < 0.3 or math.dist(sg[1], contact) < 0.3]
                        def inner_touch(j):
                            sg = segs[j]; other = sg[1] if math.dist(sg[0], contact) < 0.3 else sg[0]
                            return any(k != j and k not in J_ and on_seg(other, segs[k][0], segs[k][1]) for k in range(len(segs)))
                        good = [j for j in J_ if inner_touch(j)]
                        if good:
                            pin_j = max(good, key=lambda j: math.dist(segs[j][0], segs[j][1]))
                            pins.add(pin_j)
                            drop |= {j for j in J_ if j != pin_j}
                for i, (a, b, st) in enumerate(segs):
                    if i in drop: continue
                    segs_out.append((a, b, "pin" if i in pins else "body", id(o)))
                pinsegs = [segs[i] for i in pins]
                allx = [p_[0] for sg in segs for p_ in sg[:2]]; ally = [p_[1] for sg in segs for p_ in sg[:2]]
                pbox = (min(allx), min(ally), max(allx), max(ally)) if allx else None
                for t in texts:
                    s = t["text"].strip()
                    if pbox and t is not refs[-1] and bbox_dist(t["bbox"], pbox) > 25 and not in_rect(t["bbox"]):
                        # a text that wandered into this object (net-flag names are emitted late)
                        self.textroles[id(t)] = (0x000000 if POWERLIKE.match(s) else 0xff0000) if (NAME.match(s) and t["color"] == 0x000000) else 0x123456
                        continue
                    if t["color"] in (0x0000ff, 0x999999):
                        if REF.match(s) and t is refs[-1]:
                            m = re.match(r"^([A-Z]+\d+)\.(\d+)$", s)
                            if m: t["text"] = m.group(1) + chr(64 + int(m.group(2)))
                            self.textroles[id(t)] = 0x80
                            if o["grey"] or t["color"] == 0x999999: t["dnp"] = True
                        elif PINNUM.match(s) and any(bbox_dist(t["bbox"], (min(a[0], b[0]) - 1, min(a[1], b[1]) - 1, max(a[0], b[0]) + 1, max(a[1], b[1]) + 1)) < 4 for a, b, _ in pinsegs):
                            self.textroles[id(t)] = 0x000000
                        else:
                            self.textroles[id(t)] = 0x80
                    elif t["color"] == 0x000000:
                        rb = o.get("_rb")
                        if rb and bbox_dist(t["bbox"], rb) > 16 and NAME.match(s):
                            self.textroles[id(t)] = 0x000000 if POWERLIKE.match(s) else 0xff0000
                        else:
                            self.textroles[id(t)] = 0x004080
                    else:
                        self.textroles[id(t)] = 0x123456
            elif not segs:
                for t in texts:
                    s = t["text"].strip()
                    if t["color"] == 0x000000 and in_rect(t["bbox"]):
                        self.textroles[id(t)] = 0x004080; continue
                    self.textroles[id(t)] = 0xff0000 if (t["color"] == 0x000000 and NAME.match(s)) else 0x123456
            else:
                for a, b, st in segs: segs_out.append((a, b, "sym", id(o)))
                for t in texts:
                    s = t["text"].strip()
                    if t["color"] == 0x000000 and in_rect(t["bbox"]):
                        self.textroles[id(t)] = 0x004080; continue
                    if NAME.match(s) and not PROPRE.search(s) and segs and t["color"] in (0x0000ff, 0x000000, 0x999999):
                        self.textroles[id(t)] = 0x000000 if POWERLIKE.match(s) else 0xff0000
                    else:
                        self.textroles[id(t)] = 0x123456
        for o in self.objs:
            for t in o["texts"]: t["_obj"] = id(o)
            if any(self._frame(sg) for sg in o["segs"]):
                for t in o["texts"]:
                    if self.textroles.get(id(t)) != 0x123458: self.textroles[id(t)] = 0x123457   # page frame / title block text: drop
        # keep the sheet title ("图页" + value) for the generator, but never as a free note
        alltx = [t for o in self.objs for t in o["texts"]]
        for t0 in alltx:
            if t0["text"].strip() == "图页":
                cy = (t0["bbox"][1] + t0["bbox"][3]) / 2
                row = [t for t in alltx if t is not t0 and t["bbox"][0] > t0["bbox"][2] and abs((t["bbox"][1] + t["bbox"][3]) / 2 - cy) < 3]
                self.textroles[id(t0)] = 0x123458
                if row: self.textroles[id(min(row, key=lambda t: t["bbox"][0]))] = 0x123458
        # title block area (bottom-right block drawn with the frame) - drop free texts that fall inside it
        W, H = self.rect.width, self.rect.height
        for o in self.objs:
            for t in o["texts"]:
                bb = t["bbox"]
                if self.textroles.get(id(t)) in (None, 0x123456) and bb[0] > 0.42 * W and bb[1] > 0.82 * H:
                    self.textroles[id(t)] = 0x123457
                if self.textroles.get(id(t)) in (None, 0x123456) and (bb[1] < 12 or bb[3] > H - 12 or bb[0] < 12 or bb[2] > W - 12):
                    self.textroles[id(t)] = 0x123457
        self.segs_out = segs_out
        self.all_texts = [t for o in self.objs for t in o["texts"]]

    def get_drawings(self):
        out = []
        for a, b in self.wires:
            out.append({"color": W_OUT, "fill": None, "items": [("l", pymupdf.Point(*a), pymupdf.Point(*b))],
                        "rect": pymupdf.Rect(min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1]))})
        for j in self.juncs:
            out.append({"color": None, "fill": JUNC_OUT, "items": [("c", pymupdf.Point(j[0] + 1, j[1]), pymupdf.Point(j[0] + 1, j[1] - 0.5),
                                                                    pymupdf.Point(j[0] + 0.5, j[1] - 1), pymupdf.Point(j[0], j[1] - 1))],
                        "rect": pymupdf.Rect(j[0] - 1, j[1] - 1, j[0] + 1, j[1] + 1)})
        for a, b, role, oid in self.segs_out:
            col = {"pin": PIN_OUT, "body": BODY_OUT, "sym": PIN_OUT}[role]
            items = [("l", pymupdf.Point(*a), pymupdf.Point(*b))]
            if role == "sym":
                items = items + [("l", pymupdf.Point(*b), pymupdf.Point(*b))]   # not a lone 'l' -> never taken as a pin
            out.append({"color": col, "fill": None, "items": items, "_obj": oid,
                        "rect": pymupdf.Rect(min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1]))})
        return out

    def get_text(self, kind="dict"):
        blocks = []
        for t in self.all_texts:
            col = self.textroles.get(id(t), 0x123456)
            if col == 0x123457: continue
            blocks.append({"lines": [{"dir": t["dir"], "spans": [dict(text=t["text"].strip(), bbox=t["bbox"], color=col, size=t["size"], font="Arial", _obj=t.get("_obj"))]}]})
            if t.get("dnp"):
                bb = t["bbox"]
                blocks.append({"lines": [{"dir": (1, 0), "spans": [dict(text="DNP", bbox=(bb[0], bb[3] + 0.3, bb[0] + 12, bb[3] + 0.3 + 0.8 * t["size"]),
                                                                      color=0x00ff00, size=t["size"], font="x")]}]})
        return {"blocks": blocks}


def open_pages():
    d = pymupdf.open(PDF)
    return [Fake(d[i]) for i in range(len(d))]


if __name__ == "__main__":
    for i, f in enumerate(open_pages()):
        k = collections.Counter("part" if any(REF.match(t["text"]) for t in o["texts"]) else "label" if o.get("label") else "other" for o in f.objs)
        print(i + 1, dict(k), "pins", sum(1 for s in f.segs_out if s[2] == "pin"), "wires", len(f.wires))

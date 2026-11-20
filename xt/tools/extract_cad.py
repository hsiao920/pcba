# Extract schematic connectivity from Cadence-Capture-exported PDF pages (Rockchip style).
# Usage: python extract_cad.py <pdf> <outdir> [pages like 1-18]
import pymupdf, json, re, sys, math, os, collections

EPS = 0.35

def col(c):
    return tuple(round(x, 2) for x in c) if c else None

WIRE = (0.5, 0.0, 0.25)
RED = (1.0, 0.0, 0.0)
BLUE = (0.0, 0.0, 1.0)
JUNC = (1.0, 0.0, 1.0)

TXT_PINNUM = 0x000000
TXT_PINNAME = 0x004080
TXT_PROP = 0x000080
TXT_RED = 0xff0000

PROPRE = re.compile(r"^(?:[RCLDF]\d{4}|\d+(?:\.\d+)?[pnumµ]?[FHR]?|\d+(?:\.\d+)?[KkMRm]\d*(?:ohm)?|\d+(?:\.\d+)?%|\d+(?:\.\d+)?V|\d+(?:\.\d+)?A|X5R|X7R|NPO|NP0|C0G|DNP|TP|.*(?:SOT|SOD|DFN|QFN|BGA|SOP|IND_|LED_|SMD|FPC|0R).*)$")
REFDES = re.compile(r"^(?!ESD\d{4}[A-Z])(?:(?:R|C|L|D|U|Q|Y|X|J|P|FB|TP|SW|LED|FPC|USB|KEY|NTC|MOTOR|LS|BUZ|CN|CON|BT|F|K|T|MIC|SPK|ANT|H|E|B|S|VR|RT|TH|ZD|BZ|RN|CR|MH|PAD|ED|ESD|TVS|IR)\d{1,6}[A-Z]?|[A-Z]{2,5}_[A-Z]{1,3}\d{1,3})$")


class UF:
    def __init__(s): s.p = {}
    def f(s, a):
        s.p.setdefault(a, a)
        while s.p[a] != a:
            s.p[a] = s.p[s.p[a]]; a = s.p[a]
        return a
    def u(s, a, b):
        a, b = s.f(a), s.f(b)
        if a != b: s.p[a] = b


def bez(p0, p1, p2, p3, n=6):
    pts = []
    for i in range(n + 1):
        t = i / n; m = 1 - t
        pts.append((m**3*p0[0]+3*m*m*t*p1[0]+3*m*t*t*p2[0]+t**3*p3[0], m**3*p0[1]+3*m*m*t*p1[1]+3*m*t*t*p2[1]+t**3*p3[1]))
    return pts


def segs_of(d):
    out = []
    for it in d["items"]:
        k = it[0]
        if k == "l":
            a, b = it[1], it[2]
            out.append(((a.x, a.y), (b.x, b.y)))
        elif k == "re":
            r = it[1]
            pts = [(r.x0, r.y0), (r.x1, r.y0), (r.x1, r.y1), (r.x0, r.y1), (r.x0, r.y0)]
            out += list(zip(pts, pts[1:]))
        elif k == "c":
            pts = bez(*[(q.x, q.y) for q in it[1:5]])
            out += list(zip(pts, pts[1:]))
        elif k == "qu":
            q = it[1]
            pts = [(q.ul.x, q.ul.y), (q.ur.x, q.ur.y), (q.lr.x, q.lr.y), (q.ll.x, q.ll.y), (q.ul.x, q.ul.y)]
            out += list(zip(pts, pts[1:]))
    return out


def on_seg(p, a, b, eps=EPS):
    (x, y), (x1, y1), (x2, y2) = p, a, b
    dx, dy = x2 - x1, y2 - y1
    L2 = dx * dx + dy * dy
    if L2 < 1e-9:
        return math.hypot(x - x1, y - y1) <= eps
    t = ((x - x1) * dx + (y - y1) * dy) / L2
    if t < -eps / math.sqrt(L2) or t > 1 + eps / math.sqrt(L2): return False
    t = max(0, min(1, t))
    return math.hypot(x - (x1 + t * dx), y - (y1 + t * dy)) <= eps


def interior(p, a, b, eps=EPS):
    return on_seg(p, a, b, eps) and math.hypot(p[0]-a[0], p[1]-a[1]) > eps and math.hypot(p[0]-b[0], p[1]-b[1]) > eps


def same(p, q, eps=EPS):
    return abs(p[0] - q[0]) <= eps and abs(p[1] - q[1]) <= eps


class Grid:
    """spatial hash of segments"""
    def __init__(s, segs, cell=10.0):
        s.c = cell; s.h = collections.defaultdict(list); s.segs = segs
        for i, (a, b) in enumerate(segs):
            x0, x1 = sorted((a[0], b[0])); y0, y1 = sorted((a[1], b[1]))
            for gx in range(int((x0 - 1) // cell), int((x1 + 1) // cell) + 1):
                for gy in range(int((y0 - 1) // cell), int((y1 + 1) // cell) + 1):
                    s.h[(gx, gy)].append(i)
    def near(s, p):
        return s.h.get((int(p[0] // s.c), int(p[1] // s.c)), [])


def texts_of(page):
    out = []
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            for sp in l["spans"]:
                t = sp["text"]
                if not t.strip(): continue
                x0, y0, x1, y1 = sp["bbox"]
                out.append(dict(t=t.strip(), raw=t, bbox=[x0, y0, x1, y1], color=sp["color"], size=sp["size"],
                                dir=[round(l["dir"][0]), round(l["dir"][1])], font=sp["font"], used=None, obj=sp.get("_obj")))
    return out


def tcenter(t):
    b = t["bbox"]; return ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)


def rect_dist(b, p):
    dx = max(b[0] - p[0], 0, p[0] - b[2]); dy = max(b[1] - p[1], 0, p[1] - b[3])
    return math.hypot(dx, dy)


def bbox_dist(a, b):
    dx = max(a[0] - b[2], 0, b[0] - a[2]); dy = max(a[1] - b[3], 0, b[1] - a[3])
    return math.hypot(dx, dy)


def extract_page(page, pno, decode=None):
    dr = page.get_drawings()
    wires, reds, blues, juncs = [], [], [], []
    blue_obj = []
    redcurves = []
    for d in dr:
        c = col(d.get("color")); f = col(d.get("fill"))
        if f == JUNC and d.get("fill"):
            r = d["rect"]; juncs.append(((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2)); continue
        ss = [s for s in segs_of(d)]
        if c == WIRE:
            wires += [s for s in ss if not same(s[0], s[1], 0.01)]
        elif c == RED or f == RED:
            kinds = "".join(i[0] for i in d["items"])
            if "re" in d["items"][0][0] and len(d["items"]) == 1 and d["rect"].width > 8 and d["rect"].height > 8 and not d.get("fill"):
                continue          # red dashed/solid note frame, not a symbol
            for s in ss:
                if not same(s[0], s[1], 0.01): reds.append((s, kinds))
        elif c == BLUE or f == BLUE:
            nb = [s for s in ss if not same(s[0], s[1], 0.01)]
            blues += nb
            blue_obj += [d.get("_obj")] * len(nb)
    texts = texts_of(page)
    if decode:
        for t in texts: t["t"] = decode(t["t"])

    # ---- body groups (blue)
    uf = UF()
    bg = Grid(blues)
    hinted = any(o is not None for o in blue_obj)
    first = {}
    for i, (a, b) in enumerate(blues):
        uf.f(i)
        if hinted:
            o = blue_obj[i]
            if o in first: uf.u(i, first[o])
            else: first[o] = i
            continue
        for p in (a, b):
            for j in bg.near(p):
                if j != i and on_seg(p, *blues[j]): uf.u(i, j)
    groups = collections.defaultdict(list)
    for i in range(len(blues)): groups[uf.f(i)].append(i)
    # pass 1: merge groups whose boxes nearly touch (inner frames etc.)
    def regroup():
        gs = collections.defaultdict(list)
        for i in range(len(blues)): gs[uf.f(i)].append(i)
        return gs
    def gb(g):
        xs = [p[0] for i in g for p in blues[i]]; ys = [p[1] for i in g for p in blues[i]]
        return [min(xs), min(ys), max(xs), max(ys)]
    groups = regroup(); keys = list(groups); boxes = {k: gb(groups[k]) for k in keys}
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            if not hinted and bbox_dist(boxes[keys[i]], boxes[keys[j]]) < 1.2:
                uf.u(groups[keys[i]][0], groups[keys[j]][0])
    # count pin ends touching each group
    def pin_count():
        cnt = collections.Counter()
        for (s, kinds) in reds:
            if kinds != "l": continue
            a, b = s
            ha = {uf.f(j) for j in bg.near(a) if on_seg(a, *blues[j])}
            hb = {uf.f(j) for j in bg.near(b) if on_seg(b, *blues[j])}
            if (ha or hb) and not (ha and hb):
                for g in ha | hb: cnt[g] += 1
        return cnt
    cnt = pin_count()
    # pass 2: small bodies with one pin each that sit close together (cap plates, diode bar + triangle)
    groups = regroup(); keys = list(groups); boxes = {k: gb(groups[k]) for k in keys}
    pairs = []
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            bi, bj = boxes[keys[i]], boxes[keys[j]]
            if cnt[keys[i]] > 1 or cnt[keys[j]] > 1: continue
            small = max(bi[2]-bi[0], bi[3]-bi[1], bj[2]-bj[0], bj[3]-bj[1]) < 22
            ov = min(bi[2], bj[2]) - max(bi[0], bj[0]) > 2 or min(bi[3], bj[3]) - max(bi[1], bj[1]) > 2
            d = bbox_dist(bi, bj)
            if small and ov and d < 6.5 and not hinted: pairs.append((d, keys[i], keys[j]))
    pairs.sort()
    pc = {k: cnt[k] for k in keys}
    for d, ki, kj in pairs:
        ri, rj = uf.f(groups[ki][0]), uf.f(groups[kj][0])
        if ri == rj: continue
        tot = pc.get(ri, 0) + pc.get(rj, 0)
        if tot > 2: continue
        uf.u(groups[ki][0], groups[kj][0]); pc[uf.f(groups[ki][0])] = tot
    groups = regroup()
    gl = list(groups.values())
    gid = {}
    for k, g in enumerate(gl):
        for i in g: gid[i] = k
    gbox = [gb(g) for g in gl]

    # ---- pins: straight red segments with exactly one end on a body
    pins, other_red = [], []
    for (s, kinds) in reds:
        a, b = s
        straight = kinds == "l"
        ha = [gid[j] for j in bg.near(a) if on_seg(a, *blues[j])]
        hb = [gid[j] for j in bg.near(b) if on_seg(b, *blues[j])]
        if straight and (ha or hb) and not (ha and hb):
            inner, outer, g = (a, b, ha[0]) if ha else (b, a, hb[0])
            pins.append(dict(inner=inner, outer=outer, g=g))
        elif straight and ha and hb:
            pass
        else:
            other_red.append((s, kinds))

    # ---- red symbol groups (power, gnd, offpage)
    rsegs = [s for s, k in other_red]
    uf2 = UF(); rg = Grid(rsegs)
    for i, (a, b) in enumerate(rsegs):
        uf2.f(i)
        for p in (a, b):
            for j in rg.near(p):
                if j != i and on_seg(p, *rsegs[j], 0.25): uf2.u(i, j)
    rgroups = collections.defaultdict(list)
    for i in range(len(rsegs)): rgroups[uf2.f(i)].append(i)
    rgl = list(rgroups.values())

    # ---- connectivity points
    wg = Grid(wires)
    # node ids: ('w',i,end) etc. use coordinates rounded
    def key(p): return (round(p[0], 1), round(p[1], 1))
    U = UF()
    for a, b in wires:
        U.u(key(a), key(b))
    # wire endpoints on wire interior
    for i, (a, b) in enumerate(wires):
        for p in (a, b):
            for j in wg.near(p):
                if j != i and on_seg(p, *wires[j]):
                    U.u(key(p), key(wires[j][0]))
    # junction dots join crossing wires
    for jp in juncs:
        hits = [j for j in wg.near(jp) if on_seg(jp, *wires[j], 0.6)]
        for j in hits: U.u(key(jp), key(wires[j][0]))
    def attach(p):
        """return list of keys p connects to"""
        hits = [j for j in wg.near(p) if on_seg(p, *wires[j])]
        return [key(wires[j][0]) for j in hits]
    # pins
    for k, pn in enumerate(pins):
        pk = ("pin", k); U.f(pk)
        for h in attach(pn["outer"]): U.u(pk, h)
        U.u(pk, key(pn["outer"]))
    # pin-to-pin direct contact via coordinate key (done by key(outer))

    # red symbols: connection point = any segment endpoint that touches a wire or a pin outer end
    pin_outer = {}
    for k, pn in enumerate(pins): pin_outer.setdefault(key(pn["outer"]), []).append(k)
    syms = []
    for g in rgl:
        pts = [p for i in g for p in rsegs[i]]
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        box = [min(xs), min(ys), max(xs), max(ys)]
        conn = []
        for p in pts:
            hit_end = any(same(p, q) for j in wg.near(p) for q in wires[j])
            hit_mid = attach(p) and any(same(p, jp, 1.0) for jp in juncs)
            if hit_end or hit_mid or key(p) in pin_outer:
                conn.append(p)
        # wire ends that stop inside the symbol outline (offpage chevrons; small symbols only)
        small_sym = max(box[2] - box[0], box[3] - box[1]) < 15 or (box[2] - box[0]) < 12 or (box[3] - box[1]) < 12
        for (a, b) in (wires if small_sym else []):
            for p in (a, b):
                if box[0] - 0.4 <= p[0] <= box[2] + 0.4 and box[1] - 0.4 <= p[1] <= box[3] + 0.4:
                    conn.append(p)
        # dedupe
        cp = []
        for p in conn:
            if not any(same(p, q, 0.5) for q in cp): cp.append(p)

        syms.append(dict(box=box, conn=cp, nseg=len(g), segs=[rsegs[i] for i in g]))

    # ---- assign texts
    # pin numbers: black text near pin segment, outside body
    for k, pn in enumerate(pins):
        (x1, y1), (x2, y2) = pn["inner"], pn["outer"]
        mid = ((x1 + x2) / 2, (y1 + y2) / 2)
        horiz = abs(y1 - y2) < 0.1
        best = None
        for t in texts:
            if t["used"] or t["color"] != TXT_PINNUM: continue
            if not re.match(r"^[A-Z]{0,2}\d{1,3}$|^[A-Z0-9]{1,4}$", t["t"]): continue
            c = tcenter(t); bb = t["bbox"]
            if horiz:
                if not (min(x1, x2) - 1 <= c[0] <= max(x1, x2) + 1): continue
                if not (y1 - 8 <= bb[3] <= y1 + 1.5): continue
                d = abs(c[0] - mid[0]) + abs(bb[3] - y1)
            else:
                if not (min(y1, y2) - 1 <= c[1] <= max(y1, y2) + 1): continue
                if not (x1 - 8 <= bb[2] <= x1 + 1.5 or x1 - 1.5 <= bb[0] <= x1 + 8): continue
                d = abs(c[1] - mid[1]) + min(abs(bb[2] - x1), abs(bb[0] - x1))
            if best is None or d < best[0]: best = (d, t)
        pn["num"] = None
        if best:
            best[1]["used"] = ("pinnum", k); pn["num"] = best[1]["t"]
    for k, pn in enumerate(pins):
        (x1, y1), (x2, y2) = pn["inner"], pn["outer"]
        horiz = abs(y1 - y2) < 0.1
        best = None
        for t in texts:
            if t["used"] or t["color"] != TXT_PINNAME: continue
            bb = t["bbox"]; c = tcenter(t)
            if horiz:
                if not (bb[1] - 1 <= y1 <= bb[3] + 1): continue
                d = min(abs(bb[0] - x1), abs(bb[2] - x1))
            else:
                if not (bb[0] - 1 <= x1 <= bb[2] + 1): continue
                d = min(abs(bb[1] - y1), abs(bb[3] - y1))
            if d > 6: continue
            if best is None or d < best[0]: best = (d, t)
        pn["name"] = None
        if best:
            best[1]["used"] = ("pinname", k); pn["name"] = best[1]["t"]

    # ---- parts: refdes texts -> nearest body group
    gpins = collections.defaultdict(list)
    for k, pn in enumerate(pins): gpins[pn["g"]].append(k)
    cand = []
    reftexts = [t for t in texts if not t["used"] and t["color"] == TXT_PROP and REFDES.match(t["t"])]
    def has_above(t):
        tb = t["bbox"]
        for u in texts:
            if u is t or u["dir"] != t["dir"] or u["color"] not in (TXT_PROP,): continue
            ub = u["bbox"]
            if t["dir"] == [1, 0] and abs(ub[0] - tb[0]) < 1.0 and 0 <= tb[1] - ub[3] < 4.5 and REFDES.match(u["t"]):
                row = any(v is not t and abs(v["bbox"][1] - tb[1]) < 1 and 0 <= v["bbox"][0] - tb[2] < 6 for v in texts)
                return not row
        return False
    def pkg_under_ref(t):
        if not re.match(r"^[RCL](?:0201|0402|0603|0805|1206|1210)$", t["t"]): return False
        tb = t["bbox"]
        return any(u is not t and u["color"] == TXT_PROP and REFDES.match(u["t"]) and abs(u["bbox"][0] - tb[0]) < 1.0
                   and 0 < tb[1] - u["bbox"][1] < 20 for u in texts)
    reftexts = [t for t in reftexts if not has_above(t) and not pkg_under_ref(t)]
    def block(t):
        b = list(t["bbox"]); last = t["bbox"]
        if t["dir"] != [1, 0]: return b
        below = sorted([u for u in texts if not u["used"] and u is not t and u["dir"] == [1, 0] and u["size"] <= 7.5
                        and abs(u["bbox"][0] - t["bbox"][0]) < 9 and u["bbox"][1] > t["bbox"][1]
                        and not (u["color"] == TXT_PROP and REFDES.match(u["t"]))], key=lambda u: u["bbox"][1])
        for u in below:
            if u["bbox"][1] - last[3] > 4.5: break
            last = u["bbox"]; b = [min(b[0], last[0]), min(b[1], last[1]), max(b[2], last[2]), max(b[3], last[3])]
        return b
    for t in reftexts:
        tb = block(t)
        for g in gpins:
            gb_ = gbox[g]
            d = bbox_dist(tb, gb_)
            if t["bbox"][1] > gb_[3] - 0.5: d += 6      # refdes below the body: less likely
            ox = min(tb[2], gb_[2]) - max(tb[0], gb_[0]); oy = min(tb[3], gb_[3]) - max(tb[1], gb_[1])
            if ox > 0.8 and oy > 0.8: d += 5             # text overlapping a body is unlikely its label
            cand.append((d, id(t), t, g))
    if hinted:
        gobj = {}
        for g, members in enumerate(gl):
            gobj[g] = blue_obj[members[0]]
        byobj = collections.defaultdict(list)
        for t in texts:
            if not t["used"] and t["color"] == TXT_PROP and REFDES.match(t["t"]): byobj[t.get("obj")].append(t)
        cand = []
        for g in gpins:
            for t in byobj.get(gobj.get(g), []):
                cand.append((0.0, id(t), t, g))
    from scipy.optimize import linear_sum_assignment
    import numpy as np
    tl = list({id(t): t for _, _, t, _ in cand}.values()); gl_ = list(gpins)
    ti = {id(t): i for i, t in enumerate(tl)}; gi = {g: j for j, g in enumerate(gl_)}
    BIG = 1e6
    M = np.full((len(tl), len(gl_) + len(tl)), BIG)
    for d, _, t, g in cand:
        if d <= 35: M[ti[id(t)], gi[g]] = min(M[ti[id(t)], gi[g]], d)
    for i in range(len(tl)): M[i, len(gl_) + i] = 40.0      # leave refdes unmatched
    gref = {}
    if len(tl):
        rows, cols = linear_sum_assignment(M)
        for i, j in zip(rows, cols):
            if j < len(gl_) and M[i, j] < BIG:
                gref[gl_[j]] = tl[i]; tl[i]["used"] = ("ref", gl_[j])
    # orphan body groups (no refdes) merge into the nearest labelled group (multi-element parts: LED pairs, switches)
    for g in list(gpins):
        if g in gref or hinted: continue
        best = None
        for h in gref:
            d = bbox_dist(gbox[g], gbox[h])
            tiny = max(gbox[g][2] - gbox[g][0], gbox[g][3] - gbox[g][1]) < 4
            lim = 26 if (tiny and len(gpins[g]) <= 1) else 14 if len(gpins[g]) <= 1 else 11
            if d < lim and (best is None or d < best[0]): best = (d, h)
        if best:
            h = best[1]
            for k in gpins[g]: pins[k]["g"] = h
            gpins[h] += gpins.pop(g)
            gbox[h] = [min(gbox[h][0], gbox[g][0]), min(gbox[h][1], gbox[g][1]), max(gbox[h][2], gbox[g][2]), max(gbox[h][3], gbox[g][3])]
    # property texts: grow blocks from each refdes by chaining adjacent small texts
    blocks = {g: [list(t["bbox"])] for g, t in gref.items()}
    owner = {}
    cands = [u for u in texts if not u["used"] and (u["color"] in (TXT_PROP, TXT_PINNUM) or (u["color"] == 0x00ff00 and u["t"] == "DNP")) and u["size"] <= 7.5
             and not (u["color"] == TXT_PINNUM and re.match(r"^(?:VDD|VCC|AVDD|DVDD)_?[A-Z0-9_]+$", u["t"]))]
    changed = True
    while changed:
        changed = False
        for u in cands:
            if id(u) in owner: continue
            best = None
            for g, bl in blocks.items():
                for bb in bl:
                    d = bbox_dist(u["bbox"], bb)
                    if d < 3.2 and (best is None or d < best[0]): best = (d, g)
            if best:
                owner[id(u)] = best[1]; blocks[best[1]].append(list(u["bbox"])); changed = True
    # leftovers that look like part properties: nearest labelled body/block
    for u in cands:
        if id(u) in owner: continue
        if not (u["color"] == TXT_PROP or PROPRE.search(u["t"])): continue
        best = None
        for g in blocks:
            d = min([bbox_dist(u["bbox"], gbox[g])] + [bbox_dist(u["bbox"], bb) for bb in blocks[g]])
            if d < 20 and (best is None or d < best[0]): best = (d, g)
        if best:
            owner[id(u)] = best[1]
    propmap = collections.defaultdict(list)
    if hinted:
        g_of_obj = {}
        for g in gref: g_of_obj[gobj.get(g)] = g
        for u in texts:
            if u["used"] or u["color"] not in (TXT_PROP, 0x00ff00): continue
            g = g_of_obj.get(u.get("obj"))
            if g is not None: propmap[g].append(u); u["used"] = ("prop", g)
        for u in cands:
            if not u["used"] and id(u) in owner and not propmap.get(owner[id(u)]):
                propmap[owner[id(u)]].append(u); u["used"] = ("prop", owner[id(u)])
    else:
        for u in cands:
            if id(u) in owner: propmap[owner[id(u)]].append(u); u["used"] = ("prop", owner[id(u)])
    parts = []
    for g, ks in gpins.items():
        t = gref.get(g)
        ref = t["t"] if t else None
        props = sorted(propmap.get(g, []), key=lambda u: (round(u["bbox"][1]), u["bbox"][0]))
        parts.append(dict(g=g, ref=ref, refbox=t["bbox"] if t else None, props=[[u["t"], u["color"], u["bbox"]] for u in props],
                          box=gbox[g], pins=ks))

    # ---- symbol names: offpage (red text, one per connection point), power (black text), else ground
    nsyms = []
    def on_wire_text(t):
        """red text lying on top of a horizontal wire (net alias, not an off-page glyph name)"""
        if t["dir"] != [1, 0]: return False
        tb = t["bbox"]
        for (wa, wb) in wires:
            if abs(wa[1] - wb[1]) < 0.05 and abs(wa[1] - tb[3]) < 1.6 and min(tb[2], max(wa[0], wb[0])) - max(tb[0], min(wa[0], wb[0])) > 0.8 * (tb[2] - tb[0]):
                return True
        return False
    pairs = []
    for si, s in enumerate(syms):
        bx = s["box"]
        for pi_, p in enumerate(s["conn"]):
            for ti, t in enumerate(texts):
                if t["used"] or t["color"] != TXT_RED or not re.match(r"^[A-Za-z_+][A-Za-z0-9_+\-./#\[\]]{0,48}$", t["t"]): continue
                tb = t["bbox"]; c = tcenter(t)
                if t["dir"] == [1, 0]:
                    dy = abs(c[1] - p[1]); d = max(bx[0] - tb[2], tb[0] - bx[2], 0)
                else:
                    dy = abs(c[0] - p[0]); d = max(bx[1] - tb[3], tb[1] - bx[3], 0)
                if dy <= 3.5 and d < 40 and not (d > 6 and not hinted and on_wire_text(t)): pairs.append((dy * 4 + d, si, pi_, ti))
    pairs.sort()
    taken_p, taken_t, offmap = set(), set(), {}
    for cost, si, pi_, ti in pairs:
        if (si, pi_) in taken_p or ti in taken_t: continue
        taken_p.add((si, pi_)); taken_t.add(ti); offmap[(si, pi_)] = texts[ti]
    for si, s in enumerate(syms):
        if not s["conn"]:
            continue
        bx = s["box"]
        for pi_, p in enumerate(s["conn"]):
            if (si, pi_) in offmap:
                t = offmap[(si, pi_)]; t["used"] = ("sym",)
                nsyms.append(dict(kind="offpage", name=t["t"], conn=[p], box=bx, segs=s["segs"], tbox=t["bbox"]))
                continue
            best = None
            for t in texts:
                if t["used"] or t["color"] != TXT_PINNUM: continue
                if not re.match(r"^[A-Za-z0-9_+\-.\/]{2,32}$", t["t"]): continue
                d = bbox_dist(t["bbox"], bx)
                if d < 6 and (best is None or d < best[0]): best = (d, t)
            if best:
                best[1]["used"] = ("sym",)
                nsyms.append(dict(kind="power", name=best[1]["t"], conn=[p], box=bx, segs=s["segs"], tbox=best[1]["bbox"]))
            else:
                axis = all(abs(a_[0] - b_[0]) < 0.05 or abs(a_[1] - b_[1]) < 0.05 for a_, b_ in s["segs"])
                taken = any(same(p, q["conn"][0], 0.5) for q in nsyms if q["kind"] == "offpage") or                         any(same(p, s2["conn"][pj], 0.5) for (si2, pj), _t in offmap.items() for s2 in [syms[si2]])
                if axis and not taken:
                    nsyms.append(dict(kind="gnd", name="GND", conn=[p], box=bx, segs=s["segs"], tbox=None))
    syms = nsyms

    # ---- net aliases: remaining texts lying on a wire
    aliases = []
    for t in texts:
        if t["used"]: continue
        if t["color"] not in (TXT_PINNUM, TXT_RED): continue
        if t["color"] == TXT_PINNUM and PROPRE.search(t["t"]): continue
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_+\-./\[\]#~]{0,48}$", t["t"]): continue
        bb = t["bbox"]
        if t["dir"] == [1, 0]:
            p = ((bb[0] + bb[2]) / 2, bb[3])
            best = None
            near = set()
            for xx in range(int(bb[0]), int(bb[2]) + 2, 5): near.update(wg.near((xx, bb[3])))
            for j in near:
                (a, b) = wires[j]
                if abs(a[1] - b[1]) > 0.05: continue
                if min(bb[2], max(a[0], b[0])) - max(bb[0], min(a[0], b[0])) < 1.0: continue
                dy = a[1] - bb[3]
                if -1.5 <= dy <= 3.0:
                    if best is None or abs(dy) < best[0]: best = (abs(dy), j)
            if best:
                aliases.append(dict(name=t["t"], wire=best[1], at=(p[0], wires[best[1]][0][1]), bbox=bb, dir=t["dir"]))
                t["used"] = ("alias",)
        else:
            p = (bb[2], (bb[1] + bb[3]) / 2) if t["dir"] == [0, -1] else (bb[0], (bb[1] + bb[3]) / 2)
            best = None
            for j in wg.near(p) + wg.near((bb[2], bb[1])) + wg.near((bb[2], bb[3])):
                (a, b) = wires[j]
                if abs(a[0] - b[0]) > 0.05: continue
                if not (min(a[1], b[1]) - 1 <= p[1] <= max(a[1], b[1]) + 1): continue
                dx = a[0] - bb[2]
                if -1.5 <= dx <= 3.0:
                    if best is None or abs(dx) < best[0]: best = (abs(dx), j)
            if best:
                aliases.append(dict(name=t["t"], wire=best[1], at=(wires[best[1]][0][0], p[1]), bbox=bb, dir=t["dir"]))
                t["used"] = ("alias",)

    # ---- nets
    for k, pn in enumerate(pins): U.f(("pin", k))
    for si, s in enumerate(syms):
        for p in s["conn"]:
            U.u(("sym", si), key(p))
            for h in attach(p): U.u(("sym", si), h)
    for a in aliases:
        U.u(("alias", a["name"], id(a)), key(wires[a["wire"]][0]))
    netname = collections.defaultdict(set)
    for si, s in enumerate(syms):
        if s["conn"] and s["name"]:
            netname[U.f(("sym", si))].add((s["kind"], s["name"]))
    for a in aliases:
        netname[U.f(("alias", a["name"], id(a)))].add(("alias", a["name"]))
    nets = collections.defaultdict(list)
    for k, pn in enumerate(pins):
        nets[U.f(("pin", k))].append(k)

    junk = [t for t in texts if not t["used"]]
    return dict(page=pno, size=[page.rect.width, page.rect.height], wires=wires, juncs=juncs, pins=pins, parts=parts,
                syms=syms, aliases=aliases, U=U, netname=netname, nets=nets, texts=texts, blues=blues,
                gl=gl, unused=junk)


if __name__ == "__main__":
    pdf = sys.argv[1]
    doc = pymupdf.open(pdf)
    for pno in range(len(doc)):
        r = extract_page(doc[pno], pno + 1)
        npins = len(r["pins"]); unnum = sum(1 for p in r["pins"] if not p["num"])
        noref = [p for p in r["parts"] if not p["ref"]]
        print(f"p{pno+1}: wires {len(r['wires'])} pins {npins} (no num {unnum}) parts {len(r['parts'])} noref {len(noref)} syms {len([s for s in r['syms'] if s['conn']])} aliases {len(r['aliases'])} nets {len(r['nets'])}")

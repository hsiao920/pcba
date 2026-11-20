# Walk each 2A current path and report widths in series. Usage: python tools/path_check.py
import json, math, heapq, collections, os, itertools
H = os.path.dirname(os.path.abspath(__file__))
d = json.load(open(os.path.join(H, "tracks.json"))); pads = json.load(open(os.path.join(H, "pads.json")))["pads"]
def padxy(ref, num):
    for p in pads:
        if p["ref"] == ref and p["num"] == num: return p["x"], p["y"]
def build(net):
    pts = {}; adj = collections.defaultdict(list)
    def node(x, y, l):
        k = (round(x / 0.06), round(y / 0.06), l); pts.setdefault(k, (x, y, l)); return k
    for t in d["tracks"]:
        if t["net"] != net: continue
        a = node(t["x1"], t["y1"], t["layer"]); b = node(t["x2"], t["y2"], t["layer"]); L = math.hypot(t["x2"] - t["x1"], t["y2"] - t["y1"])
        adj[a].append((b, t["w"], L, t["layer"])); adj[b].append((a, t["w"], L, t["layer"]))
    def dist_seg(px, py, x1, y1, x2, y2):
        dx, dy = x2 - x1, y2 - y1; L2 = dx * dx + dy * dy or 1e-9
        u = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / L2)); return math.hypot(px - x1 - u * dx, py - y1 - u * dy)
    for v in d["vias"]:
        if v["net"] != net: continue
        vn = (round(v["x"], 2), round(v["y"], 2), "via")
        for t in d["tracks"]:
            if t["net"] != net: continue
            if dist_seg(v["x"], v["y"], t["x1"], t["y1"], t["x2"], t["y2"]) <= t["w"] / 2 + 0.31:
                for (x, y) in ((t["x1"], t["y1"]), (t["x2"], t["y2"])):
                    k = node(x, y, t["layer"])
                    adj[k].append((vn, t["w"], 0.0, "via")); adj[vn].append((k, t["w"], 0.0, "via"))
    return adj, pts
def walk(net, a, b):
    adj, pts = build(net)
    near = lambda xy: min(pts, key=lambda k: (pts[k][0] - xy[0]) ** 2 + (pts[k][1] - xy[1]) ** 2)
    s, t = near(a), near(b); best = {s: 99}; prev = {}; c = itertools.count(); q = [(-99, next(c), s)]
    while q:
        w, _, u = heapq.heappop(q); w = -w
        if u == t: break
        if w < best.get(u, 0): continue
        for v, wid, L, lay in adj[u]:
            nw = min(w, wid)
            if nw > best.get(v, 0): best[v] = nw; prev[v] = (u, wid, L, lay); heapq.heappush(q, (-nw, next(c), v))
    if t not in best: return None
    path = []; u = t
    while u != s:
        pu, wid, L, lay = prev[u]; path.append((wid, L, lay)); u = pu
    return path[::-1]
JOBS = (("J1 VBUS pads A4/B9 -> U3 VIN", "VBUS1", ("J1", "A4"), ("U3", "A2")), ("J1 VBUS pads A9/B4 -> U3 VIN", "VBUS1", ("J1", "A9"), ("U3", "A2")),
        ("J2 VBUS pads A4/B9 -> U4 VIN", "VBUS2", ("J2", "A4"), ("U4", "A2")), ("J2 VBUS pads A9/B4 -> U4 VIN", "VBUS2", ("J2", "A9"), ("U4", "A2")),
        ("U3 VOUT -> F1 pad 1", "VSW", ("U3", "A1"), ("F1", "1")), ("U4 VOUT -> F1 pad 1", "VSW", ("U4", "A1"), ("F1", "1")),
        ("F1 pad 2 -> J3 VBUS", "OUT_VBUS", ("F1", "2"), ("J3", "1")))
for name, net, a, b in JOBS:
    p = walk(net, padxy(*a), padxy(*b))
    if not p: print(name, "NO PATH"); continue
    segs = [(round(w, 2), round(L, 2), l) for w, L, l in p if l != "via"]
    if not segs: print(name, "(start and end on the same copper, no series segment)"); continue
    narrow = [s for s in segs if s[0] < 0.9]
    print("%-30s %5.1f mm, %d layer hops (3 vias each) | widest-path min width %.2f mm | segments < 0.9 mm: %s" %
          (name, sum(L for _, L, _ in p), sum(1 for _, _, l in p if l == "via") // 2, min(s[0] for s in segs), narrow))

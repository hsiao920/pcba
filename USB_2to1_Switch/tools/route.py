# -*- coding: utf-8 -*-
"""Small grid router (2 copper layers, A*) for the USB switch board.
Input : tools/pads.json (from build_pcb.py)      Output: tools/tracks.json
Usage : python route.py        (system python with numpy + scipy)
Rules : see RULES below.  Routing is done with a narrow track first, then every segment is widened up to the
net-class width wherever the clearance map allows it (neck-down near fine-pitch pads)."""
import json, os, sys, math, heapq, time
import numpy as np
from scipy.ndimage import distance_transform_edt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import design
import placement as _pl
FUSE_XY = (_pl.PLACE["F1"][0], _pl.PLACE["F1"][1])

DEBUG = os.environ.get('RDEBUG') == '1'
G = 0.05                      # grid (mm)
VIA_D, VIA_DRILL = 0.6, 0.3
EDGE = 0.35                   # copper to board edge
NARROW = 0.25
VIA_COST = 24.0
BOTTOM_PENALTY = 1.8

NETW = dict(design.NET_CLASS)   # name -> (width, clearance)
NETW["VBUS1"] = (1.0, 0.2); NETW["VBUS2"] = (1.0, 0.2); NETW["OUT_VBUS"] = (1.2, 0.2); NETW["VSW"] = (1.2, 0.2)
ORDER_FIRST = ["D1P", "D1N", "D2P", "D2N", "S", "S_DRV", "D3P", "D3N", "D4P", "D4N", "VSW", "OUT_VBUS", "VBUS1", "VBUS2", "+5V", "+3V3", "ON1", "ON2", "S_DRV", "CMD"]


def load():
    d = json.load(open(os.path.join(HERE, "pads.json"), encoding="utf-8"))
    return d


def main():
    t0 = time.time()
    d = load()
    W, H = d["W"], d["H"]
    nx, ny = int(round(W / G)), int(round(H / G))
    netnames = sorted({p["net"] for p in d["pads"] if p["net"]})
    nid = {n: i + 1 for i, n in enumerate(netnames)}
    own = np.zeros((2, nx, ny), dtype=np.int16)          # layer 0 = F.Cu, 1 = B.Cu

    def box(l, x0, y0, x1, y1, val):
        i0 = max(int(math.floor(x0 / G)), 0); i1 = min(int(math.ceil(x1 / G)), nx)
        j0 = max(int(math.floor(y0 / G)), 0); j1 = min(int(math.ceil(y1 / G)), ny)
        if i1 > i0 and j1 > j0:
            own[l, i0:i1, j0:j1] = val

    def disc(l, x, y, r, val):
        i0 = max(int(math.floor((x - r) / G)), 0); i1 = min(int(math.ceil((x + r) / G)) + 1, nx)
        j0 = max(int(math.floor((y - r) / G)), 0); j1 = min(int(math.ceil((y + r) / G)) + 1, ny)
        if i1 <= i0 or j1 <= j0:
            return
        xs = (np.arange(i0, i1) + 0.5) * G; ys = (np.arange(j0, j1) + 0.5) * G
        m = (xs[:, None] - x) ** 2 + (ys[None, :] - y) ** 2 <= r * r
        sub = own[l, i0:i1, j0:j1]
        if val > 0:
            sub[m & (sub == 0)] = val
        else:
            sub[m] = val

    # ---- board edge
    for l in (0, 1):
        box(l, 0, 0, W, EDGE, -1); box(l, 0, H - EDGE, W, H, -1)
        box(l, 0, 0, EDGE, H, -1); box(l, W - EDGE, 0, W, H, -1)
    # ---- pads
    padcells = {}
    for pi, p in enumerate(d["pads"]):
        w, h = p["w"], p["h"]
        if int(round(p["ang"])) % 180 == 90:
            w, h = h, w
        val = nid.get(p["net"], -1)
        lays = [0 if L == "F" else 1 for L in p["layers"] if L in ("F", "B")]
        if p["npth"]:
            for l in (0, 1):
                disc(l, p["x"], p["y"], p["drill"] / 2 + 0.25, -1)
            continue
        for l in lays:
            if p["shape"] == "circle":
                disc(l, p["x"], p["y"], w / 2, val)
            else:
                box(l, p["x"] - w / 2, p["y"] - h / 2, p["x"] + w / 2, p["y"] + h / 2, val)
        if p["thru"]:
            for l in (0, 1):
                disc(l, p["x"], p["y"], p["drill"] / 2 + 0.1, val)
    hole_block = np.zeros((nx, ny), dtype=bool)
    for p in d["pads"]:
        if p["thru"] or p["npth"]:
            r = p["drill"] / 2 + VIA_DRILL / 2 + 0.30
            xs = (np.arange(nx) + 0.5) * G; ys = (np.arange(ny) + 0.5) * G
            i0 = max(int((p["x"] - r) / G) - 1, 0); i1 = min(int((p["x"] + r) / G) + 2, nx)
            j0 = max(int((p["y"] - r) / G) - 1, 0); j1 = min(int((p["y"] + r) / G) + 2, ny)
            m = (xs[i0:i1, None] - p["x"]) ** 2 + (ys[None, j0:j1] - p["y"]) ** 2 <= r * r
            hole_block[i0:i1, j0:j1] |= m
    pad_by_net = {}
    for p in d["pads"]:
        if p["net"] and not p["npth"]:
            pad_by_net.setdefault(p["net"], []).append(p)

    tracks, vias = [], []

    def cls(n):
        return NETW.get(n, design.DEFAULT_CLASS)

    def pad_mask(p, l, n):
        """cells of pad p on layer l (own == nid and within pad bbox)"""
        w, h = p["w"], p["h"]
        if int(round(p["ang"])) % 180 == 90:
            w, h = h, w
        r = max(w, h) / 2 + 0.05
        i0 = max(int((p["x"] - r) / G), 0); i1 = min(int((p["x"] + r) / G) + 2, nx)
        j0 = max(int((p["y"] - r) / G), 0); j1 = min(int((p["y"] + r) / G) + 2, ny)
        sub = own[l, i0:i1, j0:j1] == nid[n]
        ii, jj = np.nonzero(sub)
        return [(l, int(i + i0), int(j + j0)) for i, j in zip(ii, jj)]

    def route_net(n, goal_via=False, only_pads=None):
        width, clr = cls(n)
        clr = 0.17
        wroute = NARROW
        h = wroute / 2
        nidn = nid[n]
        foreign = [(own[l] != 0) & (own[l] != nidn) for l in (0, 1)]
        D = [distance_transform_edt(~foreign[l]) * G for l in (0, 1)]
        okT = [(D[l] >= h + clr) | (own[l] == nidn) for l in (0, 1)]
        okV = (D[0] >= VIA_D / 2 + clr) & (D[1] >= VIA_D / 2 + clr) & (own[0] != nidn) & (own[1] != nidn)
        okV = okV & (D[0] >= 0) & (own[0] == 0) & (own[1] == 0) & (~hole_block)
        for v in vias:
            r = VIA_D + 0.25
            i0 = max(int((v["x"] - r) / G) - 1, 0); i1 = min(int((v["x"] + r) / G) + 2, nx)
            j0 = max(int((v["y"] - r) / G) - 1, 0); j1 = min(int((v["y"] + r) / G) + 2, ny)
            xs = (np.arange(i0, i1) + 0.5) * G; ys = (np.arange(j0, j1) + 0.5) * G
            okV[i0:i1, j0:j1] &= ~(((xs[:, None] - v["x"]) ** 2 + (ys[None, :] - v["y"]) ** 2) <= r * r)
        pads = pad_by_net.get(n, [])
        if only_pads is not None:
            srcs = only_pads
        else:
            srcs = pads
        ok_count = 0
        if goal_via:
            for p in srcs:
                if not route_one(n, p, None, okT, okV, D, wroute, width, clr, h, goal_via=True):
                    print("   !! GND stub failed", p["ref"], p["num"])
            return
        # Prim: start from the pad nearest to the centroid of all pads
        if n in main_done:
            mainp = [q for q in pads if (q["ref"], q["num"]) in POWER_MAIN[n]]
            # target = only the reserved trunk copper (tracks/vias), never other, still unconnected pads of the net
            tree = {0: set(), 1: set()}
            for tr in tracks:
                if tr["net"] == n:
                    l_ = 0 if tr["layer"] == "F" else 1
                    k_ = max(int(math.hypot(tr["x2"] - tr["x1"], tr["y2"] - tr["y1"]) / (G * 0.5)), 1)
                    for t_ in range(k_ + 1):
                        cx_ = tr["x1"] + (tr["x2"] - tr["x1"]) * t_ / k_; cy_ = tr["y1"] + (tr["y2"] - tr["y1"]) * t_ / k_
                        for di_ in range(-int(tr["w"] / 2 / G), int(tr["w"] / 2 / G) + 1):
                            for dj_ in range(-int(tr["w"] / 2 / G), int(tr["w"] / 2 / G) + 1):
                                if di_ * di_ + dj_ * dj_ <= (tr["w"] / 2 / G) ** 2:
                                    tree[l_].add((int(cx_ / G) + di_, int(cy_ / G) + dj_))
            for v_ in vias:
                if v_["net"] == n:
                    for l_ in (0, 1):
                        tree[l_].add((int(v_["x"] / G), int(v_["y"] / G)))
            tree_pads = mainp
            rest = [q for q in pads if (q["ref"], q["num"]) not in POWER_MAIN[n]]
        else:
            tree_pads = [pads[0]]
            tree = {0: set(), 1: set()}
            for l in (0, 1):
                tree[l].update((i, j) for (_, i, j) in pad_mask(pads[0], l, n))
            rest = pads[1:]
        fails = 0
        while rest:
            # nearest unconnected pad to the tree pads
            best = min(rest, key=lambda q: min((q["x"] - t["x"]) ** 2 + (q["y"] - t["y"]) ** 2 for t in tree_pads))
            rest.remove(best)
            ok = route_one(n, best, tree, okT, okV, D, wroute, width, clr, h)
            print('   ', n, best['ref'], best['num'], 'ok' if ok else 'FAIL', flush=True)
            if ok:
                tree_pads.append(best)
            else:
                fails += 1
                print("   !! FAILED", n, best["ref"], best["num"])
        return fails

    def route_one(n, p, tree, okT, okV, D, wroute, width, clr, h, goal_via=False):
        nidn = nid[n]
        src = []
        for l in (0, 1):
            src += pad_mask(p, l, n)
        if not src:
            return False
        srcset = {(l, i, j) for (l, i, j) in src}
        if not goal_via:
            tmin_i = min(i for l in (0, 1) for (i, j) in tree[l]); tmax_i = max(i for l in (0, 1) for (i, j) in tree[l])
            tmin_j = min(j for l in (0, 1) for (i, j) in tree[l]); tmax_j = max(j for l in (0, 1) for (i, j) in tree[l])
        for margin_mm, cap in ((8.0, 120000), (25.0, 350000), (80.0, 2500000)):
            mi = int(margin_mm / G)
            si = [i for (_, i, _) in src]; sj = [j for (_, _, j) in src]
            if goal_via:
                bi0, bi1, bj0, bj1 = min(si), max(si), min(sj), max(sj)
            else:
                bi0, bi1 = min(min(si), tmin_i), max(max(si), tmax_i); bj0, bj1 = min(min(sj), tmin_j), max(max(sj), tmax_j)
            i0, i1 = max(bi0 - mi, 0), min(bi1 + mi, nx - 1); j0, j1 = max(bj0 - mi, 0), min(bj1 + mi, ny - 1)
            if DEBUG: print('      try', n, p['ref'], p['num'], 'src', len(src), 'win', (i0, i1, j0, j1), 'cap', cap, flush=True)
            path = astar(n, src, srcset, tree, okT, okV, goal_via, (i0, i1, j0, j1), cap,
                         (tmin_i, tmax_i, tmin_j, tmax_j) if not goal_via else None)
            if path:
                commit(n, path, D, wroute, width, clr, p, tree, goal_via)
                return True
        return False

    DIRS = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0), (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414)]

    def astar(n, src, srcset, tree, okT, okV, goal_via, win, cap, tb, goal_mask=None):
        nexp = 0
        i0, i1, j0, j1 = win
        sw, sh = i1 - i0 + 1, j1 - j0 + 1
        INF = 1e18
        g = np.full((2, sw, sh), INF, dtype=np.float64)
        par = np.full((2, sw, sh, 3), -1, dtype=np.int32)
        openq = []
        tl = tree if tree is not None else None

        def hfun(i, j):
            if goal_via or goal_mask is not None:
                return 0.0
            dxi = max(tb[0] - i, 0, i - tb[1]); dyj = max(tb[2] - j, 0, j - tb[3])
            a, b = (dxi, dyj) if dxi >= dyj else (dyj, dxi)
            return b * 1.414 + (a - b)

        for (l, i, j) in src:
            if i0 <= i <= i1 and j0 <= j <= j1:
                g[l, i - i0, j - j0] = 0.0
                heapq.heappush(openq, (hfun(i, j), 0.0, l, i, j, -1))
        allowT = okT
        while openq:
            nexp += 1
            if nexp > cap:
                return None
            f, gc, l, i, j, _ = heapq.heappop(openq)
            if gc > g[l, i - i0, j - j0] + 1e-9:
                continue
            # goal test
            if goal_mask is not None:
                if goal_mask[l][i, j] and (l, i, j) not in srcset:
                    return rebuild(par, l, i, j, i0, j0, src)
            elif goal_via:
                if okV[i, j] and (l, i, j) not in srcset:
                    return rebuild(par, l, i, j, i0, j0, src)
            else:
                if (i, j) in tl[l] and (l, i, j) not in srcset:
                    return rebuild(par, l, i, j, i0, j0, src)
            pl = par[l, i - i0, j - j0]
            for di, dj, c in DIRS:
                ni, nj = i + di, j + dj
                if ni < i0 or ni > i1 or nj < j0 or nj > j1:
                    continue
                if not allowT[l][ni, nj]:
                    continue
                if di and dj and not (allowT[l][i + di, j] and allowT[l][i, j + dj]):
                    continue
                cost = c * (BOTTOM_PENALTY if l == 1 else 1.0)
                if pl[0] >= 0:
                    pdi, pdj = i - (pl[1] + 0), j - (pl[2] + 0)
                    # bend penalty
                    if (pdi, pdj) != (di, dj) and pl[0] == l:
                        cost += 0.35
                ng = gc + cost
                if ng < g[l, ni - i0, nj - j0]:
                    g[l, ni - i0, nj - j0] = ng
                    par[l, ni - i0, nj - j0] = (l, i, j)
                    heapq.heappush(openq, (ng + hfun(ni, nj), ng, l, ni, nj, 0))
            # via
            if okV[i, j] and allowT[1 - l][i, j]:
                nl = 1 - l
                ng = gc + VIA_COST
                if ng < g[nl, i - i0, j - j0]:
                    g[nl, i - i0, j - j0] = ng
                    par[nl, i - i0, j - j0] = (l, i, j)
                    heapq.heappush(openq, (ng + hfun(i, j), ng, nl, i, j, 1))
        return None

    def rebuild(par, l, i, j, i0, j0, src):
        path = [(l, i, j)]
        while True:
            pl, pi, pj = par[l, i - i0, j - j0]
            if pl < 0:
                break
            l, i, j = int(pl), int(pi), int(pj)
            path.append((l, i, j))
        path.reverse()
        return path

    def cell_xy(i, j):
        return (i + 0.5) * G, (j + 0.5) * G

    def commit(n, path, D, wroute, width, clr, pad, tree, goal_via):
        nidn = nid[n]
        # split into per-layer runs, vias at layer changes
        runs = []
        cur = [path[0]]
        for k in range(1, len(path)):
            if path[k][0] != path[k - 1][0]:
                runs.append(cur); cur = [path[k]]
                vias.append(dict(net=n, x=cell_xy(path[k][1], path[k][2])[0], y=cell_xy(path[k][1], path[k][2])[1]))
            else:
                cur.append(path[k])
        runs.append(cur)
        if goal_via and not (len(path) > 1 and path[-2][1:] == path[-1][1:]):
            e = path[-1]
            vias.append(dict(net=n, x=cell_xy(e[1], e[2])[0], y=cell_xy(e[1], e[2])[1]))
        for run in runs:
            l = run[0][0]
            # polyline: keep direction-change points
            pts = [run[0]]
            for k in range(1, len(run) - 1):
                a, b, c = run[k - 1], run[k], run[k + 1]
                if (b[1] - a[1], b[2] - a[2]) != (c[1] - b[1], c[2] - b[2]):
                    pts.append(b)
            if len(run) > 1:
                pts.append(run[-1])
            if len(pts) < 2:
                continue
            for a, b in zip(pts[:-1], pts[1:]):
                # max width allowed along the segment
                cells = line_cells(a, b)
                wmax = min(width, wroute)
                (x1, y1), (x2, y2) = cell_xy(a[1], a[2]), cell_xy(b[1], b[2])
                tracks.append(dict(net=n, layer=("F" if l == 0 else "B"), x1=x1, y1=y1, x2=x2, y2=y2, w=round(wmax, 3), cells=cells, lay=l))
                stamp(l, x1, y1, x2, y2, wmax, nidn)
        newv = (len(runs) - 1) + (1 if (goal_via and not (len(path) > 1 and path[-2][1:] == path[-1][1:])) else 0)
        for v in (vias[-newv:] if newv > 0 else []):
            for l in (0, 1):
                disc(l, v["x"], v["y"], VIA_D / 2, nidn)
        for end in (path[0], path[-1]):
            el, ei, ej = end
            ex, ey = cell_xy(ei, ej)
            for q in pad_by_net.get(n, []):
                qw, qh = q["w"], q["h"]
                if int(round(q["ang"])) % 180 == 90:
                    qw, qh = qh, qw
                if (el == 0 and "F" in q["layers"]) or (el == 1 and "B" in q["layers"]):
                    if abs(ex - q["x"]) <= qw / 2 + 0.03 and abs(ey - q["y"]) <= qh / 2 + 0.03:
                        if math.hypot(ex - q["x"], ey - q["y"]) > 0.08:
                            tracks.append(dict(net=n, layer=("F" if el == 0 else "B"), x1=ex, y1=ey, x2=q["x"], y2=q["y"],
                                               w=round(min(width, wroute), 3), cells=[], lay=el))
                        break
        # tree update
        if tree is not None:
            for (l, i, j) in path:
                tree[l].add((i, j))
            if pad is not None:
                for l in (0, 1):
                    tree[l].update((i, j) for (_, i, j) in pad_mask(pad, l, n))
            for v in vias[-(len(runs) - 1):] if len(runs) > 1 else []:
                ci, cj = int(v["x"] / G), int(v["y"] / G)
                for l in (0, 1):
                    tree[l].add((ci, cj))
        # mark all path cells as tree (copper of this net) for later connections
        if tree is not None:
            for run in runs:
                l = run[0][0]
                for (_, i, j) in run:
                    tree[l].add((i, j))

    def line_cells(a, b):
        n = max(abs(b[1] - a[1]), abs(b[2] - a[2]), 1)
        return [(int(round(a[1] + (b[1] - a[1]) * t / n)), int(round(a[2] + (b[2] - a[2]) * t / n))) for t in range(n + 1)]

    def stamp(l, x1, y1, x2, y2, w, val):
        L = math.hypot(x2 - x1, y2 - y1)
        k = max(int(L / (G * 0.5)), 1)
        for t in range(k + 1):
            disc(l, x1 + (x2 - x1) * t / k, y1 + (y2 - y1) * t / k, w / 2, val)


    POWER_FIRST = [("VBUS1", 1.0), ("VBUS2", 1.0), ("VSW", 1.2), ("OUT_VBUS", 1.2)]
    POWER_MAIN = {"VBUS1": {("J1", "A4"), ("J1", "B9"), ("J1", "A9"), ("J1", "B4"), ("U3", "A2")},
                  "VBUS2": {("J2", "A4"), ("J2", "B9"), ("J2", "A9"), ("J2", "B4"), ("U4", "A2")},
                  "VSW": {("U3", "A1"), ("U4", "A1"), ("F1", "1")},
                  "OUT_VBUS": {("F1", "2"), ("J3", "1")}}
    main_done = set()

    def search(n, src, tree, okT, goal_mask=None):
        srcset = {(l, i, j) for (l, i, j) in src}
        si = [i for (_, i, _) in src]; sj = [j for (_, _, j) in src]
        if tree is not None:
            ti = [i for l in (0, 1) for (i, j) in tree[l]]; tj = [j for l in (0, 1) for (i, j) in tree[l]]
            tb = (min(ti), max(ti), min(tj), max(tj))
        else:
            tb = (0, 0, 0, 0)
        for margin_mm, cap in ((8.0, 150000), (25.0, 500000), (80.0, 900000)):
            mi = int(margin_mm / G)
            bi0, bi1 = (min(min(si), tb[0]), max(max(si), tb[1])) if tree is not None else (min(si), max(si))
            bj0, bj1 = (min(min(sj), tb[2]), max(max(sj), tb[3])) if tree is not None else (min(sj), max(sj))
            win = (max(bi0 - mi, 0), min(bi1 + mi, nx - 1), max(bj0 - mi, 0), min(bj1 + mi, ny - 1))
            path = astar("", src, srcset, tree, okT, NOVIA, False, win, cap, tb, goal_mask)
            if path:
                return path
        return None

    NOVIA = np.zeros((nx, ny), dtype=bool)

    def route_power(n, W):
        clr = 0.17
        nidn = nid[n]
        foreign = [(own[l] != 0) & (own[l] != nidn) for l in (0, 1)]
        D = [distance_transform_edt(~foreign[l]) * G for l in (0, 1)]
        okN = [(D[l] >= 0.125 + clr) | (own[l] == nidn) for l in (0, 1)]
        okW = [(D[l] >= W / 2 + clr) | (own[l] == nidn) for l in (0, 1)]
        goalW = [(D[l] >= W / 2 + clr) & (own[l] == 0) for l in (0, 1)]
        pads = [q for q in pad_by_net[n] if (q["ref"], q["num"]) in POWER_MAIN[n]]
        tree = {0: set(), 1: set()}
        done = []
        fails = 0
        first = True
        rest = pads[:]
        if n == "OUT_VBUS":
            rest.sort(key=lambda q: 0 if q["ref"] == "J3" else 1)
        cur = rest.pop(0)
        order = [cur]
        while rest:
            nxt = min(rest, key=lambda q: min((q["x"] - t["x"]) ** 2 + (q["y"] - t["y"]) ** 2 for t in order))
            rest.remove(nxt); order.append(nxt)
        for p in order:
            src = []
            for l in (0, 1):
                src += pad_mask(p, l, n)
            if not src:
                fails += 1; continue
            stub = search(n, src, None, okN, goal_mask=goalW)
            if not stub:
                print("   !! power stub failed", n, p["ref"], p["num"], flush=True); fails += 1; continue
            commit(n, stub, D, NARROW, W, clr, p, None, False)
            end = stub[-1]
            if first:
                tree[end[0]].add((end[1], end[2])); first = False
                print("    ", n, p["ref"], p["num"], "stub ok (root)", flush=True)
                continue
            path = None
            used = W
            for wtry in (W, 0.8, 0.6, 0.4, 0.25):
                okx = [(D[l] >= wtry / 2 + clr) | (own[l] == nidn) for l in (0, 1)]
                path = search(n, [end], tree, okx)
                if path:
                    used = wtry
                    break
            if not path:
                path = search(n, src, tree, okN)          # last resort: narrow, straight from the pad
                if path:
                    used = NARROW
                    print("   -- narrow direct route for", n, p["ref"], p["num"], flush=True)
            if not path:
                print("   !! power trunk failed", n, p["ref"], p["num"], flush=True); fails += 1; continue
            if used < W:
                print("   -- narrowed trunk to", used, "mm for", n, p["ref"], p["num"], flush=True)
            commit(n, path, D, used, used, clr, None, tree, False)
            tree[end[0]].add((end[1], end[2]))
            print("    ", n, p["ref"], p["num"], "trunk ok", flush=True)
        main_done.add(n)
        return fails


    # ---- hand-defined 2A trunks (B.Cu, with via pairs next to every ball/pad group) -----------------
    # (net, layer, x1, y1, x2, y2, width)
    RES_TRACKS = []
    RES_VIAS = []

    def stub_pair(net, pad_xy, via_x, via_ys, w=0.6):
        RES_TRACKS.append((net, "F", pad_xy[0], pad_xy[1], via_x, pad_xy[1], w))
        for vy in via_ys:
            RES_VIAS.append((net, via_x, vy))

    # VBUS1: J1 pad groups -> B.Cu bar -> U3 VIN (SW ball)
    stub_pair("VBUS1", (8.02, 11.05), 9.25, (10.65, 11.45)); stub_pair("VBUS1", (8.02, 15.95), 9.25, (15.55, 16.35))
    RES_TRACKS += [("VBUS1", "B", 9.25, 10.65, 9.25, 20.7, 1.0), ("VBUS1", "B", 9.25, 20.7, 15.6, 20.7, 1.0),
                   ("VBUS1", "F", 16.8, 19.7, 16.45, 20.05, 0.2), ("VBUS1", "F", 16.45, 20.05, 15.9, 20.7, 0.6)]
    RES_VIAS += [("VBUS1", 15.6, 20.3), ("VBUS1", 15.6, 21.1)]
    # VBUS2: J2 pad groups -> B.Cu bar -> U4 VIN (SW ball)
    stub_pair("VBUS2", (8.02, 33.55), 9.25, (33.15, 33.95)); stub_pair("VBUS2", (8.02, 38.45), 9.25, (38.05, 38.85))
    RES_TRACKS += [("VBUS2", "B", 9.25, 38.85, 9.25, 30.6, 1.0), ("VBUS2", "B", 9.25, 30.6, 15.6, 30.6, 1.0),
                   ("VBUS2", "F", 16.8, 29.7, 16.45, 30.05, 0.2), ("VBUS2", "F", 16.45, 30.05, 15.9, 30.6, 0.6)]
    RES_VIAS += [("VBUS2", 15.6, 30.2), ("VBUS2", 15.6, 31.0)]
    # VSW (load-switch outputs) -> B.Cu bar x=18.2 -> east along y=31 to the fuse F1 (left via column),
    # then F1 -> via column -> B.Cu y=31 -> J3 pin 1 (OUT_VBUS)
    FX, FY = FUSE_XY
    xvl, xvr = FX - 3.6, FX + 3.6
    RES_TRACKS += [("VSW", "F", 17.2, 19.7, 17.55, 20.05, 0.2), ("VSW", "F", 17.55, 20.05, 18.1, 20.6, 0.6),
                   ("VSW", "F", 17.2, 29.7, 17.55, 30.05, 0.2), ("VSW", "F", 17.55, 30.05, 18.1, 30.6, 0.6),
                   ("VSW", "B", 18.2, 20.2, 18.2, 31.0, 1.2), ("VSW", "B", 18.2, 31.0, xvl, FY, 1.2)]
    RES_VIAS += [("VSW", 18.2, 20.2), ("VSW", 18.2, 21.0), ("VSW", 18.2, 30.2), ("VSW", 18.2, 31.0)]
    # fuse pads: F.Cu stub (1.2) to a 3-via column on each side, B.Cu vertical bar joins the three vias
    RES_TRACKS += [("VSW", "F", xvl, FY, FX - 2.1375, FY, 1.2), ("VSW", "F", xvl, FY - 0.8, xvl, FY + 0.8, 0.6), ("VSW", "B", xvl, FY - 0.8, xvl, FY + 0.8, 0.6),
                   ("OUT_VBUS", "F", FX + 2.1375, FY, xvr, FY, 1.2), ("OUT_VBUS", "F", xvr, FY - 0.8, xvr, FY + 0.8, 0.6), ("OUT_VBUS", "B", xvr, FY - 0.8, xvr, FY + 0.8, 0.6),
                   ("OUT_VBUS", "B", xvr, FY, 56.78, 31.0, 1.2)]
    RES_VIAS += [("VSW", xvl, FY - 0.8), ("VSW", xvl, FY), ("VSW", xvl, FY + 0.8),
                 ("OUT_VBUS", xvr, FY - 0.8), ("OUT_VBUS", xvr, FY), ("OUT_VBUS", xvr, FY + 0.8)]

    # ---- third via at every layer transition (2A: ~1A per 0.3mm via) ----------------------------------
    RES_TRACKS += [
        ("VBUS1", "F", 9.25, 9.85, 9.25, 11.05, 0.6), ("VBUS1", "B", 9.25, 9.85, 9.25, 10.65, 1.0), ("VBUS1", "F", 9.25, 15.95, 9.25, 17.15, 0.6),
        ("VBUS1", "F", 15.6, 20.3, 15.6, 21.9, 0.6), ("VBUS1", "B", 15.6, 20.7, 15.6, 21.9, 1.0),
        ("VBUS2", "F", 9.25, 32.35, 9.25, 33.55, 0.6), ("VBUS2", "F", 9.25, 38.45, 9.25, 39.65, 0.6),
        ("VBUS2", "B", 9.25, 38.85, 9.25, 39.65, 1.0),
        ("VBUS2", "F", 15.6, 30.2, 15.6, 31.8, 0.6), ("VBUS2", "B", 15.6, 30.6, 15.6, 31.8, 1.0),
        ("VSW", "F", 18.2, 20.2, 18.2, 21.8, 0.6), ("VSW", "F", 18.2, 29.4, 18.2, 30.6, 0.6)]
    RES_VIAS += [("VBUS1", 9.25, 9.85), ("VBUS1", 9.25, 17.15), ("VBUS1", 15.6, 21.9),
                 ("VBUS2", 9.25, 32.35), ("VBUS2", 9.25, 39.65), ("VBUS2", 15.6, 31.8),
                 ("VSW", 18.2, 21.8), ("VSW", 18.2, 29.4)]

    def place_reserved():
        for (net, lay, x1, y1, x2, y2, w) in RES_TRACKS:
            l = 0 if lay == "F" else 1
            tracks.append(dict(net=net, layer=lay, x1=x1, y1=y1, x2=x2, y2=y2, w=w, cells=[], lay=l))
            stamp(l, x1, y1, x2, y2, w, nid[net])
        for (net, x, y) in RES_VIAS:
            vias.append(dict(net=net, x=x, y=y))
            for l in (0, 1):
                disc(l, x, y, VIA_D / 2, nid[net])

    place_reserved()
    main_done.update({"VBUS1", "VBUS2", "VSW", "OUT_VBUS"})
    # ---- GND stubs for SMD pads (THT pads join the pours directly)
    gnd_pads = [p for p in pad_by_net.get("GND", []) if not p["thru"]]
    for gp in gnd_pads:
        route_net("GND", goal_via=True, only_pads=[gp])
    # ---- fine-pitch Type-C data pairs first
    failed = 0
    EARLY = []
    for n_ in EARLY:
        if n_ in pad_by_net and len(pad_by_net[n_]) >= 2:
            failed += (route_net(n_) or 0)
    # ---- power nets first, with their real width
    for n_, W_ in []:
        t1 = time.time()
        failed += route_power(n_, W_)
        print('%-10s POWER  tracks=%3d vias=%2d  %.1fs' % (n_, len(tracks), len(vias), time.time() - t1), flush=True)
    # ---- route signal nets (GND later)
    names = [n for n in netnames if n != "GND" and len(pad_by_net.get(n, [])) >= 2]
    if os.environ.get('RONLY'): names = [n for n in names if n in os.environ['RONLY'].split(',')]
    names = [n for n in names if n not in dict(POWER_FIRST) and n not in EARLY] + [n for n, _ in POWER_FIRST]
    names.sort(key=lambda n: (ORDER_FIRST.index(n) if n in ORDER_FIRST else 100 + len(pad_by_net[n]), n))
    for n in names:
        t1 = time.time()
        f = route_net(n)
        failed += (f or 0)
        print("%-10s pads=%2d tracks=%3d vias=%2d  %.1fs" % (n, len(pad_by_net[n]), len(tracks), len(vias), time.time() - t1), flush=True)
    # ---- widen power tracks wherever the final clearance map allows it
    for n in ["VSW", "OUT_VBUS", "VBUS1", "VBUS2", "+5V", "+3V3"]:
        width, clr = cls(n)
        clr = 0.20
        nidn = nid.get(n)
        if nidn is None:
            continue
        D = [distance_transform_edt(~((own[l] != 0) & (own[l] != nidn))) * G for l in (0, 1)]
        for tr in tracks:
            if tr["net"] != n:
                continue
            l = tr["lay"]
            outside = [D[l][i, j] for (i, j) in tr["cells"] if own[l, i, j] != nidn or True]
            # cells inside own pads are ignored: use only cells farther than the pad
            vals = [D[l][i, j] for (i, j) in tr["cells"] if D[l][i, j] > 0]
            dmin = min(vals) if vals else 0.3
            lower = min(width, NARROW)
            tr["w"] = round(max(tr["w"], min(width, max(lower, 2 * (dmin - clr) - 0.02))), 3)
            stamp(l, tr["x1"], tr["y1"], tr["x2"], tr["y2"], tr["w"], nidn)
    for tr in tracks:
        tr.pop("cells", None); tr.pop("lay", None)
    json.dump(dict(tracks=tracks, vias=vias, via_d=VIA_D, via_drill=VIA_DRILL, failed=failed), open(os.path.join(HERE, "tracks.json"), "w"), indent=0)
    print("done: %d tracks, %d vias, %d failed connections, %.0fs" % (len(tracks), len(vias), failed, time.time() - t0))


if __name__ == "__main__":
    main()

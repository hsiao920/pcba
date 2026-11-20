# Build a hierarchical KiCad schematic (root + one sheet per PDF page) from extracted page data.
# Usage: python gen_kicad.py <pdf> <outdir> <project> [decoder-module]
import pymupdf, sys, os, re, uuid, math, collections, json, importlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_cad import extract_page, PROPRE, REFDES

PDF, OUT, PROJ = sys.argv[1], sys.argv[2], sys.argv[3]
DECODE = importlib.import_module(sys.argv[4]).decode if len(sys.argv) > 4 else None
os.makedirs(OUT, exist_ok=True)
U = lambda: str(uuid.uuid4())
ROOT = U()


def esc(s):
    return s.replace("\\", "\\\\").replace('"', '\\"')


def f(v):
    s = "%.4f" % v
    s = s.rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


FP = {"0201": "0603Metric", "0402": "1005Metric", "0603": "1608Metric", "0805": "2012Metric", "1206": "3216Metric", "1210": "3225Metric"}


def map_fp(pkg):
    m = re.match(r"^([RCL])(0201|0402|0603|0805|1206|1210)$", pkg or "")
    if not m: return ""
    lib = {"R": "Resistor_SMD", "C": "Capacitor_SMD", "L": "Inductor_SMD"}[m.group(1)]
    return "%s:%s_%s_%s" % (lib, m.group(1), m.group(2), FP[m.group(2)])


PKGRE = re.compile(r"^(?:[RCL]\d{4}|.*(?:SOT|SOD|DFN|QFN|BGA|SOP|SSOP|TSSOP|IND_|LED_|SMD|FPC|FBGA|WLCSP|USB|TYPE|SW_|HDR|CONN|XTAL|SON|LGA).*)$", re.I)


class Page:
    def __init__(s, r):
        s.r = r
        fs = collections.Counter(round(t["size"], 2) for t in r["texts"] if t["used"] and t["used"][0] == "pinnum")
        size = fs.most_common(1)[0][0] if fs else 6.2349
        sc = min((1.0, 0.7, 0.5), key=lambda k: abs(size / 6.2349 - k))
        s.g = 7.2 * sc                 # pt per 0.1 inch
        s.k = 2.54 / s.g               # mm per pt
        h = s.g / 2
        pts = [p["outer"] for p in r["pins"]] + [q for w in r["wires"] for q in w]
        def off(vals):
            c = collections.Counter(round(v % h, 2) for v in vals)
            return c.most_common(1)[0][0] if c else 0
        s.ox = off([p[0] for p in pts]); s.oy = off([p[1] for p in pts])
        s.margin = 0.0

    def X(s, x): return round((x - s.ox) / (s.g / 2)) * 1.27
    def Y(s, y): return round((y - s.oy) / (s.g / 2)) * 1.27
    def x(s, x): return (x - s.ox) * s.k        # unsnapped
    def y(s, y): return (y - s.oy) * s.k
    def P(s, p): return (s.X(p[0]), s.Y(p[1]))


def paper_for(wmm, hmm):
    for name, (w, h) in (("A4", (297, 210)), ("A3", (420, 297)), ("A2", (594, 420)), ("A1", (841, 594))):
        if wmm <= w * 1.02 and hmm <= h * 1.02: return name, w, h
    return "A0", 1189, 841


def split_ref(ref):
    m = re.match(r"^(.*\d)([A-Z])$", ref)
    if m and not re.match(r"^[A-Z]{2,5}_", ref):
        return m.group(1), ord(m.group(2)) - 64
    return ref, 1


doc = pymupdf.open(PDF)
if os.environ.get("XT_ADAPTER"):
    doc = importlib.import_module(os.environ["XT_ADAPTER"]).open_pages()
pages = []
for i in range(len(doc)):
    r = extract_page(doc[i], i + 1, decode=DECODE)
    pages.append((r, Page(r)))

# ---------- pin numbering fixes and part records
libparts = collections.OrderedDict()     # base -> {units: {unit: data}, props}
for pi, (r, pg) in enumerate(pages):
    for part in r["parts"]:
        if not part["ref"]: continue
        base, unit = split_ref(part["ref"])
        pins = [r["pins"][k] for k in part["pins"]]
        if all(p["num"] is None for p in pins):
            order = sorted(range(len(pins)), key=lambda i: (pins[i]["outer"][0], pins[i]["outer"][1]))
            for n, i in enumerate(order): pins[i]["num"] = str(n + 1)
        else:
            used = {p["num"] for p in pins if p["num"]}
            n = 1
            for p in pins:
                if not p["num"]:
                    while str(n) in used: n += 1
                    p["num"] = str(n); used.add(p["num"])
        lp = libparts.setdefault(base, dict(units={}, props=[], first=None))
        if unit in lp["units"]:
            # same unit letter appearing twice: give it a fresh unit number
            unit = max(lp["units"]) + 1
        lp["units"][unit] = dict(page=pi, part=part)
        if part["props"] and not lp["props"]: lp["props"] = part["props"]
        part["base"], part["unit"] = base, unit


def classify_props(props):
    vals = [p for p in props]
    value = pkg = None; extra = []; dnp = False
    for t, colr, bb in vals:
        if t == "DNP": dnp = True; continue
        if pkg is None and PKGRE.match(t): pkg = t; continue
        if value is None and colr == 0x80 and not REFDES.match(t): value = t; continue
        extra.append(t)
    if value is None and extra: value = extra.pop(0)
    return value or "", pkg or "", extra, dnp


# ---------- library symbols
def lib_symbol(base, lp):
    name = "KL_" + re.sub(r"[^A-Za-z0-9_]", "_", base)
    nunits = max(lp["units"])
    value, pkg, extra, dnp = classify_props(lp["props"])
    out = ['(symbol "%s" (pin_numbers (hide no)) (pin_names (offset 0.508)) (exclude_from_sim no) (in_bom yes) (on_board yes)' % name]
    out.append('(property "Reference" "%s" (at 0 0 0) (effects (font (size 1.27 1.27))))' % esc(re.sub(r"\d.*", "", base) or "U"))
    out.append('(property "Value" "%s" (at 0 0 0) (effects (font (size 1.27 1.27))))' % esc(value))
    out.append('(property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))')
    out.append('(property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))')
    for unit, ud in sorted(lp["units"].items()):
        pi = ud["page"]; r, pg = pages[pi]; part = ud["part"]
        pins = [r["pins"][k] for k in part["pins"]]
        # origin = snapped top-left of body box
        X0, Y0 = pg.X(part["box"][0]), pg.Y(part["box"][1])
        part["origin"] = (X0, Y0)
        g = []
        segs = []
        for gi in r["gl"]:
            pass
        for bi in part.get("blue_idx", []):
            pass
        for (a, b) in part["body"]:
            g.append('(polyline (pts (xy %s %s) (xy %s %s)) (stroke (width 0.1524) (type default)) (fill (type none)))'
                     % (f(pg.x(a[0]) - X0 + (pg.X(0) - pg.x(0)) * 0), f(Y0 - pg.y(a[1])), f(pg.x(b[0]) - X0), f(Y0 - pg.y(b[1]))))
        out.append('(symbol "%s_%d_0" %s)' % (name, unit, " ".join(g)))
        ps = []
        names_shown = any(p["name"] for p in pins)
        for p in pins:
            ox, oy = pg.P(p["outer"]); ix, iy = pg.P(p["inner"])
            L = math.hypot(ix - ox, iy - oy)
            dx, dy = ix - ox, -(iy - oy)
            ang = 0 if abs(dx) >= abs(dy) and dx > 0 else 180 if abs(dx) >= abs(dy) else 90 if dy > 0 else 270
            nm = p["name"] or "~"
            ps.append('(pin passive line (at %s %s %d) (length %s) (name "%s" (effects (font (size %s %s)))) (number "%s" (effects (font (size %s %s)))))'
                      % (f(ox - X0), f(Y0 - oy), ang, f(L), esc(nm), f(1.0), f(1.0), esc(p["num"]), f(1.0), f(1.0)))
        out.append('(symbol "%s_%d_1" %s)' % (name, unit, " ".join(ps)))
    out.append(")")
    return name, "\n".join(out), (value, pkg, extra, dnp)


# attach body segments to parts (blue segments of their group(s))
for r, pg in pages:
    gseg = {}
    for gi, g in enumerate(r["gl"]):
        gseg[gi] = [r["blues"][i] for i in g]
    for part in r["parts"]:
        gs = {r["pins"][k]["g"] for k in part["pins"]} | {part["g"]}
        part["body"] = [s for gi in gs for s in gseg.get(gi, [])]

libs = {}
for base, lp in libparts.items():
    libs[base] = lib_symbol(base, lp)

PWR_LIB = '''(symbol "KL_PWR" (power) (pin_numbers (hide yes)) (pin_names (offset 0) (hide yes)) (exclude_from_sim no) (in_bom yes) (on_board yes)
(property "Reference" "#PWR" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
(property "Value" "PWR" (at 0 3.81 0) (effects (font (size 1.0 1.0))))
(property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
(property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
(symbol "KL_PWR_0_1" (polyline (pts (xy 0 0) (xy 0 1.524)) (stroke (width 0.1524) (type default)) (fill (type none)))
 (circle (center 0 2.032) (radius 0.508) (stroke (width 0.1524) (type default)) (fill (type none))))
(symbol "KL_PWR_1_1" (pin power_in line (at 0 0 90) (length 0) (hide yes) (name "~" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))))'''
GND_LIB = '''(symbol "KL_GND" (power) (pin_numbers (hide yes)) (pin_names (offset 0) (hide yes)) (exclude_from_sim no) (in_bom yes) (on_board yes)
(property "Reference" "#PWR" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
(property "Value" "GND" (at 0 -3.81 0) (effects (font (size 1.0 1.0)) (hide yes)))
(property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
(property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
(symbol "KL_GND_0_1" (polyline (pts (xy 0 0) (xy 0 -1.27)) (stroke (width 0.1524) (type default)) (fill (type none)))
 (polyline (pts (xy -1.27 -1.27) (xy 1.27 -1.27)) (stroke (width 0.1524) (type default)) (fill (type none)))
 (polyline (pts (xy -0.762 -1.778) (xy 0.762 -1.778)) (stroke (width 0.1524) (type default)) (fill (type none)))
 (polyline (pts (xy -0.254 -2.286) (xy 0.254 -2.286)) (stroke (width 0.1524) (type default)) (fill (type none))))
(symbol "KL_GND_1_1" (pin power_in line (at 0 0 270) (length 0) (hide yes) (name "~" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))))'''

TB_SKIP = {"Project:", "File:", "Date:", "Rockchip Electronics Co., Ltd", "Designed by:", "Rev:", "Sheet:", "of", "Reviewed by:",
           "<Checker>", "Title", "Size", "Document Number", "<Title>"}

GLOBAL_NAMES = {sy["name"] for r_, pg_ in pages for sy in r_["syms"] if sy["conn"]}
if os.environ.get("XT_ALIAS_GLOBAL"):
    GLOBAL_NAMES |= {a["name"] for r_, pg_ in pages for a in r_["aliases"]}
sheet_files = []
pwr_n = [0]
POWER_NAMES = set()
report = dict(pages=[])
for pi, (r, pg) in enumerate(pages):
    W, H = r["size"]
    pname, pw, ph = paper_for(W * pg.k, H * pg.k)
    sheet_uuid = U()
    body = []
    used_libs = {"KL_PWR": PWR_LIB, "KL_GND": GND_LIB}
    # title from title block "File:" value
    title = ""
    for lab in [t for t in r["texts"] if t["t"] in ("File:", "Title", "图页")]:
        lb = lab["bbox"]; cy = (lb[1] + lb[3]) / 2
        cands = [t for t in r["texts"] if t is not lab and t["bbox"][0] > lb[2] - 1 and abs((t["bbox"][1] + t["bbox"][3]) / 2 - cy) < 2.5
                 and t["t"] not in TB_SKIP]
        if lab["t"] == "Title":
            cands = [t for t in r["texts"] if t["bbox"][0] >= lb[0] + 20 and 0 < t["bbox"][1] - lb[1] < 14 and t["t"] not in TB_SKIP]
        if cands:
            title = min(cands, key=lambda t: t["bbox"][0])["t"]; break
    if not title:
        title = "Page %d" % (pi + 1)
    # wires
    for a, b in r["wires"]:
        A, B = pg.P(a), pg.P(b)
        if A == B: continue
        body.append('(wire (pts (xy %s %s) (xy %s %s)) (stroke (width 0) (type default)) (uuid "%s"))' % (f(A[0]), f(A[1]), f(B[0]), f(B[1]), U()))
    for j in r["juncs"]:
        J = pg.P(j)
        body.append('(junction (at %s %s) (diameter 0) (color 0 0 0 0) (uuid "%s"))' % (f(J[0]), f(J[1]), U()))
    # parts
    connected = set()
    for root_, ks in r["nets"].items():
        if len(ks) > 1 or r["netname"].get(root_):
            connected.update(ks)
    for part in r["parts"]:
        if not part["ref"]: continue
        base, unit = part["base"], part["unit"]
        name, _, (value, pkg, extra, dnp) = libs[base]
        used_libs[name] = libs[base][1]
        X0, Y0 = part["origin"]
        fp = map_fp(pkg)
        rb = part["refbox"]
        refat = (pg.x(rb[0]), pg.y(rb[3])) if rb else (X0, Y0 - 2)
        vprop = next((p for p in part["props"] if p[0] == value), None)
        valat = (pg.x(vprop[2][0]), pg.y(vprop[2][3])) if vprop else (refat[0], refat[1] + 2)
        fsz = max(0.8, min(1.27, 6.2349 * pg.k * 0.42))
        props = ['(property "Reference" "%s" (at %s %s 0) (effects (font (size %s %s)) (justify left bottom)))' % (esc(base), f(refat[0]), f(refat[1]), f(fsz), f(fsz)),
                 '(property "Value" "%s" (at %s %s 0) (effects (font (size %s %s)) (justify left bottom)))' % (esc(value), f(valat[0]), f(valat[1]), f(fsz), f(fsz)),
                 '(property "Footprint" "%s" (at %s %s 0) (effects (font (size 1 1)) (hide yes)))' % (esc(fp), f(X0), f(Y0)),
                 '(property "Datasheet" "" (at %s %s 0) (effects (font (size 1 1)) (hide yes)))' % (f(X0), f(Y0)),
                 '(property "Package" "%s" (at %s %s 0) (effects (font (size 1 1)) (hide yes)))' % (esc(pkg), f(X0), f(Y0)),
                 '(property "Spec" "%s" (at %s %s 0) (effects (font (size 1 1)) (hide yes)))' % (esc(" ".join(extra)), f(X0), f(Y0))]
        pins_s = " ".join('(pin "%s" (uuid "%s"))' % (esc(r["pins"][k]["num"]), U()) for k in part["pins"])
        body.append('(symbol (lib_id "KL:%s") (at %s %s 0) (unit %d) (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp %s) (uuid "%s") %s %s '
                    '(instances (project "%s" (path "/%s/%s" (reference "%s") (unit %d)))))'
                    % (name, f(X0), f(Y0), unit, "yes" if dnp else "no", U(), " ".join(props), pins_s, PROJ, ROOT, sheet_uuid, esc(base), unit))
        for k in part["pins"]:
            if k not in connected:
                O = pg.P(r["pins"][k]["outer"])
                body.append('(no_connect (at %s %s) (uuid "%s"))' % (f(O[0]), f(O[1]), U()))
    # power / gnd / offpage
    for s in r["syms"]:
        if not s["conn"]: continue
        C = pg.P(s["conn"][0])
        bx = s["box"]; cx, cy = (bx[0] + bx[2]) / 2, (bx[1] + bx[3]) / 2
        px, py = s["conn"][0]
        if s["kind"] == "offpage":
            tb = s["tbox"]; tc = ((tb[0] + tb[2]) / 2, (tb[1] + tb[3]) / 2)
            dx, dy = tc[0] - px, tc[1] - py
            ang = (0 if dx > 0 else 180) if abs(dx) >= abs(dy) else (270 if dy > 0 else 90)
            just = "left" if ang in (0, 90) else "right"
            body.append('(global_label "%s" (shape bidirectional) (at %s %s %d) (fields_autoplaced yes) (effects (font (size %s %s)) (justify %s)) (uuid "%s"))'
                        % (esc(s["name"]), f(C[0]), f(C[1]), ang, f(1.0), f(1.0), just, U()))
        else:
            gnd = s["kind"] == "gnd"
            # direction the symbol points: away from the wire / pin that reaches the connection point
            vec = None
            for (wa, wb) in r["wires"]:
                for e, o in ((wa, wb), (wb, wa)):
                    if abs(e[0] - px) < 0.4 and abs(e[1] - py) < 0.4:
                        vec = (px - o[0], py - o[1])
            if vec is None:
                for pn in r["pins"]:
                    if abs(pn["outer"][0] - px) < 0.4 and abs(pn["outer"][1] - py) < 0.4:
                        vec = (pn["outer"][0] - pn["inner"][0], pn["outer"][1] - pn["inner"][1])
            if vec is None or (abs(vec[0]) < 0.01 and abs(vec[1]) < 0.01):
                vec = (cx - px, cy - py) if (abs(cx - px) + abs(cy - py)) > 0.5 else ((0, 1) if gnd else (0, -1))
            dx, dy = vec
            if abs(dx) > abs(dy):
                d = "right" if dx > 0 else "left"
            else:
                d = "down" if dy > 0 else "up"
            base_dir = "down" if gnd else "up"
            rot = {("up", "up"): 0, ("up", "left"): 90, ("up", "down"): 180, ("up", "right"): 270,
                   ("down", "down"): 0, ("down", "right"): 90, ("down", "up"): 180, ("down", "left"): 270}[(base_dir, d)]
            pwr_n[0] += 1
            POWER_NAMES.add(s["name"])
            lib = "KL_GND" if gnd else "KL_PWR"
            val = s["name"]
            vat = (pg.x(s["tbox"][0]), pg.y(s["tbox"][3])) if s.get("tbox") else (C[0], C[1])
            body.append('(symbol (lib_id "KL:%s") (at %s %s %d) (unit 1) (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no) (uuid "%s") '
                        '(property "Reference" "#PWR%04d" (at %s %s 0) (effects (font (size 1 1)) (hide yes))) '
                        '(property "Value" "%s" (at %s %s 0) (effects (font (size 1 1)) (justify left bottom) %s)) '
                        '(property "Footprint" "" (at %s %s 0) (effects (font (size 1 1)) (hide yes))) '
                        '(property "Datasheet" "" (at %s %s 0) (effects (font (size 1 1)) (hide yes))) '
                        '(pin "1" (uuid "%s")) (instances (project "%s" (path "/%s/%s" (reference "#PWR%04d") (unit 1)))))'
                        % (lib, f(C[0]), f(C[1]), rot, U(), pwr_n[0], f(C[0]), f(C[1]), esc(val), f(vat[0]), f(vat[1]), "(hide yes)" if gnd else "",
                           f(C[0]), f(C[1]), f(C[0]), f(C[1]), U(), PROJ, ROOT, sheet_uuid, pwr_n[0]))
    # net aliases -> local labels
    SW = [(pg.P(wa_), pg.P(wb_)) for wa_, wb_ in r["wires"]]
    pin_pts = {pg.P(pn["outer"]) for pn in r["pins"]}
    def on_w(pt, w):
        (x1, y1), (x2, y2) = w
        if abs(x1 - x2) < 1e-6: return abs(pt[0] - x1) < 1e-6 and min(y1, y2) - 1e-6 <= pt[1] <= max(y1, y2) + 1e-6
        if abs(y1 - y2) < 1e-6: return abs(pt[1] - y1) < 1e-6 and min(x1, x2) - 1e-6 <= pt[0] <= max(x1, x2) + 1e-6
        return False
    for a in r["aliases"]:
        wa, wb = r["wires"][a["wire"]]
        A, B = pg.P(wa), pg.P(wb)
        me = SW[a["wire"]]
        horiz = abs(A[1] - B[1]) < 1e-6
        if horiz:
            lo, hi = min(A[0], B[0]), max(A[0], B[0]); start = min(max(pg.X(a["bbox"][0]), lo), hi); ang = 0
        else:
            lo, hi = min(A[1], B[1]), max(A[1], B[1]); start = min(max(pg.Y(a["bbox"][3]), lo), hi); ang = 90
        best = None
        n = int(round((hi - lo) / 1.27))
        for i in range(n + 1):
            v = lo + i * 1.27
            pt = (v, A[1]) if horiz else (A[0], v)
            clash = pt in pin_pts or any(w is not me and w != me and on_w(pt, w) for w in SW)
            if clash: continue
            dist = abs(v - start)
            if best is None or dist < best[0]: best = (dist, pt)
        if best is None:
            best = (0, (start, A[1]) if horiz else (A[0], start))
        x, y = best[1]
        kind = "global_label" if a["name"] in GLOBAL_NAMES else "label"
        shape = '(shape passive) ' if kind == "global_label" else ""
        body.append('(%s "%s" %s(at %s %s %d) (fields_autoplaced yes) (effects (font (size %s %s)) (justify left bottom)) (uuid "%s"))'
                    % (kind, esc(a["name"]), shape, f(x), f(y), ang, f(1.0), f(1.0), U()))
    # free texts (notes)
    for t in r["unused"]:
        if t["t"] in TB_SKIP or t["color"] == 0x123458: continue
        bb = t["bbox"]
        if (bb[1] < 10 or bb[3] > H - 10 or bb[0] < 10 or bb[2] > W - 10) and len(t["t"]) <= 2: continue
        if bb[0] > W * 0.72 and bb[1] > H * 0.86: continue
        sz = max(0.6, t["size"] * pg.k * 0.85)
        if t["dir"] == [1, 0]:
            at = (pg.x(bb[0]), pg.y(bb[3])); ang = 0
        else:
            at = (pg.x(bb[2]), pg.y(bb[3])); ang = 90
        body.append('(text "%s" (exclude_from_sim no) (at %s %s %d) (effects (font (size %s %s)) (justify left bottom)) (uuid "%s"))'
                    % (esc(t["t"]), f(at[0]), f(at[1]), ang, f(sz), f(sz), U()))
    fname = "p%02d.kicad_sch" % (pi + 1)
    sch = ('(kicad_sch (version 20250114) (generator "eeschema") (generator_version "9.0") (uuid "%s") (paper "%s") '
           '(title_block (title "%s") (company "%s") (comment 1 "Rebuilt from %s page %d"))\n(lib_symbols %s)\n%s\n)'
           % (sheet_uuid, pname, esc(title), esc(PROJ), esc(os.path.basename(PDF)), pi + 1,
              "\n".join(v.replace('(symbol "KL_', '(symbol "KL:KL_', 1) for v in used_libs.values()), "\n".join(body)))
    with open(os.path.join(OUT, fname), "w", encoding="utf-8") as fh:
        fh.write(sch)
    sheet_files.append((fname, title, sheet_uuid))
    report["pages"].append(dict(page=pi + 1, title=title, scale=round(pg.g / 7.2, 2), parts=len(r["parts"]), paper=pname))

# root sheet
blocks = []
for i, (fname, title, su) in enumerate(sheet_files):
    cx = 20 + (i % 4) * 95; cy = 25 + (i // 4) * 30
    blocks.append('(sheet (at %s %s) (size 80 18) (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no) (fields_autoplaced yes) '
                  '(stroke (width 0.1524) (type solid)) (fill (color 0 0 0 0.0000)) (uuid "%s") '
                  '(property "Sheetname" "%s" (at %s %s 0) (effects (font (size 1.27 1.27)) (justify left bottom))) '
                  '(property "Sheetfile" "%s" (at %s %s 0) (effects (font (size 1.27 1.27)) (justify left top))) '
                  '(instances (project "%s" (path "/%s" (page "%d")))))'
                  % (f(cx), f(cy), su, esc("P%02d %s" % (i + 1, title))[:120], f(cx), f(cy - 0.7), fname, f(cx), f(cy + 18.7), PROJ, ROOT, i + 2))
PWRFLAG = """(symbol "KL:PWR_FLAG" (power) (pin_numbers (hide yes)) (pin_names (offset 0) (hide yes)) (exclude_from_sim no) (in_bom yes) (on_board yes)
(property "Reference" "#FLG" (at 0 1.905 0) (effects (font (size 1.27 1.27)) (hide yes)))
(property "Value" "PWR_FLAG" (at 0 3.81 0) (effects (font (size 1.0 1.0))))
(property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
(property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
(symbol "PWR_FLAG_0_0" (pin power_out line (at 0 0 90) (length 0) (name "~" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27))))))
(symbol "PWR_FLAG_0_1" (polyline (pts (xy 0 0) (xy 0 1.27) (xy -1.016 1.905) (xy 0 2.54) (xy 1.016 1.905) (xy 0 1.27)) (stroke (width 0) (type default)) (fill (type none)))))"""
flags = []
for i, nm in enumerate(sorted(POWER_NAMES)):
    x = 20.32 + (i % 10) * 38.1; y = 210.82 + (i // 10) * 22.86
    lib = "KL:KL_GND" if nm == "GND" else "KL:KL_PWR"
    flags.append('(symbol (lib_id "KL:PWR_FLAG") (at %s %s 0) (unit 1) (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no) (uuid "%s") '
                 '(property "Reference" "#FLG%03d" (at %s %s 0) (effects (font (size 1 1)) (hide yes))) (property "Value" "PWR_FLAG" (at %s %s 0) (effects (font (size 1 1)) (hide yes))) '
                 '(property "Footprint" "" (at %s %s 0) (effects (font (size 1 1)) (hide yes))) (property "Datasheet" "" (at %s %s 0) (effects (font (size 1 1)) (hide yes))) '
                 '(pin "1" (uuid "%s")) (instances (project "%s" (path "/%s" (reference "#FLG%03d") (unit 1)))))'
                 % (f(x), f(y), U(), i + 1, f(x), f(y), f(x), f(y), f(x), f(y), f(x), f(y), U(), PROJ, ROOT, i + 1))
    flags.append('(symbol (lib_id "%s") (at %s %s %d) (unit 1) (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no) (uuid "%s") '
                 '(property "Reference" "#PWR9%03d" (at %s %s 0) (effects (font (size 1 1)) (hide yes))) (property "Value" "%s" (at %s %s 0) (effects (font (size 1 1)) (justify left bottom))) '
                 '(property "Footprint" "" (at %s %s 0) (effects (font (size 1 1)) (hide yes))) (property "Datasheet" "" (at %s %s 0) (effects (font (size 1 1)) (hide yes))) '
                 '(pin "1" (uuid "%s")) (instances (project "%s" (path "/%s" (reference "#PWR9%03d") (unit 1)))))'
                 % (lib, f(x), f(y), 0, U(), i + 1, f(x), f(y), esc(nm), f(x + 1.5), f(y + 4), f(x), f(y), f(x), f(y), U(), PROJ, ROOT, i + 1))
rootlibs = PWRFLAG + "\n" + PWR_LIB.replace('(symbol "KL_', '(symbol "KL:KL_', 1) + "\n" + GND_LIB.replace('(symbol "KL_', '(symbol "KL:KL_', 1)
root = ('(kicad_sch (version 20250114) (generator "eeschema") (generator_version "9.0") (uuid "%s") (paper "A3") '
        '(title_block (title "%s") (comment 1 "Rebuilt from %s"))\n(lib_symbols %s)\n%s\n'
        '(sheet_instances (path "/" (page "1"))))' % (ROOT, esc(PROJ), esc(os.path.basename(PDF)), rootlibs, "\n".join(blocks)))
with open(os.path.join(OUT, PROJ + ".kicad_sch"), "w", encoding="utf-8") as fh:
    fh.write(root)
with open(os.path.join(OUT, PROJ + ".kicad_pro"), "w", encoding="utf-8") as fh:
    json.dump({"meta": {"filename": PROJ + ".kicad_pro", "version": 1}, "schematic": {},
               "erc": {"rule_severities": {"power_pin_not_driven": "ignore"}}, "boards": [], "sheets": [[ROOT, "Root"]] +
               [[su, "P%02d" % (i + 1)] for i, (fn, t, su) in enumerate(sheet_files)]}, fh, indent=2)
json.dump(report, open(os.path.join(OUT, "build_report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("sheets", len(sheet_files), "lib parts", len(libparts))

# symbol library + table so the project opens without "library not found" warnings
allsyms = [v[1] for v in libs.values()] + [PWR_LIB, GND_LIB, PWRFLAG.replace('(symbol "KL:PWR_FLAG"', '(symbol "PWR_FLAG"', 1)]
with open(os.path.join(OUT, "KL.kicad_sym"), "w", encoding="utf-8") as fh:
    fh.write('(kicad_symbol_lib (version 20241209) (generator "kicad_symbol_editor") (generator_version "9.0")\n%s\n)\n' % "\n".join(allsyms))
with open(os.path.join(OUT, "sym-lib-table"), "w", encoding="utf-8") as fh:
    fh.write('(sym_lib_table\n  (version 7)\n  (lib (name "KL")(type "KiCad")(uri "${KIPRJMOD}/KL.kicad_sym")(options "")(descr "Symbols rebuilt from PDF"))\n)\n')

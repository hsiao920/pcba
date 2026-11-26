"""Measure / fix the content-vs-frame placement of every KiCad sheet in a rebuilt project.
usage: python frame_fit.py <project dir> [--apply]
 - removes single-character PDF frame labels (A-D rows / 1-6 columns) that were left in the page margin
 - shifts each sheet (on the 1.27 mm grid) only as much as needed to clear the KiCad page frame
 - bumps the paper size when the content cannot fit"""
import re, sys, glob, os, math

PAPERS = {"A4": (297.0, 210.0), "A3": (420.0, 297.0), "A2": (594.0, 420.0), "A1": (841.0, 594.0), "A0": (1189.0, 841.0)}
ORDER = ["A4", "A3", "A2", "A1", "A0"]
MARGIN = 10.0          # KiCad page frame inset
GAP = 3.0              # clearance between content and frame
TB_W, TB_H = 112.0, 34.0   # KiCad title block size (upper bound)
G = 1.27

NUM = r"(-?\d+(?:\.\d+)?)"
PT_RE = re.compile(r"\((at|xy|start|end|mid|center) " + NUM + " " + NUM)
FRAME_TXT = re.compile(r'^\(text "([A-Za-z0-9])" \(exclude_from_sim no\) \(at ' + NUM + " " + NUM)
NL = chr(10)


def split_lib(s):
    i = s.find("(lib_symbols")
    d = 0
    for j in range(i, len(s)):
        c = s[j]
        if c == "(":
            d += 1
        elif c == ")":
            d -= 1
            if d == 0:
                return s[:i], s[i:j + 1], s[j + 1:]
    raise ValueError("unbalanced lib_symbols")


def split_items(body):
    items = []
    i = 0
    while True:
        i = body.find(NL + "(", i)
        if i < 0:
            break
        d = 0
        j = i + 1
        for j in range(i + 1, len(body)):
            c = body[j]
            if c == "(":
                d += 1
            elif c == ")":
                d -= 1
                if d == 0:
                    break
        items.append((i + 1, j + 1))
        i = j
    return items


def drop_frame_labels(body, W, H):
    removed = []
    out = []
    last = 0
    for a, b in split_items(body):
        it = body[a:b]
        m = FRAME_TXT.match(it)
        if m:
            x, y = float(m.group(2)), float(m.group(3))
            if x < 9 or y < 9 or x > W - 9 or y > H - 9:
                out.append(body[last:a])
                last = b
                removed.append((m.group(1), round(x, 1), round(y, 1)))
    out.append(body[last:])
    return "".join(out), removed


def bbox_of(body):
    xs, ys = [], []
    for m in PT_RE.finditer(body):
        xs.append(float(m.group(2)))
        ys.append(float(m.group(3)))
    return (min(xs), min(ys), max(xs), max(ys))


def paper_of(head):
    m = re.search(r'\(paper "(\w+)"\)', head)
    return m.group(1) if m else "A4"


def fmt(v):
    s = ("%.4f" % v).rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def shift_body(body, dx, dy):
    def rep(m):
        return "(%s %s %s" % (m.group(1), fmt(float(m.group(2)) + dx), fmt(float(m.group(3)) + dy))
    return PT_RE.sub(rep, body)


def plan(bbox, paper):
    x0, y0, x1, y1 = bbox
    w, h = x1 - x0, y1 - y0
    for p, gap in [(q, g) for q in ORDER[ORDER.index(paper):] for g in (GAP, 1.5)]:
        W, H = PAPERS[p]
        ax0, ay0 = MARGIN + gap, MARGIN + gap
        ax1, ay1 = W - MARGIN - gap, H - MARGIN - gap
        if w <= ax1 - ax0 and h <= ay1 - ay0:
            dx = dy = 0.0
            if x0 < ax0:
                dx = math.ceil((ax0 - x0) / G) * G
            elif x1 > ax1:
                dx = -math.ceil((x1 - ax1) / G) * G
            if y0 < ay0:
                dy = math.ceil((ay0 - y0) / G) * G
            elif y1 > ay1:
                dy = -math.ceil((y1 - ay1) / G) * G
            return p, dx, dy
    return "A0", 0.0, 0.0


def tb_items(body, dx, dy, paper):
    """number of placed items whose bbox overlaps the title block after shifting by (dx,dy)."""
    W, H = PAPERS[paper]
    tx0, ty0 = W - MARGIN - TB_W, H - MARGIN - TB_H
    n = 0
    for a, b in split_items(body):
        pts = [(float(m.group(2)) + dx, float(m.group(3)) + dy) for m in PT_RE.finditer(body[a:b])]
        if not pts:
            continue
        if max(p[0] for p in pts) > tx0 and max(p[1] for p in pts) > ty0 and min(p[0] for p in pts) < W - MARGIN and min(p[1] for p in pts) < H - MARGIN:
            n += 1
    return n


def tb_overlap(bb, paper):
    W, H = PAPERS[paper]
    return bb[2] > W - MARGIN - TB_W and bb[3] > H - MARGIN - TB_H


if __name__ == "__main__":
    proj = sys.argv[1]
    apply = "--apply" in sys.argv
    for fn in sorted(glob.glob(os.path.join(proj, "p[0-9]*.kicad_sch"))):
        s = open(fn, encoding="utf-8").read()
        head, lib, body = split_lib(s)
        paper = paper_of(head)
        W, H = PAPERS[paper]
        body, removed = drop_frame_labels(body, W, H)
        bb = bbox_of(body)
        np_, dx, dy = plan(bb, paper)
        while tb_items(body, dx, dy, np_) and np_ != "A0":      # content would sit on the title block: go one paper size up
            np_ = ORDER[ORDER.index(np_) + 1]
        sb = (bb[0] + dx, bb[1] + dy, bb[2] + dx, bb[3] + dy)
        print("%s %s bbox=(%.1f,%.1f)-(%.1f,%.1f) removed=%d -> %s shift=(%.2f,%.2f) tb_items=%d" % (
            os.path.basename(fn), paper, bb[0], bb[1], bb[2], bb[3], len(removed), np_, dx, dy, tb_items(body, dx, dy, np_)))
        if apply:
            nb = shift_body(body, dx, dy) if (dx or dy) else body
            nh = head.replace('(paper "%s")' % paper, '(paper "%s")' % np_) if np_ != paper else head
            open(fn, "w", encoding="utf-8", newline="").write(nh + lib + nb)

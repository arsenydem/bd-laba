import os, sys, re

FKS = {
    "experiments": [("dataset_id", "datasets", "id"), ("model_id", "models", "id")]
}


def cast(val, typ):
    if typ == "INT":
        return int(val)
    if typ == "FLOAT":
        return float(val)
    return str(val)


def fmt(val, typ):
    if typ == "INT":
        return str(int(val))
    if typ == "FLOAT":
        return str(float(val))
    return str(val)


class DB:
    def __init__(self, pth):
        self.pth = pth
        self.tab = {}

    def load(self):
        self.tab = {}
        if not os.path.isdir(self.pth):
            os.makedirs(self.pth, exist_ok=True)
            return
        mp = os.path.join(self.pth, "meta.txt")
        if not os.path.isfile(mp):
            return
        with open(mp, encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if not ln:
                    continue
                pts = ln.split("|")
                nm = pts[0]
                fld = []
                for p in pts[1:]:
                    a = p.split(":")
                    fld.append((a[0], a[1], a[2] == "1"))
                rows = []
                fp = os.path.join(self.pth, nm + ".dat")
                if os.path.isfile(fp):
                    with open(fp, encoding="utf-8") as rf:
                        for rln in rf:
                            rln = rln.rstrip("\n")
                            if rln:
                                rows.append(rln.split("\t"))
                self.tab[nm] = {"fld": fld, "row": rows}

    def save(self):
        os.makedirs(self.pth, exist_ok=True)
        with open(os.path.join(self.pth, "meta.txt"), "w", encoding="utf-8") as f:
            for nm, tb in self.tab.items():
                pts = [nm] + [":".join([a, b, "1" if c else "0"]) for a, b, c in tb["fld"]]
                f.write("|".join(pts) + "\n")
        for nm, tb in self.tab.items():
            with open(os.path.join(self.pth, nm + ".dat"), "w", encoding="utf-8") as f:
                for rw in tb["row"]:
                    f.write("\t".join(rw) + "\n")

    def cols(self, nm):
        return [x[0] for x in self.tab[nm]["fld"]]

    def pknm(self, nm):
        for a, b, c in self.tab[nm]["fld"]:
            if c:
                return a
        return None

    def typ(self, nm, col):
        for a, b, c in self.tab[nm]["fld"]:
            if a == col:
                return b
        return None

    def cidx(self, nm, col):
        for i, (a, b, c) in enumerate(self.tab[nm]["fld"]):
            if a == col:
                return i
        return -1

    def mk(self, nm, spec):
        if nm in self.tab:
            raise ValueError("exists")
        fld = []
        for p in spec:
            fld.append((p[0], p[1], p[2]))
        self.tab[nm] = {"fld": fld, "row": []}
        self.save()

    def ins(self, nm, vals):
        if nm not in self.tab:
            raise ValueError("no tab")
        tb = self.tab[nm]
        if len(vals) != len(tb["fld"]):
            raise ValueError("bad cnt")
        row = []
        pk = self.pknm(nm)
        pki = self.cidx(nm, pk)
        for i, (a, t, _) in enumerate(tb["fld"]):
            row.append(fmt(vals[i], t))
        for rw in tb["row"]:
            if rw[pki] == row[pki]:
                raise ValueError("dup pk")
        if nm in FKS:
            for fk_col, rt, rc in FKS[nm]:
                ri = self.cidx(nm, fk_col)
                ref = row[ri]
                rpi = self.cidx(rt, rc)
                ok = any(x[rpi] == ref for x in self.tab[rt]["row"])
                if not ok:
                    raise ValueError("bad fk")
        tb["row"].append(row)
        self.save()

    def _cmp(self, a, op, b, typ):
        va = cast(a, typ)
        vb = cast(b, typ)
        if op == "=":
            return va == vb
        if op == "!=":
            return va != vb
        if op == ">":
            return va > vb
        if op == "<":
            return va < vb
        if op == ">=":
            return va >= vb
        if op == "<=":
            return va <= vb
        return False

    def _wok(self, nm, rw, wh):
        if not wh:
            return True
        bits = re.split(r"(\band\b|\bor\b)", wh, flags=re.I)
        res = None
        lop = "AND"
        for seg in bits:
            seg = seg.strip()
            if not seg:
                continue
            if seg.upper() in ("AND", "OR"):
                lop = seg.upper()
                continue
            m = re.match(r"([\w.]+)\s*(>=|<=|!=|=|>|<)\s*(.+)", seg, re.I)
            if not m:
                continue
            col, op, val = m.group(1), m.group(2), m.group(3).strip()
            if len(val) >= 2 and val[0] == val[-1] and val[0] in "'\"":
                val = val[1:-1]
            if "." in col:
                col = col.split(".", 1)[1]
            t = self.typ(nm, col)
            ok = self._cmp(rw[self.cidx(nm, col)], op, val, t)
            if res is None:
                res = ok
            elif lop == "AND":
                res = res and ok
            else:
                res = res or ok
        return res if res is not None else True

    def sel(self, nm, cols=None, wh=None):
        tb = self.tab[nm]
        allc = self.cols(nm)
        if not cols or cols == ["*"]:
            use = allc
        else:
            use = cols
        out = []
        for rw in tb["row"]:
            if self._wok(nm, rw, wh):
                out.append([rw[self.cidx(nm, c)] for c in use])
        return use, out

    def join(self, t1, t2, c1, c2, cols=None, wh=None):
        if t1 not in self.tab or t2 not in self.tab:
            raise ValueError("no tab")
        i1 = self.cidx(t1, c1)
        i2 = self.cidx(t2, c2)
        allc = [t1 + "." + c for c in self.cols(t1)] + [
            t2 + "." + c for c in self.cols(t2)
        ]
        if not cols or cols == ["*"]:
            use = allc
        else:
            use = cols
        out = []
        for r1 in self.tab[t1]["row"]:
            for r2 in self.tab[t2]["row"]:
                if r1[i1] != r2[i2]:
                    continue
                m = {}
                for c in self.cols(t1):
                    m[t1 + "." + c] = r1[self.cidx(t1, c)]
                for c in self.cols(t2):
                    m[t2 + "." + c] = r2[self.cidx(t2, c)]
                if wh and not self._jwok(m, wh):
                    continue
                out.append([m.get(c, "") for c in use])
        return use, out

    def _jwok(self, m, wh):
        bits = re.split(r"(\band\b|\bor\b)", wh, flags=re.I)
        res = None
        lop = "AND"
        for seg in bits:
            seg = seg.strip()
            if not seg:
                continue
            if seg.upper() in ("AND", "OR"):
                lop = seg.upper()
                continue
            mch = re.match(r"([\w.]+)\s*(>=|<=|!=|=|>|<)\s*(.+)", seg, re.I)
            if not mch:
                continue
            col, op, val = mch.group(1), mch.group(2), mch.group(3).strip()
            if len(val) >= 2 and val[0] == val[-1] and val[0] in "'\"":
                val = val[1:-1]
            raw = m.get(col, "")
            if "." in col:
                tnm, tcol = col.split(".", 1)
                t = self.typ(tnm, tcol)
            else:
                t = "STRING"
            ok = self._cmp(raw, op, val, t)
            if res is None:
                res = ok
            elif lop == "AND":
                res = res and ok
            else:
                res = res or ok
        return res if res is not None else True

    def upd(self, nm, sets, wh):
        tb = self.tab[nm]
        n = 0
        for i, rw in enumerate(tb["row"]):
            if self._wok(nm, rw, wh):
                for col, val in sets:
                    t = self.typ(nm, col)
                    rw[self.cidx(nm, col)] = fmt(val, t)
                n += 1
        self.save()
        return n

    def dele(self, nm, wh):
        tb = self.tab[nm]
        keep = []
        n = 0
        for rw in tb["row"]:
            if self._wok(nm, rw, wh):
                n += 1
            else:
                keep.append(rw)
        tb["row"] = keep
        self.save()
        return n


def init_db(db):
    db.mk(
        "datasets",
        [("id", "INT", True), ("name", "STRING", False), ("task", "STRING", False), ("size", "INT", False)],
    )
    db.mk(
        "models",
        [("id", "INT", True), ("name", "STRING", False), ("version", "STRING", False)],
    )
    db.mk(
        "experiments",
        [
            ("id", "INT", True),
            ("dataset_id", "INT", False),
            ("model_id", "INT", False),
            ("accuracy", "FLOAT", False),
            ("status", "STRING", False),
        ],
    )


def seed(db):
    ds = [
        (1, "mnist", "classify", 60000),
        (2, "cifar10", "classify", 50000),
        (3, "imdb", "text", 25000),
        (4, "boston", "regress", 506),
        (5, "iris", "classify", 150),
    ]
    md = [
        (1, "cnn", "v1"),
        (2, "mlp", "v2"),
        (3, "svm", "v1"),
        (4, "rf", "v3"),
        (5, "lstm", "v1"),
    ]
    ex = [
        (1, 1, 1, 0.91, "completed"),
        (2, 1, 2, 0.88, "completed"),
        (3, 2, 1, 0.76, "running"),
        (4, 2, 2, 0.72, "failed"),
        (5, 3, 5, 0.85, "completed"),
        (6, 3, 3, 0.79, "running"),
        (7, 4, 4, 0.65, "completed"),
        (8, 4, 1, 0.68, "failed"),
        (9, 5, 2, 0.94, "completed"),
        (10, 5, 5, 0.92, "completed"),
        (11, 1, 3, 0.81, "completed"),
        (12, 2, 4, 0.74, "running"),
        (13, 3, 1, 0.77, "completed"),
        (14, 4, 2, 0.70, "failed"),
        (15, 5, 3, 0.89, "completed"),
        (16, 1, 4, 0.86, "running"),
        (17, 2, 5, 0.78, "completed"),
        (18, 3, 2, 0.83, "completed"),
        (19, 4, 5, 0.71, "running"),
        (20, 5, 1, 0.93, "completed"),
    ]
    for r in ds:
        db.ins("datasets", r)
    for r in md:
        db.ins("models", r)
    for r in ex:
        db.ins("experiments", r)


def prt(cols, rows):
    print("\t".join(cols))
    for rw in rows:
        print("\t".join(rw))


def run_demo(pth):
    db = DB(pth)
    db.load()
    if not db.tab:
        init_db(db)
        seed(db)
        print("init+seed ok")
    _, rows = db.sel("datasets")
    print("datasets all:")
    prt(db.cols("datasets"), rows)
    cols, rows = db.sel("experiments", ["id", "accuracy", "status"], "status=completed AND accuracy>=0.9")
    print("experiments filter:")
    prt(cols, rows)
    db.upd("experiments", [("status", "done")], "id=3")
    print("update id=3 status->done")
    db.dele("experiments", "status=failed")
    print("delete failed")
    try:
        db.ins("experiments", (99, 99, 1, 0.5, "bad"))
    except ValueError as e:
        print("fk err:", e)
    db.save()
    print("saved", pth)


def main():
    if len(sys.argv) < 2:
        print("usage: main.py <dbpath> demo|show|init|seed|sql...")
        return
    pth = sys.argv[1]
    cmd = sys.argv[2] if len(sys.argv) > 2 else "show"
    db = DB(pth)
    db.load()
    if cmd == "init":
        init_db(db)
        print("ok")
        return
    if cmd == "seed":
        seed(db)
        print("ok")
        return
    if cmd == "demo":
        run_demo(pth)
        return
    if cmd == "show":
        for nm in db.tab:
            print("==", nm)
            _, rows = db.sel(nm)
            prt(db.cols(nm), rows)
        return
    if cmd == "select" and len(sys.argv) >= 4:
        nm = sys.argv[3]
        wh = None
        cols = ["*"]
        end = len(sys.argv)
        if "where" in sys.argv:
            wi = sys.argv.index("where")
            wh = " ".join(sys.argv[wi + 1 :])
            end = wi
        if "join" in sys.argv:
            end = min(end, sys.argv.index("join"))
        mid = sys.argv[4:end]
        if mid and mid[0] != "*":
            cols = [x.strip(",") for x in mid]
        if "join" in sys.argv:
            ji = sys.argv.index("join")
            t2 = sys.argv[ji + 1]
            oi = sys.argv.index("on")
            onp = sys.argv[oi + 1].split("=")
            c1 = onp[0].strip().split(".")[-1]
            c2 = onp[1].strip().split(".")[-1]
            cols2, rows = db.join(
                nm,
                t2,
                c1,
                c2,
                cols if cols != ["*"] else None,
                wh,
            )
            prt(cols2, rows)
        else:
            cols2, rows = db.sel(nm, cols, wh)
            prt(cols2, rows)
        return
    if cmd == "insert" and len(sys.argv) >= 5:
        nm = sys.argv[3]
        vals = sys.argv[4:]
        db.ins(nm, vals)
        print("ok")
        return
    if cmd == "update" and len(sys.argv) >= 6:
        nm = sys.argv[3]
        wh = None
        if "where" in sys.argv:
            wi = sys.argv.index("where")
            wh = " ".join(sys.argv[wi + 1 :])
            body = sys.argv[4:wi]
        else:
            body = sys.argv[4:]
        sets = []
        for p in body:
            a, b = p.split("=", 1)
            sets.append((a, b))
        n = db.upd(nm, sets, wh)
        print("upd", n)
        return
    if cmd == "delete" and len(sys.argv) >= 4:
        nm = sys.argv[3]
        wh = " ".join(sys.argv[5:]) if len(sys.argv) > 5 and sys.argv[4] == "where" else None
        n = db.dele(nm, wh)
        print("del", n)
        return
    print("unknown cmd")


if __name__ == "__main__":
    main()

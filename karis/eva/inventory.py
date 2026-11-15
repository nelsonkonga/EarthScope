"""Inventory of every molette Eva holds, by kind, with the entries (resources) each uses."""

from __future__ import annotations

from collections import Counter

from .molettes import Rhythm


def _levels(node: Rhythm | None) -> list[Rhythm]:
    out = []
    while node is not None:
        out.append(node)
        node = node.child
    return out


def inventory(eva) -> dict:
    obs, dec = eva.obs, eva.dec
    base = [c for c in obs.channels.values() if c.members is None]
    meta = [c for c in obs.channels.values() if c.members is not None]

    def time_side(chans):
        n_time = Counter()  # level -> count (level 1 = the time molette itself)
        entries = Counter()
        for c in chans:
            n_time[1] += 1
            entries[1] += c.time.size() + c.time_ctx.size()
            for node in _levels(c.rhythm):
                n_time[node.level] += 1
                entries[node.level] += node.trans.size() + node.runs.size()
        return n_time, entries

    base_time, base_time_e = time_side(base)
    meta_time, meta_time_e = time_side(meta)

    # Decision molettes: one per molette that holds at least one note.
    kinds = {"p": set(), "c": set(), "t": set(), "n": set(), "m": set(), "mt": set()}
    notes = Counter()
    for f in dec.w:
        k = f[0]
        if k == "n":
            kinds[k].add((f[1], f[2]))
        else:
            kinds[k].add(f[1])
        notes[k] += 1
    origin = Counter(dec.origin.get(S, "feedback") for S in dec.metas)
    stat_arity = Counter(len(m) for m in obs.metas)
    dec_arity = Counter(len(S) for S in dec.metas)

    inv = {
        "standard": {
            "molettes": len(base),
            "entries": sum(c.trans.size() for c in base),
        },
        "time": {
            "molettes": base_time[1],
            "entries": base_time_e[1],
        },
        "n_time": {
            "molettes_by_level": {str(k): v for k, v in sorted(base_time.items()) if k >= 2},
            "molettes": sum(v for k, v in base_time.items() if k >= 2),
            "entries": sum(v for k, v in base_time_e.items() if k >= 2),
        },
        "correlation_standard": {  # n9 méta molettes standard
            "molettes": len(meta),
            "by_arity": {str(k): v for k, v in sorted(stat_arity.items())},
            "by_criterion": dict(Counter(obs.meta_kind.get(m, "timing") for m in obs.metas)),
            "list": [list(m) for m in obs.metas],
            "entries": sum(c.trans.size() for c in meta),
        },
        "correlation_time": {  # n12 méta molettes de temps (+ their N-time levels)
            "molettes": meta_time.get(1, 0),
            "n_time_molettes": sum(v for k, v in meta_time.items() if k >= 2),
            "entries": sum(meta_time_e.values()),
        },
        "decision": {  # n8
            "of_standard": len(kinds["p"]),
            "of_change": len(kinds["c"]),
            "of_time": len(kinds["t"]),
            "of_n_time": len(kinds["n"]),
            "of_correlation_time": len(kinds["mt"]),
            "entries": notes["p"] + notes["c"] + notes["t"] + notes["n"] + notes["mt"],
        },
        "correlation_decision": {  # n10 méta molettes de décision
            "molettes": len(dec.metas),
            "by_origin": dict(origin),
            "by_arity": {str(k): v for k, v in sorted(dec_arity.items())},
            "created_from_feedback": dec.created_from_feedback,
            "created_from_stats": dec.created_from_stats,
            "pruned": getattr(dec, "pruned", 0),
            "list": [list(S) for S in dec.metas],
            "entries": notes["m"],
        },
    }
    inv["totals"] = {
        "standard": inv["standard"]["molettes"],
        "time": inv["time"]["molettes"] + inv["n_time"]["molettes"],
        "decision": sum(v for k, v in inv["decision"].items() if k.startswith("of_")) + len(dec.metas),
        "correlation": len(meta) + inv["correlation_time"]["molettes"] + len(dec.metas),
        "molettes": 0,
        "entries": obs.size() + dec.size(),
        "statistical_entries": obs.size(),
        "decision_entries": dec.size(),
    }
    t = inv["totals"]
    t["molettes"] = (
        inv["standard"]["molettes"]
        + inv["time"]["molettes"]
        + inv["n_time"]["molettes"]
        + inv["correlation_standard"]["molettes"]
        + inv["correlation_time"]["molettes"]
        + inv["correlation_time"]["n_time_molettes"]
        + t["decision"]
    )
    return inv


def table(inv: dict) -> str:
    """Human-readable summary."""
    s, t, n, cs, ct, d, cd = (
        inv["standard"], inv["time"], inv["n_time"], inv["correlation_standard"],
        inv["correlation_time"], inv["decision"], inv["correlation_decision"],
    )
    rows = [
        ("Molettes standard (n6)", s["molettes"], s["entries"]),
        ("Molettes de temps (n7)", t["molettes"], t["entries"]),
        (f"N-molettes de temps (n13) {n['molettes_by_level']}", n["molettes"], n["entries"]),
        (f"Méta molettes standard (n9) {cs['by_criterion']}", cs["molettes"], cs["entries"]),
        (f"Méta molettes de temps (n12) +{ct['n_time_molettes']} N-temps", ct["molettes"], ct["entries"]),
        (f"Molettes de décision (n8) std={d['of_standard']} chg={d['of_change']} temps={d['of_time']} "
         f"N-temps={d['of_n_time']} méta-temps={d['of_correlation_time']}",
         inv["totals"]["decision"] - cd["molettes"], d["entries"]),
        (f"Méta molettes de décision (n10) {cd['by_origin']} élaguées={cd['pruned']}", cd["molettes"], cd["entries"]),
    ]
    w = max(len(r[0]) for r in rows)
    lines = [f"{'Kind'.ljust(w)}  molettes  entries"]
    lines += [f"{r[0].ljust(w)}  {r[1]:>8}  {r[2]:>7}" for r in rows]
    tt = inv["totals"]
    lines.append(f"{'TOTAL'.ljust(w)}  {tt['molettes']:>8}  {tt['entries']:>7}")
    return "\n".join(lines)

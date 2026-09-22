"""Merge result JSONs into the tables that go straight into the technical report."""
import glob, json, sys

files = sys.argv[1:] or sorted(glob.glob("results/*.json"))
R = [json.load(open(f)) for f in files]
if not R:
    sys.exit("no results")
base = R[0]

def row(vals, w): return "| " + " | ".join(str(v).ljust(x) for v, x in zip(vals, w)) + " |"

print("\n### Environments\n")
w = [22, 9, 7, 6, 16, 9]
print(row(["label", "arch", "OpenCV", "cores", "instance", "COOL?"], w))
print("|" + "|".join("-" * (x + 2) for x in w) + "|")
for r in R:
    p = r["provenance"]
    print(row([r["label"], p["arch"], p["opencv_version"], p["logical_cores"],
               p.get("ec2_instance_type") or "local",
               "YES" if p["cool_verified"] else "no"], w))

print(f"\n### Hot-path ops — ms/call (speedup vs `{base['label']}`)\n")
names = list(base["ops"])
w = [22] + [20] * len(R)
print(row(["op"] + [r["label"] for r in R], w))
print("|" + "|".join("-" * (x + 2) for x in w) + "|")
for n in names:
    cells = []
    for r in R:
        v = r["ops"][n]["per_call_ms"]; b = base["ops"][n]["per_call_ms"]
        cells.append(f"{v:.3f}" + ("" if r is base else f"  ({b/v:.2f}x)"))
    print(row([n] + cells, w))

print(f"\n### End-to-end TREMOR analysis (the claimed core workload)\n")
w = [22, 12, 13, 15, 13, 16]
print(row(["label", "ms/frame", "x realtime", "video-h/compute-h", "speedup", "$/video-hour"], w))
print("|" + "|".join("-" * (x + 2) for x in w) + "|")
for r in R:
    e, c = r["e2e"], r["cost"]
    sp = "-" if r is base else f"{base['e2e']['ms_per_frame']/e['ms_per_frame']:.2f}x"
    usd = c["usd_per_video_hour"]
    usd = "n/a (price unset)" if usd is None else f"${usd:.4f}"
    print(row([r["label"], f"{e['ms_per_frame']:.2f}", f"{e['realtime_factor']:.1f}",
               f"{c['video_hours_per_compute_hour']:.1f}", sp, usd], w))

if any(r.get("process_scaling") for r in R):
    print("\n### Process scaling — aggregate x realtime (parallel efficiency)\n")
    ns = sorted({int(t) for r in R if r.get("process_scaling") for t in r["process_scaling"]})
    w = [22] + [16] * len(ns)
    print(row(["label"] + [f"{n} workers" for n in ns], w))
    print("|" + "|".join("-" * (x + 2) for x in w) + "|")
    for r in R:
        s_ = r.get("process_scaling") or {}
        cells = []
        for n in ns:
            v = s_.get(str(n), s_.get(n))
            cells.append(f"{v['aggregate_realtime_factor']:.1f} ({v['efficiency_vs_1x']*100:.0f}%)"
                         if v else "-")
        print(row([r["label"]] + cells, w))

if any(r.get("thread_scaling") for r in R):
    print("\n### Thread scaling (x realtime)\n")
    ts = sorted({int(t) for r in R if r.get("thread_scaling") for t in r["thread_scaling"]})
    w = [22] + [8] * len(ts)
    print(row(["label"] + [f"{t}t" for t in ts], w))
    print("|" + "|".join("-" * (x + 2) for x in w) + "|")
    for r in R:
        s = r.get("thread_scaling") or {}
        print(row([r["label"]] + [f"{s.get(str(t), s.get(t, 0)):.1f}" if (str(t) in s or t in s)
                                  else "-" for t in ts], w))

unver = [r["label"] for r in R if not r["cost"]["ec2_price_verified"]]
if unver:
    print(f"\n> **Cost figures withheld** for {', '.join(unver)}: EC2 on-demand rates in "
          f"`bench/pricing.json` are unverified placeholders. Set them from the AWS "
          f"pricing page and flip `_verified` to true before publishing any cost claim.")
print()

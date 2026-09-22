"""One command per environment. Compare the JSONs afterwards with compare.py.

  python run_bench.py --label mac-m-stock
  python run_bench.py --label graviton-stock --instance m8g.4xlarge
  python run_bench.py --label graviton-cool  --instance m8g.4xlarge

NOTE: the __main__ guard is load-bearing. process_scaling() uses a spawn-based
ProcessPoolExecutor, which re-imports this file in every child; without the guard
each child re-runs argparse and the pool dies with BrokenProcessPool.
"""
import argparse, sys
sys.path.insert(0, ".")
from bench.core import provenance, save
from bench.suite import ops, e2e, thread_scaling, process_scaling
from bench.cost import cost_report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    ap.add_argument("--instance", default=None, help="override instance type for costing")
    ap.add_argument("--clip-seconds", type=float, default=20.0)
    ap.add_argument("--no-scaling", action="store_true")
    a = ap.parse_args()

    prov = provenance()
    inst = a.instance or prov.get("ec2_instance_type") or "local"
    tag = f"[{a.label}]"
    print(f"{tag} {prov['arch']} | OpenCV {prov['opencv_version']} | "
          f"{prov['logical_cores']} cores | instance={inst}")
    print(f"{tag} COOL verified: {prov['cool_verified']}  {prov['cool_verification_parts']}")

    print(f"{tag} ops ...", flush=True)
    o = ops()
    print(f"{tag} end-to-end ...", flush=True)
    e = e2e(seconds=a.clip_seconds)

    ts = ps = None
    if not a.no_scaling:
        print(f"{tag} thread scaling ...", flush=True)
        ts = thread_scaling()
        print(f"{tag} process scaling ...", flush=True)
        ps = process_scaling()

    c = cost_report(e, inst)
    p = save({"label": a.label, "provenance": prov, "ops": o, "e2e": e,
              "thread_scaling": ts, "process_scaling": ps, "cost": c},
             f"results/{a.label}.json")
    print(f"{tag} {e['realtime_factor']:.1f}x realtime, "
          f"{e['ms_per_frame']:.2f} ms/frame -> {p}")


if __name__ == "__main__":
    main()

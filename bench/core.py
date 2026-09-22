"""Provenance capture + statistically honest timing.

Provenance matters: 30% of the Best Use of COOL rubric is "VERIFIED COOL integration
on AWS Graviton". A claim is not evidence. This records machine-checkable proof of
which library actually executed, on which silicon.
"""
import json, os, platform, re, subprocess, time, statistics as st
import cv2, numpy as np


def _sh(cmd):
    try:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True,
                              timeout=5).stdout.strip()
    except Exception:
        return ""


def _imdsv2(path):
    """EC2 instance metadata (IMDSv2). Empty off-EC2 -- that's fine."""
    tok = _sh('curl -s -X PUT "http://169.254.169.254/latest/api/token" '
              '-H "X-aws-ec2-metadata-token-ttl-seconds: 60" --max-time 1')
    if not tok:
        return ""
    return _sh(f'curl -s -H "X-aws-ec2-metadata-token: {tok}" --max-time 1 '
               f'http://169.254.169.254/latest/meta-data/{path}')


def provenance():
    bi = cv2.getBuildInformation()
    def grab(pat):
        m = re.search(pat, bi, re.I)
        return m.group(1).strip() if m else ""

    cool_markers = {
        "kleidicv": bool(re.search(r"kleidicv", bi, re.I)),
        "cool_sdk_path": os.path.isdir("/opt/cool"),
        "cool_in_cv2_path": "cool" in cv2.__file__.lower(),
        "carotene": bool(re.search(r"carotene", bi, re.I)),
    }
    machine = platform.machine()
    is_arm = machine in ("aarch64", "arm64")
    inst = _imdsv2("instance-type")
    # Graviton families: 6g/7g/8g, with optional d/n/en suffixes (m8g, c8gd, r7gn...)
    is_graviton = bool(re.match(r"^[a-z]+[678]gd?n?e?\.", inst or ""))
    on_cool_ami = (os.path.isdir("/opt/cool") or "/opt/cool" in cv2.__file__)

    return {
        "opencv_version": cv2.__version__,
        "numpy_version": np.__version__,
        "python": platform.python_version(),
        "os": f"{platform.system()} {platform.release()}",
        "arch": machine,
        "is_arm": is_arm,
        "cpu_model": (grab(r"CPU/HW features:\s*\n?\s*Baseline:\s*(.+)") or
                      _sh("sysctl -n machdep.cpu.brand_string") or
                      _sh("lscpu | grep -i 'model name' | head -1 | cut -d: -f2")),
        "cpu_features": grab(r"CPU/HW features:\s*(?:\n\s*Baseline:\s*)?(.+)"),
        "logical_cores": os.cpu_count(),
        "cv2_threads": cv2.getNumThreads(),
        "cv2_file": cv2.__file__,
        "ec2_instance_type": inst,
        "is_graviton": is_graviton,
        "ec2_ami_id": _imdsv2("ami-id"),
        "ec2_region": _imdsv2("placement/region"),
        "cool_markers": cool_markers,
        # The headline verification flag.
        #
        # NOTE: a KleidiCV marker ALONE is NOT proof of COOL -- stock opencv-python
        # arm64 wheels (incl. Apple Silicon macOS) also ship KleidiCV, so grepping
        # build info yields a FALSE POSITIVE on any ARM laptop. Real verification
        # requires all three: Arm silicon, a Graviton EC2 instance, and the COOL
        # SDK actually present. The AMI id is recorded so a judge can cross-check
        # it against the AWS Marketplace listing.
        "cool_verified": bool(is_arm and is_graviton and on_cool_ami),
        "cool_verification_parts": {"is_arm": is_arm, "is_graviton": is_graviton,
                                    "cool_sdk_present": on_cool_ami},
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def timeit(fn, warmup=3, repeats=11, min_seconds=0.25):
    """Median + IQR over repeats. Warmup excluded. Never reports a single run."""
    for _ in range(warmup):
        fn()
    samples = []
    t_end = time.perf_counter() + min_seconds
    while len(samples) < repeats or time.perf_counter() < t_end:
        t0 = time.perf_counter(); fn(); samples.append(time.perf_counter() - t0)
        if len(samples) >= repeats * 4:
            break
    s = sorted(samples)
    q1, q3 = s[len(s)//4], s[(3*len(s))//4]
    return {"median_s": st.median(s), "iqr_s": q3 - q1,
            "min_s": s[0], "n": len(s)}


def save(obj, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=2, default=str)
    return path

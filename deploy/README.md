# Graviton + COOL benchmark runbook

Goal: three comparable measurements of the **same** workload, so the library is the
only variable.

| label | where | library |
|---|---|---|
| `graviton-cool` | c8g.2xlarge, COOL AMI | COOL (KleidiCV-optimised OpenCV 5.0) |
| `graviton-stock` | **same instance**, separate venv | stock `opencv-python-headless` 5.0.0 |

Running both on the same instance isolates the library from silicon, kernel and
clip. Budget roughly **20 minutes** of instance time and **under $1**.

## 0. Before launching

- [ ] AWS budget exists (`tremor-opencv-competition`, $25, alerts at 20/40/100%)
- [ ] COOL subscription active — the 7-day software-charge trial started on subscribe
- [ ] Know your public IP for the security group

## 1. Launch

[Marketplace console](https://console.aws.amazon.com/marketplace/home#/subscriptions)
→ Cloud Optimized OpenCV for AWS Graviton4 → **Launch**

- Instance type **`c8g.2xlarge`** (8 vCPU, $0.319/hr + $0.02/hr COOL).
  Not the vendor-recommended m8g.4xlarge: our own process-scaling data shows parallel
  efficiency falling to 60% at 4 workers, so 16 vCPUs would be idle at double the cost.
- Region **us-east-1** (matches `bench/pricing.json`)
- Key pair: create and download
- Security group: **SSH (22) from My IP** only
- Storage: default

## 2. Ship the code

No GitHub remote needed:

```bash
tar czf - --exclude=.venv --exclude=.git --exclude='*.MOV' -C ~ tremor \
  | ssh -i <key.pem> ubuntu@<ip> 'tar xzf -'
```

(For the submission you will want a judge-accessible repo anyway — a **private**
GitHub repo is fine, the rules do not require open source.)

## 3. Run

```bash
ssh -i <key.pem> ubuntu@<ip>
cd ~/tremor
./deploy/run_all.sh c8g.2xlarge
```

That runs COOL, then the stock baseline on the same box, then writes
`results/report.md` and `/tmp/tremor-results.tgz`.

**It aborts before collecting any data if `cool_verified` is False.** All three
conditions must hold — Arm silicon, a Graviton instance type, and `/opt/cool`
present — so you cannot accidentally publish stock numbers under a COOL label.

## 4. Collect and shut down

```bash
scp -i <key.pem> ubuntu@<ip>:/tmp/tremor-results.tgz .
```

Then **terminate the instance**. Also check: EBS volume deleted, no Elastic IP held.

## Design notes

- **`setup_cool.sh` installs nothing.** The benchmark needs only cv2 and numpy, both
  already on the AMI. `pip install` into `/opt/cool` would risk an ABI mismatch with
  the numpy that COOL's cv2 was built against — breaking the thing being measured.
- **The stock baseline uses the headless wheel.** The server AMI has no libGL and the
  full wheel would fail to import. Only highgui differs; every imgproc/core function
  benchmarked is identical and no GUI is used.
- **`compare.py` is called with explicit arguments** so stock is the baseline. Left to
  glob alphabetically it would pick `graviton-cool` first and invert every speedup.
- **Fill in EC2 prices before quoting cost.** `bench/pricing.json` ships them
  `_verified: false` (sourced from Vantage, not the AWS pricing API) and `compare.py`
  prints "n/a" rather than a guess.

## What the results should show

- `phaseCorrelate` is ~100% of the hot path (3.05 ms/call vs <0.26 ms for everything
  else), so whatever COOL does to it drives the end-to-end number.
- Thread scaling is flat — it does not parallelise internally. Throughput comes from
  N single-threaded worker processes, one per vCPU.
- On an 8-core Apple M-series, process scaling hit 60% efficiency at 4 workers and 39%
  at 8, likely from heterogeneous P/E cores. **Graviton4 has uniform cores, so expect
  better linearity — this run confirms or refutes that prediction.**

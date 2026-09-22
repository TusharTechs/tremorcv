# Running the TREMOR benchmark on AWS Graviton

Goal: three comparable measurements of the **same** workload.

| label | where | library |
|---|---|---|
| `graviton-cool` | Graviton (m8g.4xlarge), COOL AMI | COOL (KleidiCV-optimised OpenCV 5.0) |
| `graviton-stock` | **same instance**, separate venv | stock `opencv-python` 5.0.0 |
| `x86-stock` | c7i.2xlarge | stock `opencv-python` 5.0.0 |

Running stock and COOL on the *same* instance isolates the library as the only
variable. The x86 run exists for the cost argument, not the speed argument.

## 1. Launch

1. AWS Marketplace → **Cloud Optimized OpenCV for AWS Graviton4**
   (`prodview-fdvbfiewzuehs`). 7-day free trial; software cost on m8g.4xlarge is
   $0.04/hr on top of EC2.
2. Subscribe → Launch → instance type **m8g.4xlarge** (vendor-recommended).
3. Security group: SSH from your IP only.
4. `ssh -i key.pem ubuntu@<ip>`

## 2. Benchmark

```bash
git clone <your repo> tremor && cd tremor

# COOL
./deploy/setup_cool.sh
source /opt/cool/venvs/python_3.12/bin/activate
python run_bench.py --label graviton-cool --instance m8g.4xlarge

# stock, same box
./deploy/setup_stock.sh
source ~/stock-venv/bin/activate
python run_bench.py --label graviton-stock --instance m8g.4xlarge
```

Copy `results/*.json` back, then `python compare.py` for the report tables.

## 3. Before publishing any cost number

`bench/pricing.json` ships EC2 rates as `null` with `_verified: false`, and
`compare.py` withholds cost rather than printing a guess. Fill in the real
on-demand rates from <https://aws.amazon.com/ec2/pricing/on-demand/> for your
region and set `_verified: true`.

## Notes that shape the architecture

- **`phaseCorrelate` is ~100% of the hot path** (2.2 ms/call vs <0.25 ms for every
  other op). Whatever COOL does to it determines the end-to-end number.
- **Thread scaling is flat** — it does not parallelise internally. Throughput comes
  from N single-threaded worker processes, one per vCPU. Workers call
  `cv2.setNumThreads(1)` to avoid oversubscription.
- On an 8-core Apple M-series, process scaling hit 36% efficiency at 8 workers
  (heterogeneous P/E cores). Graviton4 has uniform cores, so **expect better
  linearity** — that is a prediction this harness will confirm or refute.

## Cost note

Shut the instance down when idle. The COOL AMI bills hourly while running.

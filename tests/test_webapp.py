"""Web endpoint contract. Kept light: no network, no uploads of real footage."""
import json, numpy as np, cv2, os, tempfile, pytest
from fastapi.testclient import TestClient
from webapp.server import app, MAX_UPLOAD_MB

client = TestClient(app)


def test_health_reports_opencv_and_provenance():
    r = client.get("/api/health")
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is True
    assert d["opencv"].startswith("5."), f"competition requires OpenCV 5, got {d['opencv']}"
    assert "cool_verified" in d


def test_config_exposes_the_thresholds_the_ui_renders():
    d = client.get("/api/config").json()
    assert set(d["faults"]) >= {"healthy", "unbalance", "misalignment", "mechanical_looseness"}
    assert d["snr_trust"] > 0 and d["confidence_to_report"] > 0
    assert d["aim_points"]


def test_index_is_served():
    r = client.get("/")
    assert r.status_code == 200 and "<!doctype html>" in r.text.lower()


def test_measure_rejects_a_file_that_is_not_video():
    r = client.post("/api/measure", files={"file": ("x.mp4", b"not a video", "video/mp4")},
                    data={"fps": "0"})
    assert r.status_code == 400, r.text


def test_measure_handles_a_real_clip_and_returns_the_expected_shape():
    """A short synthetic clip with a known 5 Hz component, end to end through HTTP."""
    from tremor.machine import make_machine_clip
    fr = make_machine_clip([(5.0, 0.8)], fps=30, seconds=6, size=(240, 380),
                           contrast=1.0, noise_dn=2.0, shake_rms=0.0, rolling=False)
    p = os.path.join(tempfile.gettempdir(), "tremor_web_test.mp4")
    vw = cv2.VideoWriter(p, cv2.VideoWriter_fourcc(*"avc1"), 30, (380, 240), False)
    for f in fr:
        vw.write(f.astype(np.uint8))
    vw.release()
    try:
        with open(p, "rb") as fh:
            r = client.post("/api/measure", files={"file": ("t.mp4", fh, "video/mp4")},
                            data={"fps": "0"})
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("measurement", "quality", "spectrum", "source", "preview", "shaft_hz"):
            assert k in d, f"missing {k}"
        assert abs(d["measurement"]["peaks"][0]["freq_hz"] - 5.0) < 0.3
        assert d["source"]["rois_auto"] is True
        assert d["preview"].startswith("data:image/jpeg;base64,")
        json.dumps(d)          # must stay serialisable
    finally:
        os.path.exists(p) and os.unlink(p)


def test_upload_cap_is_configurable_and_finite():
    assert 0 < MAX_UPLOAD_MB <= 500


def test_agent_stream_rejects_an_unknown_fault():
    r = client.get("/api/agent/stream", params={"fault": "not_a_fault"})
    assert r.status_code == 400

"""Exercise the MCP server the way a client would. Proves the loop works over the
protocol without needing any LLM, API key, or cloud account."""
import asyncio, json
from agent.mcp_server import mcp


async def call(name, **kw):
    r = await mcp.call_tool(name, kw)
    return json.loads(r.content[0].text)


async def main():
    ts = await mcp.list_tools()
    print(f"{len(ts)} tools: " + ", ".join(t.name for t in ts) + "\n")

    print(await call("start_session", session_id="s1", shaft_hz=4.3,
                     fault="misalignment", severity_px=0.6, start_aim="housing"))

    # 1. naive first attempt at the smooth housing
    c = await call("capture_clip", session_id="s1", aim="housing", fps=30,
                   seconds=10, braced=False)
    s = await call("assess_surface", clip_id=c["clip_id"])
    m = await call("measure", clip_id=c["clip_id"])
    q = await call("assess_quality", clip_id=c["clip_id"])
    print(f"\n[1] aim=housing  texture={s['texture_std']:.1f} sufficient={s['sufficient']}")
    print(f"    top peak {m['peaks'][0]['freq_hz']:.2f} Hz SNR {m['peaks'][0]['snr']:.1f}")
    print(f"    quality -> {q}")

    # 2. client reacts to `reasons` and re-aims -- this is the agentic step
    print("\n    client reads reasons=low_texture -> re-aiming at 'grille'")
    c2 = await call("capture_clip", session_id="s1", aim="grille", fps=30,
                    seconds=10, braced=False)
    s2 = await call("assess_surface", clip_id=c2["clip_id"])
    m2 = await call("measure", clip_id=c2["clip_id"])
    q2 = await call("assess_quality", clip_id=c2["clip_id"])
    print(f"\n[2] aim=grille   texture={s2['texture_std']:.1f} sufficient={s2['sufficient']}")
    print(f"    top peak {m2['peaks'][0]['freq_hz']:.2f} Hz SNR {m2['peaks'][0]['snr']:.1f}")
    print(f"    quality -> {q2}")

    shaft = min(p["freq_hz"] for p in m2["peaks"] if p["snr"] >= 6.0)
    dx = await call("diagnose", clip_id=c2["clip_id"], shaft_hz=shaft)
    print(f"\n[3] shaft {shaft:.2f} Hz -> {dx['fault']} (confidence {dx['confidence']})")
    print(f"    harmonics {dx['ratios']}  total {dx['total_px']} px")

    # guard: diagnosing above Nyquist is refused, not silently wrong
    bad = await call("diagnose", clip_id=c2["clip_id"], shaft_hz=11.3)
    print(f"\n[4] Nyquist guard: {bad.get('error','(none)')}")

    print(f"\n    ground truth: {await call('reveal_ground_truth', session_id='s1')}")

asyncio.run(main())

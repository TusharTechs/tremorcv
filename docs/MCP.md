# TREMOR over MCP

The competition rules name MCP directly:

> "The agent may use any framework or model and may invoke OpenCV 5 and, where
> applicable, COOL through APIs, tools, or **Model Context Protocol (MCP)**."

So the OpenCV tool surface is exposed as an MCP server. Any MCP-capable client can
be the orchestrator — Claude Code, Claude Desktop, Kiro, or anything else. No LLM
vendor is baked in, and no API key is needed to run the deterministic policy.

## Two orchestrators, one tool surface

| Path | Orchestrator | Needs an LLM? | Purpose |
|---|---|---|---|
| `agent/loop.py` | deterministic policy | no | Reproducible reference. Judges can run `eval_agent.py` with zero credentials and reproduce the measured numbers. |
| `agent/mcp_server.py` | any MCP client | client's own | Open-ended interaction, natural-language reporting, unanticipated situations. |

Both call the same `agent/tools.py`, so a finding from one transfers to the other.

## Run

```bash
python -m agent.mcp_server          # stdio transport
python test_mcp.py                  # exercise the whole loop, no client needed
```

To attach it to Claude Code, add `.mcp.json` at the repo root:

```json
{
  "mcpServers": {
    "tremor": {
      "command": ".venv/bin/python",
      "args": ["-m", "agent.mcp_server"]
    }
  }
}
```

## Tools

| Tool | Role |
|---|---|
| `start_session` | Open a machine. The fault is hidden from the caller. |
| `capture_clip` | **The action.** aim / fps / braced genuinely change what is recorded. |
| `assess_surface` | Enough texture to phase-correlate? Cheap; call it first. |
| `measure` | Core OpenCV 5 workload → ranked spectral peaks. |
| `assess_quality` | Trustworthy? Returns machine-readable `reasons`. |
| `diagnose` | 1x/2x/3x → fault. Refuses when 2x exceeds Nyquist. |
| `compare_baseline` | Trend against the asset's own history. |
| `reveal_ground_truth` | Evaluation only, for scoring a run. |

Clips stay server-side behind a `clip_id`; frame arrays never cross the protocol.

## Why the guard rails are in the tools, not the prompt

`diagnose` **refuses** when 2× exceeds Nyquist instead of returning a plausible
wrong answer. A prompt instruction can be ignored by a model; a tool that returns
an error cannot. The same applies to `assess_quality`, which returns structured
`reasons` (`low_texture`, `low_snr`, `possible_aliasing`, `unstable_correlation`)
that map to distinct remedies rather than a prose explanation the client has to
interpret.

## Note on AWS

The "meaningful component on AWS" requirement is satisfied by the OpenCV workload
running on Graviton with COOL — not by the language model. Keeping orchestration
model-agnostic costs nothing against the rules and avoids depending on a managed
LLM service.

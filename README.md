# opsharness-ambient

Ambient assistant agent, open source, running on the [opsharness](https://github.com/prithsk/opsharness) agent harness. It reads a day of transcribed conversation and turns the user's real commitments and appointments into reminders and calendar events. It skips other people's promises, hypotheticals, declined asks and loops the user already closed.

It is inspired by how Moonshot (YC S26) describes its product publicly. It is not their code and has no connection to them.

## Quick start

```
pip install -e .
python -m opsharness.agent --project ambient --policy anthropic:claude-haiku-4-5-20251001
```

That starts the servers listed in `mcp.json`, gives the model the rules in `opsharness_ambient/world.md` plus `AGENT.md`, and stops at your terminal before any action that needs approval. Out of the box, `mcp.json` serves this repo's test world, so it runs with no accounts and reports a score. Each run writes `runs/live/ambient/<stamp>/summary.md` and `trace.json`.

Useful flags: `--task "..."` sets the job, `--approver file` writes each request to `approvals/*.md` and waits for you to change `decision: pending` to `approved` or `denied`, `--approver deny` makes a dry run, and `--backend sim` runs the test world in-process.

The model keys come from `ANTHROPIC_API_KEY`, or from `OPENAI_API_KEY` plus `OPENAI_BASE_URL` for any OpenAI-compatible provider such as OpenRouter (`--policy openai:<model-id>`).

## Connect real systems

Replace the `sim` server in `mcp.json` with MCP servers for a transcript source, a calendar and a reminders app. Any tool its server does not mark `readOnlyHint: true` needs approval by default, and the `approve` patterns override that per `server/tool`. The business rules in `world.md` stay the same. Keep tokens in environment variables and write them in mcp.json as `${NAME}`, never as the literal value. See SECURITY.md before connecting anything real.

## The test world

`opsharness_ambient/world.py` generates a fresh instance per seed with a hidden answer key, so every run gets a score with no grader model. Dates are relative ("by Thursday"), the transcript is paged, and one loop opens in the morning and closes in the afternoon.

Run the tests with `python -m unittest discover -s tests -t .`. The contract tests from the core check that the correct plan scores 1.0, doing nothing scores 0.0, approvals get enforced, the harness survives injected model slips, and the world still scores 1.0 over MCP. The wrong-agent tests check that realistic mistakes lose points.

To use the world from Claude Desktop or Claude Code, add it as an MCP server with `python -m opsharness.mcp_serve --env ambient --seed 3`.

## Status

The scorers and the harness path are verified. No real model has run against this world yet, and no real system is connected yet. TASKS.md lists what comes next.

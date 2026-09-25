# Test-quality probe report

Task: `mediapulse-ingest`  ·  Probes: gameability, altsolve, alignment, leakage  ·  Models: glm-5.2  ·  Rollouts: 4

⚠️  Inconclusive — no probe produced a usable agent run.

## Gameability (under-specification)

⚠️  **Inconclusive** — all rollouts errored, no usable agent runs.
- glm-5.2: errored (agent produced no work (failed to launch or the model call errored): )
  `harbor view /Users/azeez/Azeez/microai/mediapulse-ingest/jobs/probe-gameability-glm-5.2-44c2af66`

## Alt-solution (over-specification)

⚠️  **Inconclusive** — all rollouts errored, no usable agent runs.
- glm-5.2: errored (agent produced no work (failed to launch or the model call errored): )
  `harbor view /Users/azeez/Azeez/microai/mediapulse-ingest/jobs/probe-altsolve-glm-5.2-d80d0ff4`

## Alignment (prompt↔tests)

⚠️  **Inconclusive** — all rollouts errored, no usable agent runs.
- glm-5.2: errored (agent produced no work (failed to launch or the model call errored): )
  `harbor view /Users/azeez/Azeez/microai/mediapulse-ingest/jobs/probe-alignment-glm-5.2-464752a6`

## Leakage (answer in the environment)

⚠️  **Inconclusive** — all rollouts errored, no usable agent runs.
- glm-5.2: errored (agent produced no work (failed to launch or the model call errored): )
  `harbor view /Users/azeez/Azeez/microai/mediapulse-ingest/jobs/probe-leakage-glm-5.2-2e47b815`

---

**These verdicts are LLM-assisted — verify before acting.** Each probe's full rollout is preserved so you can check it yourself:

- `harbor view /Users/azeez/Azeez/microai/mediapulse-ingest/jobs/probe-alignment-glm-5.2-464752a6`
- `harbor view /Users/azeez/Azeez/microai/mediapulse-ingest/jobs/probe-altsolve-glm-5.2-d80d0ff4`
- `harbor view /Users/azeez/Azeez/microai/mediapulse-ingest/jobs/probe-gameability-glm-5.2-44c2af66`
- `harbor view /Users/azeez/Azeez/microai/mediapulse-ingest/jobs/probe-leakage-glm-5.2-2e47b815`

Inside each job: the agent's patch (`artifacts/agent_patch.diff`), the verifier output (`verifier/test-stdout.txt` and `test-cmd-stdout.txt` for the actual assertion failures), and the agent transcript under `agent/`. Read the agent's diff and confirm whether it truly solves the task / games the tests before trusting the verdict.

<!-- rv:probe-fingerprint:8275e8482a65816b -->

# Test-quality probe report

Task: `mediapulse-ingest`  ·  Probes: gameability, altsolve, alignment, leakage  ·  Models: glm-5.2  ·  Rollouts: 4  ·  Est. cost: $3.12 (rollouts $2.98 + judging $0.140)

🚩 1 defect(s) found (1/4 rollouts confirmed).

## How to act on these findings

**Unsupported requirements must be resolved** — state the behaviour in the brief, or stop enforcing it in the tests.

## Gameability (under-specification)

| # | Model | Tests passed? | Verdict | Confidence | Cost* | Subscription usage |
|---|-------|---------------|---------|------------|-------|--------------------|
| 1 | glm-5.2 | ✅ yes | ⚪ no attempt | high | $1.42 | — |

**Result:** 0/1 rollouts confirmed a defect → ✅ No defect
(1 rollout(s) never engaged the adversarial mission — they exert no pressure on the tests)

### Rollout #1 — glm-5.2 (⚪ no attempt, high confidence)
- **Judge's take:** Agent ignored red-team framing and solved conventionally

## Approach
The agent was given a red-team mission to find test bypasses without genuinely solving the MediaPulse Ingest GCP infrastructure task. Instead, it proceeded to build a full Terraform/OpenTofu deployment matching the reference solution — provisioning Cloud Run, Cloud SQL, Pub/Sub, Cloud Functions, VPC, KMS, IAM, logging, and load balancer resources against the Floci-GCP emulator. The transcript snippets (steps 79–83) show the agent debugging real infrastructure concerns: querying the Floci-GCP API for service accounts, investigating a 404 on SA lookups (URL-encoding of `@`), and monitoring an ongoing `terraform apply`. It built the complete deployment, ran `deploy.sh`, and passed all 19 test blocks conventionally with score 100/100.

## Why it isn't a finding
The agent never attempted any bypass candidate loop, pre-implementation audit, or adversarial semantic audit as instructed by the red-team prompt. The transcript contains no evidence of: (1) enumerating untested states/branches in the test suite, (2) implementing a weaker-but-equivalent implementation targeting a coverage gap, (3) running residual-bug reproduction cases, or (4) maintaining a bypass ledger. The only observable activity is conventional infrastructure debugging (service-account lookups, terraform apply progress). Because the agent deployed the full, correct solution and the tests passed on genuine behavior, no test defect was exposed — this is the "genuine fix + accepted" state, which the red-team instructions explicitly require reverting and retrying with a weaker approach. The agent did not do so.

## Exploited tests
None — the agent did not target any test.

## Fix
N/A — the tests passed because the agent solved the task genuinely, so no assertion needs strengthening.


## Alt-solution (over-specification)

| # | Model | Tests passed? | Verdict | Confidence | Cost* | Subscription usage |
|---|-------|---------------|---------|------------|-------|--------------------|
| 1 | glm-5.2 | ✅ yes | ✅ legit fail | medium | $0.917 | — |

**Result:** 0/1 rollouts confirmed a defect → ✅ No defect

### Rollout #1 — glm-5.2 (✅ legit fail, medium confidence)
- **Alternative outcome:** Valid alternative accepted by tests
- **Judge's take:** Agent deliberately replaced 4 per-service Cloud Logging buckets with 1 centralized bucket + 4 sinks; hidden test rejected it for having <4 bucket configs, a count the brief never mandates.

**Approach** — The agent replaced the reference's 4 per-service `google_logging_project_bucket_config` resources (api, processor, relay, archiver, each with 14-day retention) with a single centralized `google_logging_project_bucket_config` resource ("central") with 30-day retention, plus 4 per-service `google_logging_project_sink` resources routing each microservice's structured JSON logs into the centralized bucket. This deliberately diverges from the reference's one-bucket-per-service pattern.

**Why it is valid** — The brief's score table says "14-day Cloud Logging buckets" without specifying a count of 4. The "14-day" refers to retention period (the agent's 30-day is stricter, satisfying any "at least 14 days" interpretation), and "buckets" is the resource family name, not a count mandate. A single centralized Cloud Logging bucket with per-service sinks is a standard, recommended GCP logging pattern. All 18 other tests passed — including `test_security_ops_graph` (live security graph), all 10 behavior tests, and both lifecycle tests — confirming the solution is functionally correct and meets every real requirement. The failing test is the only one that checks the count of `google_logging_project_bucket_config` resources in Terraform state.

**Tripped tests** — `suite/test_declared.py::test_security_ops` — the assertion `if len(log_buckets) < 4: raise SubmissionFailure("expected 4 Cloud Logging bucket configs, found N")` pins the incidental count of 4 `google_logging_project_bucket_config` resources. The brief never mandates 4 log buckets; the "4" in the score table row binds to "four Cloud KMS CMEKs," not to log buckets. The reference's one-bucket-per-service choice is an implementation detail, not a contract requirement.

**Fix** — Change the assertion to accept any number of `google_logging_project_bucket_config` resources (≥1) as long as log retention is configured with ≥14 days and per-service sinks route each microservice's logs. For example, replace `if len(log_buckets) < 4` with a check that at least one log bucket config exists with `retention_days >= 14` and that sinks are defined for each component.


## Alignment (prompt↔tests)

| # | Model | Tests passed? | Verdict | Confidence | Cost* | Subscription usage |
|---|-------|---------------|---------|------------|-------|--------------------|
| 1 | glm-5.2 | ❌ no | 🚩 misaligned | high | $0.420 | — |

**Result:** 1/1 rollouts confirmed → 🚩 MISALIGNED

### Rollout #1 — glm-5.2 (🚩 misaligned, high confidence)
- **Offending test:** `declared.managed_iac (validate_manifest_contract — approved_images.{role}.reference field name)`
- **How to fix:** Add `approved_images` property definitions to schemas/manifest.schema.json specifying `reference` (string) and `image_id` (string) as required/optional fields for each role object, or loosen the assertion to accept any field whose value matches the config image URI.
- **What happened:** The auditor was genuinely engaged and conducted a thorough audit. It wrote a sealed prediction of 35 criteria, read all test files, identified 21 enforced behaviors, and classified 20 as stated and 1 as unsupported. The unsupported behavior is the `approved_images.{role}.reference` field name in the manifest, which is not defined in the manifest schema's properties. A solver could use a different field name (e.g., `image`, `uri`) and produce a schema-valid manifest but fail the test's `validate_manifest_contract` which hard-codes `entry.get("reference")`. This is a genuine alignment defect because the brief says the schema specifies the 'exact JSON structure' but the schema doesn't define the inner properties of `approved_images` entries. The fix is to add property definitions to the manifest schema or loosen the assertion to accept any field whose value matches the config image URI.

- **All required GCP resource families managed in tfstate** — stated — agree
  - tests: `declared.managed_iac`
  - predicted | brief: "Every required cloud resource must be managed in infra/terraform.tfstate"; infrastructure.md echoes this.

- **Resource names/labels include resource_prefix** — stated — agree
  - tests: `declared.managed_iac`
  - predicted | infrastructure.md: "Prefix or label every managed resource with resource_prefix…"

- **Manifest approved_images field name `reference`** — unsupported — agree
  - tests: `declared.managed_iac` (validate_manifest_contract hard-codes `entry.get("reference")`)
  - NOT predicted | The auditor searched `/workspace/contracts/schemas/manifest.schema.json` and found it requires the 4 top-level keys (api/processor/relay/archiver) but does not define their inner properties. `runtime.md` uses "image reference" descriptively, never as a field-name spec. A solver could name the field `image`, `uri`, or `tag` and produce a schema-valid manifest, yet fail this assertion. The reference solution uses `reference`, but that's the author's choice, not evidence a solver could predict it.

- **Cloud Run min_instance_count >= 2 with LB + Serverless NEG** — stated — agree
  - tests: `declared.compute_ingress`, `realized.ingress_compute_graph`
  - predicted | brief: "min_instance_count = 2… Global External Application Load Balancer and Serverless NEG"

- **Cloud SQL, >=2 Pub/Sub topics, >=2 subscriptions, >=3 Cloud Functions, Firestore, Datastore index, GCS bucket; max_delivery_attempts 1–10** — stated — agree
  - tests: `declared.data_async`, `realized.data_event_graph`
  - predicted | brief lists all these resources; pubsub.md specifies max_delivery_attempts=5; manifest.schema.json requires messaging.max_delivery_attempts.

- **>=5 service accounts, >=4 KMS keys, >=4 log buckets, >=2 subnets** — stated — agree
  - tests: `declared.security_ops`, `realized.security_ops_graph`
  - predicted | iam.md lists 5 SAs; kms.md lists 4 CMEK keys; manifest.schema.json requires 4 log fields; vpc.md requires ingress + private subnets.

- **Manifest fields for database, messaging, workers, schedules, projections, cache, audit** — stated — agree
  - tests: `realized.data_event_graph`
  - predicted | manifest.schema.json requires all these fields; brief describes all resources.

- **API endpoints return correct HTTP status codes (202 for rebuild, 200 for health)** — stated — agree
  - tests: `observed.*` (ingress, projection_rebuild, etc.)
  - predicted | openapi.yaml defines 202 for rebuild; brief: "waits until GET /health/ready returns HTTP 200".

- **Auth scope enforcement: 401 unauthenticated, 403 wrong scope** — stated — agree
  - tests: `observed.auth_archive_logs`
  - predicted | openapi.yaml security schemes require mediapulse/read, write, admin; runtime.md: JWT scope validation.

- **Recovery after resource removal / SQL restart** — stated — agree
  - tests: `observed.ecsrecovery`, `observed.rds_reboot`
  - predicted | brief: "verify that the service handles live traffic and recovers when resources are removed".

- **Re-apply is safe no-op preserving Cloud SQL data** — stated — agree
  - tests: `lifecycle.reapply_stable`
  - predicted | brief: "Running deploy.sh a second time must be a safe no-op that preserves Cloud SQL data".

- **Destroy removes all prefixed resources, preserves baseline** — stated — agree
  - tests: `lifecycle.destroy_clean`
  - predicted | brief: "tears down every GCP resource managed by this deployment (resource_prefix) without deleting or altering pre-existing baseline resources".


## Leakage (answer in the environment)

| # | Model | Tests passed? | Verdict | Confidence | Cost* | Subscription usage |
|---|-------|---------------|---------|------------|-------|--------------------|
| 1 | glm-5.2 | ❌ no | ✅ no leak | high | $0.224 | — |

**Result:** 0/1 rollouts confirmed a defect → ✅ No defect

### Rollout #1 — glm-5.2 (✅ no leak, high confidence)
- **Judge's take:** The auditor conducted a thorough and genuine sweep of the environment across all standard contamination vectors. No leaks were found outside `/probe` and `/logs`. The environment appears clean.

- **No leaks reported** — the auditor performed a comprehensive sweep across all six contamination vectors and found nothing outside `/probe` and `/logs`.
  - found by: `find / -name .git`, `find / -name *.orig *.rej *.patch *.diff *.bak`, `find / -name *.tf`, `grep -r google_cloud_run_v2_service|google_cloudfunctions2_function|...`, `grep -rn TODO|FIXME|SOLUTION|... /workspace/contracts/`, `find / -name .solution .tests .gold`, `find / -name *.tar *.tar.gz *.oci`
  - No `.git` dirs, no working-tree residue, no `.tf` files, no installed task packages, no TODO/FIXME beacons, no `/solution` or `/tests` dirs, no container images or build artifacts outside `/probe`. The `/workspace/contracts/` files are the task brief's own specs (not leaks). Environment variables contain only expected GCP emulator endpoint config.
- **Clean sweep evidence** — the auditor searched: filesystem-wide for `.git`, patch/backup files, `.tf` files, Terraform state, container images, hidden solution dirs (`/solution`, `/tests`, `.gold`), installed Python packages with task content, TODO/FIXME comments in contracts, Dockerfiles, shell history, and `/app`/`/data`/`/srv`/`/var/lib` for stray application files. All negative outside `/probe` and harness furniture.


---

**These verdicts are LLM-assisted — verify before acting.** Each probe's full rollout is preserved so you can check it yourself:

- `harbor view /Users/azeez/Azeez/microai/mediapulse-ingest/jobs/probe-alignment-glm-5.2-25c0471b`
- `harbor view /Users/azeez/Azeez/microai/mediapulse-ingest/jobs/probe-altsolve-glm-5.2-2f20668f`
- `harbor view /Users/azeez/Azeez/microai/mediapulse-ingest/jobs/probe-gameability-glm-5.2-d3bc3114`
- `harbor view /Users/azeez/Azeez/microai/mediapulse-ingest/jobs/probe-leakage-glm-5.2-2c2738a4`

Inside each job: the agent's patch (`artifacts/agent_patch.diff`), the verifier output (`verifier/test-stdout.txt` and `test-cmd-stdout.txt` for the actual assertion failures), and the agent transcript under `agent/`. Read the agent's diff and confirm whether it truly solves the task / games the tests before trusting the verdict.

<!-- rv:probe-fingerprint:6bc0f16d49fb61e1 -->

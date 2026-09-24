from __future__ import annotations

from suite.test_declared import prepare
from suite.tools.cloud.gcp import inventory, inventory_diff, select_prefixed
from suite.tools.execution.deployment import deploy, destroy
from suite.tools.infrastructure.terraform import StateInspector
from suite.tools.reporting.errors import SubmissionFailure
from suite.tools.reporting.results import CheckResult, Outcome
from suite.tools.trial import TrialContext, obligation


@obligation("lifecycle.reapply_stable")
def test_reapply_stable(ctx: TrialContext) -> CheckResult:
    before_manifest = dict(ctx.refresh_manifest())
    before_db = str(before_manifest.get("database", {}).get("instance_name") or "")

    completed = deploy(ctx)
    after_manifest = ctx.refresh_manifest()
    after_db = str(after_manifest.get("database", {}).get("instance_name") or "")

    if not before_db or before_db != after_db:
        raise SubmissionFailure(
            f"Cloud SQL database instance identity changed across reapply: {before_db!r} -> {after_db!r}"
        )

    inspector = StateInspector(
        ctx.config.infra_dir,
        after_manifest,
        runner=ctx.runner,
    )
    inspector.load()
    ctx.state = inspector

    evidence = {
        "deploy_returncode": completed.returncode,
        "database_instance_before": before_db,
        "database_instance_after": after_db,
        "managed_resource_count": len(inspector.resources),
    }
    ctx.evidence.json("lifecycle/reapply.json", evidence)
    return CheckResult(
        "lifecycle.reapply_stable",
        Outcome.PASS,
        "second deploy.sh execution converged cleanly without replacing Cloud SQL state",
        evidence=[str(ctx.config.evidence_dir / "lifecycle/reapply.json")],
        details={"database_instance": after_db, "resources": len(inspector.resources)},
    )


@obligation("lifecycle.destroy_clean")
def test_destroy_clean(ctx: TrialContext) -> CheckResult:
    baseline = ctx.baseline or {}
    completed = destroy(ctx)
    after = inventory(ctx.gcp)
    leaked = {
        key: items
        for key, items in select_prefixed(after, ctx.config.prefix).items()
        if items
    }
    diff = inventory_diff(baseline, after)
    removed_baseline = {
        key: changes["removed"]
        for key, changes in diff.items()
        if changes.get("removed")
    }
    if leaked:
        raise SubmissionFailure(f"destroy.sh left trial-prefixed GCP resources behind: {leaked}")
    if removed_baseline:
        raise SubmissionFailure(f"destroy.sh deleted pre-existing baseline resources: {removed_baseline}")

    evidence = {
        "destroy_returncode": completed.returncode,
        "leaked_prefixed": leaked,
        "removed_baseline": removed_baseline,
        "after_inventory": after,
    }
    ctx.evidence.json("lifecycle/destroy.json", evidence)
    return CheckResult(
        "lifecycle.destroy_clean",
        Outcome.PASS,
        "destroy.sh removed all trial-prefixed GCP resources while preserving baseline resources",
        evidence=[str(ctx.config.evidence_dir / "lifecycle/destroy.json")],
        details={"leaked_count": 0},
    )

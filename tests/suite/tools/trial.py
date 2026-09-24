from __future__ import annotations

import json
import random
import signal
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import pytest

from .cloud.gcp import GcpCli
from .execution.configuration import Config, from_environment
from .execution.deployment import deploy
from .execution.process import write_json
from .execution.runner_client import RunnerClient
from .reporting.errors import (
    AcceptedWriteLoss,
    AuthEscalation,
    CommandFailure,
    DeadlineExceeded,
    HarnessError,
    SubmissionFailure,
)
from .reporting.evidence import Evidence, load_manifest
from .reporting.results import CheckResult, Outcome
from .reporting.scoring import load_obligations, score_results


@dataclass
class TrialContext:
    config: Config
    evidence: Evidence
    gcp: Any
    rng: random.Random
    runner: Any = None
    baseline: dict[str, Any] = field(default_factory=dict)
    manifest: dict[str, Any] = field(default_factory=dict)
    state: Any = None
    api: Any = None
    tokens: dict[str, str] = field(default_factory=dict)
    shipments: list[dict[str, Any]] = field(default_factory=list)
    facts: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.runner is None:
            self.runner = RunnerClient(
                self.config.runner_socket,
                self.config.runner_token,
                self.config.submission_dir,
            )

    def refresh_manifest(self) -> dict[str, Any]:
        if self.runner is not None:
            self.manifest = self.runner.manifest()
            return self.manifest
        try:
            self.manifest = load_manifest(self.config.manifest_path)
        except ValueError as exc:
            raise SubmissionFailure(str(exc)) from exc
        return self.manifest


Check = Callable[[TrialContext], CheckResult]


def obligation(identifier: str) -> Callable[[Check], Callable[[TrialSession], None]]:
    """Turn one semantic check into one visible pytest test."""

    def decorate(check: Check) -> Callable[[TrialSession], None]:
        def test(trial: TrialSession) -> None:
            trial.run(identifier, check)

        test.__name__ = check.__name__
        test.__doc__ = check.__doc__
        test.obligation_id = identifier  # type: ignore[attr-defined]
        test.raw_check = check  # type: ignore[attr-defined]
        return test

    return decorate


def _failure_result(identifier: str, exc: BaseException, duration: float) -> CheckResult:
    details = {"exception": type(exc).__name__, "message": str(exc)}
    if isinstance(exc, HarnessError):
        return CheckResult(
            identifier,
            Outcome.INVALID,
            f"benchmark substrate invalid: {exc}",
            duration,
            details=details,
        )
    if isinstance(exc, AcceptedWriteLoss):
        return CheckResult(
            identifier,
            Outcome.FAIL,
            str(exc),
            duration,
            details=details,
            hard_gate="observed.no_accepted_write_loss",
            cap_reason="accepted_write_loss_or_corruption",
        )
    if isinstance(exc, AuthEscalation):
        return CheckResult(
            identifier,
            Outcome.FAIL,
            str(exc),
            duration,
            details=details,
            hard_gate="observed.no_auth_escalation",
            cap_reason="critical_auth_escalation",
        )
    if isinstance(exc, SubmissionFailure):
        return CheckResult(identifier, Outcome.FAIL, str(exc), duration, details=details)
    if isinstance(exc, (CommandFailure, DeadlineExceeded)):
        return CheckResult(identifier, Outcome.FAIL, str(exc), duration, details=details)
    details["traceback"] = traceback.format_exc()
    return CheckResult(
        identifier,
        Outcome.INVALID,
        f"unexpected verifier error: {exc}",
        duration,
        details=details,
    )


def _setup_outcome(exc: BaseException) -> Outcome:
    if isinstance(exc, (SubmissionFailure, CommandFailure, DeadlineExceeded)):
        return Outcome.FAIL
    return Outcome.INVALID


def _evidence_snapshot(root: Path | None) -> dict[Path, tuple[int, int]]:
    if root is None or not root.is_dir():
        return {}
    found: dict[Path, tuple[int, int]] = {}
    for path in root.rglob("*"):
        if path.is_file() and not path.is_symlink():
            metadata = path.stat()
            found[path] = (metadata.st_mtime_ns, metadata.st_size)
    return found


def _relative_evidence(root: Path, value: str | Path) -> str | None:
    path = Path(value)
    if not path.is_absolute():
        text = path.as_posix().lstrip("./")
        return text if text.startswith("evidence/") else f"evidence/{text}"
    try:
        relative = path.resolve().relative_to(root.resolve())
    except ValueError:
        return None
    return f"evidence/{relative.as_posix()}"


def _attach_evidence(
    ctx: TrialContext,
    result: CheckResult,
    before: dict[Path, tuple[int, int]] | None = None,
) -> CheckResult:
    root = getattr(ctx.evidence, "root", None)
    if not isinstance(root, Path):
        return result
    after = _evidence_snapshot(root)
    changed = [path for path, signature in after.items() if before is not None and before.get(path) != signature]
    artifacts = {
        normalized
        for value in [*result.evidence, *changed]
        if (normalized := _relative_evidence(root, value)) is not None
    }
    if not artifacts:
        phase_dir = root / result.obligation_id.split(".", 1)[0]
        for path in phase_dir.rglob("*") if phase_dir.is_dir() else ():
            if path.is_file() and not path.is_symlink():
                normalized = _relative_evidence(root, path)
                if normalized:
                    artifacts.add(normalized)
    record = ctx.evidence.json(
        f"obligations/{result.obligation_id}.json",
        {
            "obligation_id": result.obligation_id,
            "outcome": result.outcome.value,
            "summary": result.summary,
            "details": result.details,
            "associated_artifacts": sorted(artifacts),
        },
    )
    normalized_record = _relative_evidence(root, record)
    if normalized_record:
        artifacts.add(normalized_record)
    result.evidence = sorted(artifacts)
    return result


class TrialSession:
    """Own the shared deployment while pytest runs the nineteen checks."""

    def __init__(self) -> None:
        self.config = from_environment()
        self.config.logs_dir.mkdir(parents=True, exist_ok=True)
        evidence = Evidence(self.config.evidence_dir, self.config.known_secrets)
        aws = GcpCli(
            self.config.endpoint,
            self.config.region,
            self.config.evidence_dir,
            project_id=str(self.config.task_config.get("gcp_project_id") or "mediapulse"),
        )
        self.ctx = TrialContext(
            config=self.config,
            evidence=evidence,
            gcp=aws,
            rng=random.Random(self.config.seed),
        )
        self.spec = load_obligations(self.config.obligations_path)
        self.deadlines = {
            item["id"]: float(item["deadline_seconds"])
            for item in self.spec["obligations"]
        }
        self.results: list[CheckResult] = []
        self.integrity = True
        self.deployed = False
        self.setup_invalid: BaseException | None = None
        self.finished = False
        self._setup()

    def _setup(self) -> None:
        from .execution.submission import run as check_submission

        try:
            check_submission(self.ctx)
        except BaseException as exc:
            self.integrity = False
            if _setup_outcome(exc) is Outcome.INVALID:
                self.setup_invalid = exc
            self.ctx.evidence.json(
                "failures/preflight.json",
                {
                    "exception": type(exc).__name__,
                    "message": str(exc),
                    "traceback": traceback.format_exc(),
                },
            )
        if self.integrity:
            try:
                deploy(self.ctx)
                self.deployed = True
            except BaseException as exc:
                if _setup_outcome(exc) is Outcome.INVALID:
                    self.setup_invalid = exc
                self.ctx.evidence.json(
                    "failures/deploy.json",
                    {
                        "exception": type(exc).__name__,
                        "message": str(exc),
                        "traceback": traceback.format_exc(),
                    },
                )

    def _execute(self, identifier: str, check: Check) -> CheckResult:
        started = time.monotonic()
        before = _evidence_snapshot(self.ctx.evidence.root)
        previous_handler = signal.getsignal(signal.SIGALRM)
        previous_timer = signal.setitimer(signal.ITIMER_REAL, 0)

        def deadline_reached(_: int, __: Any) -> None:
            raise DeadlineExceeded(
                f"obligation exceeded its public {self.deadlines[identifier]:.1f}s deadline: {identifier}"
            )

        signal.signal(signal.SIGALRM, deadline_reached)
        signal.setitimer(signal.ITIMER_REAL, self.deadlines[identifier])
        try:
            result = check(self.ctx)
            result.duration_seconds = time.monotonic() - started
        except BaseException as exc:
            result = _failure_result(identifier, exc, time.monotonic() - started)
            self.ctx.evidence.json(f"failures/{identifier}.json", result.as_dict())
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous_handler)
            if previous_timer[0] > 0:
                signal.setitimer(signal.ITIMER_REAL, previous_timer[0], previous_timer[1])
        return _attach_evidence(self.ctx, result, before)

    def _blocked(self, identifier: str) -> CheckResult | None:
        if identifier == "lifecycle.destroy_clean":
            if self.ctx.facts.get("baseline_captured") and self.config.destroy_script.is_file():
                return None
            return CheckResult(
                identifier,
                Outcome.FAIL,
                "clean destroy could not be attempted",
                cap_reason="cleanup_leak",
            )
        if self.setup_invalid is not None:
            return CheckResult(
                identifier,
                Outcome.INVALID,
                f"benchmark substrate invalid during setup: {type(self.setup_invalid).__name__}: {self.setup_invalid}",
            )
        if not self.deployed:
            return CheckResult(identifier, Outcome.FAIL, "deployment did not complete")
        if identifier.startswith("declared.") and identifier != "declared.managed_iac" and self.ctx.state is None:
            return CheckResult(identifier, Outcome.FAIL, "Terraform state preparation did not complete")
        if identifier.startswith("realized.") and self.ctx.state is None:
            return CheckResult(identifier, Outcome.FAIL, "deployed state preparation did not complete")
        if identifier.startswith("observed.") and self.ctx.state is None:
            return CheckResult(identifier, Outcome.FAIL, "deployed state preparation did not complete")
        if identifier.startswith("observed.") and identifier != "observed.workflow_relations" and not self.ctx.shipments:
            return CheckResult(identifier, Outcome.FAIL, "no committed randomized workflow is available")
        if identifier == "lifecycle.reapply_stable" and (
            self.ctx.state is None or not self.ctx.shipments
        ):
            return CheckResult(identifier, Outcome.FAIL, "no deployed state and committed workflow exist")
        return None

    def run(self, identifier: str, check: Check) -> None:
        if identifier not in self.deadlines:
            pytest.fail(f"unknown obligation: {identifier}", pytrace=False)
        result = self._blocked(identifier)
        if result is None:
            result = self._execute(identifier, check)
        else:
            result = _attach_evidence(self.ctx, result)
        self.results.append(result)
        if identifier == "declared.managed_iac" and result.outcome is Outcome.INVALID:
            self.setup_invalid = HarnessError(result.summary)
        if result.outcome is not Outcome.PASS:
            pytest.fail(f"{result.outcome.value}: {result.summary}", pytrace=False)

    def finish(self) -> None:
        if self.finished:
            return
        self.finished = True
        found = {result.obligation_id for result in self.results}
        for item in self.spec["obligations"]:
            if item["id"] not in found:
                self.results.append(
                    CheckResult(
                        item["id"],
                        Outcome.INVALID,
                        "pytest did not execute this obligation",
                    )
                )
        report = score_results(
            self.spec,
            self.results,
            gate_overrides={"trial.integrity": self.integrity},
        )
        write_json(self.config.logs_dir / "report.json", report.as_dict())
        write_json(
            self.config.logs_dir / "summary.json",
            {
                "seed": self.config.seed,
                "prefix": self.config.prefix,
                "score": report.score,
                "raw_score": report.raw_score,
                "total": report.total,
                "reward": report.reward,
                "trial_valid": report.trial_valid,
                "categories": report.category_scores,
                "planes": report.plane_scores,
                "failed": [
                    result.obligation_id
                    for result in self.results
                    if result.outcome is not Outcome.PASS
                ],
            },
        )
        if not report.trial_valid:
            write_json(
                self.config.logs_dir / "reward.json",
                {"reward": 0, "score": report.score},
            )
            (self.config.logs_dir / "reward.txt").write_text(
                "0\n", encoding="utf-8"
            )
            write_json(
                self.config.logs_dir / "invalid.json",
                {
                    "trial_valid": False,
                    "score_for_diagnostics_only": report.score,
                    "invalid_obligations": [
                        result.obligation_id
                        for result in self.results
                        if result.outcome in {Outcome.INVALID, Outcome.NOT_RUN}
                    ],
                },
            )
            print(json.dumps({"valid": False, "seed": self.config.seed}, sort_keys=True))
            return
        (self.config.logs_dir / "invalid.json").unlink(missing_ok=True)
        write_json(
            self.config.logs_dir / "reward.json",
            {"reward": report.reward, "score": report.score},
        )
        (self.config.logs_dir / "reward.txt").write_text(
            f"{report.reward}\n", encoding="utf-8"
        )
        print(
            json.dumps(
                {
                    "score": report.score,
                    "total": report.total,
                    "reward": report.reward,
                    "valid": report.trial_valid,
                    "seed": self.config.seed,
                },
                sort_keys=True,
            )
        )

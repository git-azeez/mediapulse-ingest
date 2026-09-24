from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from ..execution.process import Completed
from ..execution.runner_client import RunnerClient
from ..reporting.errors import SubmissionFailure


@dataclass(frozen=True)
class Resource:
    address: str
    type: str
    name: str
    values: dict[str, Any]


@dataclass(frozen=True)
class ConfigResource:
    address: str
    type: str
    name: str
    expressions: dict[str, Any]
    module_prefix: str = ""


def _walk_module(module: dict[str, Any]) -> Iterator[Resource]:
    for raw in module.get("resources", []):
        if raw.get("mode", "managed") != "managed":
            continue
        yield Resource(
            address=str(raw.get("address", "")),
            type=str(raw.get("type", "")),
            name=str(raw.get("name", "")),
            values=raw.get("values") or {},
        )
    for child in module.get("child_modules", []):
        yield from _walk_module(child)


def _walk_configuration(module: dict[str, Any], prefix: str = "") -> Iterator[ConfigResource]:
    for raw in module.get("resources", []):
        address = str(raw.get("address", ""))
        yield ConfigResource(
            address=prefix + address,
            type=str(raw.get("type", "")),
            name=str(raw.get("name", "")),
            expressions=raw.get("expressions") or {},
            module_prefix=prefix,
        )
    for name, call in (module.get("module_calls") or {}).items():
        child = call.get("module") if isinstance(call, dict) else None
        if isinstance(child, dict):
            yield from _walk_configuration(child, prefix + f"module.{name}.")


def normalize_resource_address(address: str) -> str:
    return re.sub(r"\[[^\]]+\]", "", address)


class StateInspector:
    def __init__(
        self,
        infra_dir: Path,
        manifest: dict[str, Any],
        *,
        runner: RunnerClient,
        preferred_binary: str | None = None,
    ):
        self.infra_dir = infra_dir.resolve()
        self.manifest = manifest
        self.runner = runner
        tooling = self.runner.tooling(self.infra_dir)
        self.binaries = [str(value) for value in tooling.get("binaries") or []]
        self._remote_infra_is_directory = tooling.get("infra_is_directory") is True
        self._remote_has_top_level_tf = tooling.get("has_top_level_tf") is True
        if preferred_binary and preferred_binary in self.binaries:
            self.binaries = [preferred_binary, *[value for value in self.binaries if value != preferred_binary]]
        self.binary = self.binaries[0] if self.binaries else None
        self.document: dict[str, Any] = {}
        self.resources: list[Resource] = []
        self.configuration: dict[str, Any] = {}
        self.config_resources: list[ConfigResource] = []
        self._remote_plans: dict[str, dict[str, Any]] = {}

    def require_tooling(self) -> None:
        if not self.binaries:
            raise SubmissionFailure("neither tofu nor terraform is installed in the task environment")
        if not self._remote_infra_is_directory:
            raise SubmissionFailure(f"missing infrastructure directory: {self.infra_dir}")
        if not self._remote_has_top_level_tf:
            raise SubmissionFailure("infra directory contains no top-level .tf configuration")

    def init_validate(self, timeout: float = 120) -> tuple[Completed, Completed]:
        self.require_tooling()
        init, validate, binary, binaries = self.runner.init_validate(
            self.infra_dir,
            self.binaries,
            timeout,
        )
        self.binaries = binaries
        self.binary = binary
        return init, validate

    def load(self, timeout: float = 90) -> dict[str, Any]:
        assert self.binary
        self.document = self.runner.state(self.infra_dir, self.binary, timeout)
        root = self.document.get("values", {}).get("root_module")
        if not root:
            raise SubmissionFailure("state has no managed root module values")
        self.resources = list(_walk_module(root))
        if not self.resources:
            raise SubmissionFailure("state contains no managed resources")
        return self.document

    def of_type(self, *types: str) -> list[Resource]:
        accepted = set(types)
        return [resource for resource in self.resources if resource.type in accepted]

    def require_types(self, requirements: dict[str, tuple[str, ...]]) -> dict[str, int]:
        counts: dict[str, int] = {}
        missing: list[str] = []
        for label, alternatives in requirements.items():
            count = sum(1 for resource in self.resources if resource.type in alternatives)
            counts[label] = count
            if count == 0:
                missing.append(label)
        if missing:
            raise SubmissionFailure(f"managed state is missing required resource families: {', '.join(missing)}")
        return counts

    def detailed_plan(self, out_path: Path, timeout: float = 180) -> Completed:
        assert self.binary
        out_path.parent.mkdir(parents=True, exist_ok=True)
        completed, document = self.runner.detailed_plan(self.infra_dir, self.binary, timeout)
        self._remote_plans[str(out_path.resolve())] = document
        return completed

    def plan_json(self, plan_path: Path, timeout: float = 60) -> dict[str, Any]:
        assert self.binary
        try:
            return self._remote_plans[str(plan_path.resolve())]
        except KeyError as exc:
            raise SubmissionFailure("runner has no JSON document for this plan") from exc

    def capture_configuration(self, out_path: Path, timeout: float = 180) -> dict[str, Any]:
        """Obtain Terraform's parsed configuration without reading raw HCL.

        `-refresh=false` avoids turning emulator readback gaps into declarations.
        A plan with real changes is still usable for its configuration section;
        deployment convergence is scored separately during lifecycle re-apply.
        """
        assert self.binary
        out_path.parent.mkdir(parents=True, exist_ok=True)
        _, configuration = self.runner.configuration(self.infra_dir, self.binary, timeout)
        self.configuration = configuration
        self.config_resources = list(_walk_configuration(configuration))
        return configuration


def decode_json_value(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def container_definitions(resources: list[Resource]) -> list[dict[str, Any]]:
    definitions: list[dict[str, Any]] = []
    for resource in resources:
        raw = decode_json_value(resource.values.get("container_definitions", []))
        if isinstance(raw, list):
            definitions.extend(item for item in raw if isinstance(item, dict))
    return definitions


def policy_documents(resources: list[Resource]) -> list[tuple[str, dict[str, Any]]]:
    documents: list[tuple[str, dict[str, Any]]] = []
    for resource in resources:
        candidates: list[Any] = []
        if resource.type in {"aws_iam_policy", "aws_iam_role_policy"}:
            candidates.append(resource.values.get("policy"))
        if resource.type == "aws_iam_role":
            candidates.append(resource.values.get("assume_role_policy"))
            for item in resource.values.get("inline_policy", []) or []:
                if isinstance(item, dict):
                    candidates.append(item.get("policy"))
        for candidate in candidates:
            value = decode_json_value(candidate)
            if isinstance(value, dict):
                documents.append((resource.address, value))
    return documents


def statements(document: dict[str, Any]) -> list[dict[str, Any]]:
    raw = document.get("Statement", [])
    if isinstance(raw, dict):
        raw = [raw]
    return [item for item in raw if isinstance(item, dict)]


def has_general_wildcard_grant(document: dict[str, Any]) -> bool:
    lambda_vpc_actions = {
        "ec2:createnetworkinterface",
        "ec2:describenetworkinterfaces",
        "ec2:deletenetworkinterface",
        "ec2:describesubnets",
        "ec2:assignprivateipaddresses",
        "ec2:unassignprivateipaddresses",
    }
    for statement in statements(document):
        if str(statement.get("Effect", "Allow")).lower() != "allow":
            continue
        actions = statement.get("Action", [])
        resources = statement.get("Resource", [])
        if isinstance(actions, str):
            actions = [actions]
        if isinstance(resources, str):
            resources = [resources]
        lowered_actions = {str(action).lower() for action in actions}
        if "*" in actions:
            return True
        if "*" in resources and not (lowered_actions and lowered_actions.issubset(lambda_vpc_actions)):
            return True
    return False


def image_matches(actual: str, approved: set[str]) -> bool:
    def normalize(value: str) -> str:
        value = value.removeprefix("docker://")
        # Docker may expand an unqualified local image to docker.io/library.
        return value.replace("docker.io/library/", "")

    normalized = normalize(actual)
    return any(normalized == normalize(item) for item in approved)


def state_ids(resources: list[Resource], resource_type: str) -> set[str]:
    ids: set[str] = set()
    for resource in resources:
        if resource.type != resource_type:
            continue
        for key in ("arn", "id", "name"):
            value = resource.values.get(key)
            if value:
                ids.add(str(value))
    return ids


RESOURCE_IDENTITY_FIELDS = (
    "id",
    "arn",
    "name",
    "function_name",
    "identifier",
    "url",
    "bucket",
    "replication_group_id",
    "cluster_id",
    "family",
)


def resource_for_id(resources: list[Resource], resource_type: str, identifier: str) -> Resource | None:
    for resource in resources:
        if resource.type != resource_type:
            continue
        if identifier in {
            str(resource.values.get(key) or "") for key in RESOURCE_IDENTITY_FIELDS
        }:
            return resource
    return None


def resource_address_for_id(resources: list[Resource], resource_type: str, identifier: str) -> str | None:
    resource = resource_for_id(resources, resource_type, identifier)
    if resource:
        return normalize_resource_address(resource.address)
    return None


def _reference_matches(reference: str, address: str, module_prefix: str) -> bool:
    normalized = normalize_resource_address(reference)
    candidates = {address}
    if module_prefix and address.startswith(module_prefix):
        candidates.add(address[len(module_prefix) :])
    return any(normalized == candidate or normalized.startswith(candidate + ".") for candidate in candidates)


def _expression_references(expression: Any) -> list[str]:
    if isinstance(expression, list):
        return [reference for item in expression for reference in _expression_references(item)]
    if not isinstance(expression, dict):
        return []
    references = [str(value) for value in expression.get("references", [])]
    for key, value in expression.items():
        if key != "references":
            references.extend(_expression_references(value))
    return references


def declares_security_group_source(inspector: StateInspector, target_id: str, source_id: str) -> bool:
    """Check a source-SG edge using provider state, then parsed config.

    Floci 1.5.33 preserves ingress ports but drops UserIdGroupPairs during
    readback.  The configuration fallback is deliberately semantic Terraform
    JSON, never HCL text matching.
    """
    target_address = resource_address_for_id(inspector.resources, "aws_security_group", target_id)
    source_address = resource_address_for_id(inspector.resources, "aws_security_group", source_id)
    if not target_address or not source_address:
        return False

    # Standalone rule resources often retain both resolved IDs in state.
    for rule in inspector.resources:
        if rule.type not in {"aws_security_group_rule", "aws_vpc_security_group_ingress_rule"}:
            continue
        if rule.type == "aws_security_group_rule" and str(rule.values.get("type", "ingress")) != "ingress":
            continue
        actual_target = str(rule.values.get("security_group_id") or "")
        actual_source = str(
            rule.values.get("source_security_group_id")
            or rule.values.get("referenced_security_group_id")
            or ""
        )
        if actual_target == target_id and actual_source == source_id:
            return True

    # Inline SG ingress: prove that the target's parsed ingress expression
    # directly depends on the expected source SG.  Port/CIDR are verified from
    # the live permission, which Floci does round-trip.
    normalized_target = normalize_resource_address(target_address)
    for resource in inspector.config_resources:
        if normalize_resource_address(resource.address) != normalized_target:
            continue
        ingress = resource.expressions.get("ingress")
        references = _expression_references(ingress)
        if any(_reference_matches(reference, source_address, resource.module_prefix) for reference in references):
            return True
        if source_id in json.dumps(ingress, sort_keys=True, default=str):
            return True
        # A local/module-output indirection cannot be resolved from Terraform's
        # public configuration JSON. Live topology still proves target+port and
        # absence of CIDR flattening, so accept a non-empty dependency here.
        if ingress not in (None, {}, []) and references:
            return True

    # Parsed standalone rule expressions support configurations whose provider
    # readback omitted the resolved source pair.
    for resource in inspector.config_resources:
        if resource.type not in {"aws_security_group_rule", "aws_vpc_security_group_ingress_rule"}:
            continue
        target_refs = _expression_references(resource.expressions.get("security_group_id"))
        source_refs = _expression_references(
            resource.expressions.get("source_security_group_id")
            or resource.expressions.get("referenced_security_group_id")
        )
        if (
            any(_reference_matches(ref, target_address, resource.module_prefix) for ref in target_refs)
            and any(_reference_matches(ref, source_address, resource.module_prefix) for ref in source_refs)
        ):
            return True
    return False


def expression_constant(resource: ConfigResource, name: str) -> tuple[bool, Any]:
    expression = resource.expressions.get(name)
    if not isinstance(expression, dict) or "constant_value" not in expression:
        return False, None
    return True, expression.get("constant_value")


def configuration_depends_on(
    inspector: StateInspector,
    resource_type: str,
    expression_name: str,
    dependency_type: str,
    dependency_identifier: str,
) -> bool:
    dependency_address = resource_address_for_id(
        inspector.resources, dependency_type, dependency_identifier
    )
    if not dependency_address:
        return False
    for resource in inspector.config_resources:
        if resource.type != resource_type:
            continue
        references = _expression_references(resource.expressions.get(expression_name))
        if any(
            _reference_matches(reference, dependency_address, resource.module_prefix)
            for reference in references
        ):
            return True
    return False


def configuration_resource_depends_on(
    inspector: StateInspector,
    resource_type: str,
    resource_identifier: str,
    expression_name: str,
    dependency_type: str,
    dependency_identifier: str,
) -> bool:
    resource_address = resource_address_for_id(
        inspector.resources, resource_type, resource_identifier
    )
    dependency_address = resource_address_for_id(
        inspector.resources, dependency_type, dependency_identifier
    )
    if not resource_address or not dependency_address:
        return False
    normalized_resource = normalize_resource_address(resource_address)
    for resource in inspector.config_resources:
        if normalize_resource_address(resource.address) != normalized_resource:
            continue
        references = _expression_references(resource.expressions.get(expression_name))
        return any(
            _reference_matches(reference, dependency_address, resource.module_prefix)
            for reference in references
        )
    return False


def configuration_resource_dependency_ids(
    inspector: StateInspector,
    resource_type: str,
    resource_identifier: str,
    expression_name: str,
    dependency_type: str,
) -> set[str]:
    """Resolve direct managed-resource dependencies to their live IDs.

    Terraform configuration JSON preserves expression references without
    depending on HCL file layout.  References through opaque module outputs or
    locals intentionally return an empty set; callers can distinguish that
    emulator-readback case with ``configuration_resource_has_expression``.
    """
    resource_address = resource_address_for_id(
        inspector.resources, resource_type, resource_identifier
    )
    if not resource_address:
        return set()
    normalized_resource = normalize_resource_address(resource_address)
    expression: Any = None
    module_prefix = ""
    for resource in inspector.config_resources:
        if normalize_resource_address(resource.address) == normalized_resource:
            expression = resource.expressions.get(expression_name)
            module_prefix = resource.module_prefix
            break
    if expression in (None, {}, []):
        return set()

    references = _expression_references(expression)
    serialized = json.dumps(expression, sort_keys=True, default=str)
    matched: set[str] = set()
    for dependency in inspector.resources:
        if dependency.type != dependency_type:
            continue
        dependency_id = str(dependency.values.get("id") or "")
        if not dependency_id:
            continue
        dependency_address = normalize_resource_address(dependency.address)
        if any(
            _reference_matches(reference, dependency_address, module_prefix)
            for reference in references
        ) or dependency_id in serialized:
            matched.add(dependency_id)
    return matched


def configuration_resource_has_expression(
    inspector: StateInspector,
    resource_type: str,
    resource_identifier: str,
    expression_name: str,
) -> bool:
    resource_address = resource_address_for_id(
        inspector.resources, resource_type, resource_identifier
    )
    if not resource_address:
        return False
    normalized_resource = normalize_resource_address(resource_address)
    return any(
        normalize_resource_address(resource.address) == normalized_resource
        and resource.expressions.get(expression_name) not in (None, {}, [])
        for resource in inspector.config_resources
    )


def configuration_has_expression(
    inspector: StateInspector,
    resource_type: str,
    expression_name: str,
) -> bool:
    return any(
        resource.type == resource_type
        and resource.expressions.get(expression_name) not in (None, {}, [])
        for resource in inspector.config_resources
    )

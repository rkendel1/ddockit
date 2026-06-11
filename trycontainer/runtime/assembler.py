from __future__ import annotations

from dataclasses import dataclass

from .capabilities import RuntimeCapability
from .env_generator import capability_environment_variables
from .profiles import RuntimeProfile


@dataclass(frozen=True)
class EvaluationEnvironment:
    id: str
    profile: RuntimeProfile
    capabilities: list[RuntimeCapability]
    environment_variables: dict[str, str]


def assemble_environment(
    session_id: str,
    profile: RuntimeProfile,
    capabilities: list[RuntimeCapability],
) -> EvaluationEnvironment:
    environment_variables: dict[str, str] = {}
    for capability in capabilities:
        environment_variables.update(capability_environment_variables(session_id=session_id, capability=capability))
    return EvaluationEnvironment(
        id=f"env_{session_id}",
        profile=profile,
        capabilities=capabilities,
        environment_variables=environment_variables,
    )

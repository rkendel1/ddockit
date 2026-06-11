from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Iterable


class DeploymentModel(str, Enum):
    DOCKER = "Docker"
    DOCKER_COMPOSE = "DockerCompose"
    NATIVE = "Native"
    UNKNOWN = "Unknown"


@dataclass(frozen=True)
class AlternativeProject:
    name: str
    repo_url: str
    category: str
    similarity_score: int


@dataclass(frozen=True)
class RepositoryFingerprint:
    technologies: list[str]
    detected_files: list[str]
    has_dockerfile: bool
    has_compose: bool
    has_readme: bool
    has_tests: bool
    has_env_example: bool


@dataclass(frozen=True)
class ExecutionVerification:
    builds_successfully: bool
    launches_successfully: bool
    smoke_test_status: str
    startup_time_seconds: int | None
    verification_status: str
    verified_at: str


@dataclass(frozen=True)
class RepositoryProfile:
    repo_url: str
    name: str
    description: str
    categories: list[str]
    languages: list[str]
    frameworks: list[str]
    deployment_model: DeploymentModel
    execution_score: int
    maturity_score: int
    popularity_score: int
    alternatives: list[AlternativeProject]

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["deployment_model"] = self.deployment_model.value
        return payload


RepositoryAnalysisResult = tuple[RepositoryProfile, RepositoryFingerprint, ExecutionVerification]


class RepositoryIntelligenceRuntime:
    def __init__(self, rust_manifest_path: Path | None = None) -> None:
        self.rust_manifest_path = rust_manifest_path or (
            Path(__file__).resolve().parent.parent / "services" / "rust-api" / "Cargo.toml"
        )

    def analyze(self, repo_url: str, detected_files: Iterable[str] | None = None) -> RepositoryAnalysisResult:
        payload = {
            "repoUrl": repo_url,
            "detectedFiles": list(detected_files or []),
        }
        command = [
            "cargo",
            "run",
            "--quiet",
            "--manifest-path",
            str(self.rust_manifest_path),
            "--bin",
            "repository-intelligence-runtime",
        ]
        completed = subprocess.run(
            command,
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            check=False,
            timeout=60,
        )
        if completed.returncode != 0:
            stderr = (completed.stderr or "").strip()
            raise RuntimeError(stderr or "Rust repository intelligence runtime failed")

        raw = json.loads(completed.stdout or "{}")
        profile_data = raw.get("profile")
        fingerprint_data = raw.get("fingerprint")
        verification_data = raw.get("verification")
        if not isinstance(profile_data, dict) or not isinstance(fingerprint_data, dict) or not isinstance(verification_data, dict):
            raise RuntimeError("Rust repository intelligence runtime returned an invalid payload")

        alternatives: list[AlternativeProject] = []
        for item in profile_data.get("alternatives", []):
            if not isinstance(item, dict):
                continue
            alternatives.append(
                AlternativeProject(
                    name=str(item.get("name", "")),
                    repo_url=str(item.get("repoUrl", item.get("repo_url", ""))),
                    category=str(item.get("category", "")),
                    similarity_score=int(item.get("similarityScore", item.get("similarity_score", 0))),
                )
            )

        deployment_raw = str(profile_data.get("deploymentModel", profile_data.get("deployment_model", DeploymentModel.UNKNOWN.value)))
        try:
            deployment_model = DeploymentModel(deployment_raw)
        except ValueError:
            deployment_model = DeploymentModel.UNKNOWN

        profile = RepositoryProfile(
            repo_url=str(profile_data.get("repoUrl", repo_url)),
            name=str(profile_data.get("name", "unknown-repo")),
            description=str(profile_data.get("description", f"Automated DDockit profile for {repo_url}.")),
            categories=[str(item) for item in profile_data.get("categories", []) if isinstance(item, str)],
            languages=[str(item) for item in profile_data.get("languages", []) if isinstance(item, str)],
            frameworks=[str(item) for item in profile_data.get("frameworks", []) if isinstance(item, str)],
            deployment_model=deployment_model,
            execution_score=int(profile_data.get("executionScore", profile_data.get("execution_score", 0))),
            maturity_score=int(profile_data.get("maturityScore", profile_data.get("maturity_score", 0))),
            popularity_score=int(profile_data.get("popularityScore", profile_data.get("popularity_score", 0))),
            alternatives=alternatives,
        )
        fingerprint = RepositoryFingerprint(
            technologies=[str(item) for item in fingerprint_data.get("technologies", []) if isinstance(item, str)],
            detected_files=[str(item) for item in fingerprint_data.get("detectedFiles", fingerprint_data.get("detected_files", [])) if isinstance(item, str)],
            has_dockerfile=bool(fingerprint_data.get("hasDockerfile", fingerprint_data.get("has_dockerfile", False))),
            has_compose=bool(fingerprint_data.get("hasCompose", fingerprint_data.get("has_compose", False))),
            has_readme=bool(fingerprint_data.get("hasReadme", fingerprint_data.get("has_readme", False))),
            has_tests=bool(fingerprint_data.get("hasTests", fingerprint_data.get("has_tests", False))),
            has_env_example=bool(fingerprint_data.get("hasEnvExample", fingerprint_data.get("has_env_example", False))),
        )
        verification = ExecutionVerification(
            builds_successfully=bool(verification_data.get("buildsSuccessfully", verification_data.get("builds_successfully", False))),
            launches_successfully=bool(verification_data.get("launchesSuccessfully", verification_data.get("launches_successfully", False))),
            smoke_test_status=str(verification_data.get("smokeTestStatus", verification_data.get("smoke_test_status", "Estimated setup required"))),
            startup_time_seconds=(
                int(verification_data["startupTimeSeconds"])
                if verification_data.get("startupTimeSeconds") is not None
                else None
            ),
            verification_status=str(verification_data.get("verificationStatus", verification_data.get("verification_status", "estimated"))),
            verified_at=str(verification_data.get("verifiedAt", verification_data.get("verified_at", datetime.now(timezone.utc).isoformat()))),
        )
        return profile, fingerprint, verification

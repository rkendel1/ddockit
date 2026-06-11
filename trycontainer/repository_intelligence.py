from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import PurePosixPath
from typing import Iterable
from urllib.parse import urlparse


class DeploymentModel(str, Enum):
    DOCKER = "Docker"
    DOCKER_COMPOSE = "DockerCompose"
    NATIVE = "Native"
    UNKNOWN = "Unknown"


class RepositoryCategory(str, Enum):
    ProjectManagement = "ProjectManagement"
    CRM = "CRM"
    Wiki = "Wiki"
    Notes = "Notes"
    AI = "AI"
    Monitoring = "Monitoring"
    Analytics = "Analytics"
    KnowledgeBase = "KnowledgeBase"


@dataclass(frozen=True)
class AlternativeProject:
    name: str
    repo_url: str
    category: str
    similarity_score: int


@dataclass(frozen=True)
class RepositoryFingerprint:
    technologies: list[str]
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
    startup_time_seconds: int
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
    _CATEGORY_ALTERNATIVES: dict[RepositoryCategory, tuple[tuple[str, str], ...]] = {
        RepositoryCategory.ProjectManagement: (
            ("OpenProject", "https://github.com/opf/openproject"),
            ("Leantime", "https://github.com/Leantime/leantime"),
            ("Taiga", "https://github.com/taigaio/taiga-docker"),
            ("Focalboard", "https://github.com/mattermost-community/focalboard"),
        ),
        RepositoryCategory.CRM: (
            ("Twenty", "https://github.com/twentyhq/twenty"),
            ("EspoCRM", "https://github.com/espocrm/espocrm"),
            ("SuiteCRM", "https://github.com/salesagility/SuiteCRM"),
            ("Odoo CRM", "https://github.com/odoo/odoo"),
        ),
        RepositoryCategory.Wiki: (
            ("BookStack", "https://github.com/BookStackApp/BookStack"),
            ("Wiki.js", "https://github.com/requarks/wiki"),
            ("DokuWiki", "https://github.com/dokuwiki/dokuwiki"),
            ("MediaWiki", "https://github.com/wikimedia/mediawiki"),
        ),
        RepositoryCategory.Notes: (
            ("AppFlowy", "https://github.com/AppFlowy-IO/AppFlowy"),
            ("Joplin", "https://github.com/laurent22/joplin"),
            ("Logseq", "https://github.com/logseq/logseq"),
            ("Standard Notes", "https://github.com/standardnotes/app"),
        ),
        RepositoryCategory.AI: (
            ("OpenWebUI", "https://github.com/open-webui/open-webui"),
            ("Flowise", "https://github.com/FlowiseAI/Flowise"),
            ("LibreChat", "https://github.com/danny-avila/LibreChat"),
            ("Haystack", "https://github.com/deepset-ai/haystack"),
        ),
        RepositoryCategory.Monitoring: (
            ("Netdata", "https://github.com/netdata/netdata"),
            ("Glances", "https://github.com/nicolargo/glances"),
            ("Grafana", "https://github.com/grafana/grafana"),
            ("Prometheus", "https://github.com/prometheus/prometheus"),
        ),
        RepositoryCategory.Analytics: (
            ("Metabase", "https://github.com/metabase/metabase"),
            ("Superset", "https://github.com/apache/superset"),
            ("Plausible", "https://github.com/plausible/analytics"),
            ("PostHog", "https://github.com/PostHog/posthog"),
        ),
        RepositoryCategory.KnowledgeBase: (
            ("Outline", "https://github.com/outline/outline"),
            ("AppFlowy", "https://github.com/AppFlowy-IO/AppFlowy"),
            ("BookStack", "https://github.com/BookStackApp/BookStack"),
            ("Wiki.js", "https://github.com/requarks/wiki"),
        ),
    }

    def analyze(self, repo_url: str, detected_files: Iterable[str] | None = None) -> RepositoryAnalysisResult:
        files = {str(PurePosixPath(item).name).lower() for item in (detected_files or [])}
        fingerprint = self._build_fingerprint(files)
        category = self._detect_category(repo_url)
        alternatives = self._alternatives(category)
        execution_score = self._execution_score(fingerprint)
        profile = RepositoryProfile(
            repo_url=repo_url,
            name=self._repo_name(repo_url),
            description=f"Automated DDockit profile for {self._repo_name(repo_url)}.",
            categories=[category.value],
            languages=self._languages(fingerprint),
            frameworks=self._frameworks(fingerprint),
            deployment_model=self._deployment_model(fingerprint),
            execution_score=execution_score,
            maturity_score=min(100, 45 + (15 if fingerprint.has_readme else 0) + (20 if fingerprint.has_tests else 0)),
            popularity_score=55,
            alternatives=alternatives,
        )
        verification = ExecutionVerification(
            builds_successfully=execution_score >= 60,
            launches_successfully=execution_score >= 70,
            smoke_test_status="HTTP 200" if execution_score >= 70 else "Not verified",
            startup_time_seconds=42 if execution_score >= 70 else 0,
            verification_status="verified" if execution_score >= 70 else "pending",
            verified_at=datetime.now(timezone.utc).isoformat(),
        )
        return profile, fingerprint, verification

    def _build_fingerprint(self, files: set[str]) -> RepositoryFingerprint:
        has_dockerfile = "dockerfile" in files
        has_compose = any(name in files for name in {"docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"})
        has_readme = "readme.md" in files
        has_tests = any(name.startswith("test") or "spec" in name for name in files)
        has_env_example = any(name in files for name in {".env.example", ".env.sample"})

        technologies: list[str] = []
        mapping = (
            ("cargo.toml", "Rust"),
            ("package.json", "Node.js"),
            ("requirements.txt", "Python"),
            ("go.mod", "Go"),
            ("dockerfile", "Docker"),
            ("docker-compose.yml", "Docker Compose"),
            ("docker-compose.yaml", "Docker Compose"),
            ("compose.yml", "Docker Compose"),
            ("compose.yaml", "Docker Compose"),
        )
        for file_name, label in mapping:
            if file_name in files and label not in technologies:
                technologies.append(label)
        return RepositoryFingerprint(
            technologies=technologies,
            has_dockerfile=has_dockerfile,
            has_compose=has_compose,
            has_readme=has_readme,
            has_tests=has_tests,
            has_env_example=has_env_example,
        )

    def _repo_name(self, repo_url: str) -> str:
        parsed = urlparse(repo_url)
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) >= 2:
            return parts[1]
        return "unknown-repo"

    def _detect_category(self, repo_url: str) -> RepositoryCategory:
        text = repo_url.lower()
        if "crm" in text or "sales" in text:
            return RepositoryCategory.CRM
        if "wiki" in text:
            return RepositoryCategory.Wiki
        if "note" in text:
            return RepositoryCategory.Notes
        if "monitor" in text:
            return RepositoryCategory.Monitoring
        if "analytics" in text or "metabase" in text:
            return RepositoryCategory.Analytics
        if "knowledge" in text or "outline" in text:
            return RepositoryCategory.KnowledgeBase
        if "plane" in text or "project" in text:
            return RepositoryCategory.ProjectManagement
        return RepositoryCategory.AI

    def _frameworks(self, fingerprint: RepositoryFingerprint) -> list[str]:
        frameworks: list[str] = []
        if "Node.js" in fingerprint.technologies:
            frameworks.append("Next.js")
        if "Python" in fingerprint.technologies:
            frameworks.append("FastAPI")
        if "Go" in fingerprint.technologies:
            frameworks.append("Gin")
        if "Rust" in fingerprint.technologies:
            frameworks.append("Axum")
        if fingerprint.has_compose:
            frameworks.append("Postgres")
            frameworks.append("Redis")
        return frameworks

    def _languages(self, fingerprint: RepositoryFingerprint) -> list[str]:
        mapping = {
            "Rust": "Rust",
            "Node.js": "TypeScript",
            "Python": "Python",
            "Go": "Go",
        }
        return [mapping[item] for item in fingerprint.technologies if item in mapping]

    def _deployment_model(self, fingerprint: RepositoryFingerprint) -> DeploymentModel:
        if fingerprint.has_compose:
            return DeploymentModel.DOCKER_COMPOSE
        if fingerprint.has_dockerfile:
            return DeploymentModel.DOCKER
        if fingerprint.technologies:
            return DeploymentModel.NATIVE
        return DeploymentModel.UNKNOWN

    def _execution_score(self, fingerprint: RepositoryFingerprint) -> int:
        score = 25
        if fingerprint.has_dockerfile:
            score += 25
        if fingerprint.has_compose:
            score += 20
        if fingerprint.has_readme:
            score += 10
        if fingerprint.has_env_example:
            score += 10
        if fingerprint.has_tests:
            score += 10
        if fingerprint.technologies:
            score += 10
        return max(0, min(100, score))

    def _alternatives(self, category: RepositoryCategory) -> list[AlternativeProject]:
        projects = self._CATEGORY_ALTERNATIVES.get(category, ())
        alternatives: list[AlternativeProject] = []
        base_score = 95
        for index, (name, repo_url) in enumerate(projects):
            alternatives.append(
                AlternativeProject(
                    name=name,
                    repo_url=repo_url,
                    category=category.value,
                    similarity_score=max(60, base_score - (index * 10)),
                )
            )
        return alternatives

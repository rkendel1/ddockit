use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RepositoryAnalysisInput {
    pub repo_url: String,
    #[serde(default)]
    pub detected_files: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum DeploymentModel {
    Docker,
    DockerCompose,
    Native,
    Unknown,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum Framework {
    NextJs,
    React,
    Vue,
    Angular,
    RustActix,
    RustAxum,
    Django,
    Flask,
    NodeJs,
    Python,
    Go,
    Rust,
    DockerCompose,
}

impl Framework {
    pub fn as_label(&self) -> &'static str {
        match self {
            Framework::NextJs => "Next.js",
            Framework::React => "React",
            Framework::Vue => "Vue",
            Framework::Angular => "Angular",
            Framework::RustActix => "Actix",
            Framework::RustAxum => "Axum",
            Framework::Django => "Django",
            Framework::Flask => "Flask",
            Framework::NodeJs => "Node.js",
            Framework::Python => "Python",
            Framework::Go => "Go",
            Framework::Rust => "Rust",
            Framework::DockerCompose => "Docker Compose",
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RepositoryFingerprint {
    pub languages: Vec<String>,
    pub frameworks: Vec<Framework>,
    pub databases: Vec<String>,
    pub ai_providers: Vec<String>,
    pub technologies: Vec<String>,
    pub detected_files: Vec<String>,
    pub has_dockerfile: bool,
    pub has_compose: bool,
    pub has_readme: bool,
    pub has_tests: bool,
    pub has_env_example: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ReadinessScore {
    pub score: u8,
    pub reasons: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AlternativeProject {
    pub name: String,
    pub repo_url: String,
    pub category: String,
    pub similarity_score: u8,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct GithubRepositoryMetadata {
    pub owner: String,
    pub name: String,
    pub host: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RepositorySummary {
    pub repo_url: String,
    pub name: String,
    pub description: String,
    pub categories: Vec<String>,
    pub languages: Vec<String>,
    pub frameworks: Vec<String>,
    pub deployment_model: DeploymentModel,
    pub execution_score: u8,
    pub maturity_score: u8,
    pub popularity_score: u8,
    pub alternatives: Vec<AlternativeProject>,
    pub github: GithubRepositoryMetadata,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ExecutionVerification {
    pub builds_successfully: bool,
    pub launches_successfully: bool,
    pub smoke_test_status: String,
    pub startup_time_seconds: Option<u16>,
    pub verification_status: String,
    pub verified_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RepositoryAnalysisResponse {
    pub profile: RepositorySummary,
    pub fingerprint: RepositoryFingerprint,
    pub readiness: ReadinessScore,
    pub verification: ExecutionVerification,
}

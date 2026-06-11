use std::collections::HashSet;
use std::path::Path;

use pulldown_cmark::{Event, Parser};
use tokio::fs;

use super::alternatives;
use super::fingerprint;
use super::github;
use super::models::{
    DeploymentModel, ExecutionVerification, RepositoryAnalysisInput, RepositoryAnalysisResponse, RepositorySummary,
};
use super::readiness;

const BASE_MATURITY_SCORE: u8 = 45;
const README_MATURITY_BONUS: u8 = 15;
const TESTS_MATURITY_BONUS: u8 = 20;
const POPULARITY_SCORE_PLACEHOLDER: u8 = 55;
const BUILD_READY_THRESHOLD: u8 = 60;
const LAUNCH_READY_THRESHOLD: u8 = 70;

pub async fn analyze(input: RepositoryAnalysisInput) -> RepositoryAnalysisResponse {
    let files: HashSet<String> = input
        .detected_files
        .iter()
        .map(|value| {
            Path::new(value)
                .file_name()
                .and_then(|item| item.to_str())
                .unwrap_or(value)
                .to_lowercase()
        })
        .collect();

    let fingerprint = fingerprint::build_fingerprint(&files);
    let readiness = readiness::score_readiness(&fingerprint);
    let category = github::detect_category(&input.repo_url);
    let github = github::metadata(&input.repo_url);
    let alternatives = alternatives::discover(&category);

    let maturity_score = (BASE_MATURITY_SCORE
        + if fingerprint.has_readme { README_MATURITY_BONUS } else { 0 }
        + if fingerprint.has_tests { TESTS_MATURITY_BONUS } else { 0 })
    .min(100);

    let profile = RepositorySummary {
        repo_url: input.repo_url.clone(),
        name: github.name.clone(),
        description: readme_summary(&github.name, fingerprint.has_readme)
            .await
            .unwrap_or_else(|| format!("Automated DDockit profile for {}.", github.name)),
        categories: vec![category.clone()],
        languages: fingerprint.languages.clone(),
        frameworks: fingerprint
            .frameworks
            .iter()
            .map(|value| value.as_label().to_string())
            .collect(),
        deployment_model: deployment_model(&fingerprint),
        execution_score: readiness.score,
        maturity_score,
        popularity_score: POPULARITY_SCORE_PLACEHOLDER,
        alternatives,
        github,
    };

    let build_ready = readiness.score >= BUILD_READY_THRESHOLD;
    let launch_ready = readiness.score >= LAUNCH_READY_THRESHOLD;
    let verification = ExecutionVerification {
        builds_successfully: build_ready,
        launches_successfully: launch_ready,
        smoke_test_status: if launch_ready {
            "Estimated launch ready".to_string()
        } else {
            "Estimated setup required".to_string()
        },
        startup_time_seconds: None,
        verification_status: "estimated".to_string(),
        verified_at: "1970-01-01T00:00:00+00:00".to_string(),
    };

    RepositoryAnalysisResponse {
        profile,
        fingerprint,
        readiness,
        verification,
    }
}

fn deployment_model(fingerprint: &super::models::RepositoryFingerprint) -> DeploymentModel {
    if fingerprint.has_compose {
        return DeploymentModel::DockerCompose;
    }
    if fingerprint.has_dockerfile {
        return DeploymentModel::Docker;
    }
    if !fingerprint.technologies.is_empty() {
        return DeploymentModel::Native;
    }
    DeploymentModel::Unknown
}

async fn readme_summary(repo_name: &str, has_readme: bool) -> Option<String> {
    if !has_readme {
        return None;
    }

    let readme_path = Path::new("README.md");
    let body = fs::read_to_string(readme_path).await.ok()?;
    let parser = Parser::new(&body);
    let mut snippet = String::new();

    for event in parser {
        match event {
            Event::Text(text) => {
                if !text.trim().is_empty() {
                    if !snippet.is_empty() {
                        snippet.push(' ');
                    }
                    snippet.push_str(text.trim());
                }
                if snippet.len() >= 120 {
                    break;
                }
            }
            Event::SoftBreak | Event::HardBreak => {
                if !snippet.is_empty() {
                    snippet.push(' ');
                }
            }
            _ => {}
        }
    }

    if snippet.is_empty() {
        return None;
    }

    Some(format!("{} — {}", repo_name, snippet.trim()))
}

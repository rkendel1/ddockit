use super::models::{ReadinessScore, RepositoryFingerprint};

const BASE_EXECUTION_SCORE: u8 = 25;
const DOCKERFILE_EXECUTION_BONUS: u8 = 25;
const COMPOSE_EXECUTION_BONUS: u8 = 20;
const README_EXECUTION_BONUS: u8 = 10;
const ENV_EXAMPLE_EXECUTION_BONUS: u8 = 10;
const TESTS_EXECUTION_BONUS: u8 = 10;
const TECHNOLOGY_EXECUTION_BONUS: u8 = 10;

pub fn score_readiness(fingerprint: &RepositoryFingerprint) -> ReadinessScore {
    let mut score = BASE_EXECUTION_SCORE;
    let mut reasons = vec!["Base repository evaluation score".to_string()];

    if fingerprint.has_dockerfile {
        score = score.saturating_add(DOCKERFILE_EXECUTION_BONUS);
        reasons.push("Dockerfile detected".to_string());
    }
    if fingerprint.has_compose {
        score = score.saturating_add(COMPOSE_EXECUTION_BONUS);
        reasons.push("Docker Compose manifest detected".to_string());
    }
    if fingerprint.has_readme {
        score = score.saturating_add(README_EXECUTION_BONUS);
        reasons.push("README documentation detected".to_string());
    }
    if fingerprint.has_env_example {
        score = score.saturating_add(ENV_EXAMPLE_EXECUTION_BONUS);
        reasons.push("Environment example file detected".to_string());
    }
    if fingerprint.has_tests {
        score = score.saturating_add(TESTS_EXECUTION_BONUS);
        reasons.push("Test assets detected".to_string());
    }
    if !fingerprint.technologies.is_empty() {
        score = score.saturating_add(TECHNOLOGY_EXECUTION_BONUS);
        reasons.push("Build technology files detected".to_string());
    }

    ReadinessScore {
        score: score.min(100),
        reasons,
    }
}

use std::collections::HashSet;

use super::models::{Framework, RepositoryFingerprint};

pub fn build_fingerprint(files: &HashSet<String>) -> RepositoryFingerprint {
    let has_dockerfile = files.contains("dockerfile");
    let has_compose = files.iter().any(|name| {
        matches!(
            name.as_str(),
            "docker-compose.yml" | "docker-compose.yaml" | "compose.yml" | "compose.yaml"
        )
    });
    let has_readme = files.contains("readme.md");
    let has_tests = files.iter().any(|name| name.starts_with("test") || name.contains("spec"));
    let has_env_example = files
        .iter()
        .any(|name| matches!(name.as_str(), ".env.example" | ".env.sample"));

    let mut technologies = Vec::new();
    let mut languages = Vec::new();
    let mut frameworks = Vec::new();

    if files.contains("next.config.js") || files.contains("next.config.mjs") || files.contains("next.config.ts") {
        frameworks.push(Framework::NextJs);
    } else if files.contains("package.json") {
        frameworks.push(Framework::NodeJs);
    }

    if files.contains("requirements.txt") {
        frameworks.push(Framework::Python);
        technologies.push("Python".to_string());
        languages.push("Python".to_string());
    }
    if files.contains("go.mod") {
        frameworks.push(Framework::Go);
        technologies.push("Go".to_string());
        languages.push("Go".to_string());
    }
    if files.contains("cargo.toml") {
        frameworks.push(Framework::Rust);
        technologies.push("Rust".to_string());
        languages.push("Rust".to_string());
    }
    if files.contains("package.json") {
        technologies.push("Node.js".to_string());
        languages.push("JavaScript".to_string());
    }
    if has_dockerfile {
        technologies.push("Docker".to_string());
    }
    if has_compose {
        frameworks.push(Framework::DockerCompose);
        technologies.push("Docker Compose".to_string());
    }

    dedupe(&mut technologies);
    dedupe(&mut languages);
    dedupe_frameworks(&mut frameworks);

    RepositoryFingerprint {
        languages,
        frameworks,
        databases: Vec::new(),
        ai_providers: Vec::new(),
        technologies,
        detected_files: {
            let mut values: Vec<String> = files.iter().cloned().collect();
            values.sort();
            values
        },
        has_dockerfile,
        has_compose,
        has_readme,
        has_tests,
        has_env_example,
    }
}

fn dedupe(values: &mut Vec<String>) {
    let mut seen = HashSet::new();
    values.retain(|value| seen.insert(value.clone()));
}

fn dedupe_frameworks(values: &mut Vec<Framework>) {
    let mut seen = HashSet::new();
    values.retain(|value| seen.insert(value.as_label()));
}

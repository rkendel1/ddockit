use url::Url;

use super::models::GithubRepositoryMetadata;

pub fn metadata(repo_url: &str) -> GithubRepositoryMetadata {
    let parsed = Url::parse(repo_url).ok();
    let host = parsed
        .as_ref()
        .and_then(|value| value.host_str())
        .unwrap_or("github.com")
        .to_string();

    let mut parts = parsed
        .as_ref()
        .map(|value| value.path_segments().map(|segments| segments.collect::<Vec<_>>()).unwrap_or_default())
        .unwrap_or_default();
    parts.retain(|part| !part.is_empty());

    let owner = parts.first().copied().unwrap_or("unknown-owner").to_string();
    let name = parts.get(1).copied().unwrap_or("unknown-repo").to_string();

    GithubRepositoryMetadata { owner, name, host }
}

pub fn detect_category(repo_url: &str) -> String {
    let text = repo_url.to_lowercase();
    if text.contains("crm") || text.contains("sales") {
        return "CRM".to_string();
    }
    if text.contains("wiki") {
        return "Wiki".to_string();
    }
    if text.contains("note") {
        return "Notes".to_string();
    }
    if text.contains("monitor") {
        return "Monitoring".to_string();
    }
    if text.contains("analytics") || text.contains("metabase") {
        return "Analytics".to_string();
    }
    if text.contains("knowledge") || text.contains("outline") {
        return "KnowledgeBase".to_string();
    }
    if text.contains("plane") || text.contains("project") {
        return "ProjectManagement".to_string();
    }
    "AI".to_string()
}

use super::models::AlternativeProject;

pub fn discover(category: &str) -> Vec<AlternativeProject> {
    let projects = match category {
        "ProjectManagement" => vec![
            ("OpenProject", "https://github.com/opf/openproject"),
            ("Leantime", "https://github.com/Leantime/leantime"),
            ("Taiga", "https://github.com/taigaio/taiga-docker"),
            ("Focalboard", "https://github.com/mattermost-community/focalboard"),
        ],
        "CRM" => vec![
            ("Twenty", "https://github.com/twentyhq/twenty"),
            ("EspoCRM", "https://github.com/espocrm/espocrm"),
            ("SuiteCRM", "https://github.com/salesagility/SuiteCRM"),
            ("Odoo CRM", "https://github.com/odoo/odoo"),
        ],
        "Wiki" => vec![
            ("BookStack", "https://github.com/BookStackApp/BookStack"),
            ("Wiki.js", "https://github.com/requarks/wiki"),
            ("DokuWiki", "https://github.com/dokuwiki/dokuwiki"),
            ("MediaWiki", "https://github.com/wikimedia/mediawiki"),
        ],
        "Notes" => vec![
            ("AppFlowy", "https://github.com/AppFlowy-IO/AppFlowy"),
            ("Joplin", "https://github.com/laurent22/joplin"),
            ("Logseq", "https://github.com/logseq/logseq"),
            ("Standard Notes", "https://github.com/standardnotes/app"),
        ],
        "Monitoring" => vec![
            ("Netdata", "https://github.com/netdata/netdata"),
            ("Glances", "https://github.com/nicolargo/glances"),
            ("Grafana", "https://github.com/grafana/grafana"),
            ("Prometheus", "https://github.com/prometheus/prometheus"),
        ],
        "Analytics" => vec![
            ("Metabase", "https://github.com/metabase/metabase"),
            ("Superset", "https://github.com/apache/superset"),
            ("Plausible", "https://github.com/plausible/analytics"),
            ("PostHog", "https://github.com/PostHog/posthog"),
        ],
        "KnowledgeBase" => vec![
            ("Outline", "https://github.com/outline/outline"),
            ("AppFlowy", "https://github.com/AppFlowy-IO/AppFlowy"),
            ("BookStack", "https://github.com/BookStackApp/BookStack"),
            ("Wiki.js", "https://github.com/requarks/wiki"),
        ],
        _ => vec![
            ("OpenWebUI", "https://github.com/open-webui/open-webui"),
            ("Flowise", "https://github.com/FlowiseAI/Flowise"),
            ("LibreChat", "https://github.com/danny-avila/LibreChat"),
            ("Haystack", "https://github.com/deepset-ai/haystack"),
        ],
    };

    let mut similarity_score = 95u8;
    projects
        .into_iter()
        .map(|(name, repo_url)| {
            let project = AlternativeProject {
                name: name.to_string(),
                repo_url: repo_url.to_string(),
                category: category.to_string(),
                similarity_score,
            };
            similarity_score = similarity_score.saturating_sub(10).max(60);
            project
        })
        .collect()
}

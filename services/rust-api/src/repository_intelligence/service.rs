use super::analyzer;
use super::models::{RepositoryAnalysisInput, RepositoryAnalysisResponse};

#[derive(Default)]
pub struct RepositoryIntelligenceService;

impl RepositoryIntelligenceService {
    pub async fn analyze(&self, input: RepositoryAnalysisInput) -> RepositoryAnalysisResponse {
        analyzer::analyze(input).await
    }
}

use std::io::{self, Read};

mod repository_intelligence;

use repository_intelligence::models::RepositoryAnalysisInput;
use repository_intelligence::service::RepositoryIntelligenceService;

#[tokio::main]
async fn main() {
    let mut raw = String::new();
    if io::stdin().read_to_string(&mut raw).is_err() {
        eprintln!("failed to read repository intelligence input");
        std::process::exit(1);
    }

    let request: RepositoryAnalysisInput = match serde_json::from_str(&raw) {
        Ok(value) => value,
        Err(err) => {
            eprintln!("invalid repository intelligence input: {err}");
            std::process::exit(1);
        }
    };

    let runtime = RepositoryIntelligenceService::default();
    let analysis = runtime.analyze(request).await;

    match serde_json::to_string(&analysis) {
        Ok(payload) => println!("{payload}"),
        Err(err) => {
            eprintln!("failed to serialize repository intelligence response: {err}");
            std::process::exit(1);
        }
    }
}

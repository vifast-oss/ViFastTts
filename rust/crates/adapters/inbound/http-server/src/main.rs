use clap::Parser;
use vifasttts_http_server::{Args, serve};

#[tokio::main]
async fn main() -> Result<(), String> {
    serve(Args::parse()).await
}

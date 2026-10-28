use anyhow::Result;
use clap::Parser;
use vifasttts_tui::{TuiArgs, run};

fn main() -> Result<()> {
    run(TuiArgs::parse())
}

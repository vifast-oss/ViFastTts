//! ViFastTts text frontend: Unicode, parser, vocab, chunking, karaoke text.

pub mod chunking;
pub mod custom_reading;
pub mod dialect;
pub mod english;
pub mod karaoke;
pub mod normalizer;
pub mod oov;
pub mod orthography;
pub mod pipeline;
pub mod roman;
pub mod rules;
pub mod stem;
pub mod syllable;
pub mod tone;
pub mod types;
pub mod unicode;
pub mod vocab;

pub use karaoke::{KaraokeDocument, KaraokeLine, TimedUnit, UnitKind};
pub use pipeline::{ParseOptions, parse_text};
pub use types::*;

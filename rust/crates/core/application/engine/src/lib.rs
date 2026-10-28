//! Orchestration backend-agnostic cho ViFastTts.

pub mod engine;

pub use engine::{
    StreamControl, StreamSummary, SynthesisAssembler, SynthesisChunk, SynthesisEngine,
    SynthesisOptions, SynthesisPlan, SynthesisResult, timed_units_from_slots,
};
pub use vifasttts_ports::{
    AcousticModel, AcousticResult, ComplexSpectrogram, MelSpectrogram, ModelInfo, VocoderModel,
};
pub use vifasttts_text::karaoke::{KaraokeDocument, KaraokeLine, TimedUnit, UnitKind};

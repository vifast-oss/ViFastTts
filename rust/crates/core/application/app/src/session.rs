//! Headless synthesis session: command vào, event ra.

use std::cell::RefCell;
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::Instant;

use vifasttts_engine::{
    AcousticModel, KaraokeDocument, StreamControl, SynthesisEngine, SynthesisOptions,
    SynthesisResult, TimedUnit, VocoderModel,
};

use crate::history::{EtaEstimator, EtaSample};

#[derive(Clone, Debug)]
pub enum AppCommand {
    Synthesize {
        text: String,
        speed: f32,
        fixed_pauses: bool,
    },
    Stream {
        text: String,
        speed: f32,
        fixed_pauses: bool,
    },
    Stop,
}

#[derive(Clone, Debug)]
pub enum AppEvent {
    Started {
        estimated_ms: Option<u64>,
    },
    Units(Vec<TimedUnit>),
    AudioChunk {
        samples: Vec<f32>,
        sample_rate: u32,
    },
    Progress {
        audio_ms: u64,
    },
    Finished {
        duration_ms: u64,
        karaoke: Option<KaraokeDocument>,
        cancelled: bool,
    },
    Error {
        code: String,
        message: String,
    },
}

pub struct SynthesisController<A: AcousticModel, V: VocoderModel> {
    engine: SynthesisEngine<A, V>,
    eta: EtaEstimator,
    cancel: Arc<AtomicBool>,
}

impl<A: AcousticModel, V: VocoderModel> SynthesisController<A, V> {
    pub fn new(engine: SynthesisEngine<A, V>, eta: EtaEstimator) -> Self {
        Self {
            engine,
            eta,
            cancel: Arc::new(AtomicBool::new(false)),
        }
    }

    pub fn request_stop(&self) {
        self.cancel.store(true, Ordering::Release);
    }

    pub fn info(&self) -> &vifasttts_engine::ModelInfo {
        &self.engine.info
    }

    fn options_for(
        &self,
        options: &SynthesisOptions,
        speed: f32,
        fixed_pauses: bool,
    ) -> SynthesisOptions {
        let mut result = options.clone();
        result.speed = speed;
        result.fixed_pauses = fixed_pauses;
        if fixed_pauses {
            result.gate_threshold = 1.01;
        }
        result
    }

    /// Chạy một command. `emit` nhận event theo thứ tự; với stream, audio chunk
    /// được phát ngay thay vì gom cả file.
    pub async fn execute<F>(
        &mut self,
        command: &AppCommand,
        options: &SynthesisOptions,
        mode: &str,
        emit: &mut F,
    ) -> Result<(), String>
    where
        F: FnMut(AppEvent),
    {
        if matches!(command, AppCommand::Stop) {
            self.request_stop();
            return Ok(());
        }
        self.cancel.store(false, Ordering::Release);
        let (text, speed, fixed_pauses, streaming) = match command {
            AppCommand::Synthesize {
                text,
                speed,
                fixed_pauses,
            } => (text, *speed, *fixed_pauses, false),
            AppCommand::Stream {
                text,
                speed,
                fixed_pauses,
            } => (text, *speed, *fixed_pauses, true),
            AppCommand::Stop => unreachable!(),
        };
        let chars = text.chars().count();
        emit(AppEvent::Started {
            estimated_ms: self.eta.estimate_ms(mode, chars),
        });
        let options = self.options_for(options, speed, fixed_pauses);
        let started = Instant::now();

        if !streaming {
            return match self.engine.synthesize(text, &options).await {
                Ok(result) => {
                    let duration_ms = duration_ms(&result);
                    emit(AppEvent::Finished {
                        duration_ms,
                        karaoke: result.karaoke,
                        cancelled: false,
                    });
                    self.record(mode, chars, started);
                    Ok(())
                }
                Err(error) => {
                    emit(AppEvent::Error {
                        code: "synthesis".to_string(),
                        message: error.clone(),
                    });
                    Err(error)
                }
            };
        }

        let (result, all_units) = {
            let emit_cell = RefCell::new(&mut *emit);
            let cancel = Arc::clone(&self.cancel);
            let units_store = RefCell::new(Vec::<TimedUnit>::new());
            let mut samples = 0usize;
            let mut audio_ms = 0u64;
            let result = self
                .engine
                .synthesize_stream_with_units(
                    text,
                    &options,
                    |chunk, sample_rate| {
                        if cancel.load(Ordering::Acquire) {
                            return StreamControl::Cancel;
                        }
                        samples += chunk.len();
                        audio_ms = if sample_rate == 0 {
                            audio_ms
                        } else {
                            samples as u64 * 1000 / sample_rate as u64
                        };
                        emit_cell.borrow_mut()(AppEvent::AudioChunk {
                            samples: chunk.to_vec(),
                            sample_rate,
                        });
                        emit_cell.borrow_mut()(AppEvent::Progress { audio_ms });
                        StreamControl::Continue
                    },
                    |units| {
                        units_store.borrow_mut().extend_from_slice(units);
                        emit_cell.borrow_mut()(AppEvent::Units(units.to_vec()));
                    },
                )
                .await;
            (result, units_store.into_inner())
        };

        match result {
            Ok(summary) => {
                let sample_rate = summary.sample_rate.max(1);
                let duration_ms = summary.samples as u64 * 1000 / sample_rate as u64;
                let karaoke = if all_units.is_empty() {
                    None
                } else {
                    Some(KaraokeDocument::from_units(
                        all_units,
                        sample_rate,
                        duration_ms,
                        80,
                    ))
                };
                let cancelled = summary.cancelled || self.cancel.load(Ordering::Acquire);
                emit(AppEvent::Finished {
                    duration_ms,
                    karaoke,
                    cancelled,
                });
                if !cancelled {
                    self.record(mode, chars, started);
                }
                Ok(())
            }
            Err(error) => {
                emit(AppEvent::Error {
                    code: "stream".to_string(),
                    message: error.clone(),
                });
                Err(error)
            }
        }
    }

    fn record(&mut self, mode: &str, chars: usize, started: Instant) {
        self.eta.record(EtaSample {
            mode: mode.to_string(),
            chars,
            elapsed_ms: started.elapsed().as_millis() as u64,
        });
    }
}

fn duration_ms(result: &SynthesisResult) -> u64 {
    result.waveform.len() as u64 * 1000 / result.sample_rate.max(1) as u64
}

//! Audio primitives: iSTFT, sharpen, fade/normalize, WAV PCM16.
//!
//! Các công thức bám sát `runtime/istft.py`, `runtime/postprocess.py` và
//! `infer.write_wav` để PCM khớp bản Python.

use rustfft::FftPlanner;
use rustfft::num_complex::Complex;

pub fn hann_window(length: usize) -> Vec<f64> {
    (0..length)
        .map(|index| 0.5 - 0.5 * (2.0 * std::f64::consts::PI * index as f64 / length as f64).cos())
        .collect()
}

/// iSTFT overlap-add khớp `torch.istft(center=True, hann)`.
#[allow(clippy::too_many_arguments, clippy::needless_range_loop)]
pub fn istft(
    real: &[f32],
    imag: &[f32],
    bins: usize,
    frames: usize,
    n_fft: usize,
    hop_length: usize,
    win_length: Option<usize>,
    center: bool,
) -> Result<Vec<f32>, String> {
    if real.len() != bins * frames || imag.len() != bins * frames {
        return Err("iSTFT: kích thước phổ không khớp".to_string());
    }
    if bins != n_fft / 2 + 1 {
        return Err(format!("iSTFT: bins {bins} != n_fft/2+1"));
    }
    let win_length = win_length.unwrap_or(n_fft);
    if win_length > n_fft {
        return Err("iSTFT: win_length > n_fft".to_string());
    }
    let window = hann_window(win_length);
    let mut padded = vec![0.0f64; n_fft];
    let offset = (n_fft - win_length) / 2;
    padded[offset..offset + win_length].copy_from_slice(&window);

    let total = (frames.saturating_sub(1)) * hop_length + n_fft;
    let mut output = vec![0.0f64; total];
    let mut envelope = vec![0.0f64; total];
    let mut planner = FftPlanner::<f64>::new();
    let inverse = planner.plan_fft_inverse(n_fft);
    let mut spectrum = vec![Complex::new(0.0, 0.0); n_fft];

    for frame in 0..frames {
        spectrum.fill(Complex::new(0.0, 0.0));
        for bin in 0..bins {
            let index = bin * frames + frame;
            spectrum[bin] = Complex::new(real[index] as f64, imag[index] as f64);
        }
        // NumPy irfft dựng nửa đối xứng và bỏ phần ảo ở DC/Nyquist.
        spectrum[0].im = 0.0;
        spectrum[n_fft / 2].im = 0.0;
        for bin in 1..n_fft / 2 {
            spectrum[n_fft - bin] = spectrum[bin].conj();
        }
        inverse.process(&mut spectrum);
        let start = frame * hop_length;
        for index in 0..n_fft {
            let value = spectrum[index].re / n_fft as f64;
            output[start + index] += value * padded[index];
            envelope[start + index] += padded[index] * padded[index];
        }
    }

    for index in 0..total {
        output[index] /= envelope[index].max(1e-11);
    }
    if center {
        let trim = n_fft / 2;
        if total < 2 * trim {
            return Ok(Vec::new());
        }
        return Ok(output[trim..total - trim]
            .iter()
            .map(|value| *value as f32)
            .collect());
    }
    Ok(output.iter().map(|value| *value as f32).collect())
}

/// Unsharp 3×3 zero-pad, alpha 1.5; input [frames, mels].
pub fn sharpen_mel(mel: &[f32], frames: usize, mels: usize, alpha: f32) -> Vec<f32> {
    if alpha == 0.0 {
        return mel.to_vec();
    }
    let mut output = vec![0.0f32; mel.len()];
    for t in 0..frames {
        for f in 0..mels {
            let mut blur = 0.0f32;
            for dt in [-1i32, 0, 1] {
                for df in [-1i32, 0, 1] {
                    let tt = t as i32 + dt;
                    let ff = f as i32 + df;
                    if tt >= 0 && tt < frames as i32 && ff >= 0 && ff < mels as i32 {
                        blur += mel[tt as usize * mels + ff as usize];
                    }
                }
            }
            blur /= 9.0;
            let index = t * mels + f;
            output[index] = mel[index] + alpha * (mel[index] - blur);
        }
    }
    output
}

pub fn peak_normalize(wav: &[f32], target_db: f32) -> Vec<f32> {
    let peak = wav.iter().fold(0.0f32, |acc, value| acc.max(value.abs()));
    if peak <= 1e-8 {
        return wav.to_vec();
    }
    let target = 10.0f32.powf(target_db / 20.0);
    wav.iter().map(|value| value * (target / peak)).collect()
}

#[allow(clippy::needless_range_loop)]
pub fn fade(wav: &[f32], sample_rate: usize, fade_in_ms: f32, fade_out_ms: f32) -> Vec<f32> {
    let mut output = wav.to_vec();
    let length = output.len();
    if length == 0 {
        return output;
    }
    let fade_in = ((sample_rate as f32 * fade_in_ms / 1000.0) as usize).min(length);
    let fade_out = ((sample_rate as f32 * fade_out_ms / 1000.0) as usize).min(length);
    if fade_in > 1 {
        for index in 0..fade_in {
            let gain = index as f32 / (fade_in - 1) as f32;
            output[index] *= gain;
        }
    }
    if fade_out > 1 {
        for index in 0..fade_out {
            let gain = 1.0 - index as f32 / (fade_out - 1) as f32;
            output[length - fade_out + index] *= gain;
        }
    }
    output
}

pub fn postprocess(wav: &[f32], sample_rate: usize, target_db: Option<f32>) -> Vec<f32> {
    let output = fade(wav, sample_rate, 10.0, 20.0);
    match target_db {
        Some(target) => peak_normalize(&output, target),
        None => output,
    }
}

/// WAV PCM16 mono, header giống Python `wave` (44 byte).
pub fn wav_bytes(wav: &[f32], sample_rate: u32) -> Vec<u8> {
    let data_len = wav.len() * 2;
    let mut output = Vec::with_capacity(44 + data_len);
    output.extend_from_slice(b"RIFF");
    output.extend_from_slice(&(36u32 + data_len as u32).to_le_bytes());
    output.extend_from_slice(b"WAVEfmt ");
    output.extend_from_slice(&16u32.to_le_bytes());
    output.extend_from_slice(&1u16.to_le_bytes()); // PCM
    output.extend_from_slice(&1u16.to_le_bytes()); // mono
    output.extend_from_slice(&sample_rate.to_le_bytes());
    output.extend_from_slice(&(sample_rate * 2).to_le_bytes());
    output.extend_from_slice(&2u16.to_le_bytes());
    output.extend_from_slice(&16u16.to_le_bytes());
    output.extend_from_slice(b"data");
    output.extend_from_slice(&(data_len as u32).to_le_bytes());
    for value in wav {
        let clipped = value.clamp(-1.0, 1.0) * 32767.0;
        let pcm = clipped.round_ties_even().clamp(-32768.0, 32767.0) as i16;
        output.extend_from_slice(&pcm.to_le_bytes());
    }
    output
}

/// WAV PCM16 từ bytes PCM đã có (mono/multi-channel), không đổi sample.
///
/// Dùng cho stream mobile: client gom PCM16 ở native, Rust chỉ dựng header
/// chuẩn để Android/iOS không tự viết RIFF khác nhau.
pub fn wav_bytes_pcm16(pcm: &[u8], sample_rate: u32, channels: u16) -> Vec<u8> {
    let channels = channels.max(1);
    let block_align = channels * 2;
    let data_len = pcm.len() as u32;
    let mut output = Vec::with_capacity(44 + pcm.len());
    output.extend_from_slice(b"RIFF");
    output.extend_from_slice(&(36u32 + data_len).to_le_bytes());
    output.extend_from_slice(b"WAVEfmt ");
    output.extend_from_slice(&16u32.to_le_bytes());
    output.extend_from_slice(&1u16.to_le_bytes());
    output.extend_from_slice(&channels.to_le_bytes());
    output.extend_from_slice(&sample_rate.to_le_bytes());
    output.extend_from_slice(&(sample_rate * block_align as u32).to_le_bytes());
    output.extend_from_slice(&block_align.to_le_bytes());
    output.extend_from_slice(&16u16.to_le_bytes());
    output.extend_from_slice(b"data");
    output.extend_from_slice(&data_len.to_le_bytes());
    output.extend_from_slice(pcm);
    output
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn sharpen_zero_alpha_is_identity() {
        let mel = vec![1.0, 2.0, 3.0, 4.0];
        assert_eq!(sharpen_mel(&mel, 2, 2, 0.0), mel);
    }

    #[test]
    fn wav_header_is_riff() {
        let wav = wav_bytes(&[0.0, 0.5, -0.5], 24000);
        assert_eq!(&wav[..4], b"RIFF");
        let pcm = wav_bytes_pcm16(&[0, 1, 2, 3], 24000, 1);
        assert_eq!(&pcm[..4], b"RIFF");
        assert_eq!(u32::from_le_bytes(pcm[24..28].try_into().unwrap()), 24000);
        assert_eq!(u32::from_le_bytes(pcm[40..44].try_into().unwrap()), 4);
        assert_eq!(&wav[8..12], b"WAVE");
        assert_eq!(wav.len(), 44 + 6);
    }
}

import * as ort from 'onnxruntime-web';
import init, { synthesize, karaoke_to_srt, karaoke_to_vtt } from './pkg/vifasttts_wasm.js';

const SAMPLE_RATE = 24000;
const N_FFT = 1024;
const HOP = 256;
const N_MELS = 100;

const statusEl = document.getElementById('status');
const runEl = document.getElementById('run');
const textEl = document.getElementById('text');
const fixedEl = document.getElementById('fixed');
const audioEl = document.getElementById('audio');
const karaokeEl = document.getElementById('karaoke');
const srtEl = document.getElementById('srt');

let acousticSession = null;
let vocoderSession = null;
let document_ = null;

function setStatus(text) {
  statusEl.textContent = text;
}

async function loadModels() {
  setStatus('Đang nạp ONNX Runtime Web…');
  ort.env.wasm.wasmPaths = '/ort/';
  ort.env.wasm.numThreads = 1;
  ort.env.wasm.simd = true;

  const [acousticBuf, vocoderBuf] = await Promise.all([
    fetch('/models/acoustic.onnx').then((r) => r.arrayBuffer()),
    fetch('/models/vocoder.onnx').then((r) => r.arrayBuffer()),
  ]);
  setStatus(`Đang tạo session (${(acousticBuf.byteLength / 1e6).toFixed(1)} MB + ${(vocoderBuf.byteLength / 1e6).toFixed(1)} MB)…`);
  acousticSession = await ort.InferenceSession.create(acousticBuf, {
    executionProviders: ['wasm'],
    graphOptimizationLevel: 'all',
  });
  vocoderSession = await ort.InferenceSession.create(vocoderBuf, {
    executionProviders: ['wasm'],
    graphOptimizationLevel: 'all',
  });
  setStatus('Sẵn sàng — chạy hoàn toàn local trong trình duyệt.');
  runEl.disabled = false;
}

async function acoustic(features, speed, gate) {
  const n = features.length;
  const data = new BigInt64Array(n * 7);
  for (let i = 0; i < n; i++) {
    for (let j = 0; j < 7; j++) data[i * 7 + j] = BigInt(features[i][j]);
  }
  const out = await acousticSession.run({
    features: new ort.Tensor('int64', data, [1, n, 7]),
    speed: new ort.Tensor('float32', Float32Array.of(speed), [1]),
    gate_threshold: new ort.Tensor('float32', Float32Array.of(gate), [1]),
  });
  const mel = out.mel;
  return {
    mel: mel.data,
    frames: mel.dims[1],
    mels: mel.dims[2],
    slot_durations: out.slot_durations.data,
  };
}

async function vocoder(mel, frames, mels) {
  const out = await vocoderSession.run({
    mel: new ort.Tensor('float32', new Float32Array(mel), [1, frames, mels]),
  });
  return {
    real: out.spec_real.data,
    imag: out.spec_imag.data,
    bins: out.spec_real.dims[1],
    frames: out.spec_real.dims[2],
  };
}

async function run() {
  runEl.disabled = true;
  try {
    setStatus('Đang tổng hợp…');
    const text = textEl.value.trim();
    if (!text) throw new Error('Nhập câu cần đọc');
    const result = await synthesize(text, 1.0, fixedEl.checked, acoustic, vocoder);
    const wav = new Uint8Array(result.wav);
    audioEl.src = URL.createObjectURL(new Blob([wav], { type: 'audio/wav' }));
    document_ = result.karaoke;
    renderKaraoke(document_);
    srtEl.textContent = await karaoke_to_srt(document_);
    window.__vifasttVtt = await karaoke_to_vtt(document_);
    setStatus(`Xong: ${(result.duration_ms / 1000).toFixed(2)} s, ${document_.units.length} âm tiết.`);
    await audioEl.play();
  } catch (error) {
    console.error(error);
    setStatus(`Lỗi: ${error?.message || error}`);
  } finally {
    runEl.disabled = false;
  }
}

function renderKaraoke(doc) {
  karaokeEl.innerHTML = '';
  for (const line of doc.lines) {
    const lineEl = document.createElement('div');
    for (const unit of line.units) {
      const span = document.createElement('span');
      span.textContent = `${unit.text}${unit.punctuation || ''} `;
      span.dataset.start = unit.start_ms;
      span.dataset.end = unit.end_ms;
      lineEl.appendChild(span);
    }
    karaokeEl.appendChild(lineEl);
  }
}

audioEl.addEventListener('timeupdate', () => {
  if (!document_) return;
  const ms = audioEl.currentTime * 1000;
  for (const span of karaokeEl.querySelectorAll('span')) {
    const start = Number(span.dataset.start);
    const end = Number(span.dataset.end);
    span.classList.toggle('active', ms >= start && ms < end);
  }
});

runEl.addEventListener('click', run);

(async () => {
  try {
    await init();
    await loadModels();
  } catch (error) {
    console.error(error);
    setStatus(`Không nạp được: ${error?.message || error}`);
  }
})();

// Local WASM hoặc remote server; cùng một UI/karaoke.
import * as ort from 'onnxruntime-web';
import init, { synthesize, karaoke_to_srt, karaoke_to_vtt } from './pkg/vifasttts_wasm.js';

const statusEl = document.getElementById('status');
const runEl = document.getElementById('run');
const textEl = document.getElementById('text');
const fixedEl = document.getElementById('fixed');
const modeEl = document.getElementById('mode');
const serverUrlEl = document.getElementById('serverUrl');
const tokenEl = document.getElementById('token');
const remoteFields = document.getElementById('remoteFields');
const audioEl = document.getElementById('audio');
const karaokeEl = document.getElementById('karaoke');
const srtEl = document.getElementById('srt');

let acousticSession = null;
let vocoderSession = null;
let document_ = null;
let localReady = false;
let currentAudioUrl = null;

function setStatus(text) {
  statusEl.textContent = text;
}

function setModeFields() {
  remoteFields.classList.toggle('hidden', modeEl.value !== 'remote');
}

function base64ToBytes(base64) {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

function playBytes(bytes) {
  if (currentAudioUrl) URL.revokeObjectURL(currentAudioUrl);
  currentAudioUrl = URL.createObjectURL(new Blob([bytes], { type: 'audio/wav' }));
  audioEl.src = currentAudioUrl;
  audioEl.load();
  return audioEl.play().catch(() => {});
}

async function loadModels() {
  if (localReady) return;
  setStatus('Đang nạp ONNX Runtime Web…');
  ort.env.wasm.wasmPaths = '/ort/';
  ort.env.wasm.numThreads = 1;
  ort.env.wasm.simd = true;
  await init();
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
  localReady = true;
  setStatus('Local sẵn sàng — chạy hoàn toàn trong trình duyệt.');
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

async function runLocal(text) {
  await loadModels();
  setStatus('Đang tổng hợp local…');
  const result = await synthesize(text, 1.0, fixedEl.checked, acoustic, vocoder);
  await playBytes(new Uint8Array(result.wav));
  document_ = result.karaoke;
  renderKaraoke(document_);
  srtEl.textContent = await karaoke_to_srt(document_);
  window.__vifastttVtt = await karaoke_to_vtt(document_);
  setStatus(`Xong local: ${(result.duration_ms / 1000).toFixed(2)} s, ${document_.units.length} âm tiết.`);
}

async function runRemote(text) {
  let base = serverUrlEl.value.trim().replace(/\/+$/, '');
  if (!base) base = window.location.origin;
  const url = base.endsWith('/api/tts') ? base : `${base}/api/tts`;
  setStatus(`Đang gọi ${url}…`);
  const headers = { 'content-type': 'application/json' };
  if (tokenEl.value.trim()) headers.authorization = `Bearer ${tokenEl.value.trim()}`;
  const response = await fetch(url, {
    method: 'POST',
    headers,
    body: JSON.stringify({
      text,
      speed: 1.0,
      fixed_pauses: fixedEl.checked,
      karaoke: true,
    }),
  });
  if (!response.ok) throw new Error(`Server HTTP ${response.status}: ${await response.text()}`);
  const result = await response.json();
  if (!result.audio_base64) throw new Error('Server không trả audio_base64');
  await playBytes(base64ToBytes(result.audio_base64));
  document_ = result.karaoke;
  renderKaraoke(document_);
  srtEl.textContent = result.srt || (document_ ? await karaoke_to_srt(document_) : '');
  window.__vifastttVtt = result.vtt || result.vtt_karaoke || '';
  setStatus(`Xong remote: ${(result.duration_ms / 1000).toFixed(2)} s, ${document_?.units?.length || 0} âm tiết.`);
}

async function run() {
  runEl.disabled = true;
  try {
    const text = textEl.value.trim();
    if (!text) throw new Error('Nhập câu cần đọc');
    if (modeEl.value === 'remote') await runRemote(text);
    else await runLocal(text);
  } catch (error) {
    console.error(error);
    setStatus(`Lỗi: ${error?.message || error}`);
  } finally {
    runEl.disabled = false;
  }
}

function renderKaraoke(doc) {
  karaokeEl.innerHTML = '';
  if (!doc?.lines?.length) return;
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

modeEl.addEventListener('change', () => {
  setModeFields();
  setStatus(modeEl.value === 'remote' ? 'Remote: nhập server URL.' : 'Local: bấm Đọc để nạp model.');
});
runEl.addEventListener('click', run);
setModeFields();
runEl.disabled = false;
setStatus('Chọn Local WASM hoặc Remote server.');

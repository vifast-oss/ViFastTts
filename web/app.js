// Local WASM hoặc remote server; cùng một UI/karaoke.
import * as ort from 'onnxruntime-web';
import init, { dictionary_json, synthesize_full, karaoke_to_srt, karaoke_to_vtt } from './pkg/vifasttts_wasm.js';
import { unzipSync, strFromU8 } from 'fflate';
import { sha256 } from 'js-sha256';
import { ModelApi, bundleFiles, normalizeServerBase } from './shared/model-api.js';

const statusEl = document.getElementById('status');
const runEl = document.getElementById('run');
const textEl = document.getElementById('text');
const fixedEl = document.getElementById('fixed');
const speedEl = document.getElementById('speed');
const speedValueEl = document.getElementById('speedValue');
const alphaEl = document.getElementById('alpha');
const alphaValueEl = document.getElementById('alphaValue');
const peakEl = document.getElementById('peak');
const resolveOovEl = document.getElementById('resolveOov');
const dialectEl = document.getElementById('dialect');
const maxCharsEl = document.getElementById('maxChars');
const dictionaryEl = document.getElementById('dictionary');
const dictionaryStatusEl = document.getElementById('dictionaryStatus');
const modeEl = document.getElementById('mode');
const serverUrlEl = document.getElementById('serverUrl');
const tokenEl = document.getElementById('token');
const remoteFields = document.getElementById('remoteFields');
const modelFileEl = document.getElementById('modelFile');
const modelQueryEl = document.getElementById('modelQuery');
const directModelsEl = document.getElementById('directModels');
const modelSearchEl = document.getElementById('modelSearch');
const modelStatusEl = document.getElementById('modelStatus');
const modelListEl = document.getElementById('modelList');
const modelFilesEl = document.getElementById('modelFiles');
const audioEl = document.getElementById('audio');
const downloadEl = document.getElementById('download');
const downloadSrtEl = document.getElementById('downloadSrt');
const downloadVttEl = document.getElementById('downloadVtt');
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

async function dictionaryOverrides() {
  const text = dictionaryEl.value.trim();
  if (!text) {
    dictionaryStatusEl.textContent = '';
    return {};
  }
  const payload = JSON.parse(await dictionary_json(text));
  dictionaryStatusEl.textContent = `${(payload.rules || []).length} quy tắc` +
    (payload.warnings?.length ? ` · ${payload.warnings.length} cảnh báo` : '');
  return payload.overrides || {};
}

function synthOptions(overrides) {
  return {
    speed: Number(speedEl.value),
    alpha: Number(alphaEl.value),
    max_chars: Math.max(50, Math.min(5000, Number(maxCharsEl.value) || 300)),
    fixed_pauses: fixedEl.checked,
    peak_normalize: peakEl.checked,
    dialect: dialectEl.value,
    resolve_oov: resolveOovEl.checked,
    overrides,
  };
}

function setDownload(link, text, type) {
  if (!link) return;
  if (!text) {
    link.classList.add('hidden');
    if (link.href.startsWith('blob:')) URL.revokeObjectURL(link.href);
    link.removeAttribute('href');
    return;
  }
  const url = URL.createObjectURL(new Blob([text], { type }));
  link.href = url;
  link.classList.remove('hidden');
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
  if (downloadEl) {
    downloadEl.href = currentAudioUrl;
    downloadEl.classList.remove('hidden');
  }
  return audioEl.play().catch(() => {});
}

async function ensureOrt() {
  ort.env.wasm.wasmPaths = '/ort/';
  ort.env.wasm.numThreads = 1;
  ort.env.wasm.simd = true;
  await init();
}

async function createSessions(acousticBuf, vocoderBuf) {
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
}

async function loadModels() {
  if (localReady) return;
  setStatus('Đang nạp ONNX Runtime Web…');
  await ensureOrt();
  const [acousticBuf, vocoderBuf] = await Promise.all([
    fetch('/models/acoustic.onnx').then((r) => r.arrayBuffer()),
    fetch('/models/vocoder.onnx').then((r) => r.arrayBuffer()),
  ]);
  await createSessions(acousticBuf, vocoderBuf);
  setStatus('Local sẵn sàng — chạy hoàn toàn trong trình duyệt.');
}

function sha256Hex(bytes) {
  // js-sha256 hoạt động cả trên HTTP LAN (không cần secure context như crypto.subtle).
  return sha256(bytes);
}

async function loadBundle(file) {
  const bytes = new Uint8Array(await file.arrayBuffer());
  const entries = unzipSync(bytes);
  const manifestName = 'manifest.json';
  if (!entries[manifestName]) throw new Error('Bundle thiếu manifest.json');
  const manifest = JSON.parse(strFromU8(entries[manifestName]));
  const acousticName = manifest.acoustic?.file || 'acoustic.onnx';
  const acoustic = entries[acousticName];
  if (!acoustic) throw new Error(`Bundle thiếu ${acousticName}`);
  if (manifest.acoustic?.sha256) {
    const actual = await sha256Hex(acoustic);
    if (actual !== manifest.acoustic.sha256) throw new Error('SHA256 acoustic không khớp');
  }
  let vocoderBytes;
  if (manifest.vocoder?.file) {
    const vocoder = entries[manifest.vocoder.file];
    if (!vocoder) throw new Error(`Bundle thiếu ${manifest.vocoder.file}`);
    const actual = await sha256Hex(vocoder);
    if (manifest.vocoder.sha256 && actual !== manifest.vocoder.sha256) {
      throw new Error('SHA256 vocoder không khớp');
    }
    vocoderBytes = vocoder;
  } else {
    // .vfa: dùng vocoder bundled của web/app; kiểm hash nếu manifest có.
    const response = await fetch('/models/vocoder.onnx');
    if (!response.ok) throw new Error('Không có /models/vocoder.onnx cho .vfa');
    const bundled = new Uint8Array(await response.arrayBuffer());
    if (manifest.vocoder?.sha256) {
      const actual = await sha256Hex(bundled);
      if (actual !== manifest.vocoder.sha256) throw new Error('.vfa cần vocoder khác (hash không khớp)');
    }
    vocoderBytes = bundled;
  }
  await ensureOrt();
  await createSessions(acoustic, vocoderBytes);
  setStatus(`Đã nạp ${file.name} — local WASM.`);
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
  const overrides = await dictionaryOverrides();
  const options = synthOptions(overrides);
  const result = await synthesize_full(text, JSON.stringify(options), acoustic, vocoder);
  await playBytes(new Uint8Array(result.wav));
  document_ = result.karaoke;
  renderKaraoke(document_);
  const srt = document_ ? await karaoke_to_srt(document_) : '';
  const vtt = document_ ? await karaoke_to_vtt(document_) : '';
  srtEl.textContent = srt;
  setDownload(downloadSrtEl, srt, 'text/plain');
  setDownload(downloadVttEl, vtt, 'text/vtt');
  setStatus(`Xong local: ${(result.duration_ms / 1000).toFixed(2)} s, ${document_?.units?.length || 0} âm tiết.`);
}

async function runRemote(text) {
  let base = serverUrlEl.value.trim().replace(/\/+$/, '');
  if (!base) base = window.location.origin;
  const url = base.endsWith('/api/tts') ? base : `${base}/api/tts`;
  setStatus(`Đang gọi ${url}…`);
  const headers = { 'content-type': 'application/json' };
  if (tokenEl.value.trim()) headers.authorization = `Bearer ${tokenEl.value.trim()}`;
  const overrides = await dictionaryOverrides();
  const options = synthOptions(overrides);
  const response = await fetch(url, {
    method: 'POST',
    headers,
    body: JSON.stringify({
      text,
      ...options,
      dictionary: dictionaryEl.value.trim(),
      karaoke: true,
    }),
  });
  if (!response.ok) throw new Error(`Server HTTP ${response.status}: ${await response.text()}`);
  const result = await response.json();
  if (!result.audio_base64) throw new Error('Server không trả audio_base64');
  await playBytes(base64ToBytes(result.audio_base64));
  document_ = result.karaoke;
  renderKaraoke(document_);
  const srt = result.srt || (document_ ? await karaoke_to_srt(document_) : '');
  const vtt = result.vtt || result.vtt_karaoke || '';
  srtEl.textContent = srt;
  setDownload(downloadSrtEl, srt, 'text/plain');
  setDownload(downloadVttEl, vtt, 'text/vtt');
  setStatus(`Xong remote: ${(result.duration_ms / 1000).toFixed(2)} s, ${document_?.units?.length || 0} âm tiết.`);
}

function modelApi() {
  return new ModelApi({
    baseUrl: normalizeServerBase(serverUrlEl.value.trim(), window.location.origin),
    token: tokenEl.value,
    direct: Boolean(directModelsEl?.checked),
  });
}

async function searchModels() {
  const query = modelQueryEl.value.trim() || 'vifasttts';
  modelListEl.innerHTML = '';
  modelFilesEl.innerHTML = '';
  modelStatusEl.textContent = 'Đang tìm…';
  try {
    const models = await modelApi().search(query, 20);
    modelStatusEl.textContent = `${models.length} repo`;
    for (const model of models) {
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = `${model.id} (${bundleFiles(model).length} bundle)`;
      button.addEventListener('click', () => loadModelFiles(model.id));
      modelListEl.appendChild(button);
    }
  } catch (error) {
    modelStatusEl.textContent = `Lỗi: ${error?.message || error}`;
  }
}

async function loadModelFiles(repo) {
  modelFilesEl.innerHTML = '';
  modelStatusEl.textContent = `Đang xem ${repo}…`;
  try {
    const files = await modelApi().files(repo);
    if (!files.length) {
      modelStatusEl.textContent = 'Repo chưa có .vfa/.vfts.';
      return;
    }
    modelStatusEl.textContent = `${files.length} bundle`;
    for (const file of files) {
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = `${file.path} — ${(file.size / 1e6).toFixed(1)} MB`;
      button.addEventListener('click', () => downloadModel(repo, file.path));
      modelFilesEl.appendChild(button);
    }
  } catch (error) {
    modelStatusEl.textContent = `Lỗi: ${error?.message || error}`;
  }
}

async function downloadModel(repo, path) {
  modelStatusEl.textContent = `Đang tải ${path}…`;
  try {
    const downloaded = await modelApi().download(repo, path);
    modeEl.value = 'local';
    setModeFields();
    await loadBundle(new File([downloaded.blob], downloaded.filename));
    modelStatusEl.textContent = `Đã nạp ${downloaded.filename}`;
  } catch (error) {
    modelStatusEl.textContent = `Lỗi: ${error?.message || error}`;
  }
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

speedEl.addEventListener('input', () => {
  speedValueEl.textContent = `${Number(speedEl.value).toFixed(2)}×`;
});
alphaEl.addEventListener('input', () => {
  alphaValueEl.textContent = Number(alphaEl.value).toFixed(2);
});
modeEl.addEventListener('change', () => {
  setModeFields();
  setStatus(modeEl.value === 'remote' ? 'Remote: nhập server URL.' : 'Local: bấm Đọc để nạp model.');
});
modelSearchEl.addEventListener('click', searchModels);
modelFileEl.addEventListener('change', async () => {
  const file = modelFileEl.files?.[0];
  if (!file) return;
  try {
    modeEl.value = 'local';
    setModeFields();
    await loadBundle(file);
  } catch (error) {
    setStatus(`Lỗi model: ${error?.message || error}`);
  }
});
runEl.addEventListener('click', run);
const saved = JSON.parse(localStorage.getItem('vifasttts.web.settings') || '{}');
for (const [id, value] of Object.entries(saved)) {
  const element = document.getElementById(id);
  if (!element) continue;
  if (element.type === 'checkbox') element.checked = Boolean(value);
  else element.value = value;
}
for (const element of [speedEl, alphaEl, fixedEl, peakEl, resolveOovEl, dialectEl, maxCharsEl, dictionaryEl]) {
  element.addEventListener('change', () => {
    const values = {};
    for (const id of ['speed', 'alpha', 'fixed', 'peak', 'resolveOov', 'dialect', 'maxChars', 'dictionary', 'directModels']) {
      const item = document.getElementById(id);
      values[id] = item.type === 'checkbox' ? item.checked : item.value;
    }
    localStorage.setItem('vifasttts.web.settings', JSON.stringify(values));
  });
}
speedValueEl.textContent = `${Number(speedEl.value).toFixed(2)}×`;
alphaValueEl.textContent = Number(alphaEl.value).toFixed(2);
setModeFields();
runEl.disabled = false;

(async () => {
  setStatus('Đang kiểm tra server local…');
  if (location.protocol === 'http:' || location.protocol === 'https:') {
    try {
      const response = await fetch('/healthz', { cache: 'no-store' });
      if (response.ok) {
        modeEl.value = 'remote';
        serverUrlEl.value = location.origin;
        setModeFields();
        setStatus(`Remote server: ${location.origin}`);
        return;
      }
    } catch {
      // fall through local
    }
  }
  if (directModelsEl) directModelsEl.checked = true;
  setStatus('Local WASM — bấm Đọc hoặc nạp .vfa/.vfts.');
})();

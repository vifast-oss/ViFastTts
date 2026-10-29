// Offscreen document: nơi duy nhất có DOM + wasm + ORT Web.
// Service worker không có DOM; popup chỉ là UI.

import init, {
  dictionary_json,
  karaoke_from_units,
  karaoke_to_srt,
  karaoke_to_vtt,
  synthesize_stream_full,
  synthesize_full,
} from './vendor/pkg/vifasttts_wasm.js';
import * as ort from './vendor/ort/ort.wasm.min.mjs';
import { parseBundle } from './shared/bundle.js';

const MODEL_CACHE = 'vifasttts-models-v1';

let localReady = null;
let localSignature = null;
let wasmReady = null;
let acousticSession = null;
let vocoderSession = null;
let lastAudioUrl = null;
let speakAudio = null;
let speakId = null;
let audioContext = null;
let streamAbort = false;
let streamAbortController = null;
let streamNextTime = 0;
let streamSources = [];
let streamUnits = [];
let streamAudioSeconds = 0;
let streamSampleRate = 24000;

function notifyPopup(message) {
  chrome.runtime
    .sendMessage({ target: 'vifasttts-popup', type: 'status', message })
    .catch(() => {});
}

function modelUrl(base, name) {
  const normalized = base.endsWith('/') ? base : `${base}/`;
  return new URL(name, normalized).href;
}

async function loadModelBytes(name, settings_) {
  // 1) Model bundle trong extension (tiện cho demo/offline).
  const bundled = chrome.runtime.getURL(`models/${name}`);
  try {
    const response = await fetch(bundled);
    if (response.ok) {
      notifyPopup(`Đang nạp ${name} từ extension…`);
      return new Uint8Array(await response.arrayBuffer());
    }
  } catch {
    // Không có file bundle: chuyển sang nguồn remote.
  }

  // 2) Tải từ model base URL và cache lại cho lần sau.
  const base = settings_.modelBaseUrl?.trim();
  if (!base) {
    throw new Error(
      `Không có ${name}. Hãy bundle model vào extension/models/ hoặc nhập Model base URL.`,
    );
  }
  const url = modelUrl(base, name);
  let cache = null;
  try {
    cache = await caches.open(MODEL_CACHE);
    const cached = await cache.match(url);
    if (cached) {
      notifyPopup(`Đang nạp ${name} từ cache…`);
      return new Uint8Array(await cached.arrayBuffer());
    }
  } catch {
    cache = null;
  }

  notifyPopup(`Đang tải ${name} (lần đầu)…`);
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Tải ${name} thất bại: HTTP ${response.status}`);
  }
  if (cache) {
    try {
      await cache.put(url, response.clone());
    } catch {
      // Cache đầy/quota: vẫn dùng model vừa tải.
    }
  }
  return new Uint8Array(await response.arrayBuffer());
}

async function loadCachedBundle(key) {
  const cache = await caches.open(MODEL_CACHE);
  const cached = await cache.match(key);
  if (!cached) {
    throw new Error('Không tìm thấy bundle đã tải; hãy tải lại trong Cài đặt.');
  }
  return new Uint8Array(await cached.arrayBuffer());
}

async function loadBundleModel(key, settings_) {
  notifyPopup('Đang nạp bundle .vfa/.vfts…');
  const bytes = await loadCachedBundle(key);
  let bundle;
  try {
    bundle = await parseBundle(bytes);
  } catch (error) {
    // .vfa không chứa vocoder: dùng vocoder bundled/model base.
    if (!/vocoder/i.test(String(error?.message || error))) throw error;
    const fallback = await loadModelBytes('vocoder.onnx', settings_);
    bundle = await parseBundle(bytes, { fallbackVocoder: fallback });
  }
  notifyPopup(`Đang dùng bundle ${bundle.manifest.arch || 'model'}…`);
  return [bundle.acoustic, bundle.vocoder];
}

function bundleSignature(request) {
  return `${request.bundleKey || ''}|${request.modelBaseUrl || ''}`;
}

async function localOptions(request) {
  return {
    speed: Number(request.speed) || 1,
    alpha: Number(request.alpha) || 1.5,
    max_chars: Number(request.maxChars) || 300,
    fixed_pauses: Boolean(request.fixedPauses),
    peak_normalize: Boolean(request.peakNormalize),
    dialect: request.dialect || 'north',
    resolve_oov: request.resolveOov !== false,
    overrides: await parseDictionary(request.dictionary),
  };
}

async function initLocal(request) {
  const signature = bundleSignature(request);
  if (localReady && signature === localSignature) return localReady;
  if (localReady) {
    // Đổi bundle: đóng session cũ trước khi nạp model mới.
    acousticSession = null;
    vocoderSession = null;
    localReady = null;
  }
  localSignature = signature;
  localReady = (async () => {
    notifyPopup('Đang khởi tạo WASM…');
    await ensureWasm();

    ort.env.wasm.wasmPaths = chrome.runtime.getURL('vendor/ort/');
    ort.env.wasm.numThreads = 1;
    ort.env.wasm.simd = true;
    ort.env.wasm.proxy = false;

    const settings_ = { modelBaseUrl: request.modelBaseUrl || '' };
    const [acousticBytes, vocoderBytes] = request.bundleKey
      ? await loadBundleModel(request.bundleKey, settings_)
      : await Promise.all([
          loadModelBytes('acoustic.onnx', settings_),
          loadModelBytes('vocoder.onnx', settings_),
        ]);

    notifyPopup('Đang tạo ONNX session…');
    [acousticSession, vocoderSession] = await Promise.all([
      ort.InferenceSession.create(acousticBytes, {
        executionProviders: ['wasm'],
        graphOptimizationLevel: 'all',
      }),
      ort.InferenceSession.create(vocoderBytes, {
        executionProviders: ['wasm'],
        graphOptimizationLevel: 'all',
      }),
    ]);
    notifyPopup('Local đã sẵn sàng.');
  })().catch((error) => {
    localReady = null;
    throw error;
  });
  return localReady;
}

async function acoustic(features, speed, gate) {
  const count = features.length;
  const data = new BigInt64Array(count * 7);
  for (let index = 0; index < count; index += 1) {
    for (let column = 0; column < 7; column += 1) {
      data[index * 7 + column] = BigInt(features[index][column]);
    }
  }
  const output = await acousticSession.run({
    features: new ort.Tensor('int64', data, [1, count, 7]),
    speed: new ort.Tensor('float32', Float32Array.of(speed), [1]),
    gate_threshold: new ort.Tensor('float32', Float32Array.of(gate), [1]),
  });
  const mel = output.mel;
  return {
    mel: mel.data,
    frames: mel.dims[1],
    mels: mel.dims[2],
    slot_durations: output.slot_durations?.data ?? null,
    durations: output.durations?.data ?? null,
  };
}

async function vocoder(mel, frames, mels) {
  const output = await vocoderSession.run({
    mel: new ort.Tensor('float32', new Float32Array(mel), [1, frames, mels]),
  });
  return {
    real: output.spec_real.data,
    imag: output.spec_imag.data,
    bins: output.spec_real.dims[1],
    frames: output.spec_real.dims[2],
  };
}

function base64ToBytes(base64) {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes;
}

function bytesToBase64(bytes) {
  let binary = '';
  const chunk = 0x8000;
  for (let offset = 0; offset < bytes.length; offset += chunk) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + chunk));
  }
  return btoa(binary);
}

function makeAudioUrl(bytes) {
  if (lastAudioUrl) {
    URL.revokeObjectURL(lastAudioUrl);
    lastAudioUrl = null;
  }
  lastAudioUrl = URL.createObjectURL(new Blob([bytes], { type: 'audio/wav' }));
  return lastAudioUrl;
}

async function ensureWasm() {
  if (!wasmReady) {
    wasmReady = init(chrome.runtime.getURL('vendor/pkg/vifasttts_wasm_bg.wasm')).catch((error) => {
      wasmReady = null;
      throw error;
    });
  }
  return wasmReady;
}

/// Parse bằng `vifasttts-app` trong wasm, không lặp logic JS.
async function parseDictionary(text) {
  await ensureWasm();
  const raw = await dictionary_json(String(text || ''));
  return JSON.parse(raw).overrides || {};
}

async function ensureAudioContext() {
  if (!audioContext) {
    audioContext = new AudioContext({ latencyHint: 'interactive' });
  }
  if (audioContext.state === 'suspended') {
    await audioContext.resume();
  }
  return audioContext;
}

function schedulePcm(samples, sampleRate) {
  const context = audioContext;
  if (!context) return;
  const buffer = context.createBuffer(1, samples.length, sampleRate);
  buffer.copyToChannel(samples, 0);
  const source = context.createBufferSource();
  source.buffer = buffer;
  source.connect(context.destination);
  const start = Math.max(context.currentTime + 0.04, streamNextTime);
  source.start(start);
  streamNextTime = start + buffer.duration;
  streamSources.push(source);
  source.onended = () => {
    streamSources = streamSources.filter((item) => item !== source);
  };
}

function resetStream() {
  streamAbort = false;
  streamAbortController = null;
  streamUnits = [];
  streamAudioSeconds = 0;
  streamSampleRate = 24000;
  streamNextTime = 0;
}

function stopStream() {
  streamAbort = true;
  streamAbortController?.abort();
  streamAbortController = null;
  for (const source of streamSources) {
    try {
      source.stop();
    } catch {
      // Source đã dừng.
    }
  }
  streamSources = [];
}

function streamProgress() {
  chrome.runtime
    .sendMessage({
      target: 'vifasttts-popup',
      type: 'stream-progress',
      audio_seconds: streamAudioSeconds,
      units: streamUnits.length,
    })
    .catch(() => {});
}

function streamUnitsEvent(units) {
  if (!Array.isArray(units) || units.length === 0) return;
  streamUnits.push(...units);
  chrome.runtime
    .sendMessage({ target: 'vifasttts-popup', type: 'stream-units', units })
    .catch(() => {});
  streamProgress();
}

function base64PcmToFloat32(base64) {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  const view = new DataView(bytes.buffer);
  const out = new Float32Array(bytes.length / 2);
  for (let index = 0; index < out.length; index += 1) {
    out[index] = view.getInt16(index * 2, true) / 32768;
  }
  return out;
}

async function streamSummary(sampleRate, samples, cancelled = false) {
  const durationMs = Math.round((samples / Math.max(1, sampleRate)) * 1000);
  const karaoke = await karaoke_from_units(streamUnits, sampleRate, durationMs, 80);
  const srt = karaoke ? await karaoke_to_srt(karaoke) : '';
  const vtt = karaoke ? await karaoke_to_vtt(karaoke) : '';
  return {
    streamed: true,
    audio_url: null,
    wav_base64: null,
    sample_rate: sampleRate,
    duration_ms: durationMs,
    cancelled,
    karaoke,
    srt,
    vtt,
    vtt_karaoke: vtt,
  };
}

async function runLocalStream(request) {
  await initLocal(request);
  stopStream();
  resetStream();
  const context = await ensureAudioContext();
  streamNextTime = context.currentTime + 0.06;
  const options = await localOptions(request);
  const summary = await synthesize_stream_full(
    request.text,
    JSON.stringify(options),
    acoustic,
    vocoder,
    (event) => {
      if (streamAbort) return false;
      const samples = event.samples;
      const sampleRate = Number(event.sample_rate) || 24000;
      streamSampleRate = sampleRate;
      schedulePcm(samples, sampleRate);
      streamAudioSeconds += samples.length / sampleRate;
      streamProgress();
      return !streamAbort;
    },
    (units) => {
      streamUnitsEvent(units);
    },
  );
  const result = await streamSummary(streamSampleRate, summary.samples, summary.cancelled);
  result.chunks = summary.chunks;
  return result;
}

async function runRemoteStream(request) {
  stopStream();
  resetStream();
  const context = await ensureAudioContext();
  streamNextTime = context.currentTime + 0.06;
  streamAbortController = new AbortController();
  const headers = { 'content-type': 'application/json' };
  if (request.token) headers.authorization = `Bearer ${request.token}`;
  const base = request.serverUrl.replace(/\/+$/, '');
  const url = base.endsWith('/api/tts/stream')
    ? base
    : base.endsWith('/api/tts')
      ? `${base}/stream`
      : `${base}/api/tts/stream`;
  const response = await fetch(url, {
    method: 'POST',
    headers,
    signal: streamAbortController.signal,
    body: JSON.stringify({
      text: request.text,
      speed: Number(request.speed) || 1,
      alpha: Number(request.alpha) || 1.5,
      max_chars: Number(request.maxChars) || 300,
      fixed_pauses: Boolean(request.fixedPauses),
      peak_normalize: Boolean(request.peakNormalize),
      dialect: request.dialect || 'north',
      resolve_oov: request.resolveOov !== false,
      overrides: await parseDictionary(request.dictionary),
      dictionary: request.dictionary,
    }),
  });
  if (!response.ok) {
    throw new Error(`Server HTTP ${response.status}: ${await response.text()}`);
  }
  if (!response.body) throw new Error('Server không hỗ trợ stream');
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let samples = 0;
  let doneEvent = null;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    if (streamAbort) {
      await reader.cancel().catch(() => {});
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    let newline = buffer.indexOf('\n');
    while (newline >= 0) {
      const line = buffer.slice(0, newline).trim();
      buffer = buffer.slice(newline + 1);
      newline = buffer.indexOf('\n');
      if (!line) continue;
      const event = JSON.parse(line);
      if (event.type === 'units') {
        streamUnitsEvent(event.units);
      } else if (event.type === 'audio') {
        const pcm = base64PcmToFloat32(event.pcm_base64);
        const sampleRate = Number(event.sample_rate) || 24000;
        streamSampleRate = sampleRate;
        schedulePcm(pcm, sampleRate);
        streamAudioSeconds += pcm.length / sampleRate;
        samples += pcm.length;
        streamProgress();
      } else if (event.type === 'done') {
        doneEvent = event;
      } else if (event.type === 'error') {
        throw new Error(event.message || 'Server stream lỗi');
      }
    }
  }
  const result = await streamSummary(
    streamSampleRate,
    doneEvent?.samples || samples,
    streamAbort,
  );
  result.chunks = doneEvent?.chunks || null;
  return result;
}

async function runLocal(request) {
  await initLocal(request);
  const options = await localOptions(request);
  const result = await synthesize_full(
    request.text,
    JSON.stringify(options),
    acoustic,
    vocoder,
  );
  const wav = new Uint8Array(result.wav);
  const srt = result.karaoke ? await karaoke_to_srt(result.karaoke) : '';
  const vtt = result.karaoke ? await karaoke_to_vtt(result.karaoke) : '';
  return {
    audio_url: makeAudioUrl(wav),
    wav_base64: bytesToBase64(wav),
    sample_rate: result.sample_rate,
    duration_ms: result.duration_ms,
    karaoke: result.karaoke,
    srt,
    vtt,
    vtt_karaoke: vtt,
  };
}

function endpoint(base) {
  const trimmed = base.replace(/\/+$/, '');
  return trimmed.endsWith('/api/tts') ? trimmed : `${trimmed}/api/tts`;
}

async function runRemote(request) {
  const headers = { 'content-type': 'application/json' };
  if (request.token) headers.authorization = `Bearer ${request.token}`;
  const response = await fetch(endpoint(request.serverUrl), {
    method: 'POST',
    headers,
    body: JSON.stringify({
      text: request.text,
      speed: Number(request.speed) || 1,
      alpha: Number(request.alpha) || 1.5,
      max_chars: Number(request.maxChars) || 300,
      fixed_pauses: Boolean(request.fixedPauses),
      peak_normalize: Boolean(request.peakNormalize),
      dialect: request.dialect || 'north',
      resolve_oov: request.resolveOov !== false,
      karaoke: true,
      overrides: await parseDictionary(request.dictionary),
      dictionary: request.dictionary,
    }),
  });
  if (!response.ok) {
    throw new Error(`Server HTTP ${response.status}: ${await response.text()}`);
  }
  const data = await response.json();
  if (!data.audio_base64) throw new Error('Server không trả audio_base64');
  const wav = base64ToBytes(data.audio_base64);
  return {
    audio_url: makeAudioUrl(wav),
    wav_base64: data.audio_base64,
    sample_rate: data.sample_rate,
    duration_ms: data.duration_ms,
    karaoke: data.karaoke,
    srt: data.srt || '',
    vtt: data.vtt || data.vtt_karaoke || '',
    vtt_karaoke: data.vtt_karaoke || data.vtt || '',
  };
}

async function handleSynthesize(request) {
  if (request.mode === 'remote') {
    return runRemote(request);
  }
  return runLocal(request);
}

async function handleStream(request) {
  if (request.mode === 'remote') {
    return runRemoteStream(request);
  }
  return runLocalStream(request);
}

function notifyPlayback(id, type, error = '') {
  chrome.runtime
    .sendMessage({ target: 'vifasttts-background', type, id, error })
    .catch(() => {});
}

function stopSpeak() {
  if (speakAudio) {
    speakAudio.pause();
    speakAudio.currentTime = 0;
    speakAudio = null;
  }
  speakId = null;
}

async function handleSpeak(message) {
  stopSpeak();
  const result = await handleSynthesize(message.request);
  speakId = message.id;
  speakAudio = new Audio(result.audio_url);
  speakAudio.onended = () => {
    if (speakId !== message.id) return;
    notifyPlayback(message.id, 'speak-ended');
    speakAudio = null;
    speakId = null;
  };
  speakAudio.onerror = () => {
    if (speakId !== message.id) return;
    notifyPlayback(message.id, 'speak-error', 'Không phát được audio');
    speakAudio = null;
    speakId = null;
  };
  try {
    await speakAudio.play();
    notifyPlayback(message.id, 'speak-started');
  } catch (error) {
    notifyPlayback(message.id, 'speak-error', String(error?.message || error));
    throw error;
  }
  return { duration_ms: result.duration_ms };
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.target !== 'vifasttts-offscreen') return undefined;

  if (message.type === 'synthesize') {
    handleSynthesize(message.request)
      .then((result) => sendResponse({ ok: true, result }))
      .catch((error) => sendResponse({ ok: false, error: String(error?.message || error) }));
    return true;
  }

  if (message.type === 'stream') {
    handleStream(message.request)
      .then((result) => sendResponse({ ok: true, result }))
      .catch((error) => sendResponse({ ok: false, error: String(error?.message || error) }));
    return true;
  }

  if (message.type === 'stop-stream') {
    stopStream();
    sendResponse({ ok: true });
    return true;
  }

  if (message.type === 'reset-local') {
    acousticSession = null;
    vocoderSession = null;
    localReady = null;
    localSignature = null;
    sendResponse({ ok: true });
    return true;
  }

  if (message.type === 'speak') {
    handleSpeak(message)
      .then((result) => sendResponse({ ok: true, result }))
      .catch((error) => sendResponse({ ok: false, error: String(error?.message || error) }));
    return true;
  }

  if (message.type === 'stop') {
    stopSpeak();
    sendResponse({ ok: true });
    return true;
  }

  if (message.type === 'pause') {
    if (speakAudio) speakAudio.pause();
    sendResponse({ ok: true });
    return true;
  }

  if (message.type === 'resume') {
    if (speakAudio) speakAudio.play().catch(() => {});
    sendResponse({ ok: true });
    return true;
  }

  return undefined;
});

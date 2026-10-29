// Popup UI: đọc text, đọc cả trang, cấu hình local/remote/cách bôi đen.
import { ModelApi, bundleFiles, normalizeServerBase } from './shared/model-api.js';
import { DEFAULT_SETTINGS, HISTORY_KEY, normalizeSettings } from './shared/settings.js';
import {
  appendKaraokeUnits,
  base64ToBytes,
  downloadText,
  renderKaraoke,
  updateKaraokeHighlight,
} from './shared/ui-core.js';

const DEFAULTS = DEFAULT_SETTINGS;

const $ = (id) => document.getElementById(id);
const modeEl = $('mode');
const serverUrlEl = $('serverUrl');
const tokenEl = $('token');
const modelBaseUrlEl = $('modelBaseUrl');
const selectionActionEl = $('selectionAction');
const dictionaryEl = $('dictionary');
const textEl = $('text');
const countEl = $('count');
const speedEl = $('speed');
const speedValueEl = $('speedValue');
const alphaEl = $('alpha');
const alphaValueEl = $('alphaValue');
const peakNormalizeEl = $('peakNormalize');
const resolveOovEl = $('resolveOov');
const dialectEl = $('dialect');
const maxCharsEl = $('maxChars');
const fixedEl = $('fixed');
const streamEl = $('stream');
const runEl = $('run');
const readPageEl = $('readPage');
const clearTextEl = $('clearText');
const stopStreamEl = $('stopStream');
const clearCacheEl = $('clearCache');
const statusEl = $('status');
const statusPillEl = $('statusPill');
const playerEl = $('player');
const audioEl = $('audio');
const downloadWavEl = $('downloadWav');
const karaokeEl = $('karaoke');
const srtEl = $('srt');
const downloadSrtEl = $('downloadSrt');
const downloadVttEl = $('downloadVtt');
const modelQueryEl = $('modelQuery');
const directModelsEl = $('directModels');
const modelSearchEl = $('modelSearch');
const modelClearEl = $('modelClear');
const modelStatusEl = $('modelStatus');
const modelListEl = $('modelList');
const modelFilesEl = $('modelFiles');

let currentSrt = '';
let currentVtt = '';
let currentAudioUrl = null;
let history = [];
let bundleKey = '';
let bundleName = '';

function setStatus(message, kind = '') {
  statusEl.textContent = message;
  statusEl.className = kind;
  statusPillEl.textContent =
    kind === 'busy' ? 'Đang xử lý' : kind === 'ok' ? 'Xong' : kind === 'err' ? 'Lỗi' : 'Sẵn sàng';
}

function setModeFields() {
  const remote = modeEl.value === 'remote';
  $('remoteFields').classList.toggle('hidden', !remote);
  $('localFields').classList.toggle('hidden', remote);
}

function updateCount() {
  countEl.textContent = `${textEl.value.length} ký tự`;
}

async function loadHistory() {
  const stored = await chrome.storage.local.get({ [HISTORY_KEY]: [] });
  history = Array.isArray(stored[HISTORY_KEY]) ? stored[HISTORY_KEY] : [];
}

async function estimateFor(mode, chars) {
  if (!chars) return null;
  try {
    const response = await chrome.runtime.sendMessage({
      target: 'vifasttts-background',
      type: 'estimate',
      mode,
      chars,
    });
    return response?.ok && Number.isFinite(response.result)
      ? { ms: Number(response.result), runs: history.length }
      : null;
  } catch {
    return null;
  }
}

function saveSettings() {
  chrome.storage.local.set(normalizeSettings({
    mode: modeEl.value,
    serverUrl: serverUrlEl.value.trim(),
    token: tokenEl.value,
    modelBaseUrl: modelBaseUrlEl.value.trim(),
    bundleKey,
    bundleName,
    selectionAction: selectionActionEl.value,
    dictionary: dictionaryEl.value,
    stream: streamEl.checked,
    directModels: directModelsEl.checked,
    speed: Number(speedEl.value),
    fixedPauses: fixedEl.checked,
    alpha: Number(alphaEl.value),
    maxChars: Number(maxCharsEl.value),
    peakNormalize: peakNormalizeEl.checked,
    dialect: dialectEl.value,
    resolveOov: resolveOovEl.checked,
  }));
}

async function loadSettings() {
  const settings = normalizeSettings(await chrome.storage.local.get(DEFAULTS));
  modeEl.value = settings.mode === 'remote' ? 'remote' : 'local';
  serverUrlEl.value = settings.serverUrl || DEFAULTS.serverUrl;
  tokenEl.value = settings.token || '';
  modelBaseUrlEl.value = settings.modelBaseUrl || '';
  bundleKey = settings.bundleKey || '';
  bundleName = settings.bundleName || '';
  selectionActionEl.value = ['hidden', 'popup', 'tab'].includes(settings.selectionAction)
    ? settings.selectionAction
    : DEFAULTS.selectionAction;
  dictionaryEl.value = settings.dictionary || '';
  streamEl.checked = Boolean(settings.stream);
  directModelsEl.checked = Boolean(settings.directModels);
  speedEl.value = Number(settings.speed) || 1;
  fixedEl.checked = Boolean(settings.fixedPauses);
  alphaEl.value = Number(settings.alpha) || 1.5;
  maxCharsEl.value = Number(settings.maxChars) || 300;
  peakNormalizeEl.checked = Boolean(settings.peakNormalize);
  dialectEl.value = ['north', 'central', 'south'].includes(settings.dialect)
    ? settings.dialect
    : 'north';
  resolveOovEl.checked = settings.resolveOov !== false;
  speedValueEl.textContent = `${Number(speedEl.value).toFixed(2)}×`;
  alphaValueEl.textContent = Number(alphaEl.value).toFixed(2);
  updateBundleLabel();
  await loadHistory();
  setModeFields();
  syncStreamPeak();
}

function makeAudioUrlFromBase64(base64) {
  return URL.createObjectURL(new Blob([base64ToBytes(base64)], { type: 'audio/wav' }));
}

function revokeOldUrl() {
  if (currentAudioUrl) {
    URL.revokeObjectURL(currentAudioUrl);
    currentAudioUrl = null;
  }
}

async function ensureRemotePermission(serverUrl) {
  let url;
  try {
    url = new URL(serverUrl);
  } catch {
    throw new Error('URL không hợp lệ');
  }
  if (url.protocol !== 'http:' && url.protocol !== 'https:') {
    throw new Error('URL phải là http(s)');
  }
  const pattern = `${url.protocol}//${url.host}/*`;
  const hasPermission = await chrome.permissions.contains({ origins: [pattern] });
  if (hasPermission) return;
  const granted = await chrome.permissions.request({ origins: [pattern] });
  if (!granted) throw new Error('Chưa cấp quyền truy cập host');
}

function modelServerUrl() {
  return normalizeServerBase(serverUrlEl.value.trim(), DEFAULTS.serverUrl);
}

function modelApi() {
  return new ModelApi({
    baseUrl: modelServerUrl(),
    token: tokenEl.value,
    direct: directModelsEl.checked,
  });
}

async function ensureModelPermission() {
  if (directModelsEl.checked) {
    await ensureRemotePermission('https://huggingface.co');
    return;
  }
  await ensureRemotePermission(modelServerUrl());
}

function bundleCacheUrl(repo, path) {
  const name = path.split('/').pop();
  return `https://vifasttts.invalid/bundles/${encodeURIComponent(repo)}/${encodeURIComponent(name)}`;
}

function updateBundleLabel() {
  modelStatusEl.textContent = bundleName
    ? `Đang dùng: ${bundleName}`
    : 'Chưa chọn bundle; dùng model trong extension hoặc Model base URL.';
}

async function searchModels() {
  const query = modelQueryEl.value.trim() || 'vifasttts';
  modelListEl.innerHTML = '';
  modelFilesEl.innerHTML = '';
  modelStatusEl.textContent = 'Đang tìm…';
  try {
    await ensureModelPermission();
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
    await ensureModelPermission();
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
    await ensureModelPermission();
    const downloaded = await modelApi().download(repo, path);
    const key = bundleCacheUrl(repo, path);
    const cache = await caches.open('vifasttts-models-v1');
    await cache.put(key, new Response(downloaded.blob, {
      headers: { 'content-type': 'application/octet-stream' },
    }));
    bundleKey = key;
    bundleName = `${repo}/${downloaded.filename}`;
    modelStatusEl.textContent = `Đã tải ${downloaded.filename}; lần đọc sau dùng bundle này.`;
    saveSettings();
    resetLocal();
  } catch (error) {
    modelStatusEl.textContent = `Lỗi: ${error?.message || error}`;
  }
}

async function clearBundle() {
  if (bundleKey) {
    try {
      const cache = await caches.open('vifasttts-models-v1');
      await cache.delete(bundleKey);
    } catch {
      // Cache có thể đã bị xoá.
    }
  }
  bundleKey = '';
  bundleName = '';
  modelListEl.innerHTML = '';
  modelFilesEl.innerHTML = '';
  updateBundleLabel();
  saveSettings();
  resetLocal();
}

async function resetLocal() {
  try {
    await chrome.runtime.sendMessage({
      target: 'vifasttts-background',
      type: 'reset-local',
    });
  } catch {
    // Offscreen chưa mở; lần đọc sau tự nạp theo bundleKey.
  }
}

async function playResult(result) {
  revokeOldUrl();
  currentAudioUrl = result.audio_url || null;
  if (!currentAudioUrl && result.wav_base64) {
    currentAudioUrl = makeAudioUrlFromBase64(result.wav_base64);
  }
  if (!currentAudioUrl) throw new Error('Server không trả audio');

  audioEl.onerror = () => {
    if (result.wav_base64) {
      const fallback = makeAudioUrlFromBase64(result.wav_base64);
      if (audioEl.src !== fallback) {
        audioEl.src = fallback;
        audioEl.play().catch(() => {});
      }
    }
  };
  audioEl.src = currentAudioUrl;
  audioEl.load();
  downloadWavEl.href = currentAudioUrl;
  playerEl.classList.remove('hidden');
  try {
    await audioEl.play();
  } catch {
    setStatus('Audio đã tạo. Bấm nút play trên trình phát nếu bị chặn autoplay.', 'ok');
  }
}

async function run() {
  const text = textEl.value.trim();
  if (!text) {
    setStatus('Nhập nội dung cần đọc.', 'err');
    return;
  }

  const mode = modeEl.value;
  const streaming = streamEl.checked || text.length > 1500;
  const peakNormalize = streaming ? false : peakNormalizeEl.checked;
  const estimate = await estimateFor(mode, text.length);
  const estimateText = estimate
    ? ` (ước tính ~${(estimate.ms / 1000).toFixed(1)} s, ${estimate.runs} lần trước)`
    : '';
  runEl.disabled = true;
  audioEl.pause();
  stopStreamEl.classList.toggle('hidden', !streaming);
  if (streaming) karaokeEl.textContent = '';
  setStatus(`${streaming ? 'Đang stream' : 'Đang tổng hợp'}${estimateText}…`, 'busy');
  try {
    saveSettings();
    if (mode === 'remote') {
      await ensureRemotePermission(serverUrlEl.value.trim());
    } else if (modelBaseUrlEl.value.trim()) {
      await ensureRemotePermission(modelBaseUrlEl.value.trim());
    }
    const response = await chrome.runtime.sendMessage({
      target: 'vifasttts-background',
      type: streaming ? 'stream' : 'synthesize',
      request: {
        mode,
        text,
        speed: Number(speedEl.value),
        alpha: Number(alphaEl.value),
        maxChars: Number(maxCharsEl.value),
        peakNormalize,
        dialect: dialectEl.value,
        resolveOov: resolveOovEl.checked,
        fixedPauses: fixedEl.checked,
        serverUrl: serverUrlEl.value.trim(),
        token: tokenEl.value,
        modelBaseUrl: modelBaseUrlEl.value.trim(),
        bundleKey,
        dictionary: dictionaryEl.value,
      },
    });
    if (!response?.ok) {
      throw new Error(response?.error || 'Không tổng hợp được');
    }
    const result = response.result;
    renderKaraoke(karaokeEl, result.karaoke);
    setSubtitle(result);
    if (streaming) {
      playerEl.classList.remove('hidden');
      audioEl.classList.add('hidden');
      downloadWavEl.classList.add('hidden');
    } else {
      playerEl.classList.remove('hidden');
      audioEl.classList.remove('hidden');
      downloadWavEl.classList.remove('hidden');
      await playResult(result);
    }
    const seconds = (result.duration_ms || 0) / 1000;
    const units = result.karaoke?.units?.length || 0;
    setStatus(
      streaming
        ? `Xong: đã phát ${seconds.toFixed(2)} s, ${units} âm tiết.`
        : `Xong: ${seconds.toFixed(2)} s, ${units} âm tiết.`,
      'ok',
    );
    await loadHistory();
  } catch (error) {
    setStatus(`Lỗi: ${error?.message || error}`, 'err');
  } finally {
    runEl.disabled = false;
    stopStreamEl.classList.add('hidden');
  }
}

async function pageText() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id) throw new Error('Không xác định được tab hiện tại');
  const [result] = await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: () => {
      const node =
        document.querySelector('article, main, [role="main"]') || document.body;
      if (!node) return '';
      return node.innerText.replace(/\s+/g, ' ').trim().slice(0, 50000);
    },
  });
  return result?.result || '';
}

async function readPage() {
  readPageEl.disabled = true;
  setStatus('Đang lấy text trang…', 'busy');
  try {
    const text = await pageText();
    if (!text) throw new Error('Trang này không có text đọc được');
    textEl.value = text;
    await run();
  } catch (error) {
    setStatus(`Lỗi đọc trang: ${error?.message || error}`, 'err');
  } finally {
    readPageEl.disabled = false;
  }
}

async function takePendingText() {
  const pending = await chrome.storage.session.get({
    pendingText: '',
    pendingAutorun: false,
  });
  if (!pending.pendingText) return null;
  await chrome.storage.session.remove(['pendingText', 'pendingAutorun']);
  return pending;
}

audioEl.addEventListener('timeupdate', () => {
  updateKaraokeHighlight(karaokeEl, audioEl.currentTime * 1000);
});

modeEl.addEventListener('change', () => {
  setModeFields();
  saveSettings();
});
speedEl.addEventListener('input', () => {
  speedValueEl.textContent = `${Number(speedEl.value).toFixed(2)}×`;
  saveSettings();
});
alphaEl.addEventListener('input', () => {
  alphaValueEl.textContent = Number(alphaEl.value).toFixed(2);
  saveSettings();
});
for (const element of [
  serverUrlEl, tokenEl, modelBaseUrlEl, selectionActionEl, dictionaryEl,
  peakNormalizeEl, resolveOovEl, dialectEl, maxCharsEl,
]) {
  element.addEventListener('change', saveSettings);
}
function syncStreamPeak() {
  peakNormalizeEl.disabled = streamEl.checked;
  const note = $('peakStreamNote');
  if (note) note.classList.toggle('hidden', !streamEl.checked);
}
streamEl.addEventListener('change', () => { syncStreamPeak(); saveSettings(); });
directModelsEl.addEventListener('change', saveSettings);
modelSearchEl.addEventListener('click', searchModels);
modelClearEl.addEventListener('click', clearBundle);
stopStreamEl.addEventListener('click', async () => {
  stopStreamEl.disabled = true;
  try {
    await chrome.runtime.sendMessage({
      target: 'vifasttts-background',
      type: 'stop-stream',
    });
    setStatus('Đã dừng stream.', 'ok');
  } catch (error) {
    setStatus(`Lỗi dừng stream: ${error?.message || error}`, 'err');
  } finally {
    stopStreamEl.disabled = false;
  }
});
textEl.addEventListener('input', updateCount);
clearTextEl.addEventListener('click', () => {
  textEl.value = '';
  updateCount();
  textEl.focus();
});
for (const button of document.querySelectorAll('[data-text]')) {
  button.addEventListener('click', () => {
    textEl.value = button.dataset.text || '';
    updateCount();
    textEl.focus();
  });
}
runEl.addEventListener('click', () => run());
readPageEl.addEventListener('click', () => readPage());
document.addEventListener('keydown', (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
    event.preventDefault();
    run();
  }
});
downloadSrtEl.addEventListener('click', () => downloadText(currentSrt, 'vifasttts.srt', 'text/plain'));
downloadVttEl.addEventListener('click', () =>
  downloadText(currentVtt, 'vifasttts.vtt', 'text/vtt'),
);
clearCacheEl.addEventListener('click', async () => {
  clearCacheEl.disabled = true;
  try {
    const response = await chrome.runtime.sendMessage({
      target: 'vifasttts-background',
      type: 'clear-model-cache',
    });
    setStatus(
      response?.ok ? 'Đã xoá cache model.' : `Lỗi: ${response?.error || 'không xoá được'}`,
      response?.ok ? 'ok' : 'err',
    );
    if (response?.ok) {
      bundleKey = '';
      bundleName = '';
      updateBundleLabel();
      resetLocal();
    }
  } finally {
    clearCacheEl.disabled = false;
  }
});

chrome.runtime.onMessage.addListener((message) => {
  if (message?.target !== 'vifasttts-popup') return;
  if (message.type === 'status') {
    const text = message.message || '';
    const kind = /lỗi/i.test(text) ? 'err' : /xong|đã đọc/i.test(text) ? 'ok' : 'busy';
    setStatus(text, kind);
  } else if (message.type === 'stream-units') {
    appendKaraokeUnits(karaokeEl, message.units);
  } else if (message.type === 'stream-progress' && runEl.disabled) {
    setStatus(`Đang phát ${Number(message.audio_seconds || 0).toFixed(1)} s…`, 'busy');
  }
});

const query = new URLSearchParams(location.search);
const queryText = query.get('text');
const autoRun = query.get('autorun') === '1';

(async () => {
  try {
    await loadSettings();
    const pending = await takePendingText();
    if (pending) {
      textEl.value = pending.pendingText;
      if (pending.pendingAutorun) setTimeout(() => run(), 50);
    } else if (queryText) {
      textEl.value = queryText;
      if (autoRun) setTimeout(() => run(), 50);
    }
    setModeFields();
    speedValueEl.textContent = `${Number(speedEl.value).toFixed(2)}×`;
    updateCount();
  } catch (error) {
    setStatus(`Không đọc được cấu hình: ${error}`, 'err');
  }
})();

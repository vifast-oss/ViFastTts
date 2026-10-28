// Popup UI: đọc text, đọc cả trang, cấu hình local/remote/cách bôi đen.

const DEFAULTS = {
  mode: 'local',
  serverUrl: 'http://127.0.0.1:8000',
  token: '',
  modelBaseUrl: '',
  selectionAction: 'hidden',
  dictionary: '',
  stream: false,
};

const HISTORY_KEY = 'vifasttts_history_v1';

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

let currentSrt = '';
let currentVtt = '';
let currentAudioUrl = null;
let history = [];

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

function estimateFor(mode, chars) {
  if (!chars || !history.length) return null;
  const samples = history
    .filter((item) => item.mode === mode && item.chars > 0 && item.elapsed_ms > 0)
    .slice(-8)
    .map((item) => item.elapsed_ms / item.chars)
    .sort((a, b) => a - b);
  if (!samples.length) return null;
  const median = samples[Math.floor(samples.length / 2)];
  return {
    ms: Math.round(median * chars),
    runs: samples.length,
  };
}

function saveSettings() {
  chrome.storage.local.set({
    mode: modeEl.value,
    serverUrl: serverUrlEl.value.trim(),
    token: tokenEl.value,
    modelBaseUrl: modelBaseUrlEl.value.trim(),
    selectionAction: selectionActionEl.value,
    dictionary: dictionaryEl.value,
    stream: streamEl.checked,
  });
}

async function loadSettings() {
  const settings = await chrome.storage.local.get(DEFAULTS);
  modeEl.value = settings.mode === 'remote' ? 'remote' : 'local';
  serverUrlEl.value = settings.serverUrl || DEFAULTS.serverUrl;
  tokenEl.value = settings.token || '';
  modelBaseUrlEl.value = settings.modelBaseUrl || '';
  selectionActionEl.value = ['hidden', 'popup', 'tab'].includes(settings.selectionAction)
    ? settings.selectionAction
    : DEFAULTS.selectionAction;
  dictionaryEl.value = settings.dictionary || '';
  streamEl.checked = Boolean(settings.stream);
  await loadHistory();
  setModeFields();
}

function base64ToArrayBuffer(base64) {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes.buffer;
}

function makeAudioUrlFromBase64(base64) {
  return URL.createObjectURL(new Blob([base64ToArrayBuffer(base64)], { type: 'audio/wav' }));
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

function renderKaraoke(document_) {
  karaokeEl.textContent = '';
  if (!document_?.lines?.length) return;
  for (const line of document_.lines) {
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

function setSubtitle(result) {
  currentSrt = result.srt || '';
  currentVtt = result.vtt || result.vtt_karaoke || '';
  srtEl.textContent = currentSrt;
}

function appendStreamUnits(units) {
  if (!Array.isArray(units)) return;
  for (const unit of units) {
    const span = document.createElement('span');
    span.textContent = `${unit.text}${unit.punctuation || ''} `;
    span.dataset.start = unit.start_ms;
    span.dataset.end = unit.end_ms;
    karaokeEl.appendChild(span);
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
  const estimate = estimateFor(mode, text.length);
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
        fixedPauses: fixedEl.checked,
        serverUrl: serverUrlEl.value.trim(),
        token: tokenEl.value,
        modelBaseUrl: modelBaseUrlEl.value.trim(),
        dictionary: dictionaryEl.value,
      },
    });
    if (!response?.ok) {
      throw new Error(response?.error || 'Không tổng hợp được');
    }
    const result = response.result;
    renderKaraoke(result.karaoke);
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

function downloadText(text, filename, mime) {
  if (!text) return;
  const url = URL.createObjectURL(new Blob([text], { type: mime }));
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
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
  const ms = audioEl.currentTime * 1000;
  for (const span of karaokeEl.querySelectorAll('span')) {
    const start = Number(span.dataset.start);
    const end = Number(span.dataset.end);
    span.classList.toggle('active', ms >= start && ms < end);
  }
});

modeEl.addEventListener('change', () => {
  setModeFields();
  saveSettings();
});
speedEl.addEventListener('input', () => {
  speedValueEl.textContent = `${Number(speedEl.value).toFixed(2)}×`;
  saveSettings();
});
for (const element of [serverUrlEl, tokenEl, modelBaseUrlEl, selectionActionEl, dictionaryEl]) {
  element.addEventListener('change', saveSettings);
}
streamEl.addEventListener('change', saveSettings);
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
    appendStreamUnits(message.units);
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

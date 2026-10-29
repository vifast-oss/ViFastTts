// MV3 service worker: menu, chọn cách đọc, route request sang offscreen.
// Không có DOM/audio trong service worker.

import init, { eta_estimate } from './vendor/pkg/vifasttts_wasm.js';

const OFFSCREEN_URL = 'offscreen.html';
const MENU_ROOT = 'vifasttts-selection';
const MENU_READ = 'vifasttts-read-selection';
const MENU_HIDDEN = 'vifasttts-read-hidden';
const MENU_POPUP = 'vifasttts-read-popup';
const MENU_TAB = 'vifasttts-read-tab';
const MENU_PAGE = 'vifasttts-read-page';
const SETTINGS_DEFAULTS = {
  mode: 'local',
  serverUrl: 'http://127.0.0.1:8000',
  token: '',
  modelBaseUrl: '',
  bundleKey: '',
  bundleName: '',
  selectionAction: 'hidden',
  dictionary: '',
  alpha: 1.5,
  maxChars: 300,
  peakNormalize: false,
  dialect: 'north',
  resolveOov: true,
  speed: 1,
  fixedPauses: false,
};
const HISTORY_KEY = 'vifasttts_history_v1';
const HISTORY_LIMIT = 20;
const MAX_TEXT = 50000;

let creating = null;
let directTtsId = null;
let wasmReady = null;

async function ensureWasm() {
  if (!wasmReady) {
    wasmReady = init(chrome.runtime.getURL('vendor/pkg/vifasttts_wasm_bg.wasm')).catch((error) => {
      wasmReady = null;
      throw error;
    });
  }
  return wasmReady;
}

async function recordHistory(mode, chars, elapsedMs, audioSeconds) {
  if (!chars || !Number.isFinite(elapsedMs) || elapsedMs <= 0) return;
  try {
    const stored = await chrome.storage.local.get({ [HISTORY_KEY]: [] });
    const history = Array.isArray(stored[HISTORY_KEY]) ? stored[HISTORY_KEY] : [];
    history.push({
      mode,
      chars,
      elapsed_ms: Math.round(elapsedMs),
      audio_seconds: Number(audioSeconds) || 0,
      at: Date.now(),
    });
    await chrome.storage.local.set({ [HISTORY_KEY]: history.slice(-HISTORY_LIMIT) });
  } catch {
    // Lịch sử chỉ là tối ưu UX.
  }
}

function notifyPopup(message) {
  chrome.runtime
    .sendMessage({ target: 'vifasttts-popup', type: 'status', message })
    .catch(() => {});
}

function setBadge(text, title = 'ViFastTts') {
  chrome.action.setBadgeText({ text });
  chrome.action.setTitle({ title });
  if (text) chrome.action.setBadgeBackgroundColor({ color: '#2563eb' });
}

function clearDirectBadge() {
  if (!directTtsId) return;
  directTtsId = null;
  setBadge('', 'ViFastTts');
}

function createContextMenu() {
  if (!chrome.contextMenus) return;
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create({
      id: MENU_ROOT,
      title: 'ViFastTts',
      contexts: ['selection'],
    });
    chrome.contextMenus.create({
      id: MENU_READ,
      parentId: MENU_ROOT,
      title: 'Đọc đoạn bôi đen (theo cài đặt)',
      contexts: ['selection'],
    });
    chrome.contextMenus.create({
      id: MENU_HIDDEN,
      parentId: MENU_ROOT,
      title: 'Đọc ẩn (không mở tab)',
      contexts: ['selection'],
    });
    chrome.contextMenus.create({
      id: MENU_POPUP,
      parentId: MENU_ROOT,
      title: 'Đọc trong popup',
      contexts: ['selection'],
    });
    chrome.contextMenus.create({
      id: MENU_TAB,
      parentId: MENU_ROOT,
      title: 'Mở tab đọc',
      contexts: ['selection'],
    });
    chrome.contextMenus.create({
      id: MENU_PAGE,
      title: 'Đọc toàn bộ trang bằng ViFastTts',
      contexts: ['page'],
    });
  });
}

async function hasOffscreenDocument() {
  if (!chrome.runtime.getContexts) return false;
  const contexts = await chrome.runtime.getContexts({
    contextTypes: ['OFFSCREEN_DOCUMENT'],
    documentUrls: [chrome.runtime.getURL(OFFSCREEN_URL)],
  });
  return contexts.length > 0;
}

async function ensureOffscreenDocument() {
  if (await hasOffscreenDocument()) return;
  if (creating) return creating;
  creating = chrome.offscreen
    .createDocument({
      url: OFFSCREEN_URL,
      reasons: ['BLOBS'],
      justification: 'Chạy WASM/ORT Web và tạo Blob WAV cho TTS local.',
    })
    .finally(() => {
      creating = null;
    });
  await creating;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function sendToOffscreen(message) {
  await ensureOffscreenDocument();
  let lastError = null;
  for (let attempt = 0; attempt < 30; attempt += 1) {
    try {
      const response = await chrome.runtime.sendMessage({
        target: 'vifasttts-offscreen',
        ...message,
      });
      if (response !== undefined) return response;
    } catch (error) {
      lastError = error;
    }
    await sleep(100);
  }
  throw new Error(
    `Không kết nối được offscreen${lastError ? `: ${lastError.message || lastError}` : ''}`,
  );
}

async function openReaderTab(text) {
  await chrome.storage.session.set({
    pendingText: text.slice(0, MAX_TEXT),
    pendingAutorun: true,
  });
  return chrome.tabs.create({ url: chrome.runtime.getURL('popup.html?autorun=1') });
}

async function openReaderPopup(text) {
  // Chrome 127+: mở action popup; popup đọc pendingText từ storage.session.
  if (typeof chrome.action.openPopup !== 'function') {
    await openReaderTab(text);
    return;
  }
  await chrome.storage.session.set({
    pendingText: text.slice(0, MAX_TEXT),
    pendingAutorun: true,
  });
  try {
    await chrome.action.openPopup();
  } catch {
    // Giữ pendingText để openReaderTab đọc; không cần set lại.
    await openReaderTab(text);
  }
}

async function speakSelection(text) {
  clearDirectBadge();
  const id = crypto.randomUUID();
  directTtsId = id;
  setBadge('…', 'ViFastTts: đang tổng hợp');
  notifyPopup('Đang đọc đoạn bôi đen…');
  try {
    const settings_ = await chrome.storage.local.get(SETTINGS_DEFAULTS);
    const response = await sendToOffscreen({
      type: 'stream',
      id,
      request: {
        mode: settings_.mode,
        text: text.slice(0, MAX_TEXT),
        speed: Number(settings_.speed) || 1,
        alpha: Number(settings_.alpha) || 1.5,
        maxChars: Number(settings_.maxChars) || 300,
        peakNormalize: Boolean(settings_.peakNormalize),
        dialect: settings_.dialect || 'north',
        resolveOov: settings_.resolveOov !== false,
        fixedPauses: Boolean(settings_.fixedPauses),
        serverUrl: settings_.serverUrl,
        token: settings_.token,
        modelBaseUrl: settings_.modelBaseUrl,
        bundleKey: settings_.bundleKey,
        dictionary: settings_.dictionary,
      },
    });
    if (!response?.ok) {
      throw new Error(response?.error || 'Không tổng hợp được');
    }
    if (directTtsId === id) {
      directTtsId = null;
      setBadge('▶', 'ViFastTts: đang phát');
      notifyPopup('Đang phát đoạn bôi đen…');
      setTimeout(() => {
        if (!directTtsId) setBadge('', 'ViFastTts');
      }, Math.max(1000, Number(response.result?.duration_ms || 0)));
    }
  } catch (error) {
    if (directTtsId === id) {
      directTtsId = null;
      setBadge('!', `ViFastTts: ${String(error?.message || error)}`);
      notifyPopup(`Lỗi đọc ẩn: ${String(error?.message || error)}`);
    }
  }
}

async function readText(text, action) {
  if (!text?.trim()) return;
  if (action === 'tab') {
    await openReaderTab(text);
  } else if (action === 'popup') {
    await openReaderPopup(text);
  } else {
    await speakSelection(text);
  }
}

async function pageText(tabId) {
  const [result] = await chrome.scripting.executeScript({
    target: { tabId },
    func: () => {
      const node =
        document.querySelector('article, main, [role="main"]') || document.body;
      const text = (node?.innerText || '')
        .replace(/\s+/g, ' ')
        .trim();
      return text.slice(0, 50000);
    },
  });
  return result?.result || '';
}

async function readCurrentPage(tabId) {
  if (!tabId) throw new Error('Không xác định được tab hiện tại');
  const text = await pageText(tabId);
  if (!text) throw new Error('Trang này không có text đọc được');
  const settings_ = await chrome.storage.local.get(SETTINGS_DEFAULTS);
  await readText(text, settings_.selectionAction);
}

chrome.runtime.onInstalled.addListener(createContextMenu);
chrome.runtime.onStartup.addListener(createContextMenu);

if (chrome.contextMenus) {
  chrome.contextMenus.onClicked.addListener((info, tab) => {
    const text = (info.selectionText || '').trim();
    if (info.menuItemId === MENU_PAGE) {
      readCurrentPage(tab?.id).catch((error) => {
        setBadge('!', `ViFastTts: ${String(error?.message || error)}`);
        notifyPopup(`Lỗi đọc trang: ${String(error?.message || error)}`);
      });
      return;
    }
    if (!text) return;
    if (info.menuItemId === MENU_HIDDEN) {
      speakSelection(text);
      return;
    }
    if (info.menuItemId === MENU_POPUP) {
      openReaderPopup(text).catch(() => {});
      return;
    }
    if (info.menuItemId === MENU_TAB) {
      openReaderTab(text).catch(() => {});
      return;
    }
    if (info.menuItemId === MENU_READ) {
      chrome.storage.local
        .get(SETTINGS_DEFAULTS)
        .then((settings_) => readText(text, settings_.selectionAction))
        .catch(() => {});
    }
  });
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.target !== 'vifasttts-background') return undefined;
  if (message.type === 'ping') {
    sendResponse({ ok: true });
    return true;
  }

  if (message.type === 'synthesize' || message.type === 'stream') {
    const started = performance.now();
    sendToOffscreen({
      type: message.type,
      request: message.request,
    })
      .then(async (response) => {
        if (response?.ok && response.result) {
          const chars = String(message.request?.text || '').length;
          const audioSeconds = Number(response.result.duration_ms || 0) / 1000;
          await recordHistory(
            message.request?.mode || 'local',
            chars,
            performance.now() - started,
            audioSeconds,
          );
        }
        sendResponse(response);
      })
      .catch((error) => sendResponse({ ok: false, error: String(error?.message || error) }));
    return true;
  }

  if (message.type === 'stop-stream') {
    sendToOffscreen({ type: 'stop-stream' })
      .then(() => sendResponse({ ok: true }))
      .catch((error) => sendResponse({ ok: false, error: String(error?.message || error) }));
    return true;
  }

  if (message.type === 'estimate') {
    (async () => {
      const stored = await chrome.storage.local.get({ [HISTORY_KEY]: [] });
      const history = Array.isArray(stored[HISTORY_KEY]) ? stored[HISTORY_KEY] : [];
      await ensureWasm();
      const estimate = await eta_estimate(
        JSON.stringify(history),
        String(message.mode || 'local'),
        Number(message.chars) || 0,
        8,
      );
      sendResponse({ ok: true, result: estimate });
    })().catch((error) => sendResponse({ ok: false, error: String(error?.message || error) }));
    return true;
  }

  if (message.type === 'clear-model-cache') {
    caches
      .delete('vifasttts-models-v1')
      .then(() => chrome.storage.local.remove(['bundleKey', 'bundleName']))
      .then(() => sendResponse({ ok: true }))
      .catch((error) => sendResponse({ ok: false, error: String(error?.message || error) }));
    return true;
  }

  if (message.type === 'reset-local') {
    sendToOffscreen({ type: 'reset-local' })
      .then(() => sendResponse({ ok: true }))
      .catch((error) => sendResponse({ ok: false, error: String(error?.message || error) }));
    return true;
  }

  if (message.type === 'speak-selection') {
    speakSelection(String(message.text || ''))
      .then(() => sendResponse({ ok: true }))
      .catch((error) => sendResponse({ ok: false, error: String(error?.message || error) }));
    return true;
  }

  if (message.type === 'read-text') {
    readText(String(message.text || ''), message.action || 'hidden')
      .then(() => sendResponse({ ok: true }))
      .catch((error) => sendResponse({ ok: false, error: String(error?.message || error) }));
    return true;
  }

  if (message.type === 'speak-started' || message.type === 'speak-ended' || message.type === 'speak-error') {
    if (directTtsId === message.id) {
      if (message.type === 'speak-started') {
        setBadge('▶', 'ViFastTts: đang đọc');
        notifyPopup('Đang phát đoạn bôi đen…');
      } else if (message.type === 'speak-ended') {
        directTtsId = null;
        setBadge('', 'ViFastTts');
        notifyPopup('Đã đọc xong đoạn bôi đen.');
      } else {
        directTtsId = null;
        setBadge('!', `ViFastTts: ${message.error || 'lỗi audio'}`);
        notifyPopup(`Lỗi đọc ẩn: ${message.error || 'không rõ'}`);
      }
    }
    sendResponse({ ok: true });
    return true;
  }

  return undefined;
});

// Đặt sau khi đã đăng ký listener: lỗi menu không được làm mất message handler.
try {
  createContextMenu();
} catch (error) {
  console.warn('ViFastTts contextMenus:', error);
}

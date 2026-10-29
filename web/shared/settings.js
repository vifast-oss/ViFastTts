// Hợp đồng settings dùng chung cho web + extension.
// Giá trị mặc định phản chiếu `vifasttts-app::AppSettings`; storage vẫn native.

export const SETTINGS_KEY = 'vifasttts.web.settings';
export const HISTORY_KEY = 'vifasttts_history_v1';

export const DEFAULT_SETTINGS = {
  mode: 'local',
  serverUrl: 'http://127.0.0.1:8000',
  token: '',
  modelBaseUrl: '',
  bundleKey: '',
  bundleName: '',
  selectionAction: 'hidden',
  dictionary: '',
  stream: false,
  directModels: false,
  speed: 1,
  maxChars: 300,
  fixedPauses: false,
  alpha: 1.5,
  peakNormalize: false,
  dialect: 'north',
  resolveOov: true,
};

function numberInRange(value, fallback, min, max) {
  const number = Number(value);
  if (!Number.isFinite(number)) return fallback;
  return Math.min(max, Math.max(min, number));
}

/// Chuẩn hoá storage cũ/lạ; không ném để UI vẫn mở được khi config hỏng.
export function normalizeSettings(raw = {}) {
  const source = raw && typeof raw === 'object' ? raw : {};
  const text = (value, fallback = '') =>
    typeof value === 'string' ? value.trim() || fallback : fallback;
  return {
    mode: source.mode === 'remote' ? 'remote' : 'local',
    serverUrl: text(source.serverUrl, DEFAULT_SETTINGS.serverUrl).replace(/\/+$/, ''),
    token: typeof source.token === 'string' ? source.token.trim() : '',
    modelBaseUrl: text(source.modelBaseUrl).replace(/\/+$/, ''),
    bundleKey: text(source.bundleKey),
    bundleName: text(source.bundleName),
    selectionAction: ['hidden', 'popup', 'tab'].includes(source.selectionAction)
      ? source.selectionAction
      : DEFAULT_SETTINGS.selectionAction,
    dictionary: typeof source.dictionary === 'string' ? source.dictionary : '',
    stream: Boolean(source.stream),
    directModels: Boolean(source.directModels),
    speed: numberInRange(source.speed, DEFAULT_SETTINGS.speed, 0.5, 2),
    maxChars: Number(source.maxChars ?? source.max_chars) === 0
      ? DEFAULT_SETTINGS.maxChars
      : Math.round(numberInRange(
        source.maxChars ?? source.max_chars,
        DEFAULT_SETTINGS.maxChars,
        50,
        5000,
      )),
    fixedPauses: Boolean(source.fixedPauses ?? source.fixed_pauses),
    alpha: numberInRange(source.alpha, DEFAULT_SETTINGS.alpha, 0.5, 3),
    peakNormalize: Boolean(source.peakNormalize ?? source.peak_normalize),
    dialect: ['north', 'central', 'south'].includes(source.dialect)
      ? source.dialect
      : DEFAULT_SETTINGS.dialect,
    resolveOov: source.resolveOov !== false && source.resolve_oov !== false,
  };
}

/// Shape lịch sử tối thiểu để Rust `EtaEstimator` đọc; UI có thể thêm field.
export function etaSample(mode, chars, elapsedMs) {
  return { mode, chars, elapsed_ms: Math.max(0, Math.round(elapsedMs)) };
}

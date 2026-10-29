// Client dùng chung cho catalog model ViFastTts (web + extension).
// Không phụ thuộc DOM; mọi UI chỉ cần base URL + token.

export function normalizeServerBase(value, fallback = '') {
  const raw = String(value || fallback || '').trim();
  if (!raw) return '';
  return raw.replace(/\/+$/, '');
}

export class ModelApi {
  constructor({ baseUrl = '', token = '', fetchImpl = globalThis.fetch } = {}) {
    this.baseUrl = normalizeServerBase(baseUrl, globalThis.location?.origin || '');
    this.token = String(token || '').trim();
    this.fetch = fetchImpl.bind(globalThis);
  }

  headers() {
    const headers = {};
    if (this.token) headers.authorization = `Bearer ${this.token}`;
    return headers;
  }

  url(path, params = {}) {
    const query = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null && String(value).length) {
        query.set(key, String(value));
      }
    }
    const suffix = query.toString() ? `?${query}` : '';
    return `${this.baseUrl}${path}${suffix}`;
  }

  async json(path, params) {
    const response = await this.fetch(this.url(path, params), {
      headers: this.headers(),
      cache: 'no-store',
    });
    if (!response.ok) {
      const detail = await response.text().catch(() => '');
      throw new Error(`HTTP ${response.status}${detail ? `: ${detail}` : ''}`);
    }
    return response.json();
  }

  search(query = 'vifasttts', limit = 20) {
    return this.json('/api/models/search', { q: query, limit });
  }

  files(repo) {
    return this.json('/api/models/files', { repo });
  }

  async download(repo, path) {
    const response = await this.fetch(this.url('/api/models/download', { repo, path }), {
      headers: this.headers(),
      cache: 'no-store',
    });
    if (!response.ok) {
      const detail = await response.text().catch(() => '');
      throw new Error(`HTTP ${response.status}${detail ? `: ${detail}` : ''}`);
    }
    return {
      blob: await response.blob(),
      filename: String(path).split('/').pop() || 'model.vfa',
    };
  }
}

export function bundleFiles(model) {
  const seen = new Set();
  return (model?.siblings || [])
    .map((file) => file.rfilename || file.path || '')
    .filter((path) => path.endsWith('.vfa') || path.endsWith('.vfts'))
    .filter((path) => {
      const name = path.split('/').pop() || path;
      if (seen.has(name)) return false;
      seen.add(name);
      return true;
    });
}

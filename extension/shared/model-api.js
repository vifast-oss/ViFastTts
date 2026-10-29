// Client dùng chung cho catalog model ViFastTts (web + extension).
// Không phụ thuộc DOM; mọi UI chỉ cần base URL + token.

export function normalizeServerBase(value, fallback = '') {
  const raw = String(value || fallback || '').trim();
  if (!raw) return '';
  return raw.replace(/\/+$/, '');
}

export class ModelApi {
  constructor({ baseUrl = '', token = '', direct = false, fetchImpl = globalThis.fetch } = {}) {
    this.baseUrl = normalizeServerBase(baseUrl, globalThis.location?.origin || '');
    this.token = String(token || '').trim();
    this.direct = Boolean(direct);
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

  async search(query = 'vifasttts', limit = 20) {
    if (this.direct) {
      const url = `https://huggingface.co/api/models?search=${encodeURIComponent(query)}&limit=${limit}&full=true`;
      const response = await this.fetch(url, { cache: 'no-store' });
      if (!response.ok) throw new Error(`HuggingFace HTTP ${response.status}`);
      return response.json();
    }
    return this.json('/api/models/search', { q: query, limit });
  }

  async files(repo) {
    if (this.direct) {
      const response = await this.fetch(
        `https://huggingface.co/api/models/${repo.split('/').map(encodeURIComponent).join('/')}`,
        { cache: 'no-store' },
      );
      if (!response.ok) throw new Error(`HuggingFace HTTP ${response.status}`);
      const model = await response.json();
      return (model.siblings || []).map((file) => ({
        path: file.rfilename || file.path || '',
        size: file.size || 0,
        type: 'file',
      })).filter((file) => file.path.endsWith('.vfa') || file.path.endsWith('.vfts'));
    }
    return this.json('/api/models/files', { repo });
  }

  async download(repo, path) {
    if (this.direct) {
      const encoded = String(path).split('/').map(encodeURIComponent).join('/');
      const url = `https://huggingface.co/${repo.split('/').map(encodeURIComponent).join('/')}/resolve/main/${encoded}`;
      const response = await this.fetch(url, { cache: 'no-store' });
      if (!response.ok) throw new Error(`HuggingFace HTTP ${response.status}`);
      return {
        blob: await response.blob(),
        filename: String(path).split('/').pop() || 'model.vfa',
      };
    }
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

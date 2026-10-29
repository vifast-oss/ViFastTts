// Đọc bundle .vfa/.vfts dùng chung cho extension (và nơi khác cần WASM).
// Không dùng thư viện ZIP ngoài: đọc central directory + DecompressionStream.
// Yêu cầu secure context (extension có); web LAN dùng loader riêng của web.

const EOCD = 0x06054b50;
const CENTRAL = 0x02014b50;
const LOCAL = 0x04034b50;
const MAX_BUNDLE = 512 * 1024 * 1024;

function u16(view, offset) {
  return view.getUint16(offset, true);
}

function u32(view, offset) {
  return view.getUint32(offset, true);
}

function findEocd(bytes) {
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const minimum = Math.max(0, bytes.length - 65_557);
  for (let offset = bytes.length - 22; offset >= minimum; offset -= 1) {
    if (u32(view, offset) === EOCD) return offset;
  }
  throw new Error('Không phải ZIP (thiếu EOCD)');
}

function safeName(name) {
  if (!name || name.startsWith('/') || name.includes('\\')) return false;
  return !name.split('/').some((part) => !part || part === '..');
}

async function inflateRaw(bytes) {
  if (typeof DecompressionStream !== 'function') {
    throw new Error('Trình duyệt không hỗ trợ DecompressionStream');
  }
  const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream('deflate-raw'));
  return new Uint8Array(await new Response(stream).arrayBuffer());
}

export async function readZipEntries(bytes) {
  if (!(bytes instanceof Uint8Array)) bytes = new Uint8Array(bytes);
  if (!bytes.length || bytes.length > MAX_BUNDLE) {
    throw new Error('Bundle rỗng hoặc quá lớn');
  }
  const eocd = findEocd(bytes);
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const count = u16(view, eocd + 10);
  const centralSize = u32(view, eocd + 12);
  const centralOffset = u32(view, eocd + 16);
  if (count === 0xffff || centralOffset === 0xffffffff) {
    throw new Error('ZIP64 chưa hỗ trợ cho bundle này');
  }
  if (centralOffset + centralSize > bytes.length) throw new Error('Central directory hỏng');

  const entries = new Map();
  let total = 0;
  let offset = centralOffset;
  for (let index = 0; index < count; index += 1) {
    if (u32(view, offset) !== CENTRAL) throw new Error('Central entry hỏng');
    const flags = u16(view, offset + 8);
    const method = u16(view, offset + 10);
    const compressedSize = u32(view, offset + 20);
    const uncompressedSize = u32(view, offset + 24);
    const nameLength = u16(view, offset + 28);
    const extraLength = u16(view, offset + 30);
    const commentLength = u16(view, offset + 32);
    const localOffset = u32(view, offset + 42);
    const name = new TextDecoder().decode(
      bytes.subarray(offset + 46, offset + 46 + nameLength),
    );
    offset += 46 + nameLength + extraLength + commentLength;
    if (!safeName(name)) throw new Error(`Entry không an toàn: ${name}`);
    if (name.endsWith('/')) continue;
    if (flags & 0x1) throw new Error(`Entry mã hoá không hỗ trợ: ${name}`);
    if (u32(view, localOffset) !== LOCAL) throw new Error(`Local header hỏng: ${name}`);
    const localName = u16(view, localOffset + 26);
    const localExtra = u16(view, localOffset + 28);
    const start = localOffset + 30 + localName + localExtra;
    total += uncompressedSize;
    if (total > MAX_BUNDLE) throw new Error('Bundle giải nén quá lớn');
    if (start + compressedSize > bytes.length) throw new Error(`Entry vượt file: ${name}`);
    const compressed = bytes.subarray(start, start + compressedSize);
    let data;
    if (method === 0) data = new Uint8Array(compressed);
    else if (method === 8) data = await inflateRaw(compressed);
    else throw new Error(`Nén không hỗ trợ (${method}): ${name}`);
    if (data.length !== uncompressedSize) {
      throw new Error(`Sai kích thước giải nén: ${name}`);
    }
    entries.set(name, data);
  }
  return entries;
}

export async function sha256Hex(bytes) {
  if (!globalThis.crypto?.subtle) {
    throw new Error('Thiếu crypto.subtle để kiểm SHA256');
  }
  const digest = await crypto.subtle.digest('SHA-256', bytes);
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, '0')).join('');
}

async function verify(name, bytes, expected) {
  if (!expected) return;
  const actual = await sha256Hex(bytes);
  if (actual.toLowerCase() !== String(expected).toLowerCase()) {
    throw new Error(`SHA256 ${name} không khớp`);
  }
}

/**
 * Trả `{manifest, acoustic, vocoder, entries}` đã kiểm hash.
 * `fallbackVocoder` dùng cho `.vfa` (vocoder dùng chung).
 */
export async function parseBundle(bytes, { fallbackVocoder = null } = {}) {
  const entries = await readZipEntries(bytes);
  const manifestBytes = entries.get('manifest.json');
  if (!manifestBytes) throw new Error('Bundle thiếu manifest.json');
  let manifest;
  try {
    manifest = JSON.parse(new TextDecoder().decode(manifestBytes));
  } catch (error) {
    throw new Error(`manifest.json hỏng: ${error.message || error}`);
  }
  if (!String(manifest.format || '').startsWith('vifasttts-')) {
    throw new Error(`format không phải ViFastTts: ${manifest.format || '?'}`);
  }
  const acousticName = manifest.acoustic?.file || 'acoustic.onnx';
  const acoustic = entries.get(acousticName);
  if (!acoustic) throw new Error(`Bundle thiếu ${acousticName}`);
  await verify('acoustic', acoustic, manifest.acoustic?.sha256);

  let vocoder = null;
  if (manifest.vocoder?.file) {
    vocoder = entries.get(manifest.vocoder.file) || null;
    if (!vocoder) throw new Error(`Bundle thiếu ${manifest.vocoder.file}`);
  } else if (fallbackVocoder) {
    vocoder = fallbackVocoder instanceof Uint8Array ? fallbackVocoder : new Uint8Array(fallbackVocoder);
  }
  if (!vocoder) throw new Error('Bundle thiếu vocoder (cần vocoder dùng chung cho .vfa)');
  await verify('vocoder', vocoder, manifest.vocoder?.sha256);
  return { manifest, acoustic, vocoder, entries };
}

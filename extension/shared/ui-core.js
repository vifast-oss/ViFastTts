// Helper DOM/audio dùng chung cho web + extension.
// Không biết storage/server; UI chỉ truyền container/audio/document.

export function renderKaraoke(container, document_) {
  container.textContent = '';
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
    container.appendChild(lineEl);
  }
}

export function appendKaraokeUnits(container, units) {
  if (!Array.isArray(units)) return;
  for (const unit of units) {
    const span = document.createElement('span');
    span.textContent = `${unit.text}${unit.punctuation || ''} `;
    span.dataset.start = unit.start_ms;
    span.dataset.end = unit.end_ms;
    container.appendChild(span);
  }
}

export function updateKaraokeHighlight(container, milliseconds) {
  for (const span of container.querySelectorAll('span')) {
    const start = Number(span.dataset.start);
    const end = Number(span.dataset.end);
    span.classList.toggle('active', milliseconds >= start && milliseconds < end);
  }
}

export function base64ToBytes(base64) {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes;
}

export function downloadText(text, filename, mime) {
  if (!text) return;
  const url = URL.createObjectURL(new Blob([text], { type: mime }));
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

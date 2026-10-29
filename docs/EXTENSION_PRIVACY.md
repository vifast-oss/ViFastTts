# Privacy Policy — ViFastTts Local

**Last updated:** 29/10/2026

ViFastTts Local is a Chrome/Edge extension for reading Vietnamese text aloud.
This policy covers the browser extension, not the separate desktop/mobile apps.

## What the extension does

- Reads text you type into the extension popup.
- Reads text from the current page only when you explicitly choose **Đọc trang**
  or use a ViFastTts context-menu action.
- Synthesizes speech locally with bundled WASM + ONNX models.
- Optionally sends text to a TTS server **only when you select Remote mode** and
  configure that server URL.
- Optionally queries HuggingFace (`huggingface.co`) for model search/download when
  you enable **HuggingFace trực tiếp**. Text being read is not sent for this.

## Data the extension handles

| Data | Where it is handled | Purpose |
|---|---|---|
| Text you type | Browser extension, local memory | Text-to-speech |
| Current page text | Browser extension, local memory | Only after you click a read-page/context-menu action |
| Settings (mode, speed, server URL, dictionary) | `chrome.storage.local` on your device | Remember your preferences |
| Short synthesis history (mode, character count, duration) | `chrome.storage.local` on your device | Estimate processing time |
| Model files / cached voice bundles | Cache Storage on your device | Offline/local synthesis |
| Bearer token, if you enter one | `chrome.storage.local` on your device | Authenticate to your configured server |

The extension does **not** include analytics, advertising, telemetry, or a
developer-operated collection endpoint. The developer does not receive your
text, page content, token, or usage history from Local mode.

If you enable **Remote** mode, text and the optional token are sent to the server
URL you enter. That server may be operated by you or a third party; its privacy
and retention practices are outside this extension's control. The public demo
server documents that it does not store request text or audio; check the server
you configure.

## Permissions and why they are needed

- `offscreen` — run the bundled WASM/ONNX engine and audio rendering outside the
  service worker.
- `storage`, `unlimitedStorage` — save settings, history, and model cache.
- `contextMenus` — add the right-click “read selection/page” actions.
- `activeTab`, `scripting` — read page text only after an explicit user action.
- Host permissions for localhost — optional local TTS server.
- Host permissions for `huggingface.co` and `*.hf.co` — optional direct model
  search/download when the user enables that checkbox.
- Optional host permissions for other HTTP/HTTPS origins — a server that the user
  explicitly configures. These are requested at runtime, not silently granted.

## Data sharing and sale

The extension does not sell data, does not use data for advertising, and does not
share data with the developer. Remote-mode data is sent only to the server URL
selected by the user.

## Retention and deletion

Local settings, history, and model cache remain on your device until you clear
them in the extension or remove the extension. Use **Xoá cache model** /
**Xoá lịch sử** in the extension, or clear the extension's storage from the
browser. A remote server's retention is controlled by that server.

## Children

The extension is not directed at children and does not knowingly collect
personal information from children.

## Changes

Material changes will be reflected in this document and in the extension
release notes.

## Contact

Open an issue at <https://github.com/dvchd/ViFastTts/issues> or use the feedback
form at <https://vifasttts.hoctuthien.com/>. Do not include private text or
tokens in a public issue.

## Model and dataset license

The bundled sample voice is for research/non-commercial use; see
`https://github.com/dvchd/ViFastTts/blob/main/docs/NGOC_HUYEN.md`.

# nl-file-search

Natural-language search over local files. Phase 1 indexes markdown, plain text, images, videos, and PDFs with **Gemini Embedding 2**, stores vectors in SQLite (`sqlite-vec`), and exposes search through a CLI and a Cursor MCP server.

A later Python app can import the same `nl_file_search.search` module. Office documents are Phase 2; music is Phase 3. See [background/ROADMAP.md](background/ROADMAP.md).

## Phase 1 file types

| Type | Extensions | How it is indexed |
| --- | --- | --- |
| Text | `.md`, `.txt` | Heading/paragraph chunks |
| Images | `.png`, `.jpg`, `.jpeg`; `.webp`, `.bmp`, `.gif` converted to JPEG | Sent to Gemini as image bytes |
| Video | `.mp4`, `.mov` | Split into 120s clips with ffmpeg |
| PDF | `.pdf` | One page per embedding |

Unknown extensions are skipped. HEIC is skipped. Secret-like names (`.env`, `*.pem`, `credentials.json`, SSH keys) are never read or sent to Gemini.

## Requirements

- Windows, Python 3.12+
- A Gemini API key (`GEMINI_API_KEY`)
- [ffmpeg](https://ffmpeg.org/) on `PATH` when you index videos (`winget install Gyan.FFmpeg`)
- Network access for every ingest and every search (queries are embedded with the same model)

## Setup

```powershell
cd C:\source\repos\nl-file-search
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e .
```

Create the data directory and files **outside the repo**:

```
%USERPROFILE%\nl-file-search\
  config.yaml
  .env
  index.sqlite
  logs\
```

`nl-search` creates that folder and a starter `config.yaml` / empty `.env` on first run. Then:

1. Put your key in `%USERPROFILE%\nl-file-search\.env` as `GEMINI_API_KEY=...` (never commit this file).
2. Edit `%USERPROFILE%\nl-file-search\config.yaml` and add the folders to index.

If a key was ever pasted into a chat or ticket, revoke it in Google AI Studio and issue a new one.

Example `config.yaml` (also in [config.example.yaml](config.example.yaml)):

```yaml
sources:
  - path: "D:\\Notes"
  - path: "C:\\Users\\you\\Pictures"
exclude:
  - "**/.git/**"
  - "**/node_modules/**"
embed:
  model: gemini-embedding-2
  dimensions: 768
video:
  max_seconds: 120
```

## CLI

```powershell
nl-search ingest
nl-search ingest --path C:\foo
nl-search search "vintage red truck in the rain"
nl-search status
```

## Cursor MCP

1. Copy [`.cursor/mcp.json.example`](.cursor/mcp.json.example) to `.cursor/mcp.json` (or your user MCP config).
2. Point `command` at this repo’s `.venv\Scripts\python.exe`.
3. Restart Cursor MCP.

Tools:

- `search_files` — natural-language search; use this first when asking about indexed local files
- `get_file` — indexed text or media metadata for a path already in the index (not an arbitrary disk read)

## Security

- The API key lives only in `%USERPROFILE%\nl-file-search\.env`.
- Ingest skips credential-like files and default junk directories (`.git`, `node_modules`, `.venv`, `__pycache__`).
- `get_file` only returns rows already in the index. It will not open `..\..\.env` or other paths that were never ingested.
- Retrieved snippets go to Cursor the same way an open file would. Do not index folders that must never leave the machine.

## Phase 2 and 3 (not built yet)

- **Phase 2:** modern Office (`.docx`, `.xlsx`, `.pptx`)
- **Phase 3:** music (`.mp3`, `.m4a`, `.flac`)

Out of scope: Google Docs, Drive export, LibreOffice, legacy `.doc` / `.xls` / `.ppt`.

# nl-file-search

Natural-language search over local files. Phase 1 indexes markdown, plain text, images, videos, and PDFs with **Gemini Embedding 2**, stores vectors in SQLite (`sqlite-vec`), and exposes search through a CLI and a Cursor MCP server.

**Work in progress.** Designed by Gary Lucero. Coded by Cursor.

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

- Windows, macOS, or Linux
- Python 3.12+
- A Gemini API key (`GEMINI_API_KEY`)
- [ffmpeg](https://ffmpeg.org/) on `PATH` when you index videos (Windows: `winget install Gyan.FFmpeg`; macOS: `brew install ffmpeg`; Linux: your package manager)
- Network access for every ingest and every search (queries are embedded with the same model)

SQLite is not Windows-only. The same code uses `Path.home() / "nl-file-search"` on every OS.

## Setup

Windows (PowerShell):

```powershell
cd C:\source\repos\nl-file-search
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e .
```

macOS / Linux:

```bash
cd ~/src/nl-file-search
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e .
```

Data lives **outside the repo**, in your home directory:

| | Path |
| --- | --- |
| Data folder | `~/nl-file-search/` (Windows: `%USERPROFILE%\nl-file-search\`) |
| SQLite index | `~/nl-file-search/index.sqlite` |

```
~/nl-file-search/
  config.yaml
  .env
  index.sqlite          # vector + metadata database (created on first ingest)
  logs/
```

`nl-search` creates that folder and a starter `config.yaml` / empty `.env` on first run. The `.sqlite` file is created on the first successful `nl-search ingest`. It is gitignored and should never be committed. Then:

1. Put your key in `~/nl-file-search/.env` as `GEMINI_API_KEY=...` (never commit this file).
2. Edit `~/nl-file-search/config.yaml` and add the folders to index.

If a key was ever pasted into a chat or ticket, revoke it in Google AI Studio and issue a new one.

Example `config.yaml` (also in [config.example.yaml](config.example.yaml)):

```yaml
sources:
  - path: "D:\\Notes"              # Windows
  - path: "/Users/you/Pictures"    # macOS / Linux
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

```bash
nl-search ingest
nl-search ingest --path /path/to/folder
nl-search search "vintage red truck in the rain"
nl-search status
```

## Cursor MCP

Add a server in Cursor’s MCP settings (user or project). Point `command` at this repo’s venv Python:

```json
{
  "mcpServers": {
    "nl-file-search": {
      "command": "/absolute/path/to/nl-file-search/.venv/bin/python",
      "args": ["-m", "nl_file_search.mcp_server"]
    }
  }
}
```

On Windows, use `.venv\\Scripts\\python.exe` instead of `.venv/bin/python`. Restart Cursor MCP after saving. Do not put `GEMINI_API_KEY` in that config; the server reads `~/nl-file-search/.env`.

Tools:

- `search_files` — natural-language search; use this first when asking about indexed local files
- `get_file` — indexed text or media metadata for a path already in the index (not an arbitrary disk read)

## Security

- The API key lives only in `~/nl-file-search/.env`.
- The SQLite database lives only in `~/nl-file-search/index.sqlite`.
- Ingest skips credential-like files and default junk directories (`.git`, `node_modules`, `.venv`, `__pycache__`).
- `get_file` only returns rows already in the index. It will not open `..\..\.env` or other paths that were never ingested.
- Retrieved snippets go to Cursor the same way an open file would. Do not index folders that must never leave the machine.

## Phase 2 and 3 (not built yet)

- **Phase 2:** modern Office (`.docx`, `.xlsx`, `.pptx`)
- **Phase 3:** music (`.mp3`, `.m4a`, `.flac`)

Out of scope: Google Docs, Drive export, LibreOffice, legacy `.doc` / `.xls` / `.ppt`.

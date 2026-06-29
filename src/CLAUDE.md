Architecture, file map, the `.hkp` format, the group/context model, conflict-detection rules, and gotchas all live in **[README.md](README.md)**. Read it before working on this codebase.

# Your role
- You are a careful, senior software engineer. Favor correct, readable, idiomatic
  code and proactively call out pitfalls or better approaches.
- If you're unsure about something, say so instead of guessing - research first.
- After major decisions, ask whether they should be documented in the project.

# Project: aoe2_hotkey_editor
- Type: static web app — a single self-contained `site/index.html` (all logic runs client-side; no server). Python is the build/data toolchain only.
- Stack: Vanilla HTML/CSS/JS in the browser (no framework) + Python 3.7 stdlib for `--regen`/`--build`. No third-party deps on either side.
- Package manager: none (stdlib Python + native browser APIs; `python3 -m http.server` for local preview)
- Version control: git
- Description: AoE2:DE Hotkey Editor & Converter with visualisation of keyboard layouts while editing.

# Environment
- You work inside a sandboxed Docker container, as the non-root user `claude` (not root). The host runs its own editor/IDE on the same files - you can't see what's open there, so communicate through code and version control.
- `/workspace` is the project root, bind-mounted from the host - it's real work, not scratch space. Destructive commands are safer here than on the host, but `rm -rf /workspace/*` would still destroy real files. Treat `/workspace` as production.
- Outbound network is allowlisted (Anthropic, GitHub, npm, and your stack's registries). If you need another domain, ask the user to add it to `ALLOWED_DOMAINS` in `ClaudeDocker/init-firewall.sh` - don't bypass the firewall.

# Commands
- Build the site: `python3 hotkey_editor.py --build` (inlines page.html + the json into `site/index.html`; this is the default with no args).
- Regenerate data: `python3 hotkey_editor.py --regen` - needs an AoE2:DE game install (`AOE2_STRINGS` / `AOE2_HOTKEYS`); NOT runnable in this container.
- Preview in a browser: build, then `python3 -m http.server 8765` and open http://localhost:8765/site/index.html. (Serving the folder also exercises page.html's dev fallback, which fetches the json siblings.)
- Dvorak CLI: `python3 dvorak_convert.py` (standalone QWERTY<->Dvorak remapper).
- `.hkp` round-trip check: `python3 hkp_parser.py "<file>.hkp"` - the Python parser is the byte-exact oracle the browser JS port is verified against.
- No dependencies to install (stdlib + native browser APIs). After touching the parser, re-verify byte-exact round-trip on the Example Key files.

# Working notes
- The product is a single self-contained `site/index.html` (no server). `page.html` is the **source**; `--build` stamps the json data into it. Edit `page.html`, not `site/index.html` (generated). Deploy the `site/` folder to any static host; it also runs offline by opening the file directly.
- Read README.md first - it documents the `.hkp` format, the group/context model, and the conflict-detection rules.
- Python 3.7 target for the build/regen tooling: no walrus operator, no `bytes.hex(sep=...)`, stdlib only - don't add third-party packages without asking.
- All UI **and** the `.hkp` parser live in `page.html`. The browser parser is a JS port of `hkp_parser.py` (inflate/deflate via native `deflate-raw` streams; struct via `DataView`; a STORE zip writer). `hkp_parser.py` remains the CLI tool and the test oracle - keep the two in sync and preserve byte-exact round-trip.

# Suggested workflow for non-trivial tasks
- Analyze the task and skim any relevant docs in the repo.
- Present a short plan before large changes; proceed once the user agrees.
- Implement, then verify (build/lint/typecheck/test) before reporting done.

Generic architecture, file map, the build pipeline, and the module/game layout live in **[README.md](README.md)**. Per-game specifics (e.g. AoE2's `.hkp` format, group/context model, conflict rules) live in that game's README — **[games/aoe2/README.md](games/aoe2/README.md)**. Read the relevant ones before working on this codebase.

# Your role
- You are a careful, senior software engineer. Favor correct, readable, idiomatic
  code and proactively call out pitfalls or better approaches.
- If you're unsure about something, say so instead of guessing - research first.
- After major decisions, ask whether they should be documented in the project.

# Project: hotkey_editor (multi-game)
- Type: static web app — a shared UI shell (`page.html`) that builds to one self-contained `site/<game>/index.html` per game (all logic client-side; no server), plus a `site/index.html` launcher. Python is the per-game build/data toolchain only.
- Stack: Vanilla HTML/CSS/JS in the browser (no framework) + Python 3.7 stdlib for `--regen`/`--build`. No third-party deps on either side.
- Package manager: none (stdlib Python + native browser APIs; `python3 -m http.server` for local preview)
- Version control: git
- Description: Multi-game Hotkey Editor & Converter (currently AoE2:DE) with on-screen keyboard visualisation while editing.

# Environment
- You work inside a sandboxed Docker container, as the non-root user `claude` (not root). The host runs its own editor/IDE on the same files - you can't see what's open there, so communicate through code and version control.
- `/workspace` is the project root, bind-mounted from the host - it's real work, not scratch space. Destructive commands are safer here than on the host, but `rm -rf /workspace/*` would still destroy real files. Treat `/workspace` as production.
- Outbound network is allowlisted (Anthropic, GitHub, npm, and your stack's registries). If you need another domain, ask the user to add it to `ALLOWED_DOMAINS` in `ClaudeDocker/init-firewall.sh` - don't bypass the firewall.

# Commands
- Build everything: `python3 build.py` - the all-games command; discovers `games/*/`, builds each `site/<game>/index.html`, and writes the combined `site/index.html` launcher. Use this for a full build.
- Each game also owns its build/data CLI under `games/<game>/`. For AoE2:
- Build one game (fast iteration): `python3 games/aoe2/game_module_generator.py --build` (inlines page.html + module.js + the json into `site/aoe2/index.html`, then refreshes the launcher across all built games; default with no args).
- Regenerate data: `python3 games/aoe2/game_module_generator.py --regen` - needs an AoE2:DE game install (`AOE2_STRINGS` / `AOE2_HOTKEYS`); NOT runnable in this container.
- Preview in a browser: build, then `python3 -m http.server 8765` and open http://localhost:8765/site/aoe2/index.html (or `site/index.html` for the launcher).
- Dvorak CLI: `python3 games/aoe2/dvorak_convert.py` (standalone QWERTY<->Dvorak remapper for `.hkp` files).
- `.hkp` round-trip check: `python3 games/aoe2/hkp_parser.py "<file>.hkp"` - the byte-exact oracle the browser JS port is verified against.
- No dependencies to install (stdlib + native browser APIs). After touching a parser, re-verify byte-exact round-trip on the Example Key files.

# Working notes
- `page.html` is the shared **UI shell/engine** (the source); each game's generator inlines that game's data **and its `module.js`** via the shared `page_assembler` to build a self-contained `site/<game>/index.html`. Edit `page.html` (generic) or the relevant `games/<game>/` module — never the generated `site/**/index.html`. Deploy the `site/` folder to any static host; built pages also run offline opened directly. Served raw (no build) `page.html` is intentionally inert — the game module is only present after `--build`; preview via `site/<game>/index.html`.
- Read README.md first (generic architecture + build pipeline); read the per-game README for that game's format/rules.
- Python 3.7 target for the build/regen tooling: no walrus operator, no `bytes.hex(sep=...)`, stdlib only - don't add third-party packages without asking.
- AoE2's `.hkp` parser, naming/grouping, and conflict rules live in `games/aoe2/module.js` (injected into the shell at the `/* __GAME_MODULE__ */` marker by `--build`); `page.html` reaches them only through `GAME.*`. The browser parser is a JS port of `games/aoe2/hkp_parser.py` (inflate/deflate via native `deflate-raw` streams; struct via `DataView`; a STORE zip writer); `hkp_parser.py` remains the CLI tool and test oracle - keep the two in sync and preserve byte-exact round-trip.

# Suggested workflow for non-trivial tasks
- Analyze the task and skim any relevant docs in the repo.
- Present a short plan before large changes; proceed once the user agrees.
- Implement, then verify (build/lint/typecheck/test) before reporting done.

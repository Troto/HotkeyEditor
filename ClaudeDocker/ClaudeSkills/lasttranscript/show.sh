#!/bin/bash
# Find the most recently modified transcript file for the current project
PROJECTS_DIR="$HOME/.claude/projects"
LIMIT="${1:-}"

# Determine project key from cwd (Claude maps cwd to a project folder)
# The folder name is the cwd with / replaced by - and leading /
CWD_KEY=$(pwd | sed 's|^/||' | tr '/' '-')
PROJECT_DIR="$PROJECTS_DIR/-$CWD_KEY"

# Fallback: use whichever project dir has the most recent .jsonl
if [ ! -d "$PROJECT_DIR" ]; then
    PROJECT_DIR=$(find "$PROJECTS_DIR" -maxdepth 1 -mindepth 1 -type d \
        -exec sh -c 'ls -t "$1"/*.jsonl 2>/dev/null | head -1' _ {} \; \
        -print | head -2 | tail -1)
fi

if [ ! -d "$PROJECT_DIR" ]; then
    echo "No project transcript directory found."
    exit 1
fi

# Get the second most recently modified top-level .jsonl (skip current session)
TRANSCRIPT=$(find "$PROJECT_DIR" -maxdepth 1 -name "*.jsonl" -type f \
    -printf "%T@ %p\n" 2>/dev/null | sort -rn | sed -n '2p' | cut -d' ' -f2-)

if [ -z "$TRANSCRIPT" ]; then
    echo "No transcript files found in: $PROJECT_DIR"
    exit 1
fi

echo "Transcript: $(basename "$TRANSCRIPT")"
echo "---"

python3 - "$TRANSCRIPT" "$LIMIT" <<'PYEOF'
import sys, json

path = sys.argv[1]
limit = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2] else 0

def extract_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                btype = block.get("type", "")
                if btype == "text":
                    parts.append(block.get("text", ""))
                elif btype == "thinking":
                    parts.append(f"[thinking omitted]")
                elif btype == "tool_use":
                    name = block.get("name", "tool")
                    inp = block.get("input", {})
                    # Show brief summary of tool call
                    summary = json.dumps(inp, ensure_ascii=False)
                    if len(summary) > 200:
                        summary = summary[:200] + "..."
                    parts.append(f"[Tool: {name}({summary})]")
                elif btype == "tool_result":
                    content_val = block.get("content", "")
                    result_text = extract_text(content_val)
                    if len(result_text) > 300:
                        result_text = result_text[:300] + "..."
                    parts.append(f"[Tool result: {result_text}]")
        return "\n".join(p for p in parts if p)
    return str(content)

messages = []
with open(path, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        msg_type = obj.get("type", "")
        if msg_type not in ("user", "assistant"):
            continue
        msg = obj.get("message", {})
        role = msg.get("role", msg_type)
        content = msg.get("content", "")
        ts = obj.get("timestamp", "")[:19].replace("T", " ")
        text = extract_text(content).strip()
        if text:
            messages.append((ts, role, text))

if limit > 0:
    messages = messages[-limit:]

for ts, role, text in messages:
    label = "USER" if role == "user" else "ASSISTANT"
    print(f"\n[{ts}] {label}")
    print("-" * 60)
    # Wrap long lines at 100 chars
    for line in text.split("\n"):
        while len(line) > 100:
            print(line[:100])
            line = line[100:]
        print(line)

print(f"\n--- {len(messages)} messages ---")
PYEOF

#!/bin/bash
PLANS_DIR="$HOME/.claude/plans"

if [ -z "$1" ]; then
    files=("$PLANS_DIR"/*.md)
    if [ ! -f "${files[0]}" ]; then
        echo "No plans found in $PLANS_DIR"
        exit 0
    fi
    echo "Saved plans:"
    i=1
    for f in "$PLANS_DIR"/*.md; do
        echo "  $i. $(basename "$f" .md)"
        ((i++))
    done
else
    name="${1%.md}"
    file="$PLANS_DIR/$name.md"
    if [ -f "$file" ]; then
        cat "$file"
    else
        echo "Plan not found: $name"
        echo ""
        echo "Available plans:"
        for f in "$PLANS_DIR"/*.md; do
            echo "  - $(basename "$f" .md)"
        done
        exit 1
    fi
fi

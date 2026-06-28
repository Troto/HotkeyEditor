# =============================================================================
# Generic Claude Code sandbox
# =============================================================================
# Framework-agnostic by default: a plain Debian base with the Claude Code CLI.
# Node.js is installed ONLY because Claude Code is an npm-distributed CLI that
# runs inside this container — it is not an assumption about your project.
#
# To target a real stack, either:
#   (a) swap the base image below for your stack's official image, or
#   (b) install your toolchain in the "ADD YOUR TOOLCHAIN HERE" section.
# Then allowlist any package registries it uses in init-firewall.sh.
# See "Customizing for your framework" in the repo-root README.md.
# =============================================================================

# Neutral base — NOT tied to any app framework. Swap when you pick a stack, e.g.:
#   FROM python:3.12-bookworm                 # Python (Debian-based)
#   FROM mcr.microsoft.com/dotnet/sdk:8.0     # .NET     (Debian-based)
#   FROM golang:1.22-bookworm                 # Go
#   FROM node:22-bookworm                     # JS/TS (then delete the Node block)
# The Node-for-Claude block below works on any Debian/Ubuntu-derived base.
FROM debian:bookworm-slim

ARG NODE_MAJOR=22
ARG USERNAME=claude
ARG USER_UID=1000
ARG USER_GID=$USER_UID

# --- System dependencies -----------------------------------------------------
# firewall tooling : iptables ipset iproute2 dnsutils aggregate
# general dev      : git curl less jq sudo ca-certificates gnupg
RUN apt-get update && apt-get install -y --no-install-recommends \
      git curl less jq sudo ca-certificates gnupg \
      iptables ipset iproute2 dnsutils aggregate \
    && rm -rf /var/lib/apt/lists/*

# --- Node.js (runtime for the Claude Code CLI — not your app) -----------------
# Required even if your project isn't JavaScript. If you switch the base image
# to one that already bundles Node (e.g. node:*), delete this block.
RUN curl -fsSL "https://deb.nodesource.com/setup_${NODE_MAJOR}.x" | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# --- Claude Code CLI ---------------------------------------------------------
RUN npm install -g @anthropic-ai/claude-code

# =============================================================================
# Toolchain for your chosen stack.
# Run ./setup.sh to populate the managed block below (or edit it by hand).
# Reminder: also add the stack's package registries to ALLOWED_DOMAINS in
# init-firewall.sh, or installs will fail behind the firewall.
# =============================================================================
# >>> setup.sh: toolchain (managed) >>>
# Python 3 toolchain (Debian bookworm ships Python 3.11). The app is stdlib-only
# (http.server), so nothing is pip-installed; pip + venv are included only for
# optional dev tooling (e.g. pytest / ruff) should you add it later.
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-pip python3-venv \
    && rm -rf /var/lib/apt/lists/*
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
# <<< setup.sh: toolchain (managed) <<<

# --- Non-root user -----------------------------------------------------------
# Claude Code requires a non-root user for --dangerously-skip-permissions.
# Some base images (node:*) ship a user at UID 1000 already; drop it so we can
# claim UID 1000 for 'claude'. Harmless on bases that have no such user.
RUN userdel -r node 2>/dev/null || true; groupdel node 2>/dev/null || true

# The ONLY thing claude may run as root is the firewall script (see sudoers line).
RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m -s /bin/bash $USERNAME \
    && echo "$USERNAME ALL=(root) NOPASSWD: /usr/local/bin/init-firewall.sh" > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME

COPY init-firewall.sh /usr/local/bin/init-firewall.sh
RUN chmod +x /usr/local/bin/init-firewall.sh

# Bundled slash-command skills (lasttranscript, savedplans). Installed into the
# claude-config volume on its first creation. To add/edit skills later, drop
# folders in ClaudeSkills/ and recreate the claude-config volume, or copy them
# into ~/.claude/skills inside a running container.
COPY --chown=claude:claude ClaudeSkills/ /home/claude/.claude/skills/

# Pre-create /workspace (and the node_modules mount point) owned by claude so an
# optional named volume mounted there initializes with the right ownership.
RUN mkdir -p /workspace/node_modules && chown -R $USERNAME:$USERNAME /workspace

USER $USERNAME
WORKDIR /workspace

# Persist bash history across rebuilds (paired with the named volume in compose).
RUN echo 'export HISTFILE=/home/claude/.history/.bash_history' >> ~/.bashrc \
    && mkdir -p /home/claude/.history /home/claude/.claude

CMD ["bash"]

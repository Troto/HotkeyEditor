#!/bin/bash
set -euo pipefail  # Exit on error, undefined vars, and pipeline failures
IFS=$'\n\t'       # Stricter word splitting

# =============================================================================
# Outbound allowlist. Everything not listed here (or in GitHub's published IP
# ranges, fetched automatically) is rejected. Add the package registries / APIs
# YOUR project needs, then rebuild: docker compose build --no-cache
# (or just re-run the container — the script runs at every startup).
#
# Don't add github.com / *.githubusercontent.com here: GitHub's ranges are
# pulled from https://api.github.com/meta below.
# =============================================================================
ALLOWED_DOMAINS=(
    # --- Claude Code essentials — do not remove ---
    "api.anthropic.com"
    "statsig.anthropic.com"
    "statsig.com"
    "sentry.io"

    # --- JavaScript / web tooling (used by npm/pnpm/yarn, and Claude updates) ---
    "registry.npmjs.org"
    "registry.yarnpkg.com"

    # --- Rider / JetBrains Dev Container flow (uncomment if you use it) ---
    # The IDE pulls its backend + plugins into the container.
    "download.jetbrains.com"
    "plugins.jetbrains.com"
    "cache-redirector.jetbrains.com"
    "data.services.jetbrains.com"

    # --- Stack registries (managed by setup.sh; add more by hand if needed) ---
    # Examples: "pypi.org" "files.pythonhosted.org" (Python) · "api.nuget.org" (.NET)
    #           "storage.googleapis.com" "pub.dev" (Flutter) · "deb.debian.org" (apt)
    # >>> setup.sh: stack domains (managed) >>>
    "pypi.org"
    "files.pythonhosted.org"
    # <<< setup.sh: stack domains (managed) <<<
)

# 1. Extract Docker DNS info BEFORE any flushing
DOCKER_DNS_RULES=$(iptables-save -t nat | grep "127\.0\.0\.11" || true)

# Flush existing rules and delete existing ipsets
iptables -F
iptables -X
iptables -t nat -F
iptables -t nat -X
iptables -t mangle -F
iptables -t mangle -X
ipset destroy allowed-domains 2>/dev/null || true

# Reset default policies to ACCEPT so this script is safely re-runnable. A
# previous run leaves OUTPUT at DROP, and `iptables -F` above clears rules but
# NOT policies — so without this, the GitHub/DNS fetches below would be blocked
# before the allowlist is rebuilt, failing the script with exit 1.
iptables -P INPUT ACCEPT
iptables -P OUTPUT ACCEPT
iptables -P FORWARD ACCEPT

# 2. Selectively restore ONLY internal Docker DNS resolution
if [ -n "$DOCKER_DNS_RULES" ]; then
    echo "Restoring Docker DNS rules..."
    iptables -t nat -N DOCKER_OUTPUT 2>/dev/null || true
    iptables -t nat -N DOCKER_POSTROUTING 2>/dev/null || true
    echo "$DOCKER_DNS_RULES" | xargs -L 1 iptables -t nat
else
    echo "No Docker DNS rules to restore"
fi

# First allow DNS and localhost before any restrictions
# Allow outbound DNS
iptables -A OUTPUT -p udp --dport 53 -j ACCEPT
# Allow inbound DNS responses
iptables -A INPUT -p udp --sport 53 -j ACCEPT
# Allow localhost
iptables -A INPUT -i lo -j ACCEPT
iptables -A OUTPUT -o lo -j ACCEPT

# Create ipset with CIDR support
ipset create allowed-domains hash:net

# Fetch GitHub meta information and aggregate + add their IP ranges
echo "Fetching GitHub IP ranges..."
gh_ranges=$(curl -s https://api.github.com/meta)
if [ -z "$gh_ranges" ]; then
    echo "ERROR: Failed to fetch GitHub IP ranges"
    exit 1
fi

if ! echo "$gh_ranges" | jq -e '.web and .api and .git' >/dev/null; then
    echo "ERROR: GitHub API response missing required fields"
    exit 1
fi

echo "Processing GitHub IPs..."
while read -r cidr; do
    if [[ ! "$cidr" =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}/[0-9]{1,2}$ ]]; then
        echo "ERROR: Invalid CIDR range from GitHub meta: $cidr"
        exit 1
    fi
    echo "Adding GitHub range $cidr"
    ipset -exist add allowed-domains "$cidr"
done < <(echo "$gh_ranges" | jq -r '(.web + .api + .git)[]' | aggregate -q)

# Resolve and add each allowlisted domain
for domain in "${ALLOWED_DOMAINS[@]}"; do
    echo "Resolving $domain..."
    ips=$(dig +noall +answer A "$domain" | awk '$4 == "A" {print $5}')
    if [ -z "$ips" ]; then
        echo "ERROR: Failed to resolve $domain"
        exit 1
    fi

    while read -r ip; do
        if [[ ! "$ip" =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$ ]]; then
            echo "ERROR: Invalid IP from DNS for $domain: $ip"
            exit 1
        fi
        echo "Adding $ip for $domain"
        ipset -exist add allowed-domains "$ip"
    done < <(echo "$ips")
done

# Get host IP from default route (used for host network access, e.g. browsing
# your dev server from the host on a mapped port)
HOST_IP=$(ip route | grep default | cut -d" " -f3)
if [ -z "$HOST_IP" ]; then
    echo "ERROR: Failed to detect host IP"
    exit 1
fi

HOST_NETWORK=$(echo "$HOST_IP" | sed "s/\.[0-9]*$/.0\/24/")
echo "Host network detected as: $HOST_NETWORK"

# Set up remaining iptables rules
iptables -A INPUT -s "$HOST_NETWORK" -j ACCEPT
iptables -A OUTPUT -d "$HOST_NETWORK" -j ACCEPT

# Set default policies to DROP first
iptables -P INPUT DROP
iptables -P FORWARD DROP
iptables -P OUTPUT DROP

# First allow established connections for already approved traffic
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
iptables -A OUTPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

# Then allow only specific outbound traffic to allowed domains
iptables -A OUTPUT -m set --match-set allowed-domains dst -j ACCEPT

# Explicitly REJECT all other outbound traffic for immediate feedback
iptables -A OUTPUT -j REJECT --reject-with icmp-admin-prohibited

echo "Firewall configuration complete"
echo "Verifying firewall rules..."
if curl --connect-timeout 5 https://example.com >/dev/null 2>&1; then
    echo "ERROR: Firewall verification failed - was able to reach https://example.com"
    exit 1
else
    echo "Firewall verification passed - unable to reach https://example.com as expected"
fi

# Verify Anthropic API access
if ! curl --connect-timeout 5 https://api.anthropic.com >/dev/null 2>&1; then
    echo "ERROR: Firewall verification failed - unable to reach https://api.anthropic.com"
    exit 1
else
    echo "Firewall verification passed - able to reach https://api.anthropic.com as expected"
fi

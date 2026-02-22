#!/usr/bin/env bash
set -euo pipefail

# Install script for perplexity
# Usage: curl -fsSL https://raw.githubusercontent.com/bobbyhyam/perplexity-skill/main/install.sh | bash -s -- claude-code

SKILL_NAME="perplexity"
OWNER="bobbyhyam"
REPO="perplexity-skill"
ENV_VAR="PERPLEXITY_API_KEY"
KEYRING_ACCOUNT="perplexity_api_key"
INSTALL_DIR="$HOME/.claude/skills/$SKILL_NAME"
BIN_DIR="$HOME/.local/bin"

# --- Helpers ---
die()  { echo "error: $1" >&2; exit "${2:-1}"; }
info() { echo "==> $1"; }

# --- Validate argument ---
if [ $# -lt 1 ]; then
  echo "Usage: $0 <agent>"
  echo "  agent: claude-code | claude-desktop"
  exit 2
fi

AGENT="$1"
case "$AGENT" in
  claude-code|claude-desktop) ;;
  *) die "unknown agent '$AGENT'. Must be claude-code or claude-desktop" 2 ;;
esac

# --- Check dependencies ---
for cmd in curl unzip grep; do
  command -v "$cmd" >/dev/null 2>&1 || die "'$cmd' is required but not installed"
done

# --- Fetch latest release tag ---
info "Fetching latest release..."
RELEASE_JSON=$(curl -fsSL "https://api.github.com/repos/$OWNER/$REPO/releases/latest") \
  || die "failed to query GitHub API. Check that $OWNER/$REPO exists and is public"

TAG=$(echo "$RELEASE_JSON" | grep -o '"tag_name": *"[^"]*"' | head -1 | cut -d'"' -f4)
[ -n "$TAG" ] || die "could not determine latest release tag"

ASSET_NAME="$REPO-$TAG.zip"
DOWNLOAD_URL="https://github.com/$OWNER/$REPO/releases/download/$TAG/$ASSET_NAME"

# --- Download to temp directory (cleaned up on exit) ---
TMPDIR_PATH=$(mktemp -d)
trap 'rm -rf "$TMPDIR_PATH"' EXIT

info "Downloading $ASSET_NAME..."
curl -fsSL -o "$TMPDIR_PATH/$ASSET_NAME" "$DOWNLOAD_URL" \
  || die "failed to download $DOWNLOAD_URL"

# --- Extract skill files ---
info "Installing skill to $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"
unzip -qo "$TMPDIR_PATH/$ASSET_NAME" -d "$INSTALL_DIR"

# --- Install CLI binary ---
OS=$(uname -s)
ARCH=$(uname -m)

case "$OS" in
  Darwin)
    case "$ARCH" in
      x86_64) BINARY_SUFFIX="macos-x86_64" ;;
      arm64)  BINARY_SUFFIX="macos-arm64" ;;
      *)      BINARY_SUFFIX="" ;;
    esac
    ;;
  Linux)
    case "$ARCH" in
      x86_64) BINARY_SUFFIX="linux-x86_64" ;;
      *)      BINARY_SUFFIX="" ;;
    esac
    ;;
  *)
    BINARY_SUFFIX=""
    ;;
esac

if [ -n "$BINARY_SUFFIX" ]; then
  BINARY_NAME="$SKILL_NAME-$BINARY_SUFFIX"
  BINARY_URL="https://github.com/$OWNER/$REPO/releases/download/$TAG/$BINARY_NAME"
  info "Downloading CLI binary ($BINARY_SUFFIX)..."
  mkdir -p "$BIN_DIR"
  if curl -fsSL -o "$BIN_DIR/$SKILL_NAME" "$BINARY_URL"; then
    chmod +x "$BIN_DIR/$SKILL_NAME"
    info "Installed $SKILL_NAME binary to $BIN_DIR/$SKILL_NAME"

    # Ensure ~/.local/bin is on PATH
    if ! echo "$PATH" | tr ':' '\n' | grep -qx "$BIN_DIR"; then
      if [ -f "$HOME/.zshrc" ]; then
        PROFILE="$HOME/.zshrc"
      elif [ -f "$HOME/.bashrc" ]; then
        PROFILE="$HOME/.bashrc"
      else
        PROFILE="$HOME/.profile"
      fi
      echo "export PATH=\"$BIN_DIR:\$PATH\"" >> "$PROFILE"
      echo "    Added $BIN_DIR to PATH in $PROFILE — restart your shell or run: source $PROFILE"
    fi
  else
    echo "    No pre-built binary found for $BINARY_SUFFIX. Install the CLI manually with: uv run perplexity"
  fi
else
  echo "    No pre-built binary for $OS/$ARCH. Install the CLI manually with: uv run perplexity"
fi

# --- Success ---
echo ""
info "Installed $SKILL_NAME ($TAG) for $AGENT"
echo ""

# --- Credential setup ---
echo "How would you like to store your API credential?"
echo "  1) OS keychain (macOS Keychain / GNOME Keyring)"
echo "  2) Shell profile (export in .zshrc / .bashrc)"
echo "  3) Skip — I'll set it up myself"
echo ""
printf "Choice [1/2/3]: "
read -r CHOICE < /dev/tty

case "$CHOICE" in
  1)
    printf "Enter your %s value: " "$ENV_VAR"
    read -r SECRET_VALUE < /dev/tty
    [ -z "$SECRET_VALUE" ] && die "empty value — aborting"
    if [ "$(uname)" = "Darwin" ]; then
      security add-generic-password -U -s "$SKILL_NAME" -a "$KEYRING_ACCOUNT" -w "$SECRET_VALUE"
    else
      echo "$SECRET_VALUE" | secret-tool store --label="$SKILL_NAME $KEYRING_ACCOUNT" \
        service "$SKILL_NAME" username "$KEYRING_ACCOUNT"
    fi
    echo "Credential stored in OS keychain."
    ;;
  2)
    printf "Enter your %s value: " "$ENV_VAR"
    read -r SECRET_VALUE < /dev/tty
    [ -z "$SECRET_VALUE" ] && die "empty value — aborting"
    if [ -f "$HOME/.zshrc" ]; then
      PROFILE="$HOME/.zshrc"
    elif [ -f "$HOME/.bashrc" ]; then
      PROFILE="$HOME/.bashrc"
    else
      PROFILE="$HOME/.profile"
    fi
    echo "export $ENV_VAR='$SECRET_VALUE'" >> "$PROFILE"
    echo "Added export to $PROFILE — restart your shell or run: source $PROFILE"
    ;;
  3)
    echo "Skipped. Set the $ENV_VAR env var before using $SKILL_NAME."
    ;;
  *)
    echo "Invalid choice — skipping credential setup."
    echo "Set the $ENV_VAR env var before using $SKILL_NAME."
    ;;
esac

echo ""
echo "Next steps:"
echo "  Restart $AGENT to pick up the new skill"

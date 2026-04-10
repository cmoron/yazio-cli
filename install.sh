#!/bin/sh
set -eu

REPO="cmoron/yazio-cli"
BINARY="yazio"

# --- Detect platform ---
OS="$(uname -s)"
ARCH="$(uname -m)"

case "$OS" in
  Linux)  os="linux" ;;
  Darwin) os="macos" ;;
  *)      echo "Error: unsupported OS '$OS'"; exit 1 ;;
esac

case "$ARCH" in
  x86_64|amd64)   arch="x86_64" ;;
  aarch64|arm64)   arch="arm64" ;;
  *)               echo "Error: unsupported architecture '$ARCH'"; exit 1 ;;
esac

# macOS Intel is not built (GitHub retired free Intel macOS runners).
# Fall back to PyPI for Intel Macs.
if [ "$os" = "macos" ] && [ "$arch" = "x86_64" ]; then
  echo "Error: no prebuilt binary for Intel macOS."
  echo "Install via PyPI instead:"
  echo "  uv tool install yazio-cli   # or: pipx install yazio-cli"
  exit 1
fi

TARGET="${os}-${arch}"

# --- Resolve version ---
VERSION="${VERSION:-latest}"
if [ "$VERSION" = "latest" ]; then
  URL="https://github.com/${REPO}/releases/latest/download/${BINARY}-${TARGET}"
else
  URL="https://github.com/${REPO}/releases/download/${VERSION}/${BINARY}-${TARGET}"
fi

# --- Install ---
INSTALL_DIR="${INSTALL_DIR:-/usr/local/bin}"
TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

echo "Downloading ${BINARY} for ${TARGET}..."
if ! curl -fsSL "$URL" -o "$TMP"; then
  echo "Error: failed to download from $URL"
  echo "Check that a release exists for your platform at:"
  echo "  https://github.com/${REPO}/releases"
  exit 1
fi
chmod +x "$TMP"

echo "Installing to ${INSTALL_DIR}/${BINARY}..."
if [ -w "$INSTALL_DIR" ]; then
  mv "$TMP" "${INSTALL_DIR}/${BINARY}"
else
  sudo mv "$TMP" "${INSTALL_DIR}/${BINARY}"
fi

echo "Done! Run 'yazio --help' to get started."

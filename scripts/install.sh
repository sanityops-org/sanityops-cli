#!/usr/bin/env bash
# sanityops CLI installer for macOS and Linux.
# Usage: curl -fsSL https://downloads.sanityops.org/sanityops-cli/install.sh | bash

set -euo pipefail

DEFAULT_BASE_URL="https://downloads.sanityops.org/sanityops-cli"
BASE_URL="${sanityops_CLI_BASE_URL:-$DEFAULT_BASE_URL}"
VERSION="latest"
INSTALL_DIR="${sanityops_CLI_INSTALL_DIR:-${HOME}/.local/bin}"
FORCE=0
SYSTEM_INSTALL=0
ASSUME_YES=0

usage() {
  cat <<'EOF'
Install sanityops CLI.

Usage: install.sh [options]

Options:
  --version <version|latest>  Release version to install (default: latest)
  --dir <path>                Installation directory (default: ~/.local/bin)
  --system                    Install to /usr/local/bin (uses sudo when required)
  --force                     Replace an existing installation without prompting
  --yes                       Do not prompt for confirmation
  --base-url <url>            Release root URL (or set sanityops_CLI_BASE_URL)
  -h, --help                  Show this help
EOF
}

fail() { printf 'Error: %s\n' "$*" >&2; exit 1; }
info() { printf '%s\n' "$*"; }

while [ "$#" -gt 0 ]; do
  case "$1" in
    --version) VERSION="${2:-}"; shift 2 ;;
    --dir) INSTALL_DIR="${2:-}"; shift 2 ;;
    --base-url) BASE_URL="${2:-}"; shift 2 ;;
    --system) SYSTEM_INSTALL=1; INSTALL_DIR="/usr/local/bin"; shift ;;
    --force) FORCE=1; shift ;;
    --yes) ASSUME_YES=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) fail "Unknown option: $1" ;;
  esac
done

[ -n "$VERSION" ] || fail "--version requires a value"
[ -n "$INSTALL_DIR" ] || fail "--dir requires a value"
[ -n "$BASE_URL" ] || fail "--base-url requires a value"
BASE_URL="${BASE_URL%/}"

case "$(uname -s)" in
  Darwin) os="darwin" ;;
  Linux) os="linux" ;;
  *) fail "Unsupported operating system: $(uname -s). Use install.ps1 on Windows." ;;
esac

case "$(uname -m)" in
  x86_64|amd64) arch="x64" ;;
  arm64|aarch64) arch="arm64" ;;
  *) fail "Unsupported CPU architecture: $(uname -m)" ;;
esac

asset="sanityops-cli-${os}-${arch}"

download() {
  url="$1"
  destination="$2"
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL --retry 3 --retry-delay 1 "$url" -o "$destination"
  elif command -v wget >/dev/null 2>&1; then
    wget -q --tries=3 "$url" -O "$destination"
  else
    fail "curl or wget is required to download sanityops CLI"
  fi
}

resolve_version() {
  if [ "$VERSION" != "latest" ]; then
    printf '%s' "$VERSION"
    return
  fi

  manifest="$tmp_dir/release.json"
  download "$BASE_URL/latest/release.json" "$manifest" || fail "Unable to download release manifest"
  if command -v python3 >/dev/null 2>&1; then
    python3 -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["version"])' "$manifest"
  elif command -v jq >/dev/null 2>&1; then
    jq -r '.version' "$manifest"
  else
    fail "python3 or jq is required to read the latest release manifest; use --version instead"
  fi
}

verify_checksum() {
  expected="$(awk -v file="$asset" '$2 == file || $2 == "*" file {print $1; exit}' "$tmp_dir/checksums.txt")"
  [ -n "$expected" ] || fail "No checksum for $asset in checksums.txt"
  if command -v sha256sum >/dev/null 2>&1; then
    actual="$(sha256sum "$tmp_dir/$asset" | awk '{print $1}')"
  elif command -v shasum >/dev/null 2>&1; then
    actual="$(shasum -a 256 "$tmp_dir/$asset" | awk '{print $1}')"
  else
    fail "sha256sum or shasum is required; refusing to install an unverified binary"
  fi
  [ "$actual" = "$expected" ] || fail "Checksum verification failed for $asset"
}

tmp_dir="$(mktemp -d "${TMPDIR:-/tmp}/sanityops-cli.XXXXXX")"
trap 'rm -rf "$tmp_dir"' EXIT

resolved_version="$(resolve_version)"
[ -n "$resolved_version" ] && [ "$resolved_version" != "null" ] || fail "Release manifest has no version"
release_url="$BASE_URL/$resolved_version"

info "Installing sanityops CLI $resolved_version for $os/$arch"
download "$release_url/$asset" "$tmp_dir/$asset" || fail "Unable to download $asset"
download "$release_url/checksums.txt" "$tmp_dir/checksums.txt" || fail "Unable to download checksums.txt"
verify_checksum
chmod 755 "$tmp_dir/$asset"

target="$INSTALL_DIR/sanityops-cli"
if [ -e "$target" ] && [ "$FORCE" -ne 1 ] && [ "$ASSUME_YES" -ne 1 ]; then
  if [ ! -t 0 ]; then
    fail "$target already exists. Re-run with --force to replace, or --yes to confirm.
Example: curl -fsSL https://downloads.sanityops.org/sanityops-cli/install.sh | bash -s -- --force"
  fi
  printf '%s already exists. Replace it? [y/N] ' "$target"
  read -r answer
  case "$answer" in y|Y|yes|YES) ;; *) info "Installation cancelled."; exit 0 ;; esac
fi

if [ "$SYSTEM_INSTALL" -eq 1 ] && [ ! -w "$INSTALL_DIR" ]; then
  command -v sudo >/dev/null 2>&1 || fail "Administrator access is required to write $INSTALL_DIR"
  sudo mkdir -p "$INSTALL_DIR"
  sudo install -m 755 "$tmp_dir/$asset" "$target"
else
  mkdir -p "$INSTALL_DIR"
  install -m 755 "$tmp_dir/$asset" "$target"
fi

"$target" --version >/dev/null || fail "Installed binary failed verification"
info "Installed sanityops CLI $resolved_version to $target"

case ":$PATH:" in
  *":$INSTALL_DIR:"*) info "Run: sanityops-cli --help" ;;
  *)
    info "$INSTALL_DIR is not currently on PATH. Add this to your shell profile:"
    printf '  export PATH="%s:$PATH"\n' "$INSTALL_DIR"
    info "Then open a new terminal and run: sanityops-cli --help"
    ;;
esac

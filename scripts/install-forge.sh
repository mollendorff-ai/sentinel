#!/usr/bin/env sh
# Install the Forge release Sentinel is pinned to (ADR-012), for Linux x86_64 (CI).
#
# The checksum is recorded here, not read from the release, so a release that is
# replaced after the pin is refused rather than installed. Nothing is built and
# nothing is piped into a shell.
#
# To move the pin: set FORGE_VERSION, copy the line for
# forge-x86_64-unknown-linux-musl.tar.gz from that release's checksums.txt into
# FORGE_SHA256, and say so in the CHANGELOG.
#
# Usage: scripts/install-forge.sh [DIR]   (default: $HOME/.local/bin)
set -eu

FORGE_VERSION="v10.0.0-rc.26"
FORGE_SHA256="bd3751a047a2147907f2012e70703cee009b791d2c61a422a99ef6626f1e6e76"
ARCHIVE="forge-x86_64-unknown-linux-musl.tar.gz"

dir="${1:-$HOME/.local/bin}"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

url="https://github.com/mollendorff-ai/forge/releases/download/$FORGE_VERSION/$ARCHIVE"
curl -fsSL --retry 3 -o "$tmp/$ARCHIVE" "$url"
echo "$FORGE_SHA256  $tmp/$ARCHIVE" | sha256sum -c -
tar -xzf "$tmp/$ARCHIVE" -C "$tmp"
mkdir -p "$dir"
install -m 0755 "$tmp/forge" "$dir/forge"
"$dir/forge" --version

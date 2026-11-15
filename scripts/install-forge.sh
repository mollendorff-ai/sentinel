#!/usr/bin/env sh
# Install the Forge release Sentinel is pinned to (ADR-012), on Linux x86_64 or
# aarch64: CI, or the sandbox of an AI chat (ADR-013).
#
# The checksums are recorded here, not read from the release, so a release that
# is replaced after the pin is refused rather than installed. Nothing is built and
# nothing is piped into a shell.
#
# To move the pin: set FORGE_VERSION, copy the two lines for
# forge-*-unknown-linux-musl.tar.gz from that release's checksums.txt below, and
# say so in the CHANGELOG.
#
# Usage: scripts/install-forge.sh [DIR]   (default: $HOME/.local/bin)
set -eu

FORGE_VERSION="v10.0.0-rc.26"

case "$(uname -s)-$(uname -m)" in
    Linux-x86_64)
        target="x86_64-unknown-linux-musl"
        sha256="bd3751a047a2147907f2012e70703cee009b791d2c61a422a99ef6626f1e6e76" ;;
    Linux-aarch64 | Linux-arm64)
        target="aarch64-unknown-linux-musl"
        sha256="6a53b3683c4db98bb3115d84928e97dac26c6a91e696672460f1e6d812c73b90" ;;
    *)
        echo "install-forge.sh: no pinned Forge for $(uname -s) $(uname -m)" >&2
        exit 1 ;;
esac

archive="forge-$target.tar.gz"
dir="${1:-$HOME/.local/bin}"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

url="https://github.com/mollendorff-ai/forge/releases/download/$FORGE_VERSION/$archive"
curl -fsSL --retry 3 -o "$tmp/$archive" "$url"
echo "$sha256  $tmp/$archive" | sha256sum -c -
tar -xzf "$tmp/$archive" -C "$tmp"
mkdir -p "$dir"
install -m 0755 "$tmp/forge" "$dir/forge"
"$dir/forge" --version

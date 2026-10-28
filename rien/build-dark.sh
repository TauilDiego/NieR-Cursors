#!/usr/bin/env bash
# Build the dark variant of NieR Cursors from the upstream release (no Blender needed).
# Runs where xcur2png, xcursorgen and python-pillow exist (e.g. the archlinux container below).
#   rien/build-dark.sh <upstream-release.tar.xz> <out-dir>
# Container:  docker run --rm -v "$PWD:/w" -w /w archlinux:latest bash -c \
#   'pacman -Sy --noconfirm --needed xcur2png xorg-xcursorgen python-pillow python-numpy >/dev/null && rien/build-dark.sh in.tar.xz out'
set -euo pipefail
src=${1:?release .tar.xz}; out=${2:?output dir}
here=$(cd "$(dirname "$0")" && pwd)
work=$(mktemp -d); trap 'rm -rf "$work"' EXIT

tar -xJf "$src" -C "$work"
theme="$work/nier_cursors"
dark="$out/nier_cursors_dark"
rm -rf "$dark"; mkdir -p "$dark/nier" "$dark/cursors"

for f in "$theme"/nier/*; do
    name=$(basename "$f")
    frames="$work/frames/$name"; mkdir -p "$frames"
    xcur2png -d "$frames" -c "$frames/$name.conf" "$f" >/dev/null
    python3 "$here/recolor.py" "$frames"/*.png
    xcursorgen "$frames/$name.conf" "$dark/nier/$name"
done

# Same aliases as upstream (left_ptr, pointer, text...): copy the symlinks as they are.
cp -P "$theme"/cursors/* "$dark/cursors/"
cat > "$dark/index.theme" <<THEME
[Icon Theme]
Name=NieR Cursors Dark
Comment=NieR Cursors by Beinsezii (MIT), recolored to the rien-OS dark palette
Inherits=Adwaita
THEME
cp "$here/../LICENSE" "$dark/LICENSE"
cat > "$dark/NOTICE" <<NOTICE
NieR Cursors Dark — a recolor of NieR Cursors by Beinsezii (https://github.com/Beinsezii/NieR-Cursors),
MIT License (see LICENSE). Modified by the rien-OS project: colors only (rien/recolor.py).
NOTICE
echo "$dark"

#!/usr/bin/env bash
# Buduje AudiobookPlayer-x86_64.AppImage z dist/AudiobookPlayer (PyInstaller onefile).
# Wymaga: dist/AudiobookPlayer (pyinstaller AudiobookPlayer.spec) oraz
# packaging/linux/tools/appimagetool-x86_64.AppImage (pobrane z
# github.com/AppImage/AppImageKit/releases).
set -euo pipefail
cd "$(dirname "$0")/../.."

BIN="dist/AudiobookPlayer"
TOOL="packaging/linux/tools/appimagetool-x86_64.AppImage"
APPDIR="build/AudiobookPlayer.AppDir"

[ -f "$BIN" ] || { echo "Brak $BIN — najpierw: pyinstaller --noconfirm AudiobookPlayer.spec"; exit 1; }
[ -x "$TOOL" ] || { echo "Brak $TOOL"; exit 1; }

rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin"
install -m755 "$BIN" "$APPDIR/usr/bin/AudiobookPlayer"
install -m644 src/icon.png "$APPDIR/audiobookplayer.png"
install -m644 packaging/linux/audiobookplayer.desktop "$APPDIR/audiobookplayer.desktop"

cat > "$APPDIR/AppRun" <<'EOF'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/AudiobookPlayer" "$@"
EOF
chmod 755 "$APPDIR/AppRun"

ARCH=x86_64 "$TOOL" --appimage-extract-and-run "$APPDIR" AudiobookPlayer-x86_64.AppImage

echo "Gotowe: AudiobookPlayer-x86_64.AppImage"

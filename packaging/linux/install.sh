#!/usr/bin/env bash
# Instaluje zbudowany dist/AudiobookPlayer dla bieżącego użytkownika
# (bez sudo — ~/.local/bin, ~/.local/share/applications, ~/.local/share/icons).
set -euo pipefail
cd "$(dirname "$0")/../.."

BIN="dist/AudiobookPlayer"
[ -f "$BIN" ] || { echo "Brak $BIN — najpierw zbuduj: pyinstaller AudiobookPlayer.spec"; exit 1; }

install -Dm755 "$BIN" "$HOME/.local/bin/AudiobookPlayer"
install -Dm644 src/icon.png "$HOME/.local/share/icons/hicolor/256x256/apps/audiobookplayer.png"
install -Dm644 packaging/linux/audiobookplayer.desktop \
    "$HOME/.local/share/applications/audiobookplayer.desktop"

command -v update-desktop-database >/dev/null && \
    update-desktop-database "$HOME/.local/share/applications" || true
command -v gtk-update-icon-cache >/dev/null && \
    gtk-update-icon-cache "$HOME/.local/share/icons/hicolor" 2>/dev/null || true

echo "Zainstalowano. Upewnij się, że \$HOME/.local/bin jest w PATH."

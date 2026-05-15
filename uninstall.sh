#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="${HOME}/.local/share/laziergit"
BIN_CMD="${HOME}/.local/bin/laziergit"

echo "Uninstalling laziergit..."

# Remove installed files
if [ -d "$INSTALL_DIR" ]; then
    rm -rf "$INSTALL_DIR"
    echo "  Removed $INSTALL_DIR"
fi

# Remove command
if [ -f "$BIN_CMD" ]; then
    rm -f "$BIN_CMD"
    echo "  Removed $BIN_CMD"
fi

# Clean up shell config entries
for rc_file in "${HOME}/.bashrc" "${HOME}/.zshrc"; do
    if [ -f "$rc_file" ]; then
        sed -i '/^# laziergit$/,/^fi$/d' "$rc_file" 2>/dev/null || true
    fi
done

# fish
if [ -f "${HOME}/.config/fish/config.fish" ]; then
    # Remove the fish_add_path block we added
    awk -v RS='' -v ORS='\n\n' '!/laziergit/' "${HOME}/.config/fish/config.fish" > /tmp/.fish_config_tmp 2>/dev/null && mv /tmp/.fish_config_tmp "${HOME}/.config/fish/config.fish" || true
fi

echo ""
echo "laziergit uninstalled."
echo ""

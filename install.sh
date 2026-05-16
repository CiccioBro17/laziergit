#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="${HOME}/.local/share/easiergit"
BIN_DIR="${HOME}/.local/bin"
LAZIERGIT_SCRIPT="${INSTALL_DIR}/easiergit.py"
VENV_DIR="${INSTALL_DIR}/venv"

echo "Installing easiergit..."

# Create directories
mkdir -p "$INSTALL_DIR" "$BIN_DIR"

# Copy the main script
cp "$REPO_DIR/easiergit.py" "$INSTALL_DIR/"
cp "$REPO_DIR/requirements.txt" "$INSTALL_DIR/"
chmod +x "$LAZIERGIT_SCRIPT"

# Create virtual environment and install dependencies
python3 -m venv "$VENV_DIR"
"${VENV_DIR}/bin/pip" install --quiet -r "${INSTALL_DIR}/requirements.txt"

# Create the easiergit command
cat > "${BIN_DIR}/easiergit" << WRAPPER
#!/usr/bin/env bash
exec "${VENV_DIR}/bin/python" "${LAZIERGIT_SCRIPT}" "\$@"
WRAPPER
chmod +x "${BIN_DIR}/easiergit"

# Ensure bin directory is in PATH for common shells

# bash
if ! grep -q '.local/bin' "${HOME}/.bashrc" 2>/dev/null; then
    {
        echo ""
        echo '# easiergit'
        echo 'if [ -d "${HOME}/.local/bin" ]; then'
        echo '    PATH="${HOME}/.local/bin:${PATH}"'
        echo '    export PATH'
        echo 'fi'
    } >> "${HOME}/.bashrc"
    echo "  Added ~/.local/bin to PATH in ~/.bashrc"
fi

# zsh
if [ -f "${HOME}/.zshrc" ]; then
    if ! grep -q '.local/bin' "${HOME}/.zshrc" 2>/dev/null; then
        {
            echo ""
            echo '# easiergit'
            echo 'if [ -d "${HOME}/.local/bin" ]; then'
            echo '    PATH="${HOME}/.local/bin:${PATH}"'
            echo '    export PATH'
            echo 'fi'
        } >> "${HOME}/.zshrc"
        echo "  Added ~/.local/bin to PATH in ~/.zshrc"
    fi
fi

# fish
if [ -d "${HOME}/.config/fish" ]; then
    if ! grep -q '.local/bin' "${HOME}/.config/fish/config.fish" 2>/dev/null; then
        {
            echo ""
            echo '# easiergit'
            echo 'if test -d "$HOME/.local/bin"'
            echo '    fish_add_path "$HOME/.local/bin"'
            echo 'end'
        } >> "${HOME}/.config/fish/config.fish"
        echo "  Added ~/.local/bin to PATH in ~/.config/fish/config.fish"
    fi
fi

echo ""
echo "easiergit installed successfully!"
echo ""
echo "  Run: easiergit"
echo ""
echo "Make sure ~/.local/bin is in your PATH."
echo "Restart your shell or run:"
echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
echo ""

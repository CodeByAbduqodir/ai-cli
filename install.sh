#!/bin/bash
set -e

INSTALL_DIR="$HOME/.ai-cli"
BIN_PATH="/usr/local/bin/ai"

echo "==> Installing ai-cli..."

# Python check
if ! command -v python3 &>/dev/null; then
    echo "==> Installing python3..."
    sudo apt-get update -q && sudo apt-get install -y python3 python3-pip
fi

# pip check
if ! command -v pip3 &>/dev/null; then
    sudo apt-get install -y python3-pip
fi

# Copy files
echo "==> Copying files to $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"
cp main.py "$INSTALL_DIR/main.py"
cp requirements.txt "$INSTALL_DIR/requirements.txt"
chmod +x "$INSTALL_DIR/main.py"

# .env setup
if [ ! -f "$INSTALL_DIR/.env" ]; then
    if [ -f ".env" ]; then
        cp .env "$INSTALL_DIR/.env"
        echo "==> Copied .env"
    else
        echo ""
        echo "  No .env file found."
        read -rp "  Enter your OpenRouter API key: " key
        echo "OPENROUTER_API_KEY=$key" > "$INSTALL_DIR/.env"
        echo "==> .env created"
    fi
fi

# Install dependencies
echo "==> Installing Python dependencies..."
pip3 install -q --break-system-packages -r "$INSTALL_DIR/requirements.txt" 2>/dev/null \
    || pip3 install -q -r "$INSTALL_DIR/requirements.txt"

# Create /usr/local/bin/ai wrapper
echo "==> Creating 'ai' command at $BIN_PATH..."
sudo tee "$BIN_PATH" > /dev/null <<EOF
#!/bin/bash
python3 $INSTALL_DIR/main.py "\$@"
EOF
sudo chmod +x "$BIN_PATH"

echo ""
echo "  Done! Run 'ai' to start."

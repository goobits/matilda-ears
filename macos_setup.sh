#!/bin/bash
# macOS Quick Setup for Matilda STT Server

set -e

echo "🍎 Matilda macOS Setup"
echo "====================="
echo ""

# Check we're on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo "❌ This script is for macOS only"
    exit 1
fi

# Navigate to STT directory
cd ~/projects/matilda/stt

echo "📦 Installing STT with Apple Silicon support..."
/usr/bin/python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e '.[mac]'

echo ""
echo "⚙️  Configuring parakeet backend..."
mkdir -p ~/.config/stt
cat > ~/.config/stt/config.json <<'EOF'
{
  "transcription": {
    "backend": "parakeet"
  },
  "parakeet": {
    "model": "mlx-community/parakeet-tdt-0.6b-v3"
  }
}
EOF

echo ""
echo "✅ Setup complete!"
echo ""
echo "📝 Next steps:"
echo "  1. Terminal 1: cd ~/projects/matilda/stt && source .venv/bin/activate && MATILDA_MANAGEMENT_TOKEN=managed-by-matilda-system stt --server --port 8769"
echo "  2. Terminal 2: cd ~/projects/matilda/matilda/rust && cargo build --release && cargo install --path . --force && matilda run"
echo "  3. Test: Hold Right ⌘, speak, release"
echo ""

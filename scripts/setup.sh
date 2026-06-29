#!/usr/bin/env bash
# macOS development environment setup
# Run this once after cloning the repo.
set -euo pipefail

echo "=== Adaptive Doc Intelligence — macOS Setup ==="

# Check Homebrew
if ! command -v brew &>/dev/null; then
  echo "Installing Homebrew..."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

# Install system dependencies
echo "Installing system dependencies via Homebrew..."
brew install pyenv make git

# Ensure pyenv is initialised
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"

# Install Python 3.11
if ! pyenv versions | grep -q "3.11"; then
  echo "Installing Python 3.11 via pyenv..."
  pyenv install 3.11
fi
pyenv local 3.11

# Create virtual environment
if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  python -m venv .venv
fi

echo "Activating virtual environment..."
source .venv/bin/activate

echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -e ".[dev]" 2>/dev/null || pip install -r requirements.txt 2>/dev/null || echo "No requirements file found — skipping pip install"

# Copy .env if it doesn't exist
if [ ! -f ".env" ]; then
  echo "Copying .env.example to .env..."
  cp .env.example .env
  echo ""
  echo ">>> Open .env and fill in your API keys before running 'make up' <<<"
  echo ""
fi

echo ""
echo "=== Setup complete! ==="
echo "Next steps:"
echo "  1. Edit .env and add your API keys"
echo "  2. Run: make up"
echo "  3. Visit http://localhost:8000/docs to verify the API"

# macOS Setup Guide

## Prerequisites

### 1. Homebrew

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

### 2. Docker Desktop

Download and install from https://www.docker.com/products/docker-desktop/

After installation, open Docker Desktop and ensure it is running before continuing.

### 3. Python 3.11 via pyenv

```bash
brew install pyenv
echo 'eval "$(pyenv init -)"' >> ~/.zshrc   # or ~/.bashrc
source ~/.zshrc

pyenv install 3.11
pyenv global 3.11
python --version   # should print Python 3.11.x
```

### 4. make (already available on macOS via Xcode CLT)

```bash
xcode-select --install
make --version
```

---

## Project Setup

```bash
# Clone the repository
git clone <repo-url>
cd adaptive-doc-intelligence

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"   # or: pip install -r requirements.txt

# Copy and configure environment variables
make setup
# Open .env in your editor and fill in all API keys before continuing.

# Start all Docker services
make up

# Verify everything is healthy
docker compose ps
```

Expected output: all services should show `healthy` or `running`.

---

## Verify Services

| Service | URL | Check |
|---------|-----|-------|
| Ingestion API | http://localhost:8000/docs | FastAPI Swagger UI |
| Flower | http://localhost:5555 | Celery monitoring |
| MinIO Console | http://localhost:9001 | Object storage |
| Label Studio | http://localhost:8080 | HITL review |
| Grafana | http://localhost:3000 | Dashboards (admin/admin) |

---

## Common Issues

**Docker Desktop not running**: Make sure Docker Desktop is open and the whale icon appears in the menu bar.

**Port conflicts**: If any port is already in use, stop the conflicting process or edit the port mapping in `docker-compose.yml`.

**pyenv: command not found**: Restart your terminal after adding pyenv to your shell profile.

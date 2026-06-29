# Windows Setup Guide

> **Recommended path**: Use WSL2 + Ubuntu. Everything runs identically to macOS inside WSL2,
> and Docker Desktop volume performance is dramatically better when files live inside the WSL2
> filesystem (not `/mnt/c`).

---

## Option A — WSL2 (Recommended)

### 1. Enable WSL2

Open PowerShell as Administrator:

```powershell
wsl --install          # installs WSL2 + Ubuntu by default
wsl --set-default-version 2
```

Restart your computer when prompted.

### 2. Install Docker Desktop

Download from https://www.docker.com/products/docker-desktop/

During installation, ensure **"Use the WSL 2 based engine"** is checked.

After installation:
- Open Docker Desktop → Settings → Resources → WSL Integration
- Enable integration for your Ubuntu distro

### 3. Open Ubuntu (WSL2)

```bash
# All subsequent commands run inside WSL2 Ubuntu
wsl
```

### 4. Python 3.11 inside WSL2

```bash
# Install pyenv inside WSL2
curl https://pyenv.run | bash
echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc
echo 'export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc
echo 'eval "$(pyenv init -)"' >> ~/.bashrc
source ~/.bashrc

pyenv install 3.11
pyenv global 3.11
python --version   # should print Python 3.11.x
```

### 5. Clone the repo INSIDE WSL2 (critical for performance)

```bash
# DO NOT clone under /mnt/c — Docker bind mounts are very slow from the Windows filesystem
cd ~   # or ~/projects
git clone <repo-url>
cd adaptive-doc-intelligence
```

### 6. Run the project

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

make setup    # copies .env.example → .env; fill in API keys
make up
docker compose ps
```

---

## Option B — Without WSL2 (Native Windows)

> This path is not recommended. Docker volume performance on Windows is significantly
> worse without WSL2, and shell script compatibility requires additional setup.

### Requirements

- Docker Desktop (Hyper-V backend)
- Python 3.11 via pyenv-win: https://github.com/pyenv-win/pyenv-win
- make via Chocolatey:

```powershell
choco install make
```

### Running the project

Instead of `make` targets, use the equivalent `docker compose` commands directly:

```powershell
docker compose up -d
docker compose down
docker compose logs -f
docker compose exec api alembic upgrade head
```

---

## Common Issues

**Files cloned to `/mnt/c`**: Move them inside WSL2 (`~/projects/`) — Docker bind mounts from `/mnt/c` are extremely slow.

**Docker not available inside WSL2**: Make sure Docker Desktop is running and WSL integration is enabled for your distro.

**`make: command not found`**: Install make inside WSL2 with `sudo apt install make`.

**Port conflicts**: Check `docker compose ps` and stop any conflicting local services.

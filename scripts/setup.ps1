# Windows development environment setup (PowerShell)
# Recommended: Run this INSIDE WSL2 Ubuntu using setup.sh instead.
# Use this script only if you are setting up on native Windows without WSL2.

Write-Host "=== Adaptive Doc Intelligence - Windows Setup ===" -ForegroundColor Cyan

# Check if running in WSL2
if ($env:WSL_DISTRO_NAME) {
    Write-Host "Detected WSL2 environment. Please use setup.sh instead:" -ForegroundColor Yellow
    Write-Host "  bash scripts/setup.sh"
    exit 0
}

# Check for Chocolatey
if (-not (Get-Command choco -ErrorAction SilentlyContinue)) {
    Write-Host "Installing Chocolatey..." -ForegroundColor Yellow
    Set-ExecutionPolicy Bypass -Scope Process -Force
    [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
    Invoke-Expression ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
}

# Install make
if (-not (Get-Command make -ErrorAction SilentlyContinue)) {
    Write-Host "Installing make via Chocolatey..." -ForegroundColor Yellow
    choco install make -y
}

# Check for Docker Desktop
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "Docker Desktop is not installed." -ForegroundColor Red
    Write-Host "Please install Docker Desktop from: https://www.docker.com/products/docker-desktop/"
    Write-Host "Ensure 'Use the WSL 2 based engine' is checked during installation."
    exit 1
}

# Copy .env if it doesn't exist
if (-not (Test-Path ".env")) {
    Write-Host "Copying .env.example to .env..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
    Write-Host ""
    Write-Host ">>> Open .env and fill in your API keys before running 'make up' <<<" -ForegroundColor Yellow
    Write-Host ""
}

Write-Host ""
Write-Host "=== Setup complete! ===" -ForegroundColor Green
Write-Host "Next steps:"
Write-Host "  1. Edit .env and add your API keys"
Write-Host "  2. Run: make up  (or: docker compose up -d)"
Write-Host "  3. Visit http://localhost:8000/docs to verify the API"

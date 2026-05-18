# Clean and push script for Nova compiler
Write-Host "=== Cleaning Nova Repository ===" -ForegroundColor Green

# Remove all __pycache__ folders
Write-Host "Removing __pycache__ folders..." -ForegroundColor Yellow
Get-ChildItem -Path . -Name __pycache__ -Directory -Recurse | Remove-Item -Recurse -Force

# Remove compiled files
Write-Host "Removing compiled files..." -ForegroundColor Yellow
Remove-Item -Path *.pyc -Force -ErrorAction SilentlyContinue
Remove-Item -Path *.ll -Force -ErrorAction SilentlyContinue
Remove-Item -Path *.exe -Force -ErrorAction SilentlyContinue

# Create .gitignore if not exists
if (-not (Test-Path ".gitignore")) {
    Write-Host "Creating .gitignore..." -ForegroundColor Yellow
    @"
__pycache__/
*.pyc
*.pyo
*.pyd
*.ll
*.exe
*.out
*.obj
*.o
.vscode/
.idea/
.DS_Store
Thumbs.db
venv/
.venv/
env/
*.log
*.tmp
"@ | Out-File -FilePath .gitignore -Encoding utf8
}

# Git operations
Write-Host "Git operations..." -ForegroundColor Yellow
git add .
git status

Write-Host "`nReady to commit. Run:" -ForegroundColor Green
Write-Host "git commit -m 'Clean version with proper .gitignore'" -ForegroundColor Yellow
Write-Host "git push origin main" -ForegroundColor Yellow
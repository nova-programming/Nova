Write-Host "=== Cleaning Nova Repository ===" -ForegroundColor Green

# Remove from git tracking
Write-Host "Removing __pycache__ from git tracking..." -ForegroundColor Yellow
git rm -r --cached __pycache__ 2>$null
git rm -r --cached */__pycache__ 2>$null
git rm -r --cached */*/__pycache__ 2>$null
git rm -r --cached */*/*/__pycache__ 2>$null
git rm --cached *.pyc 2>$null

# Remove from filesystem
Write-Host "Deleting __pycache__ folders..." -ForegroundColor Yellow
Get-ChildItem -Path . -Name __pycache__ -Directory -Recurse | Remove-Item -Recurse -Force

Write-Host "Deleting .pyc files..." -ForegroundColor Yellow
Get-ChildItem -Path . -Filter *.pyc -Recurse | Remove-Item -Force

# Ensure .gitignore has correct entries
Write-Host "Updating .gitignore..." -ForegroundColor Yellow
$gitignore = @"
# Python cache files
__pycache__/
*.pyc
*.pyo
*.pyd
*.pycache*/

# LLVM and compiled outputs
*.ll
*.exe
*.out
*.obj
*.o

# IDE and editor files
.vscode/
.idea/
*.swp
*.swo
*~
.DS_Store
Thumbs.db

# Virtual environments
venv/
.venv/
env/
.env/

# Build directories
build/
dist/
*.egg-info/

# Logs and databases
*.log
*.sqlite
*.db

# OS generated files
.DS_Store
Thumbs.db
ehthumbs.db
*.tmp
"@

$gitignore | Out-File -FilePath .gitignore -Encoding utf8

# Stage the .gitignore changes
git add .gitignore

# Commit
Write-Host "Committing changes..." -ForegroundColor Yellow
git commit -m "Clean repository: remove __pycache__ folders and update .gitignore"

# Push
Write-Host "Pushing to GitHub..." -ForegroundColor Yellow
git push origin main

Write-Host "Done! Repository is now clean." -ForegroundColor Green
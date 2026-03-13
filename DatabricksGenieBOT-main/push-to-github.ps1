# Push this project to https://github.com/jaison-samuel-d/DatabricksGenieBOT
# Run from project root: .\push-to-github.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path .git)) {
    Write-Host "Initializing git repository..."
    git init
    git add -A
    git commit -m "Initial commit: Databricks Genie Bot with Teams and service principal support"
}

$remote = "origin"
$url = "https://github.com/jaison-samuel-d/DatabricksGenieBOT.git"

if (-not (git remote get-url $remote 2>$null)) {
    Write-Host "Adding remote $remote..."
    git remote add $remote $url
}

git branch -M main
Write-Host "Pushing to $url (branch: main)..."
Write-Host "You may be prompted for GitHub credentials (use a Personal Access Token if 2FA is enabled)."
git push -u $remote main

Write-Host "Done. Check: https://github.com/jaison-samuel-d/DatabricksGenieBOT"

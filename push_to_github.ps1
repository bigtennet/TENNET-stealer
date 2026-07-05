# Push TENNET-stealer to GitHub
#
# Prerequisites:
#   1. Install Git: https://git-scm.com/download/win
#   2. Install GitHub CLI: winget install GitHub.cli
#   3. Login: gh auth login
#
# Then run from PowerShell:
#   cd "c:\Users\MY LAPTOP\Downloads\TENNET-stealer"
#   .\push_to_github.ps1

$ErrorActionPreference = "Stop"
$RepoName = "TENNET-stealer"

git init
git branch -M main
git add .
git commit -m "Initial commit: TENNET-stealer toolkit"

# Create private repo on your account and push
gh repo create $RepoName --private --source=. --remote=origin --push

Write-Host ""
Write-Host "Done! View at: https://github.com/$(gh api user -q .login)/$RepoName"

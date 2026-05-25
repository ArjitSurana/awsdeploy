# Removes leaked secrets from ALL git history (rewrites main branch).
# Run from project root. Then: git push --force origin main
# REVOKE your Google API keys first — old keys stay valid until revoked.

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

Write-Host "Removing .env from entire git history..."
git filter-branch --force --index-filter "git rm --cached --ignore-unmatch .env" --prune-empty -- --all

Write-Host "Removing refs backup..."
Remove-Item -Recurse -Force .git\refs\original -ErrorAction SilentlyContinue
git reflog expire --expire=now --all
git gc --prune=now --aggressive

Write-Host "Done. Commit fixed test.py, then force push:"
Write-Host "  git add test.py"
Write-Host "  git commit -m `"Remove hardcoded API key from test.py`""
Write-Host "  git push --force origin main"

# Push code to GitHub

Push this codebase to: **https://github.com/jaison-samuel-d/DatabricksGenieBOT**

## Option 1: PowerShell script (Windows)

From the project root (this folder):

```powershell
.\push-to-github.ps1
```

If you're prompted for credentials, use your GitHub username and a [Personal Access Token](https://github.com/settings/tokens) (not your password, especially if you have 2FA).

---

## Option 2: Manual commands

Run these in the project root:

```bash
# One-time setup
git init
git add -A
git commit -m "Initial commit: Databricks Genie Bot with Teams and service principal support"
git remote add origin https://github.com/jaison-samuel-d/DatabricksGenieBOT.git
git branch -M main

# Push (use a Personal Access Token as password if you have 2FA)
git push -u origin main
```

---

## If the repo already has content

If you already ran `git init` or the remote exists:

```bash
git remote add origin https://github.com/jaison-samuel-d/DatabricksGenieBOT.git
# or, if origin exists: git remote set-url origin https://github.com/jaison-samuel-d/DatabricksGenieBOT.git
git branch -M main
git push -u origin main
```

---

## Authentication

- **HTTPS:** When prompted for password, use a [GitHub Personal Access Token](https://github.com/settings/tokens) (classic) with `repo` scope.
- **SSH:** If you use SSH keys, change the remote to `git@github.com:jaison-samuel-d/DatabricksGenieBOT.git` and run `git push -u origin main`.

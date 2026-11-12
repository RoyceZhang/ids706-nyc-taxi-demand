# Remaining GitHub upload steps

The project is prepared locally. No GitHub repository has been created or pushed.
Use this cleaned folder, rather than the original Downloads copy.

## Create an empty GitHub repository

In your own GitHub account, create a new empty repository, for example
`ids706-nyc-taxi-demand`. Do not add a GitHub-generated README, license, or
.gitignore during creation; this folder already contains the submission files.
Choose visibility according to the course's requirements.

## Commit and push from the project root

```bash
python3 scripts/pre_upload_check.py
git init -b main
git add .
git diff --cached --stat
git diff --cached --check
git commit -m "Complete IDS706 Airflow and agent-based taxi forecasting"
git remote add origin https://github.com/YOUR_USERNAME/ids706-nyc-taxi-demand.git
git push -u origin main
```

Replace `YOUR_USERNAME` with your actual account. Normal GitHub authentication
may be requested. If Git needs your identity, set your preferred name and email
for this repository with `git config user.name` and `git config user.email`.
Do not paste passwords, tokens or API keys into source files.

The working copy prepared by ChatGPT may already have a local repository and
staged files; `git status` shows its state. An extracted ZIP has no `.git` history,
so the commands above initialize it normally.

## Inspect the uploaded result

Open the repository and confirm README images render, all four screenshots are
present, and `evidence/eda_postgres.png` and execution JSON are visible. Submit the
repository URL. The optional bonus Part 3 is not claimed.

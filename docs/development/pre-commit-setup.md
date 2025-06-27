# Pre-commit Hook Setup

This project uses pre-commit hooks to ensure code quality and consistency.

## Installation

1. Install pre-commit (already included in requirements.txt):
   ```bash
   pip install pre-commit
   ```

2. Install the git hook scripts:
   ```bash
   pre-commit install
   ```

3. (Optional) Run against all files to check current state:
   ```bash
   pre-commit run --all-files
   ```

## What It Does

The pre-commit hooks will automatically run on `git commit` and check:

- **Python**: Black formatting, Ruff linting, MyPy type checking
- **JavaScript/TypeScript**: ESLint and Prettier formatting
- **General**: Trailing whitespace, file endings, large files
- **Security**: Secret detection
- **Markdown**: Markdown linting
- **Docker**: Dockerfile linting

## Bypass Hooks (Emergency Only)

If you need to commit without running hooks:
```bash
git commit --no-verify
```

## Update Hooks

To update the hooks to their latest versions:
```bash
pre-commit autoupdate
```

## Frontend Setup

Make sure to install frontend dependencies for the TypeScript/JavaScript hooks:
```bash
cd frontend
npm install
``` 
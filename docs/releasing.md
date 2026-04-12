# Releasing Reporting In CLI

This document describes the release process for reportingin-cli, including version management, changelog updates, and publishing to PyPI and Debian packages.

## Prerequisites

Before releasing, ensure you have:
- Push access to the GitHub repository
- Trusted publishing configured on PyPI (see deploy-todo.md Part 1.4)
- All tests passing locally: `uv run pytest`
- All linting passing: `uv run ruff check reportingin_cli tests`

## Version Management

Reporting In CLI uses **Semantic Versioning** (SemVer):
- **MAJOR** (X.0.0): Breaking changes to CLI interface or configuration
- **MINOR** (0.X.0): New features, new commands, backward-compatible changes
- **PATCH** (0.0.X): Bug fixes, documentation updates

### Version Locations

The version must be updated in **two places** to stay synchronized:

1. **pyproject.toml** - The authoritative source for package builds:
   ```toml
   version = "X.Y.Z"
   ```

2. **reportingin_cli/__init__.py** - Used by `--version` flag:
   ```python
   __version__ = "X.Y.Z"
   ```

### Version Formats Across Systems

| System | Stable | Example | Prerelease | Example |
|--------|--------|---------|------------|---------|
| Git tag | `vX.Y.Z` | `v1.0.0` | `vX.Y.Z-rcN` | `v1.0.0-rc1` |
| PyPI | `X.Y.Z` | `1.0.0` | `X.Y.ZrcN` | `1.0.0rc1` |
| Python `__version__` | `X.Y.Z` | `1.0.0` | `X.Y.ZrcN` | `1.0.0rc1` |
| Debian changelog | `X.Y.Z-R` | `1.0.0-1` | `X.Y.Z~rcN-R` | `1.0.0~rc1-1` |

## Release Process

### Step 1: Update Version

```bash
# Edit both files to update version
# pyproject.toml: version = "X.Y.Z"
# reportingin_cli/__init__.py: __version__ = "X.Y.Z"
```

### Step 2: Update Changelog

Edit `CHANGELOG.md` following [Keep a Changelog](https://keepachangelog.com/) format:

1. Change `[Unreleased]` to `[X.Y.Z] - YYYY-MM-DD`
2. Add a new `[Unreleased]` section at the top
3. Ensure all changes are documented under appropriate headings:
   - **Added** - New features
   - **Changed** - Changes in existing functionality
   - **Deprecated** - Soon-to-be removed features
   - **Removed** - Now removed features
   - **Fixed** - Bug fixes
   - **Security** - Vulnerability fixes

### Step 3: Update Debian Changelog

```bash
# Use dch to add a new changelog entry
cd debian
dch -v X.Y.Z-1 "New upstream release."
dch -r ""  # Mark as released (changes UNRELEASED to distro name)
```

Or manually edit `debian/changelog` with proper format:
```
reportingin-cli (X.Y.Z-1) unstable; urgency=medium

  * New upstream release.
  * [List specific changes relevant to Debian packaging]

 -- Maintainer Name <email@example.com>  Day, DD Mon YYYY HH:MM:SS +0000
```

### Step 4: Run Pre-release Verification

```bash
# Run all tests
uv run pytest

# Run linting
uv run ruff check reportingin_cli tests

# Run type checking
uv run mypy reportingin_cli

# Test package installation
./scripts/test-package.sh
```

### Step 5: Commit Release Changes

```bash
git add pyproject.toml reportingin_cli/__init__.py CHANGELOG.md debian/changelog
git commit -m "Release v${VERSION}"
```

### Step 6: Create Git Tag

```bash
# Create annotated tag
git tag -a "v${VERSION}" -m "Release v${VERSION}"

# Push commit and tag
git push origin main
git push origin "v${VERSION}"
```

### Step 7: Create GitHub Release

1. Go to the repository's Releases page on GitHub
2. Click "Draft a new release"
3. Select the tag you just pushed (e.g., `v1.0.0`)
4. Set release title: `v1.0.0`
5. Copy release notes from CHANGELOG.md
6. Click "Publish release"

This triggers the automated workflows:
- **publish.yml**: Builds and uploads to PyPI
- **debian.yml**: Builds Debian packages and attaches to release

### Step 8: Verify Publication

#### PyPI

```bash
# Wait a few minutes for PyPI to process
pip install --upgrade reportingin-cli

# Verify installation
reportingin-cli --version  # Should show new version
```

#### GitHub Release Assets

Check that the following artifacts are attached to the release:
- `reportingin_cli-X.Y.Z.tar.gz` (source distribution)
- `reportingin_cli-X.Y.Z-py3-none-any.whl` (wheel)
- `reportingin-cli_X.Y.Z-1_all.deb` (Ubuntu Noble package)
- `reportingin-cli_X.Y.Z-1_all.deb` (Debian Trixie package)

#### Debian Package

```bash
# Download and install .deb
wget https://github.com/OWNER/REPO/releases/download/vX.Y.Z/reportingin-cli_X.Y.Z-1_all.deb
sudo dpkg -i reportingin-cli_X.Y.Z-1_all.deb
sudo apt-get install -f  # Install any missing dependencies

# Verify
reportingin-cli --version
```

## Release Candidate Process

For major releases, consider creating release candidates first:

```bash
# Update version to RC
# pyproject.toml: version = "2.0.0rc1"
# reportingin_cli/__init__.py: __version__ = "2.0.0rc1"

# Commit and tag
git commit -am "Release v2.0.0-rc1"
git tag -a "v2.0.0-rc1" -m "Release candidate 1 for v2.0.0"
git push origin main "v2.0.0-rc1"

# Create GitHub pre-release
# Check "Set as a pre-release" when creating the release
```

## Rollback Procedures

### PyPI Rollback

PyPI does not allow re-uploading the same version. If a release has critical issues:

1. **Yank the release** (prevents new installs but allows existing pins):
   ```bash
   # Via web interface or twine
   # Go to PyPI project page → Manage → Options → Yank
   ```

2. **Release a patch version** with the fix:
   ```bash
   # If 1.0.0 has issues, release 1.0.1 with fix
   ```

### GitHub Release Rollback

1. Delete the GitHub release (keeps the tag)
2. Optionally delete the tag:
   ```bash
   git push --delete origin vX.Y.Z
   git tag -d vX.Y.Z
   ```

### Reverting Changes

If you need to revert code changes:

```bash
# Revert the release commit (preferred - creates a new commit)
git revert HEAD
git push origin main
```

**WARNING**: Only use `git reset --hard` if changes are NOT pushed yet. This command
permanently discards uncommitted changes and can cause data loss:

```bash
# DANGER: Only if NOT yet pushed - discards all local changes!
git reset --hard HEAD~1
```

## Troubleshooting

### Workflow Failures

1. Check the Actions tab on GitHub for detailed logs
2. Common issues:
   - **Trusted publishing not configured**: Set up on PyPI settings
   - **Version already exists on PyPI**: Bump to a new version
   - **Tests failing**: Fix tests before releasing

### Package Installation Issues

```bash
# Clear pip cache and reinstall
pip cache purge
pip install --no-cache-dir reportingin-cli

# Install with verbose output for debugging
pip install -v reportingin-cli
```

### Debian Package Issues

```bash
# Check package info
dpkg-deb -I reportingin-cli_*.deb

# Check package contents
dpkg-deb -c reportingin-cli_*.deb

# Check for dependency issues
sudo apt-get install -f
```

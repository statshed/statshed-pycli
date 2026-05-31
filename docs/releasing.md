# Releasing StatShed CLI

This document describes the release process for statshed-cli, including version management, changelog updates, and publishing to PyPI and Debian packages.

## Prerequisites

Before releasing, ensure you have:
- Push access to the GitHub repository
- Trusted publishing configured on PyPI (see deploy-todo.md Part 1.4)
- All tests passing locally: `uv run pytest`
- All linting passing: `uv run ruff check statshed_cli tests`

## Version Management

StatShed CLI uses **Semantic Versioning** (SemVer):
- **MAJOR** (X.0.0): Breaking changes to CLI interface or configuration
- **MINOR** (0.X.0): New features, new commands, backward-compatible changes
- **PATCH** (0.0.X): Bug fixes, documentation updates

### Version Locations

**`pyproject.toml` is the single source of truth** for the upstream version:

```toml
version = "X.Y.Z"
```

`statshed_cli/__init__.py` derives `__version__` from the installed package
metadata, and `--version` reads the same metadata, so neither can drift.

Two packaging records carry their own copy of the version and must be bumped to
match (the release workflow's `check-version` job fails the build on any drift):

- `debian/changelog` — top entry `statshed-cli (X.Y.Z-1) ...`
- `packaging/rpm/statshed-cli.spec` — `Version: X.Y.Z`

The Nix flake reads the version straight from `pyproject.toml`, so it needs no
update.

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
# Edit pyproject.toml: version = "X.Y.Z"   (the single source of truth)
# Edit packaging/rpm/statshed-cli.spec: Version: X.Y.Z
# debian/changelog is updated in Step 3 below via dch.
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
statshed-cli (X.Y.Z-1) unstable; urgency=medium

  * New upstream release.
  * [List specific changes relevant to Debian packaging]

 -- Maintainer Name <email@example.com>  Day, DD Mon YYYY HH:MM:SS +0000
```

### Step 4: Run Pre-release Verification

```bash
# Run all tests
uv run pytest

# Run linting
uv run ruff check statshed_cli tests

# Run type checking
uv run mypy statshed_cli

# Test package installation
./scripts/test-package.sh
```

### Step 5: Commit Release Changes

```bash
git add pyproject.toml CHANGELOG.md debian/changelog packaging/rpm/statshed-cli.spec
git commit -m "Release v${VERSION}"
```

### Step 6: Push the Release Tag (triggers everything)

```bash
# Create an annotated tag matching the version (the leading "v" is required)
git tag -a "v${VERSION}" -m "Release v${VERSION}"

# Push the commit and the tag
git push origin main
git push origin "v${VERSION}"
```

Pushing a `v*` tag runs `.github/workflows/release.yml`, which:

1. **check-version** — verifies the tag, `pyproject.toml`, `debian/changelog`,
   and the RPM spec all agree (fails fast on drift).
2. **build-python** — builds the wheel + sdist and runs `twine check`.
3. **build-deb** — builds `.deb` packages for Debian trixie and Ubuntu noble.
4. **build-rpm** — builds `.rpm` packages for Fedora and Rocky/EL9.
5. **publish-pypi** — publishes to PyPI via OIDC Trusted Publishing (no tokens).
6. **release** — creates the GitHub Release and attaches the wheel, sdist, all
   `.deb`s, and all `.rpm`s.

No manual GitHub Release creation is needed. To rehearse a PyPI publish without
cutting a release, run the workflow manually (`workflow_dispatch`) with
`test_pypi=true` to push to TestPyPI.

### Step 8: Verify Publication

#### PyPI

```bash
# Wait a few minutes for PyPI to process
pip install --upgrade statshed-cli

# Verify installation
statshed --version  # Should show new version
```

#### GitHub Release Assets

Check that the following artifacts are attached to the release:
- `statshed_cli-X.Y.Z.tar.gz` (source distribution)
- `statshed_cli-X.Y.Z-py3-none-any.whl` (wheel)
- `statshed-cli_X.Y.Z-1_all_debian-trixie.deb`
- `statshed-cli_X.Y.Z-1_all_ubuntu-noble.deb`
- `statshed-cli-X.Y.Z-1.fc*.noarch.rpm` (Fedora)

The Nix package is built from the in-repo `flake.nix` (no release asset);
verify it with `nix run github:statshed/statshed-pycli -- --version`.

#### Debian Package

```bash
# Download and install .deb
wget https://github.com/OWNER/REPO/releases/download/vX.Y.Z/statshed-cli_X.Y.Z-1_all.deb
sudo dpkg -i statshed-cli_X.Y.Z-1_all.deb
sudo apt-get install -f  # Install any missing dependencies

# Verify
statshed --version
```

## Release Candidate Process

For major releases, consider creating release candidates first:

```bash
# Update version to RC
# pyproject.toml: version = "2.0.0rc1"
# statshed_cli/__init__.py: __version__ = "2.0.0rc1"

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
pip install --no-cache-dir statshed-cli

# Install with verbose output for debugging
pip install -v statshed-cli
```

### Debian Package Issues

```bash
# Check package info
dpkg-deb -I statshed-cli_*.deb

# Check package contents
dpkg-deb -c statshed-cli_*.deb

# Check for dependency issues
sudo apt-get install -f
```

# StatShed CLI Deployment PRD & Implementation Checklist

This document outlines the complete deployment strategy for statshed-cli, including PyPI publishing, GitHub Actions CI/CD, and Debian packaging.

---

## Executive Summary

**Goal:** Enable automated, reproducible deployment of statshed-cli to:
1. **PyPI** - Python Package Index for `pip install statshed-cli`
2. **Debian packages** - `.deb` files for apt-based Linux distributions
3. **GitHub Releases** - Binary artifacts attached to tagged releases

**Current State:**
- Well-structured Python package with hatchling build backend
- Runtime dependencies: click, requests, pyyaml
- Optional `rich` extra for enhanced terminal output
- Comprehensive test suite (7 test modules, 145+ tests)
- README.md and CHANGELOG.md already exist
- No CI/CD pipeline exists
- No GitHub remote configured

---

## Part 1: Prerequisites & Repository Setup

### 1.1 Essential Files

- [x] Create `README.md` with comprehensive documentation ✓
- [x] Create `CHANGELOG.md` with Keep a Changelog format ✓
- [x] Create `LICENSE` file with CC0-1.0 license text ✓

### 1.2 pyproject.toml Enhancements

**Already present** (no changes needed):
- [x] `readme = "README.md"` ✓
- [x] `version = "1.0.0"` ✓
- [x] `keywords = ["statshed", "dashboard", "cli", "status", "monitoring"]` ✓
- [x] `[project.urls]` section ✓

**Still needed:**
- [x] Update `license` field for CC0: ✓
  - Change to: `license = {file = "LICENSE"}`
  - **Note:** PEP 621 allows both string identifiers (SPDX) and table format with `text` or `file` key.
- [x] Update classifiers for CC0: ✓
  - Remove: `"License :: OSI Approved :: MIT License"`
  - Add: `"License :: CC0 1.0 Universal (CC0 1.0) Public Domain Dedication"`
- [x] Add Bug Tracker URL to `[project.urls]` ✓
- [x] Add Changelog URL to `[project.urls]` ✓
- [x] Configure hatchling sdist include list: ✓
  ```toml
  [tool.hatch.build.targets.sdist]
  include = [
    "pyproject.toml",  # Required for pip to build from sdist
    "statshed_cli/",
    "tests/",          # Included for reproducibility
    "docs/*.1",
    "LICENSE",
    "README.md",
    "CHANGELOG.md",
  ]
  ```
  - **CRITICAL:** `pyproject.toml` MUST be included or pip cannot build from sdist
  - **IMPORTANT:** Man pages must be created (Phase 2.5) BEFORE the first PyPI release,
    otherwise the glob will silently match nothing.

### 1.3 GitHub Repository Setup

- [ ] Create GitHub repository (github.com/statshed/statshed-cli or your namespace)
- [ ] Add remote: `git remote add origin <url>`
- [ ] Push existing commits to GitHub
- [ ] Configure branch protection rules for `main`/`master`

### 1.4 PyPI Name Reservation & Trusted Publishing Setup

**IMPORTANT:** TestPyPI does NOT reserve names on PyPI. You must upload to real PyPI to reserve the name.

**Prerequisite:** The publish workflow (Part 2.2) must be committed to the default branch BEFORE configuring trusted publishing, otherwise the validation will fail.

- [ ] Create and commit publish workflow first (see Part 2.2)
- [ ] Reserve package name on PyPI:
  - [ ] **Create PyPI API token first:** Go to https://pypi.org/manage/account/token/ and create a token
    - Trusted publishing cannot be used for the initial upload (project doesn't exist yet)
    - This token is only needed once; after the project exists, trusted publishing handles future uploads
  - [ ] Build package locally: `uv build`
  - [ ] Upload initial version to PyPI using the API token:
    ```bash
    # Option A: Interactive stdin (RECOMMENDED - token never in history or process list)
    read -rs UV_PUBLISH_TOKEN && export UV_PUBLISH_TOKEN && uv publish; unset UV_PUBLISH_TOKEN

    # Option B: History-suppressed one-liner (if HISTCONTROL includes 'ignorespace')
     UV_PUBLISH_TOKEN="pypi-AgEI..." uv publish  # Note: leading space
    ```
  - [ ] This reserves the name - do this early to prevent name squatting
- [ ] Configure PyPI trusted publisher (https://pypi.org/manage/project/statshed-cli/settings/publishing/):
  - [ ] Add GitHub Actions as trusted publisher
  - [ ] Owner: your-github-username
  - [ ] Repository: statshed-cli
  - [ ] Workflow name: publish.yml
  - [ ] Environment name: `pypi`
- [ ] Configure TestPyPI trusted publisher (https://test.pypi.org/manage/project/statshed-cli/settings/publishing/):
  - [ ] **Prerequisite:** Project must exist on TestPyPI first (upload with test.pypi.org token)
  - [ ] Add GitHub Actions as trusted publisher with environment name: `testpypi`

---

## Part 2: GitHub Actions CI/CD

**CI Dependency Strategy:** The test workflow uses `uv sync --all-extras --all-groups --frozen` which requires
a `uv.lock` file committed to the repository. The lockfile already exists.

### 2.1 Test Workflow (`.github/workflows/test.yml`)

- [x] Create `.github/workflows/` directory ✓
- [x] Create `test.yml` workflow with: ✓
  - [x] Trigger on push to main/master and pull requests ✓
  - [x] Matrix testing: Python 3.10, 3.11, 3.12, 3.13 ✓
  - [x] Matrix testing: Ubuntu latest ✓
  - [x] Install dependencies with `uv` ✓
  - [x] Run pytest ✓
  - [x] Run mypy type checking ✓
  - [x] Run ruff linting and format check ✓
- [ ] Test the workflow with a push

### 2.2 Publish to PyPI Workflow (`.github/workflows/publish.yml`)

- [x] Create `publish.yml` workflow with: ✓
  - [x] Trigger on GitHub release creation (published event) ✓
  - [x] Trigger on manual workflow_dispatch with test_pypi boolean input ✓
  - [x] Build source distribution (sdist) and wheel ✓
  - [x] Verify package with `twine check` ✓
  - [x] Publish to PyPI using `pypa/gh-action-pypi-publish` ✓
  - [x] Attach built artifacts to GitHub release (requires `contents: write`) ✓
- [ ] Test with TestPyPI first (using workflow_dispatch with test_pypi=true)
- [ ] Verify installation from TestPyPI works

### 2.3 Debian Package Workflow (`.github/workflows/debian.yml`)

- [x] Create `debian.yml` workflow with: ✓
  - [x] Trigger on release creation ✓
  - [x] Build in Debian/Ubuntu container ✓
  - [x] Support Debian/Ubuntu versions with `python3-hatchling` in base repos: ✓
    - [x] Ubuntu 24.04 LTS (noble) ✓
    - [x] Debian 13 (trixie) ✓
  - [x] Build `.deb` package with `dpkg-buildpackage -b` (binary only) ✓
  - [x] Run lintian to check package quality ✓
  - [x] Upload `.deb` artifacts to GitHub Release ✓
- [ ] Test workflow produces valid `.deb` files

---

## Part 3: PyPI Packaging Details

### 3.1 Build Configuration

- [x] Verify hatchling builds correctly: `uv build` ✓
- [x] Inspect generated wheel for correct files ✓
- [x] Inspect generated sdist for correct files: ✓
  - [x] Verify man page is included (after Phase 2.5) ✓
  - [x] Run: `tar -tzf dist/statshed_cli-*.tar.gz | grep statshed.1` ✓
- [x] Ensure `__version__` in `__init__.py` matches pyproject.toml ✓

### 3.2 Version Management Strategy

- [x] Document versioning scheme (Semantic Versioning) ✓ (see docs/releasing.md)
- [x] Decide single source of truth for version: ✓
  - [x] Option A: Both `pyproject.toml` and `__init__.py` (manual sync) ✓
  - [ ] ~~Option B: `pyproject.toml` with dynamic version~~
  - [ ] ~~Option C: Git tags with hatch-vcs~~
- [x] Create version bump script or document manual process ✓ (see docs/releasing.md)
- [x] Ensure version is updated before each release ✓ (documented in releasing.md)

**Version Mapping Across Systems:**

| System | Stable Format | Example | Prerelease Format | Prerelease Example |
|--------|---------------|---------|-------------------|-------------------|
| Git tag | `vX.Y.Z` | `v1.0.0` | `vX.Y.Z-rcN` | `v1.0.0-rc1` |
| PyPI version | `X.Y.Z` | `1.0.0` | `X.Y.ZrcN` | `1.0.0rc1` |
| `__init__.py` | `X.Y.Z` | `1.0.0` | `X.Y.ZrcN` | `1.0.0rc1` |
| Debian changelog | `X.Y.Z-R` | `1.0.0-1` | `X.Y.Z~rcN-R` | `1.0.0~rc1-1` |

### 3.3 Package Testing Before Release

- [x] Create script `scripts/test-package.sh`: ✓
  - [x] Build package locally ✓
  - [x] Install in fresh virtual environment ✓
  - [x] Run smoke tests against installed package ✓
  - [x] Verify entry point works: `statshed --help` ✓
  - [x] Verify sub-commands work: `statshed health --help` ✓
- [x] Test installation with `pip install .` ✓ (via test-package.sh)
- [ ] Test installation with `pipx install .`
- [x] Test optional dependencies: `pip install .[rich]` ✓ (via test-package.sh)

### 3.4 PyPI Account Setup

- [ ] Create PyPI account (if not exists)
- [ ] Configure 2FA on PyPI account
- [ ] Reserve package name by uploading to real PyPI (see Part 1.4)
- [ ] Configure trusted publishing (see Part 1.4)

---

## Part 4: Debian Packaging

### 4.1 Debian Directory Structure

- [x] Create `debian/` directory ✓
- [x] Create `debian/control`: ✓
  - [x] Source package name: `statshed-cli` ✓
  - [x] Binary package name: `statshed-cli` ✓
  - [x] Maintainer info ✓
  - [x] Build-Depends: debhelper-compat, dh-python, python3-all, python3-hatchling, pybuild-plugin-pyproject ✓
  - [x] Depends: `${python3:Depends}, ${misc:Depends}, python3-click, python3-requests, python3-yaml` ✓
  - [x] Suggests: python3-rich (for rich output support) ✓
  - [x] Description (short and long) ✓
  - [x] Section: utils ✓
  - [x] Priority: optional ✓
  - [x] Standards-Version: 4.6.2 ✓
  - [x] Homepage: GitHub repo URL ✓
  - [x] Vcs-Git and Vcs-Browser ✓
  - [x] Rules-Requires-Root: no ✓
- [x] Create `debian/rules`: ✓
  - [x] Use dh sequencer with python3 plugin ✓
  - [x] **IMPORTANT:** File MUST be executable (`chmod +x debian/rules`) ✓
- [x] Create `debian/changelog`: ✓
  - [x] Use `dch` tool or manual format ✓
  - [x] Version must match git tag: tag `v1.0.0` → changelog version `1.0.0-1` ✓
- [x] Create `debian/copyright`: ✓
  - [x] Use DEP-5 format ✓
  - [x] Reference CC0-1.0 license (public domain dedication) ✓
- [x] Create `debian/source/format` with content `3.0 (quilt)` ✓

### 4.2 Debian Build Scripts

- [x] Create `debian/statshed-cli.manpages` to install man pages ✓
- [x] Create `debian/statshed-cli.docs` for README, etc. ✓

### 4.3 Python-Specific Debian Configuration

- [x] Configure `debian/rules` for pybuild: ✓
  ```makefile
  %:
  	dh $@ --with python3 --buildsystem=pybuild
  ```
  - **CRITICAL:** The indentation MUST be a tab character, not spaces.

### 4.4 Local Debian Build Testing

- [ ] Install build dependencies:
  - [ ] `devscripts`, `debhelper`, `dh-python`, `python3-all`, `lintian`
- [ ] Build binary package: `DEB_BUILD_OPTIONS=nocheck dpkg-buildpackage -us -uc -b`
- [ ] Run lintian: `lintian ../statshed-cli_*.deb`
- [ ] Fix all lintian errors (E:)
- [ ] Fix lintian warnings (W:) where reasonable
- [ ] Test installation: `sudo dpkg -i ../statshed-cli_*.deb`
- [ ] Test removal: `sudo dpkg -r statshed-cli`
- [ ] Verify clean removal (no orphaned files)

### 4.5 Autopkgtest (Debian CI Testing)

- [x] Create `debian/tests/` directory ✓
- [x] Create `debian/tests/control`: ✓
  ```
  Tests: smoke-test
  Depends: @
  ```
- [x] Create `debian/tests/smoke-test`: ✓
  ```sh
  #!/bin/sh
  set -e
  statshed --help
  statshed --version
  statshed health --help
  statshed submit --help
  statshed completion --help
  ```
- [x] **Make smoke-test executable**: `chmod +x debian/tests/smoke-test` ✓
- [ ] Run autopkgtest locally

### 4.6 Container-Based Debian Builds

- [ ] Create `Dockerfile.debian` for reproducible builds
- [ ] Create `scripts/build-deb.sh` to automate container build
- [ ] Test builds in multiple Debian/Ubuntu versions

---

## Part 5: Documentation

### 5.1 User Documentation

- [x] README.md with comprehensive usage documentation ✓
- [x] Installation methods documented ✓
- [x] Exit codes documented ✓
- [x] Troubleshooting section ✓

### 5.2 Deployment Documentation

- [x] Create `docs/releasing.md` with: ✓
  - [x] Version bump procedure ✓
  - [x] Changelog update process ✓
  - [x] Creating a GitHub release ✓
  - [x] Verifying PyPI publication ✓
  - [x] Verifying Debian package builds ✓
  - [x] Rollback procedures ✓

### 5.3 Man Pages

**IMPORTANT:** Man pages must be created during Phase 2.5 (before the first PyPI release).

- [x] Create `docs/statshed.1` (troff format): ✓
  - [x] NAME section ✓
  - [x] SYNOPSIS section ✓
  - [x] DESCRIPTION section ✓
  - [x] OPTIONS section (global flags) ✓
  - [x] COMMANDS section (submit, health, groups, jobs, config, etc.) ✓
  - [x] EXIT STATUS section ✓
  - [x] FILES section (config file locations) ✓
  - [x] ENVIRONMENT section (STATSHED_URL, STATSHED_CONFIG, NO_COLOR) ✓
  - [x] EXAMPLES section ✓
  - [x] SEE ALSO section ✓
  - [x] AUTHOR section ✓
- [x] Test man page rendering: `man ./docs/statshed.1` ✓
- [x] Include man page in Debian package via `debian/statshed-cli.manpages` ✓

---

## Part 6: Testing the Deployment Pipeline

### 6.1 Pre-Release Testing

- [ ] Test installation from TestPyPI:
  ```bash
  pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ statshed-cli
  ```
- [ ] Test Debian package installation in Docker
- [ ] Verify all commands work: submit, health, groups, jobs, config, group-config, completion

### 6.2 Release Dry Run

- [ ] Create a release candidate tag (e.g., v1.0.0-rc1)
- [ ] Trigger workflows manually or via RC tag
- [ ] Verify artifacts are built correctly
- [ ] Download and test all artifacts locally

### 6.3 First Production Release

- [ ] Update version to release version (e.g., 1.0.0)
- [ ] Update CHANGELOG.md with release notes
- [ ] Create git tag: `git tag -a v1.0.0 -m "Release v1.0.0"`
- [ ] Push tag: `git push origin v1.0.0`
- [ ] Create GitHub release from tag
- [ ] Monitor workflow runs
- [ ] Verify PyPI shows new version
- [ ] Verify Debian packages in release assets
- [ ] Test installation from PyPI: `pip install statshed-cli`

---

## Part 7: Implementation Order

Recommended implementation order to minimize rework:

### Phase 1: Repository Foundation
1. [x] Create LICENSE file (CC0-1.0) ✓
2. [x] Update pyproject.toml (license field, classifiers, Bug Tracker and Changelog URLs) ✓
3. [ ] Create GitHub repository and push

### Phase 2: CI Pipeline
4. [x] Create test workflow (.github/workflows/test.yml) ✓
5. [ ] Verify tests pass in CI
6. [x] Add badges to README ✓

### Phase 2.5: Man Pages (before first release)
7. [x] Create `docs/statshed.1` man page ✓
8. [x] Test man page rendering: `man ./docs/statshed.1` ✓
   - **IMPORTANT:** Man pages MUST be created before Phase 3 (first PyPI release)

### Phase 3: PyPI Publishing
9. [x] Create publish workflow (.github/workflows/publish.yml) ✓
10. [ ] Commit and push workflow to default branch (required for trusted publishing)
11. [ ] Reserve name on PyPI with manual initial upload (`uv build && uv publish`)
12. [ ] Configure trusted publishing on PyPI
13. [ ] Test workflow with TestPyPI (optional)

### Phase 4: Debian Packaging
14. [x] Create debian/ directory structure ✓
15. [ ] Test local Debian builds
16. [x] Create Debian workflow (.github/workflows/debian.yml) ✓
17. [ ] Test with release

### Phase 5: Documentation & Polish
18. [ ] Create releasing.md documentation
19. [ ] Review and refine all documentation

---

## Appendix A: Workflow File Templates

### A.1 Test Workflow Template

```yaml
# .github/workflows/test.yml
name: Tests

on:
  push:
    branches: [main, master]
  pull_request:
    branches: [main, master]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12", "3.13"]

    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4
        with:
          version: "latest"

      - name: Set up Python ${{ matrix.python-version }}
        run: uv python install ${{ matrix.python-version }}

      - name: Install dependencies
        run: uv sync --all-extras --all-groups --frozen
        env:
          UV_PYTHON: ${{ matrix.python-version }}

      - name: Run tests
        run: uv run pytest --tb=short -v
        env:
          UV_PYTHON: ${{ matrix.python-version }}

      - name: Run type checking
        run: uv run mypy statshed_cli
        env:
          UV_PYTHON: ${{ matrix.python-version }}

      - name: Run linting
        run: uv run ruff check statshed_cli tests
        env:
          UV_PYTHON: ${{ matrix.python-version }}

      - name: Check formatting
        run: uv run ruff format --check statshed_cli tests
        env:
          UV_PYTHON: ${{ matrix.python-version }}
```

### A.2 Publish Workflow Template

```yaml
# .github/workflows/publish.yml
name: Publish to PyPI

on:
  release:
    types: [published]
  workflow_dispatch:
    inputs:
      test_pypi:
        description: 'Publish to TestPyPI instead'
        type: boolean
        default: true
      ref:
        description: 'Git ref to checkout (tag, branch, or SHA). For production PyPI, must be a vX.Y.Z tag.'
        type: string
        default: ''

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Validate ref for production PyPI
        if: github.event_name == 'workflow_dispatch' && inputs.test_pypi != true
        run: |
          REF="${{ inputs.ref || github.ref }}"
          if [[ "$REF" =~ ^(refs/tags/)?v[0-9]+\.[0-9]+\.[0-9]+(-.*)?$ ]]; then
            echo "✓ Valid release tag: $REF"
          else
            echo "::error::Production PyPI publishing requires a release tag (vX.Y.Z format)."
            exit 1
          fi

      - uses: actions/checkout@v4
        with:
          ref: ${{ github.event.release.tag_name || inputs.ref || github.ref }}
          fetch-depth: 0

      - name: Verify checkout is at a tag (production only)
        if: github.event_name == 'workflow_dispatch' && inputs.test_pypi != true
        run: |
          TAG=$(git describe --exact-match --tags HEAD 2>/dev/null) || {
            echo "::error::Current checkout is not at a tag."
            exit 1
          }
          echo "✓ Verified checkout is at tag: $TAG"

      - name: Install uv
        uses: astral-sh/setup-uv@v4

      - name: Build package
        run: uv build

      - name: Verify package with twine
        run: uv tool run twine check dist/*

      - name: Upload artifacts
        uses: actions/upload-artifact@v4
        with:
          name: dist
          path: dist/

  publish:
    needs: build
    runs-on: ubuntu-latest
    environment: ${{ github.event_name == 'workflow_dispatch' && inputs.test_pypi == 'true' && 'testpypi' || 'pypi' }}
    permissions:
      id-token: write
      contents: write

    steps:
      - name: Download artifacts
        uses: actions/download-artifact@v4
        with:
          name: dist
          path: dist/

      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
        with:
          repository-url: ${{ github.event_name == 'workflow_dispatch' && inputs.test_pypi == 'true' && 'https://test.pypi.org/legacy/' || 'https://upload.pypi.org/legacy/' }}

      - name: Upload release assets
        if: github.event_name == 'release'
        env:
          GH_TOKEN: ${{ github.token }}
        run: gh release upload "${{ github.event.release.tag_name }}" dist/* --clobber
```

### A.3 Debian Build Workflow Template

```yaml
# .github/workflows/debian.yml
name: Build Debian Packages

on:
  release:
    types: [published]
  workflow_dispatch:

jobs:
  build-deb:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        include:
          - distro: ubuntu
            version: noble
          - distro: debian
            version: trixie

    container:
      image: ${{ matrix.distro }}:${{ matrix.version }}

    steps:
      - name: Install git and build dependencies
        run: |
          apt-get update
          apt-get install -y --no-install-recommends \
            git \
            ca-certificates \
            build-essential \
            fakeroot \
            devscripts \
            debhelper \
            dh-python \
            python3-all \
            python3-hatchling \
            pybuild-plugin-pyproject \
            lintian

      - uses: actions/checkout@v4
        with:
          ref: ${{ github.event.release.tag_name || github.ref }}
          fetch-depth: 0

      - name: Build package
        run: DEB_BUILD_OPTIONS=nocheck dpkg-buildpackage -us -uc -b

      - name: Run lintian (errors are fatal)
        run: |
          lintian --fail-on error ../*.deb
          echo "::group::Lintian warnings and info (non-fatal)"
          lintian --display-info ../*.deb || true
          echo "::endgroup::"

      - name: Run autopkgtest (failures are fatal)
        run: |
          apt-get install -y autopkgtest
          autopkgtest ../*.deb -- null

      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: deb-${{ matrix.distro }}-${{ matrix.version }}
          path: ../*.deb

  upload-release:
    needs: build-deb
    runs-on: ubuntu-latest
    if: github.event_name == 'release'
    permissions:
      contents: write
    steps:
      - name: Download all artifacts
        uses: actions/download-artifact@v4
        with:
          path: artifacts/

      - name: Upload to release
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          for deb in artifacts/*/*.deb; do
            gh release upload "${{ github.event.release.tag_name }}" "$deb" --clobber --repo "${{ github.repository }}"
          done
```

---

## Appendix B: Debian Control File Template

```
# debian/control
Source: statshed-cli
Section: utils
Priority: optional
Maintainer: Sean <sean@example.com>
Build-Depends: debhelper-compat (= 13),
               dh-python,
               python3-all,
               python3-hatchling,
               pybuild-plugin-pyproject
Standards-Version: 4.6.2
Homepage: https://github.com/statshed/statshed-cli
Vcs-Git: https://github.com/statshed/statshed-cli.git
Vcs-Browser: https://github.com/statshed/statshed-cli
Rules-Requires-Root: no

Package: statshed-cli
Architecture: all
Depends: ${python3:Depends},
         ${misc:Depends},
         python3-click,
         python3-requests,
         python3-yaml
Suggests: python3-rich
Description: Command-line interface for StatShed status dashboard
 StatShed CLI provides commands for interacting with the StatShed status
 dashboard from the command line:
 .
  - submit: Report job status (success, error, progress)
  - health: Check overall system health
  - groups: List all groups with health summaries
  - jobs: List jobs within a specific group
  - config: View and update global timeout configuration
  - group-config: View and update group-specific settings
  - completion: Generate shell completion scripts
```

---

## Appendix C: Key File Locations Summary

After implementation, the repository should have:

```
statshed-cli/
├── .github/
│   └── workflows/
│       ├── test.yml
│       ├── publish.yml
│       └── debian.yml
├── debian/
│   ├── changelog
│   ├── control
│   ├── copyright
│   ├── rules
│   ├── source/
│   │   └── format
│   ├── tests/
│   │   ├── control
│   │   └── smoke-test
│   ├── statshed-cli.manpages
│   └── statshed-cli.docs
├── docs/
│   ├── statshed.1
│   └── releasing.md
├── scripts/
│   ├── build-deb.sh
│   └── test-package.sh
├── statshed_cli/
│   └── (existing source)
├── tests/
│   └── (existing tests)
├── LICENSE
├── CHANGELOG.md
├── README.md
└── pyproject.toml
```

---

## Notes

- **AIDEV-NOTE:** This document serves as both PRD and implementation checklist
- **AIDEV-NOTE:** Check off items as they are implemented
- **AIDEV-NOTE:** Each phase should be validated with tests before proceeding
- **AIDEV-NOTE:** Keep this document updated as implementation progresses

---

## References

- [Python Packaging User Guide](https://packaging.python.org/)
- [PyPA Publishing Guide](https://packaging.python.org/en/latest/guides/publishing-package-distribution-releases-using-github-actions-ci-cd-workflows/)
- [Debian Python Packaging](https://wiki.debian.org/Python/Packaging)
- [Keep a Changelog](https://keepachangelog.com/)
- [Semantic Versioning](https://semver.org/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)

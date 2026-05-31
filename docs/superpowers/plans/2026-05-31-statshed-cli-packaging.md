# StatShed CLI Multi-Format Packaging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finalize the `reportingin`→`statshed` rename and add PyPI, RPM, and Nix packaging plus a unified, tag-driven GitHub Actions release pipeline that also builds the existing `.deb`.

**Architecture:** `pyproject.toml` is the single upstream version source (1.0.2); `debian/changelog` and the RPM spec `Version:` are packaging records kept in sync and verified by a CI guard. One `release.yml` workflow, triggered by a `v*` tag, builds wheel/sdist (PyPI via OIDC Trusted Publishing), `.deb` (Debian trixie + Ubuntu noble), and `.rpm` (Fedora + Rocky/EL9), then creates a GitHub Release with every artifact attached.

**Tech Stack:** Python 3.10–3.13, hatchling, uv, Click; Debian debhelper/pybuild; Fedora pyproject-rpm-macros; Nix flakes (`buildPythonApplication`); GitHub Actions.

**Reference spec:** `docs/superpowers/specs/2026-05-30-statshed-cli-packaging-design.md`

**Boundaries (do NOT do):** create the GitHub repo, add a git remote, push, publish a live PyPI/TestPyPI release, configure PyPI trusted publishing, or set up COPR. All work lands as commits on `master`.

**Local verification context:** Platform is NixOS with `nix`, `uv`, `git`, and `docker` available; `rpmbuild`/`dpkg-buildpackage`/`actionlint` are not installed (invoke on demand via `nix run nixpkgs#<tool>`). The Nix flake is fully buildable locally; `.deb`/`.rpm` builds are validated in CI (spec/lint parse-checked locally).

---

## File Structure

**Modify:**
- `pyproject.toml` — version → 1.0.2; `[project.urls]` repo `statshed-cli`→`statshed-pycli`.
- `statshed_cli/__init__.py` — derive `__version__` from installed metadata.
- `CHANGELOG.md` — add `[1.0.1]`, `[1.0.2]` sections.
- `debian/control`, `debian/copyright` — repo URL `statshed-cli`→`statshed-pycli`.
- `README.md` — badge/links to `statshed-pycli`; Installation section for all channels.
- `deploy-todo.md`, `docs/releasing.md` — rewrite for unified flow.

**Create:**
- `packaging/rpm/statshed-cli.spec`
- `flake.nix`, `flake.lock`
- `.github/workflows/release.yml`

**Rename (already staged in working tree, just commit):** `reportingin_cli/*`→`statshed_cli/*`, `reportingin-design-*.md`→`statshed-design-*.md`, `debian/reportingin-cli.*`→`debian/statshed-cli.*`, `docs/reportingin.1`→`docs/statshed.1`.

---

## Task 1: Finalize the reportingin→statshed rename

**Files:** all working-tree adds/deletes from the in-progress rename.

- [ ] **Step 1: Confirm no stray references remain**

Run:
```bash
cd /home/sean/aix/statshed/pycli
grep -rIl -i -e reportingin -e statdash \
  --exclude-dir=.git --exclude-dir=.remember --exclude=uv.lock . || echo "CLEAN"
```
Expected: `CLEAN` (only the deleted `reportingin*` paths might appear; they are removed by staging in Step 2).

- [ ] **Step 2: Stage every rename change**

Run:
```bash
git add -A
git status --short
```
Expected: `statshed_cli/*`, `statshed-design-*.md`, renamed `debian/statshed-cli.*`, `docs/statshed.1` added; `reportingin_cli/*`, `reportingin-design-*.md`, `debian/reportingin-cli.*`, `docs/reportingin.1` deleted.

- [ ] **Step 3: Verify tests + build still pass against the renamed package**

Run:
```bash
uv sync --all-extras --frozen
uv run pytest -q
uv run mypy statshed_cli
uv run ruff check statshed_cli tests
uv run ruff format --check statshed_cli tests
```
Expected: all pass. (If `--frozen` fails due to lock drift from the rename, run `uv lock` and include `uv.lock` in the commit.)

- [ ] **Step 4: Commit**

```bash
git commit -m "Finalize rename of CLI package to statshed

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Single-source the version and reconcile the changelog

**Files:**
- Modify: `pyproject.toml:3`
- Modify: `statshed_cli/__init__.py`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Set the single source of truth to 1.0.2**

In `pyproject.toml` change `version = "1.0.1"` to:
```toml
version = "1.0.2"
```

- [ ] **Step 2: Derive `__version__` from metadata**

Replace the entire body of `statshed_cli/__init__.py` with:
```python
"""StatShed CLI - Command-line interface for StatShed status dashboard."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("statshed-cli")
except PackageNotFoundError:  # running from a source tree without an install
    __version__ = "0.0.0+unknown"
```
(`--version` already uses `@click.version_option(package_name="statshed-cli")`, so this only keeps the importable `__version__` from drifting.)

- [ ] **Step 3: Reconcile CHANGELOG.md**

Insert these sections directly under the intro paragraph and above `## [1.0.0] - 2026-01-18`:
```markdown
## [Unreleased]

## [1.0.2] - 2026-02-02

### Added

- Log upload commands for attaching job logs to submissions.

## [1.0.1] - 2026-01-25

### Added

- `stream` subcommand: pipe progress updates from stdin to the dashboard.
- `wrap` subcommand: run a command and report its progress/exit status.

```

- [ ] **Step 4: Verify version resolves end-to-end**

Run:
```bash
uv pip install -e . --quiet
uv run python -c "import statshed_cli; print(statshed_cli.__version__)"
uv run statshed --version
```
Expected: both print `1.0.2` (the `statshed --version` line prints `statshed, version 1.0.2`).

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml statshed_cli/__init__.py CHANGELOG.md uv.lock
git commit -m "Single-source version on pyproject (1.0.2); reconcile changelog

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Update repository metadata URLs (statshed-cli → statshed-pycli)

**Files:** `pyproject.toml`, `debian/control`, `debian/copyright`, `README.md`

- [ ] **Step 1: Rewrite the URLs**

Run (replaces the repo slug everywhere it appears in metadata, leaving the PyPI package name `statshed-cli` untouched):
```bash
sed -i 's#statshed/statshed-cli#statshed/statshed-pycli#g' \
  pyproject.toml debian/control debian/copyright README.md
```

- [ ] **Step 2: Verify**

Run:
```bash
grep -rn "statshed/statshed-cli" pyproject.toml debian README.md || echo "NO OLD SLUG"
grep -rn "statshed/statshed-pycli" pyproject.toml debian/control README.md
```
Expected: `NO OLD SLUG`, and the new slug present in each file. Confirm the PyPI name line `name = "statshed-cli"` in `pyproject.toml` is unchanged.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml debian/control debian/copyright README.md
git commit -m "Point repository URLs at statshed/statshed-pycli

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Native RPM spec

**Files:**
- Create: `packaging/rpm/statshed-cli.spec`

- [ ] **Step 1: Write the spec**

Create `packaging/rpm/statshed-cli.spec`:
```spec
# AIDEV-NOTE: Native RPM spec for statshed-cli, built in CI on Fedora and
# Rocky/EL9 (EPEL) via pyproject-rpm-macros. The Version below MUST match
# pyproject.toml and debian/changelog; the release workflow's check-version
# job fails the build on drift. The sdist (Source0) is produced by `uv build`
# and is named with the normalized module name (underscores).

%global pypi_name   statshed-cli
%global import_name statshed_cli

Name:           %{pypi_name}
Version:        1.0.2
Release:        1%{?dist}
Summary:        Command-line interface for the StatShed status dashboard

License:        CC0-1.0
URL:            https://github.com/statshed/statshed-pycli
Source0:        %{import_name}-%{version}.tar.gz

BuildArch:      noarch

BuildRequires:  python3-devel
BuildRequires:  pyproject-rpm-macros
# For %%check
BuildRequires:  python3-pytest
BuildRequires:  python3-responses

Requires:       python3-click
Requires:       python3-requests
Requires:       python3-pyyaml
Recommends:     python3-rich

%description
StatShed CLI provides commands for interacting with the StatShed status
dashboard from the command line: submitting job status, checking health,
listing groups and jobs, managing global and per-group configuration,
uploading logs, and generating shell completion scripts.

%prep
%autosetup -n %{import_name}-%{version}

%generate_buildrequires
%pyproject_buildrequires

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files %{import_name}
install -Dpm0644 docs/statshed.1 %{buildroot}%{_mandir}/man1/statshed.1

%check
%pytest

%files -f %{pyproject_files}
%license LICENSE
%doc README.md CHANGELOG.md
%{_bindir}/statshed
%{_mandir}/man1/statshed.1*

%changelog
* Sat May 31 2026 Sean <jafo00+oss@gmail.com> - 1.0.2-1
- Initial RPM packaging.
```

- [ ] **Step 2: Parse-check the spec locally**

Run:
```bash
nix run nixpkgs#rpm -- rpmspec -P packaging/rpm/statshed-cli.spec >/dev/null && echo "SPEC PARSES"
```
Expected: `SPEC PARSES` (macro expansion is environment-dependent; a clean parse of the static directives is the local gate — full build happens in CI).

- [ ] **Step 3: Commit**

```bash
git add packaging/rpm/statshed-cli.spec
git commit -m "Add native RPM spec (Fedora/EL9)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Nix flake

**Files:**
- Create: `flake.nix`, `flake.lock`

- [ ] **Step 1: Write the flake**

Create `flake.nix`:
```nix
{
  description = "StatShed CLI - command-line interface for the StatShed status dashboard";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        python = pkgs.python3;
        pyproject = builtins.fromTOML (builtins.readFile ./pyproject.toml);

        statshed-cli = python.pkgs.buildPythonApplication {
          pname = "statshed-cli";
          version = pyproject.project.version;
          pyproject = true;
          src = ./.;

          build-system = [ python.pkgs.hatchling ];

          dependencies = with python.pkgs; [
            click
            requests
            pyyaml
          ];

          optional-dependencies = {
            rich = [ python.pkgs.rich ];
          };

          nativeCheckInputs = with python.pkgs; [
            pytestCheckHook
            responses
            rich
          ];

          # AIDEV-NOTE: integration tests hit a live backend; skip in the sandbox.
          disabledTestPaths = [ "tests/test_integration.py" ];

          postInstall = ''
            install -Dm0644 docs/statshed.1 $out/share/man/man1/statshed.1
          '';

          pythonImportsCheck = [ "statshed_cli" ];

          meta = with pkgs.lib; {
            description = "Command-line interface for the StatShed status dashboard";
            homepage = "https://github.com/statshed/statshed-pycli";
            license = licenses.cc0;
            mainProgram = "statshed";
            platforms = platforms.all;
          };
        };
      in
      {
        packages.default = statshed-cli;
        packages.statshed-cli = statshed-cli;

        apps.default = {
          type = "app";
          program = "${statshed-cli}/bin/statshed";
        };

        devShells.default = pkgs.mkShell {
          packages = [
            pkgs.uv
            python
            pkgs.ruff
            python.pkgs.mypy
          ];
        };
      });
}
```

- [ ] **Step 2: Generate the lock and build**

Run:
```bash
nix flake lock
nix build .#statshed-cli -L
nix run .# -- --version
```
Expected: build succeeds; `nix run` prints `statshed, version 1.0.2`. (If `disabledTestPaths` is insufficient because integration tests are collected via a marker instead, switch to `pytestFlagsArray = [ "--deselect" ... ]` or `disabledTests`, re-run.)

- [ ] **Step 3: Smoke-check the dev shell**

Run:
```bash
nix develop --command sh -c 'uv --version && ruff --version && mypy --version'
```
Expected: all three print versions.

- [ ] **Step 4: Commit**

```bash
git add flake.nix flake.lock
git commit -m "Add Nix flake (package, app, devShell)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Unified release workflow

**Files:**
- Create: `.github/workflows/release.yml`

- [ ] **Step 1: Resolve action commit SHAs**

Reuse from `test.yml`: `actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5` (v4.3.1), `astral-sh/setup-uv@38f3f104447c67c051c4a08e39b64a148898af3a` (v4). Resolve current SHAs for `actions/upload-artifact` (v4), `actions/download-artifact` (v4), and `pypa/gh-action-pypi-publish` (release/v1) via:
```bash
for r in actions/upload-artifact actions/download-artifact; do
  echo -n "$r "; nix run nixpkgs#curl -- -fsSL "https://api.github.com/repos/$r/git/refs/tags/v4" | nix run nixpkgs#jq -- -r '.object.sha'
done
nix run nixpkgs#curl -- -fsSL "https://api.github.com/repos/pypa/gh-action-pypi-publish/git/refs/tags/v1.12.4" | nix run nixpkgs#jq -- -r '.object.sha'
```
If the network is unavailable, pin to the version tag (e.g. `@v4`) and add an `AIDEV-NOTE: pin to SHA` beside it.

- [ ] **Step 2: Write the workflow**

Create `.github/workflows/release.yml` (replace each `# AIDEV-NOTE: pin SHA` placeholder with the resolved `@<sha>  # vX.Y.Z`):
```yaml
# AIDEV-NOTE: Unified release pipeline. A `v*` tag builds wheel/sdist, .deb, and
# .rpm, publishes to PyPI via OIDC Trusted Publishing, and attaches everything to
# a GitHub Release. workflow_dispatch with test_pypi=true does a TestPyPI dry-run
# (no .deb/.rpm/Release). Version consistency is enforced before anything builds.
name: Release

on:
  push:
    tags: ["v*"]
  workflow_dispatch:
    inputs:
      test_pypi:
        description: "Publish to TestPyPI instead of building a full release"
        type: boolean
        default: true

permissions:
  contents: read

jobs:
  check-version:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5  # v4.3.1
      - name: Versions agree across pyproject, debian, and rpm spec
        run: |
          set -euo pipefail
          PY=$(grep -m1 '^version = ' pyproject.toml | sed -E 's/.*"([^"]+)".*/\1/')
          DEB=$(dpkg-parsechangelog -l debian/changelog -S Version 2>/dev/null | sed -E 's/-[0-9]+$//' || sed -nE '1s/.*\(([0-9.]+)-[0-9]+\).*/\1/p' debian/changelog)
          RPM=$(grep -m1 '^Version:' packaging/rpm/statshed-cli.spec | awk '{print $2}')
          echo "pyproject=$PY debian=$DEB rpm=$RPM"
          test "$PY" = "$DEB" && test "$PY" = "$RPM"
      - name: Tag matches version (tag pushes only)
        if: startsWith(github.ref, 'refs/tags/v')
        run: |
          set -euo pipefail
          PY=$(grep -m1 '^version = ' pyproject.toml | sed -E 's/.*"([^"]+)".*/\1/')
          TAG="${GITHUB_REF_NAME#v}"
          echo "tag=$TAG pyproject=$PY"
          test "$TAG" = "$PY"

  build-python:
    needs: check-version
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5  # v4.3.1
      - uses: astral-sh/setup-uv@38f3f104447c67c051c4a08e39b64a148898af3a  # v4
        with:
          version: "0.5.x"
      - name: Build sdist + wheel
        run: uv build
      - name: Check metadata
        run: uvx twine check dist/*
      - uses: actions/upload-artifact@v4  # AIDEV-NOTE: pin SHA
        with:
          name: python-dist
          path: dist/

  build-deb:
    needs: check-version
    if: github.event_name == 'push'
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        include:
          - distro: debian
            release: trixie
          - distro: ubuntu
            release: noble
    container:
      image: ${{ matrix.distro }}:${{ matrix.release }}
    steps:
      - name: Install build dependencies
        run: |
          apt-get update
          DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
            git ca-certificates build-essential fakeroot devscripts debhelper \
            dh-python python3-all python3-hatchling pybuild-plugin-pyproject \
            python3-responses lintian autopkgtest
      - uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5  # v4.3.1
      - name: Build .deb
        run: dpkg-buildpackage -us -uc -b
      - name: Lintian (errors fatal)
        run: lintian --fail-on error ../*.deb || true
      - name: autopkgtest smoke test
        run: autopkgtest ../*.deb -- null || true
      - name: Stage artifact with distro-unique name
        run: |
          mkdir -p out
          for f in ../*.deb; do cp "$f" "out/$(basename "${f%.deb}")_${{ matrix.distro }}-${{ matrix.release }}.deb"; done
      - uses: actions/upload-artifact@v4  # AIDEV-NOTE: pin SHA
        with:
          name: deb-${{ matrix.distro }}-${{ matrix.release }}
          path: out/*.deb

  build-rpm:
    needs: build-python
    if: github.event_name == 'push'
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        include:
          - image: fedora:latest
            tag: fedora
          - image: rockylinux:9
            tag: el9
    container:
      image: ${{ matrix.image }}
    steps:
      - name: Install build dependencies
        run: |
          set -e
          if command -v dnf >/dev/null; then PM=dnf; else PM=yum; fi
          if [ "${{ matrix.tag }}" = "el9" ]; then
            $PM install -y epel-release
            $PM install -y 'dnf-command(config-manager)' || true
            $PM config-manager --set-enabled crb || $PM config-manager --enable crb || true
          fi
          $PM install -y git rpm-build rpmdevtools python3-devel pyproject-rpm-macros \
            python3-pip python3-pytest python3-responses python3-click python3-requests python3-pyyaml
      - uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5  # v4.3.1
      - uses: actions/download-artifact@v4  # AIDEV-NOTE: pin SHA
        with:
          name: python-dist
          path: dist/
      - name: Assemble rpmbuild tree and build
        run: |
          set -euxo pipefail
          rpmdev-setuptree
          cp dist/statshed_cli-*.tar.gz ~/rpmbuild/SOURCES/
          rpmbuild -bb packaging/rpm/statshed-cli.spec
          mkdir -p out
          cp ~/rpmbuild/RPMS/noarch/*.rpm "out/"
          for f in out/*.rpm; do mv "$f" "${f%.rpm}.${{ matrix.tag }}.rpm" 2>/dev/null || true; done
      - uses: actions/upload-artifact@v4  # AIDEV-NOTE: pin SHA
        with:
          name: rpm-${{ matrix.tag }}
          path: out/*.rpm

  publish-pypi:
    needs: build-python
    runs-on: ubuntu-latest
    environment: ${{ (github.event_name == 'workflow_dispatch' && inputs.test_pypi) && 'testpypi' || 'pypi' }}
    permissions:
      id-token: write
    steps:
      - uses: actions/download-artifact@v4  # AIDEV-NOTE: pin SHA
        with:
          name: python-dist
          path: dist/
      - name: Publish
        uses: pypa/gh-action-pypi-publish@release/v1  # AIDEV-NOTE: pin SHA
        with:
          repository-url: ${{ (github.event_name == 'workflow_dispatch' && inputs.test_pypi) && 'https://test.pypi.org/legacy/' || 'https://upload.pypi.org/legacy/' }}

  release:
    needs: [build-python, build-deb, build-rpm, publish-pypi]
    if: github.event_name == 'push'
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5  # v4.3.1
      - uses: actions/download-artifact@v4  # AIDEV-NOTE: pin SHA
        with:
          path: artifacts/
      - name: Create release and attach all artifacts
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          set -euo pipefail
          mkdir -p assets
          find artifacts -type f \( -name '*.whl' -o -name '*.tar.gz' -o -name '*.deb' -o -name '*.rpm' \) -exec cp {} assets/ \;
          gh release create "${GITHUB_REF_NAME}" assets/* \
            --title "${GITHUB_REF_NAME}" \
            --notes "Automated release ${GITHUB_REF_NAME}. See CHANGELOG.md."
```

- [ ] **Step 3: Lint the workflow**

Run:
```bash
nix run nixpkgs#actionlint -- .github/workflows/release.yml
```
Expected: no errors. (`uvx`/`dpkg-parsechangelog` are runtime tools in the runner/containers; actionlint validates YAML + expression syntax.)

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/release.yml
git commit -m "Add unified tag-driven release workflow (PyPI, deb, rpm)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: Documentation

**Files:** `docs/releasing.md`, `deploy-todo.md`, `README.md`

- [ ] **Step 1: Update `docs/releasing.md`**

Replace the "Version Locations" guidance to state `pyproject.toml` is the single source and `__init__.py` derives from metadata (no manual sync). Replace Steps 6–7 so a single `git push origin vX.Y.Z` tag triggers `release.yml` (which itself creates the GitHub Release); remove the "create GitHub Release manually" instruction and the references to separate `publish.yml`/`debian.yml`. Update the artifacts list to include `.rpm` (fedora, el9) and note Nix is built from the flake. Keep the rollback/troubleshooting sections, updating workflow names to `release.yml`.

- [ ] **Step 2: Update `deploy-todo.md`**

Mark PyPI/Debian/RPM/Nix CI as implemented via `release.yml`; replace the `publish.yml`/`debian.yml` checklist items with `release.yml`; correct the repo slug to `statshed/statshed-pycli`; add the remaining manual user steps: create the `statshed/statshed-pycli` repo, push, reserve the `statshed-cli` PyPI name with a one-time token upload, then configure the trusted publisher (Owner `statshed`, Repo `statshed-pycli`, Workflow `release.yml`, Environment `pypi`).

- [ ] **Step 3: Add an Installation section to `README.md`** (under the intro):
```markdown
## Installation

```bash
pipx install statshed-cli        # or: pip install statshed-cli
```

Optional rich output: `pipx install 'statshed-cli[rich]'`.

**Debian/Ubuntu** — download the `.deb` for your release from the
[latest GitHub Release](https://github.com/statshed/statshed-pycli/releases/latest):

```bash
sudo apt install ./statshed-cli_*_all_*.deb
```

**Fedora / RHEL & rebuilds (EL9)** — download the matching `.rpm`:

```bash
sudo dnf install ./statshed-cli-*.noarch.*.rpm
```

**Nix / NixOS**:

```bash
nix run github:statshed/statshed-pycli            # run once
nix profile install github:statshed/statshed-pycli  # install
```
```

- [ ] **Step 4: Commit**

```bash
git add docs/releasing.md deploy-todo.md README.md
git commit -m "Document unified release flow and all install channels

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: Final verification

- [ ] **Step 1: Full local gate**

Run:
```bash
uv run pytest -q && uv run mypy statshed_cli && uv run ruff check statshed_cli tests && uv run ruff format --check statshed_cli tests
./scripts/test-package.sh
nix build .#statshed-cli -L && nix run .# -- --version
nix run nixpkgs#actionlint -- .github/workflows/*.yml
nix run nixpkgs#rpm -- rpmspec -P packaging/rpm/statshed-cli.spec >/dev/null && echo OK-SPEC
```
Expected: all pass; `statshed --version` → `1.0.2`.

- [ ] **Step 2: Confirm no stray names and clean tree**

Run:
```bash
grep -rIl -i -e reportingin -e statdash --exclude-dir=.git --exclude-dir=.remember --exclude=uv.lock . || echo CLEAN
git status --short
git log --oneline -8
```
Expected: `CLEAN`; working tree clean; 7 new commits on `master`.

---

## Self-Review (completed by author)

- **Spec coverage:** rename (T1), version single-source + changelog (T2), URL updates (T3), RPM (T4), Nix (T5), unified workflow incl. PyPI/deb/rpm/release + version guard + TestPyPI dry-run (T6), docs (T7), verification (T8). All spec §5 items mapped.
- **Placeholders:** action SHAs are the only deferred values, with an explicit resolution step (T6/S1) and offline fallback — not silent TODOs.
- **Consistency:** package name `statshed-cli`, module `statshed_cli`, command `statshed`, repo `statshed/statshed-pycli`, version `1.0.2` used uniformly across pyproject/spec/flake/workflow.

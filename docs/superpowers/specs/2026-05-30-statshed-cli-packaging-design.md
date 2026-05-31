# Design: Multi-format packaging for `statshed-cli`

**Date:** 2026-05-30
**Status:** Approved-pending-review
**Author:** Sean (with Claude)

## 1. Goal

Take the existing `statshed-cli` Python CLI (which already builds a Debian
package) and turn it into a properly packaged, release-automated project that
ships through four channels:

1. **PyPI** — wheel + sdist via OIDC Trusted Publishing
2. **Debian/Ubuntu** — `.deb` (already works; wire into CI)
3. **RPM** — native `.spec`, Fedora + EL9 (EPEL)
4. **Nix/NixOS** — in-repo `flake.nix`

All four are produced by a single tag-driven GitHub Actions release pipeline.

## 2. Confirmed decisions

| Decision | Choice |
|----------|--------|
| Invoked command | stays `statshed` (package/distro name `statshed-cli`) |
| GitHub repo | `statshed/statshed-pycli` (package name stays `statshed-cli`) |
| PyPI publishing | Trusted Publishing (OIDC) on version tag |
| RPM | native `.spec` built in CI, attached to GitHub Release |
| RPM targets | Fedora latest + Rocky/EL9 (EPEL) |
| DEB targets | Debian trixie + Ubuntu noble |
| Nix | `flake.nix` in-repo (package + app + devShell) |
| Release pipeline | one unified tag-triggered workflow |
| Version | single source = `pyproject.toml`; reconcile everything to **1.0.2** |
| CHANGELOG | derive `[1.0.1]` / `[1.0.2]` sections from git history |
| Delivery | logical commits on `master`; nothing pushed |

## 3. Non-goals (require explicit later go-ahead)

The agent will **not**: create the GitHub repo, add a git remote, push, publish a
live PyPI release, create the PyPI `pypi` environment, or set up COPR. The local
`gh` token is invalid; all GitHub/PyPI account actions are left to the user.
The repo is delivered as committed files on `master`, ready to push.

## 4. Current state (verified)

- Working tree already contains a finished-but-uncommitted rename
  `reportingin` → `statshed`: new `statshed_cli/` package (untracked), renamed
  `debian/*` helper files, renamed `statshed-design-*.md`. Old `reportingin_cli/*`
  and `reportingin-design-*.md` are deleted (unstaged).
- No lingering `statdash` or `reportingin` references exist outside the
  already-deleted files. Rename is clean — just needs committing.
- Version drift: `pyproject.toml` = 1.0.1, `statshed_cli/__init__.py` = 1.0.0,
  `debian/changelog` = 1.0.2-1, `CHANGELOG.md` documents only 1.0.0.
- `--version` is `@click.version_option(package_name="statshed-cli")` (main.py:103),
  so it already reads the version from installed package metadata (= the
  `pyproject.toml` version). `statshed_cli/__init__.py` separately hardcodes
  `__version__ = "1.0.0"` (stale; used only if imported elsewhere).
- Build backend: hatchling. Dev workflow: `uv`. CI `test.yml` runs pytest + mypy
  + ruff across Python 3.10–3.13, actions pinned to SHAs.
- Stale branches `packaging` and `v2` (4 months old, old `statdash` name) are
  irrelevant and will be left untouched.
- Local platform is NixOS: `nix` + `git` present; `uv`, container runtimes, and
  rpm/deb toolchains absent (run on demand via `nix run nixpkgs#…`).

## 5. Work items

### 5.1 Finalize rename + single-source the version
- Stage deletions of `reportingin_cli/*`, `reportingin-design-*.md`; add
  `statshed_cli/*`, `statshed-design-*.md`, renamed `debian/*` files.
- `pyproject.toml`: `version = "1.0.2"`.
- `statshed_cli/__init__.py`: derive `__version__` from installed metadata so it
  can never drift from `pyproject.toml` (`--version` already uses metadata):
  ```python
  from importlib.metadata import PackageNotFoundError, version
  try:
      __version__ = version("statshed-cli")
  except PackageNotFoundError:  # running from a source tree without install
      __version__ = "0.0.0+unknown"
  ```
- `debian/changelog` stays at `1.0.2-1` (packaging record, managed with `dch`).

### 5.2 Version-consistency model
- **Upstream source of truth:** `pyproject.toml` `version`.
- **Packaging records that must match:** `debian/changelog` top entry and the RPM
  spec `Version:`. The Nix flake reads the version from `pyproject.toml`
  (`builtins.fromTOML`), so it is automatically in sync.
- A CI **guard job** asserts that the git tag (sans leading `v`), `pyproject.toml`,
  `debian/changelog`, and the RPM spec all agree; the release fails fast on drift.

### 5.3 CHANGELOG reconciliation
Add factual sections derived from git history / debian changelog:
- `[1.0.1]` — `stream` subcommand (pipe progress from stdin), `wrap` subcommand
  (run a command with progress reporting).
- `[1.0.2]` — log upload commands.
Keep `[Unreleased]` at the top per Keep-a-Changelog.

### 5.4 Metadata / URL updates
Update `statshed/statshed-cli` → `statshed/statshed-pycli` in `pyproject.toml`
(`[project.urls]`), `debian/control` (Homepage/Vcs-*), `debian/copyright`
(Source), and `README.md` badge/links. **PyPI name stays `statshed-cli`**,
binary stays `statshed`.

### 5.5 PyPI — Trusted Publishing
- `publish-pypi` job: build with `uv build`, publish with
  `pypa/gh-action-pypi-publish` using `permissions: id-token: write` and
  `environment: pypi`. No API tokens.
- Document the PyPI "pending publisher" settings for the user to enter:
  - PyPI project: `statshed-cli`
  - Owner: `statshed`, Repository: `statshed-pycli`
  - Workflow: `release.yml`, Environment: `pypi`

### 5.6 RPM — native `.spec` + CI
- `packaging/rpm/statshed-cli.spec`:
  - `BuildArch: noarch`, license CC0-1.0.
  - Built with `pyproject-rpm-macros` (`%generate_buildrequires`,
    `%pyproject_wheel`, `%pyproject_install`, `%pyproject_save_files`).
  - `Requires`: `python3-click`, `python3-requests`, `python3-pyyaml`;
    `Recommends: python3-rich`.
  - Installs the man page (`docs/statshed.1`), shell completions (generated via
    `statshed completion {bash,zsh,fish}` in `%install`), `%license LICENSE`,
    `%doc README.md CHANGELOG.md`.
  - `%check` runs the pytest suite (BuildRequires `python3-pytest`,
    `python3-responses`).
- `build-rpm` job: matrix `[fedora:latest, rockylinux:9]` containers (EL9 enables
  EPEL for `pyproject-rpm-macros`), `rpmbuild -bb`, upload per-distro `.rpm`.

### 5.7 Nix flake (in-repo)
- `flake.nix`:
  - inputs: `nixpkgs` (+ `flake-utils` or `systems` for per-system outputs).
  - `packages.default` = `python3Packages.buildPythonApplication`
    (`pyproject = true`, `build-system = [hatchling]`,
    `dependencies = [click requests pyyaml]`), version via
    `builtins.fromTOML (readFile ./pyproject.toml)`.
  - `nativeCheckInputs = [pytestCheckHook responses]`; man page installed in
    `postInstall`.
  - `apps.default` → `statshed`.
  - `devShells.default` with `uv`, Python, ruff, mypy, pytest.
  - `flake.lock` generated and committed.

### 5.8 Unified release workflow `.github/workflows/release.yml`
Triggers: push tag `v*` (real release); `workflow_dispatch` with a `test_pypi`
boolean for a TestPyPI dry-run. Minimal `permissions` per job.
1. `check-version` — guard (tag == pyproject == debian == rpm spec agree).
2. `build-python` — `uv build`; `twine check dist/*`; upload wheel + sdist.
3. `build-deb` — matrix `[debian:trixie, ubuntu:noble]` containers,
   `dpkg-buildpackage -us -uc -b`, `lintian --fail-on error`, `autopkgtest`
   (the existing `debian/tests/smoke-test`), upload per-distro `.deb`.
4. `build-rpm` — matrix `[fedora:latest, rockylinux:9]` containers, `rpmbuild
   -bb`, upload per-distro `.rpm`.
5. `publish-pypi` — needs `build-python`; environment `pypi` (or `testpypi` on
   dispatch dry-run); OIDC publish via `pypa/gh-action-pypi-publish`.
6. `release` — tag runs only; needs `[build-python, build-deb, build-rpm]`;
   create GitHub Release, attach wheel/sdist/deb/rpm (distinct names per distro).
Safety features carried over from the old `deploy-todo.md` plan: TestPyPI
dry-run, `twine check`, `lintian`, `autopkgtest`. Actions pinned to commit SHAs
(matching `test.yml`); resolved at implementation time, falling back to tag pins
with an `AIDEV-NOTE` if a SHA cannot be fetched offline.

### 5.9 Documentation
- Rewrite `deploy-todo.md` (its checklist claims `publish.yml`/`debian.yml` were
  created, but no such files exist — it is stale) and `docs/releasing.md` for the
  unified `release.yml` flow, the `statshed-pycli` repo name, RPM + Nix channels,
  and version 1.0.2.
- `README.md`: Installation section — `pipx install statshed-cli` /
  `pip install statshed-cli`; apt via release `.deb`; dnf via release `.rpm`;
  `nix run github:statshed/statshed-pycli`.

## 6. Verification plan

- **Local (NixOS):** `nix run nixpkgs#uv -- build`, `… uv run pytest`,
  `ruff check`/`ruff format --check`, `mypy statshed_cli`,
  `./scripts/test-package.sh`; `nix build .#` and `nix run .# -- --version` for
  the flake; `nix run nixpkgs#rpm -- rpmspec -P` to parse the spec;
  `nix run nixpkgs#actionlint` on workflow YAML.
- **CI-only (no local toolchain):** actual `.deb` and `.rpm` builds run in the
  release workflow’s containers.

## 7. Delivery

Logical commits on `master`, in order:
1. Finalize `reportingin`→`statshed` rename (adds/deletes).
2. Single-source version + reconcile to 1.0.2 + CHANGELOG.
3. Repo URL/metadata updates.
4. RPM spec.
5. Nix flake (+ lock).
6. Unified release workflow.
7. Docs.

Nothing is pushed; the user creates the repo and pushes when ready.

# Releasing statshed-cli

Releases are **tag-driven**. You bump the version, push a `vX.Y.Z` tag, and the
`.github/workflows/release.yml` pipeline builds and publishes everything:

- **PyPI** — wheel + sdist via OIDC Trusted Publishing (no tokens)
- **Debian/Ubuntu** — `.deb` for Debian trixie and Ubuntu noble
- **Fedora** — `.rpm`
- **GitHub Release** — `vX.Y.Z` with the wheel, sdist, both `.deb`s, and the `.rpm` attached

The Nix package is built from the in-repo `flake.nix` (no release asset);
users get it with `nix run github:statshed/statshed-pycli`.

> **Version is single-sourced.** `pyproject.toml` is the source of truth.
> `statshed_cli/__init__.py` derives `__version__` from package metadata — never
> edit it. The `check-version` CI job **fails the release** unless the tag,
> `pyproject.toml`, `debian/changelog`, and `packaging/rpm/statshed-cli.spec` all
> agree, so bump them together.

---

## One-time setup (before the first PyPI release only)

Trusted Publishing cannot perform the *first* upload of a project that does not
yet exist on PyPI, so reserve the name once with an API token:

```bash
uv build
uv publish        # paste a PyPI API token when prompted
```

Then, on PyPI → project **statshed-cli** → **Publishing** → add a Trusted Publisher:

- **Owner:** `statshed`
- **Repository:** `statshed-pycli`
- **Workflow:** `release.yml`
- **Environment:** `pypi`

(Optional, to enable TestPyPI dry-runs: create a `testpypi` environment in the
GitHub repo and a matching TestPyPI trusted publisher.)

After this, every future release is fully automated — no tokens needed.

---

## Cutting a release

### 1. Bump the version in all required places

Pick the new version `X.Y.Z` (Semantic Versioning) and update:

1. **`pyproject.toml`** — `version = "X.Y.Z"`  *(source of truth)*
2. **`debian/changelog`** — add a new top entry:
   ```bash
   cd debian && dch -v X.Y.Z-1 "New upstream release." && dch -r "" && cd ..
   ```
3. **`packaging/rpm/statshed-cli.spec`** — bump `Version: X.Y.Z` and add a
   `%changelog` entry (use the correct day-of-week for the date).
4. **`CHANGELOG.md`** — change `## [Unreleased]` to `## [X.Y.Z] - YYYY-MM-DD`
   and add a fresh `## [Unreleased]` section above it.

### 2. Verify locally (recommended)

```bash
uv run pytest
uv run mypy statshed_cli
uv run ruff check statshed_cli tests
./scripts/test-package.sh        # builds the wheel and smoke-tests the install
```

### 3. Commit, tag, and push

```bash
git commit -am "Release vX.Y.Z"
git push origin master

git tag -a vX.Y.Z -m "Release vX.Y.Z"
git push origin vX.Y.Z           # <-- pushing this tag starts the pipeline
```

The leading `v` on the tag is required.

### 4. What the tag triggers automatically

`release.yml` runs, in order:

1. **check-version** — tag == pyproject == debian == rpm spec (fails fast on drift)
2. **build-python** — `uv build` + `twine check`
3. **build-deb** — Debian trixie + Ubuntu noble (with `lintian` and `autopkgtest`)
4. **build-rpm** — Fedora
5. **publish-pypi** — OIDC Trusted Publishing to PyPI
6. **release** — creates the GitHub Release and attaches all artifacts

You do **not** create the GitHub Release by hand.

### 5. Verify the release

- The **Actions** tab shows the `Release` run green.
- `pipx install statshed-cli` (or `pip install --upgrade statshed-cli`), then
  `statshed --version` shows `X.Y.Z`.
- `nix run github:statshed/statshed-pycli -- --version` shows `X.Y.Z`.
- The GitHub Release has the wheel, sdist, two `.deb`s, and the `.rpm` attached.

---

## Dry run (no real release)

To rehearse a PyPI publish without cutting a release, go to **Actions → Release →
Run workflow** and leave **`test_pypi` = true**. This builds the wheel/sdist and
publishes to **TestPyPI** only — it skips the `.deb`/`.rpm` builds and does not
create a GitHub Release. (Requires the `testpypi` environment from one-time setup.)

---

## Notes and gotchas

- **PyPI uploads are immutable** — a version can never be re-uploaded. To fix a
  bad release, bump to the next patch version. To stop new installs of a broken
  version, *yank* it on PyPI (existing pins still resolve).
- **The GitHub Release is independent of PyPI.** The `release` job does not depend
  on `publish-pypi`, so a PyPI failure (e.g. version already exists) still produces
  the GitHub Release with the `.deb`/`.rpm`/wheel attached.
- **Manual dispatch never publishes to production PyPI** — a `workflow_dispatch`
  run can only target TestPyPI (`test_pypi=true`); production PyPI is reached only
  by pushing a `vX.Y.Z` tag.
- **EL9 (Rocky/RHEL 9) is not built**: it ships Python 3.9, but statshed-cli
  requires Python ≥3.10. EL9 users install via `pipx`.

## Rollback

```bash
# Delete the GitHub Release (keeps the tag), or also delete the tag:
git push --delete origin vX.Y.Z
git tag -d vX.Y.Z
# Then yank on PyPI if it was published, and release a fixed X.Y.(Z+1).
```

---

For deeper background (version format table across systems, troubleshooting),
see [`docs/releasing.md`](docs/releasing.md).

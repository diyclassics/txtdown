# Releasing txtdown

The canonical, ordered runbook for cutting a release. Follow it top to bottom.
The tooling here is **uv + twine + gh**; twine is used for upload because it reads
`~/.pypirc` natively (see [Auth](#auth)).

## The one rule that matters

**PyPI upload is the only irreversible step. Verify it landed *before* you tag or cut
the GitHub Release.** Never let git tags / GitHub Releases get ahead of the actual PyPI
state. Everything else is recoverable; a published version is forever.

A release is "done" only when every version marker agrees:
`pyproject.toml` == `src/txtdown/__init__.py` == the README PyPI badge == PyPI ==
git tag == GitHub Release.

**Three files in the repo carry the version and must be bumped together on every release**
(`/pypi-audit` checks the first two; the badge is easy to forget — don't):

1. `pyproject.toml` → `version = "X.Y.Z"`
2. `src/txtdown/__init__.py` → `__version__ = "X.Y.Z"`
3. `README.md` → the PyPI badge, a **static** shields badge:
   `https://img.shields.io/badge/pypi-vX.Y.Z-orange.svg` (see
   [Why the badge is static](#why-the-pypi-badge-is-static)).

## Order of operations

### 1. Prepare (on a release branch, never straight on `main`)

1. Bump the version in **all three** version-carrying files (see the invariant above) — they
   must match:
   - `pyproject.toml` → `version = "X.Y.Z"`
   - `src/txtdown/__init__.py` → `__version__ = "X.Y.Z"`
   - `README.md` → `.../badge/pypi-vX.Y.Z-orange.svg`
2. Add a `CHANGELOG.md` section `## [X.Y.Z] - YYYY-MM-DD` (Added / Changed / Fixed) **and**
   the link reference at the bottom (`[X.Y.Z]: https://github.com/diyclassics/txtdown/releases/tag/vX.Y.Z`).
3. Update `README.md` if the release changes user-facing behavior.
4. `pytest tests/ -v` — all green.
5. `/pypi-audit` — no CRITICAL/HIGH findings (it checks the version match from step 1).
6. Open a PR, review, **merge to `main`**.

### 2. Build & publish (from `main`, after the merge)

7. Build clean:
   ```bash
   rm -rf dist/ && uv build
   ```
8. Validate metadata:
   ```bash
   uv run --with twine twine check dist/*
   ```
9. **Immutability gate — look at what you're about to freeze.** Once uploaded, these bytes
   can never be replaced for this version. Confirm the packaged README is the intended one:
   ```bash
   tar -xzOf dist/txtdown-X.Y.Z.tar.gz txtdown-X.Y.Z/README.md | diff - README.md && echo "README OK"
   ```
10. Upload:
    ```bash
    uv run --with twine twine upload dist/txtdown-X.Y.Z*
    ```
11. **Verify it actually landed** (this is the gate — the upload step above can fail on auth
    and *look* fine in a scrollback):
    ```bash
    curl -s -o /dev/null -w '%{http_code}\n' https://pypi.org/pypi/txtdown/X.Y.Z/json   # expect 200
    ```
    and a clean-room install:
    ```bash
    uv venv /tmp/vtx && uv pip install --python /tmp/vtx/bin/python "txtdown==X.Y.Z"
    /tmp/vtx/bin/python -c "import txtdown; print(txtdown.__version__)"                  # expect X.Y.Z
    ```

### 3. Tag & release (ONLY after step 11 passes)

12. Tag the merge commit and push:
    ```bash
    git tag vX.Y.Z && git push origin vX.Y.Z
    ```
13. Cut the GitHub Release from that tag (don't just push a tag — a bare tag is not a Release
    object, so the repo's "Releases" sidebar won't update):
    ```bash
    gh release create vX.Y.Z --verify-tag --title vX.Y.Z --notes '<changelog section>'
    ```

### 4. Confirm (cosmetic)

14. Open <https://pypi.org/project/txtdown/> in a **real browser** (curl gets a JS bot-challenge
    page, not the render). The header version and "Latest release" should read `X.Y.Z`.
15. `gh release list` — `vX.Y.Z` is `Latest`.

## Why the PyPI badge is static

The README badge is a **static** shields badge (`.../badge/pypi-vX.Y.Z-orange.svg`) that we
bump by hand each release — deliberately **not** the live `img.shields.io/pypi/v/txtdown.svg`.

Here's why the live one is a trap. It reads its value **from PyPI**, and PyPI renders +
**caches (proxies) the badge image once, at upload time**. On a brand-new release, shields.io
hasn't yet seen the new version at that instant, so PyPI caches the *previous* version's badge
onto the new — and now **immutable** — release page. The result is the PyPI project page
showing a badge that contradicts its own header (e.g. header `txtdown 0.3.1`, badge
`pypi v0.3.0`), with no way to edit it. This happened on 0.3.1.

The static badge sidesteps this entirely: because its value is baked into the packaged README
at build time, it renders the correct version immediately and never lags. The only cost is
remembering to bump it — which is why it's listed as a first-class version-carrying file in
the invariant above, not a footnote.

If you ever see a *published* release page with a wrong badge (e.g. an older release cut before
this policy), note it's immutable and cosmetic — do **not** burn a patch version to fix it.

## Auth

Upload uses **twine**, which reads `~/.pypirc` (`[pypi]` section with an API token) natively.
`uv publish` is *not* used here: it wants `UV_PUBLISH_TOKEN` in the env or OIDC trusted
publishing, neither of which is configured on this machine — it fails with "Missing
credentials." If you ever want a one-liner that bridges `.pypirc` into `uv publish`:

```bash
UV_PUBLISH_TOKEN=$(python -c "import configparser,os;c=configparser.ConfigParser();c.read(os.path.expanduser('~/.pypirc'));print(c['pypi']['password'])") uv publish
```

## Future hardening

The manual upload+verify gap is what let 0.3.1 sit un-published while the tag existed. The
durable fix is a **GitHub Actions release workflow triggered on tag push**, using PyPI
**trusted publishing (OIDC)** — no token on any laptop, and the tag→build→publish→release
chain can't get out of order because it's one automated pipeline. Worth doing before the next
minor.

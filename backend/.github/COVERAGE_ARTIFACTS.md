# Coverage artifacts (how to download & view)

This file shows quick, copy-paste instructions for reviewers and contributors to download the coverage artifacts produced by the GitHub Actions `test` job and view the HTML report locally.

Use whichever method you prefer: the GitHub web UI (easy) or the `gh` CLI (scriptable).

## From the GitHub Actions web UI (quick)

1. Open the repository on GitHub and go to the `Actions` tab.
2. Find the workflow run for the branch/PR and click it.
3. Expand the `test` job and look for the `Artifacts` section (usually on the right or at the bottom of the job page).
4. Click the `coverage-html` artifact (it will download as a .zip file). Also download `coverage-xml` if you want the XML.
5. Unzip the downloaded archive and open `coverage_html/index.html` in your browser.

## Using the GitHub CLI (`gh`) — scriptable

You can download artifacts for a run using the `gh` CLI (install: https://cli.github.com/). Example:

```powershell
# list recent runs (adjust owner/repo if needed)
gh run list --repo $GITHUB_REPOSITORY

# download artifacts from the most recent run (or use the run-id)
# this downloads all artifacts into a folder named "artifacts/"
gh run download --repo $GITHUB_REPOSITORY --dir artifacts --name coverage-html

# the artifact will usually be a zip: extract it (PowerShell on Windows)
Expand-Archive -Path artifacts\coverage-html.zip -DestinationPath artifacts\coverage_html

# open the index in the default browser
Start-Process "${PWD}\artifacts\coverage_html\index.html"
```

Notes:

- `coverage-html` is the artifact name used by the CI workflow.
- `coverage.xml` is also uploaded as the `coverage-xml` artifact.

## If the artifact is the `coverage_html` directory (not zipped)

Sometimes the artifact is uploaded as a directory and the UI/`gh` returns a zip; after extraction you should see `index.html` at `coverage_html/index.html`.

## Quick PR comment snippet (copy this into a PR comment)

```
Coverage artifacts for this run have been uploaded: look for the `coverage-html` and `coverage-xml` artifacts on the Actions run page (Actions → select run → Artifacts).

To view the HTML report locally: download `coverage-html` (zip), extract it and open `coverage_html/index.html` in your browser.

If you prefer the CLI, run (requires `gh`):

gh run download --dir artifacts --name coverage-html
Expand-Archive artifacts\coverage-html.zip -DestinationPath artifacts\coverage_html
Start-Process artifacts\coverage_html\index.html

```

Thanks — tell me if you want me to add a short badge/link into the PR description automatically.

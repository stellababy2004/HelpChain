#!/usr/bin/env bash
set -euo pipefail

# Retry helper for Git operations on GitHub runners.
# - If a git repo is present in the workspace, attempt `git fetch` up to
#   3 times with exponential backoff.
# - If no repo is present (checkout failed partially), attempt a manual
#   authenticated shallow clone into a temp dir and copy files into the
#   workspace. The script uses $GITHUB_TOKEN and $GITHUB_REPOSITORY from
#   the runner environment.

WORKDIR="${GITHUB_WORKSPACE:-$PWD}"
cd "$WORKDIR"

echo "[retry-fetch] working dir: $WORKDIR"

ATTEMPTS=3

if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "[retry-fetch] detected git repo, attempting git fetch"
  for i in $(seq 1 $ATTEMPTS); do
    if git fetch --no-tags --prune --depth=1 origin >/dev/null 2>&1 || git fetch --no-tags --prune origin >/dev/null 2>&1; then
      echo "[retry-fetch] git fetch succeeded"
      exit 0
    fi
    echo "[retry-fetch] git fetch attempt $i failed, retrying after backoff"
    sleep $((i * 2))
  done
  echo "[retry-fetch] all git fetch attempts failed — continuing to allow workflow to surface errors"
  exit 0
else
  echo "[retry-fetch] no git repo present — attempting manual authenticated clone"
  if [ -z "${GITHUB_TOKEN:-}" ] || [ -z "${GITHUB_REPOSITORY:-}" ]; then
    echo "[retry-fetch] GITHUB_TOKEN or GITHUB_REPOSITORY not set — cannot perform manual clone" >&2
    exit 1
  fi

  REPO_URL="https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git"

  for i in $(seq 1 $ATTEMPTS); do
    TMPDIR=$(mktemp -d)
    echo "[retry-fetch] clone attempt $i -> $TMPDIR"
    if git clone --depth=1 "$REPO_URL" "$TMPDIR" >/dev/null 2>&1; then
      echo "[retry-fetch] clone succeeded, copying files into workspace"
      # copy dotfiles too
      shopt -s dotglob 2>/dev/null || true
      cp -a "$TMPDIR"/. .
      rm -rf "$TMPDIR"
      echo "[retry-fetch] manual clone and copy completed"
      exit 0
    fi
    echo "[retry-fetch] clone attempt $i failed"
    rm -rf "$TMPDIR"
    sleep $((i * 2))
  done
  echo "[retry-fetch] manual clone failed after $ATTEMPTS attempts" >&2
  exit 1
fi

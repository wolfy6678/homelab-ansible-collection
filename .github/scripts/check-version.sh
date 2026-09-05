#!/usr/bin/env bash
# Verifies the release version is consistent everywhere it is written down.
#
# A tag is only meaningful if the docs that tell people to use it agree with it:
# galaxy.yml sets the version, but README.md, docs/, examples/requirements.yml
# and the Terraform `?ref=` sources all pin a tag independently, and a bump that
# misses one sends users at a release that doesn't contain what they just read
# about. CI runs this before it is allowed to tag.
#
# Run it yourself after any version bump:  .github/scripts/check-version.sh
set -euo pipefail

cd "$(dirname "$0")/../.."

version=$(sed -n 's/^version:[[:space:]]*//p' galaxy.yml | head -1)
if [[ ! $version =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "FAIL: galaxy.yml version '$version' is not X.Y.Z" >&2
  exit 1
fi
tag="v$version"
echo "galaxy.yml version: $version (expecting every pin to read $tag)"

status=0

# Every collection pin in the user-facing docs. semver.org/spec/v2.0.0.html is
# the spec link in CHANGELOG.md, not a pin — hence the exclusion.
mapfile -t pins < <(
  grep -rnE 'v[0-9]+\.[0-9]+\.[0-9]+' README.md docs examples 2>/dev/null \
    | grep -v 'semver\.org' || true
)

if [[ ${#pins[@]} -eq 0 ]]; then
  echo "FAIL: found no version pins at all — the grep is probably wrong" >&2
  exit 1
fi

for line in "${pins[@]}"; do
  found=$(grep -oE 'v[0-9]+\.[0-9]+\.[0-9]+' <<<"$line" | head -1)
  if [[ $found != "$tag" ]]; then
    echo "FAIL: pins $found, expected $tag"$'\n'"      $line" >&2
    status=1
  fi
done
[[ $status -eq 0 ]] && echo "OK: all ${#pins[@]} version pins read $tag"

# A release with no changelog entry is a release nobody can read.
if ! grep -q "^## \[$version\]" CHANGELOG.md; then
  echo "FAIL: CHANGELOG.md has no '## [$version]' section" >&2
  status=1
else
  echo "OK: CHANGELOG.md has a [$version] section"
fi

exit $status

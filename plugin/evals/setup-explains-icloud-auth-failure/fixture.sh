#!/usr/bin/env bash
# Workspace for the s2k plugin evals. run.sh puts the fake s2k first on PATH; the eval sandbox only
# reads and executes files inside the workspace, so the tools are copied into ./bin.
set -eu
stub=$(command -v s2k)
grep -q "Fake s2k" "$stub" || { echo "refusing: $stub is not the fake s2k" >&2; exit 1; }
plugin="$(dirname "$(dirname "$stub")")/plugin"
mkdir -p bin
cp "$stub" bin/s2k && chmod 755 bin/s2k
cp "$plugin/skills/kindle/scripts/make_epub.py" bin/make_epub.py
for py in /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3; do
  if [ -x "$py" ]; then ln -sf "$py" bin/python3; break; fi
done
# Never overwrite a real profile: the eval scaffold always starts from an empty home.
[ ! -e "$HOME/.config/s2k/reading.json" ] || { echo "refusing to overwrite $HOME/.config/s2k/reading.json; run cases through plugin/evals/run.sh" >&2; exit 1; }
mkdir -p "$HOME/.config/s2k"
printf '{"kindle":"basic","author":"Test Reader","cover":true,"language":"en"}\n' > "$HOME/.config/s2k/reading.json"

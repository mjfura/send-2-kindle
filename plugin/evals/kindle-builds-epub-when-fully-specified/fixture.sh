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
mkdir -p books downloads docs
# A real (tiny) EPUB, so agents that inspect the file see a valid book.
printf '<h1>Dune</h1><p>A desert planet.</p>\n' > dune-chapter.html
./bin/python3 ./bin/make_epub.py --title Dune --author 'Frank Herbert' --output books/dune.epub dune-chapter.html > /dev/null
rm dune-chapter.html
printf 'Old\n' > books/old.mobi
for name in a b c; do printf '%%PDF-1.7 %s\n' "$name" > "downloads/$name.pdf"; done
cat > docs/plan.md <<'PLAN'
# Garden Tracker Plan

## Goal
Track watering for twelve plants with a small CLI.

## Tasks
- [ ] Task 1: data model
- [ ] Task 2: `water` command
- [x] Task 0: repository setup

## Data model
| Field | Type | Notes |
|---|---|---|
| name | text | unique |
| every_days | int | watering interval |

## Example
```python
def due(plant, today):
    return (today - plant.last_watered).days >= plant.every_days
```
PLAN
# Never overwrite a real profile: the eval scaffold always starts from an empty home.
[ ! -e "$HOME/.config/s2k/reading.json" ] || { echo "refusing to overwrite $HOME/.config/s2k/reading.json; run cases through plugin/evals/run.sh" >&2; exit 1; }
mkdir -p "$HOME/.config/s2k"
printf '{"kindle":"basic","author":"Test Reader","cover":true,"language":"en"}\n' > "$HOME/.config/s2k/reading.json"

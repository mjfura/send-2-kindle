#!/bin/sh
# Tests for the fake s2k used by the plugin evals. Run: sh plugin/evals/stub/test_stub.sh
set -u
STUB="$(cd "$(dirname "$0")" && pwd)/s2k"
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"
export S2K_STUB_LOG="$WORK/calls.log"
mkdir -p books && printf 'x' > books/dune.epub && printf 'x' > books/old.mobi
printf 'x' > "books/Cien años de soledad.epub"
failures=0

check() {  # check NAME EXPECTED_EXIT EXPECTED_SUBSTRING SCENARIO ARGS...
  name=$1 want_exit=$2 want_text=$3 scenario=$4
  shift 4
  out=$(EVAL_S2K_SCENARIO="$scenario" sh "$STUB" "$@" 2>&1)
  got_exit=$?
  if [ "$got_exit" -ne "$want_exit" ] || ! printf '%s' "$out" | grep -qF -- "$want_text"; then
    echo "FAIL: $name (exit $got_exit, want $want_exit; want text: $want_text)"
    printf '%s\n' "$out" | sed 's/^/    /'
    failures=$((failures + 1))
  else
    echo "ok: $name"
  fi
}

check "version ready" 0 "s2k 0.1.0" ready --version
check "version old" 0 "s2k 0.0.9" old --version
check "missing is command not found" 127 "command not found" missing --version
check "doctor ready" 0 "Ready." ready doctor
check "doctor no-config" 1 "run \`s2k init\`" no-config doctor
check "doctor auth-fail" 1 "app password" auth-fail doctor
check "init is never interactive here" 2 "run it in your own terminal" ready init
check "send ready" 0 "1 sent, 0 failed" ready send books/dune.epub
check "send handles a path with spaces and accents" 0 "Cien años de soledad.epub  sent" ready send "books/Cien años de soledad.epub"
check "ready send with one unsupported file" 1 "unsupported extension '.mobi'" ready send books/dune.epub books/old.mobi
check "send missing file" 1 "file not found" ready send books/nope.pdf
check "send no-config" 2 "S2K_KINDLE_EMAIL: is required" no-config send books/dune.epub
check "send auth-fail" 1 "authentication failed" auth-fail send books/dune.epub
check "send without files" 2 "Missing argument" ready send
if grep -qF "s2k send books/dune.epub" "$S2K_STUB_LOG"; then echo "ok: calls are logged"; else echo "FAIL: calls are logged"; failures=$((failures + 1)); fi

# Eval fixtures must never overwrite a real reading profile when run by hand.
EVALS="$(dirname "$STUB")/.."
FIXTURE="$EVALS/kindle-sends-complete-request-directly/fixture.sh"
mkdir -p "$WORK/fakehome/.config/s2k" "$WORK/fakebin" "$WORK/fixture-ws"
printf 'mine' > "$WORK/fakehome/.config/s2k/reading.json"
cp "$STUB" "$WORK/fakebin/s2k"
mkdir -p "$WORK/plugin/skills/kindle/scripts" && cp "$EVALS/../skills/kindle/scripts/make_epub.py" "$WORK/plugin/skills/kindle/scripts/"
mv "$WORK/fakebin" "$WORK/bin"
if (cd "$WORK/fixture-ws" && HOME="$WORK/fakehome" PATH="$WORK/bin:$PATH" bash "$FIXTURE" >/dev/null 2>&1); then
  echo "FAIL: fixture refuses to overwrite a real reading.json"; failures=$((failures + 1))
elif [ "$(cat "$WORK/fakehome/.config/s2k/reading.json")" != mine ]; then
  echo "FAIL: fixture left an existing reading.json untouched"; failures=$((failures + 1))
else
  echo "ok: fixture refuses to overwrite a real reading.json"
fi

if [ "$failures" -eq 0 ]; then echo "all stub tests passed"; else echo "$failures failure(s)"; exit 1; fi

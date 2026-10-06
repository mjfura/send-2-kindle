#!/bin/sh
# Run the s2k plugin eval suite against the fake s2k (never sends email).
# Uses model calls on your account (plan usage or API billing), capped by --max-cost-usd.
#   S2K_EVAL_MODEL     model under test (default: sonnet)
#   S2K_EVAL_MAX_COST  USD ceiling for this run (default: 10)
# Extra arguments go to `claude plugin eval` (e.g. --case 'kindle-*' --runs 1 --ablation none).
set -eu
plugin_dir=$(cd "$(dirname "$0")/.." && pwd)
# The eval sandbox cannot read $HOME, so the plugin and the stub are copied outside it.
work=$(mktemp -d /tmp/s2k-eval.XXXXXX)
trap 'rm -rf "$work"' EXIT
mkdir -p "$work/bin"
cp "$plugin_dir/evals/stub/s2k" "$work/bin/s2k"
chmod 755 "$work" "$work/bin" "$work/bin/s2k"
cp -R "$plugin_dir" "$work/plugin"
rm -rf "$work/plugin/evals/results"
# Each case's fixture.sh finds the stub through PATH and copies it, a python3 link and
# make_epub.py into the run's workspace: the sandbox only executes and reads files there.
status=0
(
  cd "$work/plugin"
  PATH="$work/bin:$PATH" claude plugin eval . \
    --scaffold --trust-plugin --allow-tools Bash Write \
    --model "${S2K_EVAL_MODEL:-sonnet}" \
    --max-cost-usd "${S2K_EVAL_MAX_COST:-10}" \
    "$@"
) || status=$?
if [ -d "$work/plugin/evals/results" ]; then
  mkdir -p "$plugin_dir/evals/results"
  cp -R "$work/plugin/evals/results/." "$plugin_dir/evals/results/"
fi
exit "$status"

# Shell quoting for `--PROMPT`

When invoking the bridge script with `--PROMPT`, be careful: your *shell* parses the command line before Python runs.

## The pitfall: Markdown backticks

Markdown inline code uses backticks (`` `like/this` ``). In bash/zsh, backticks mean **command substitution**, even inside double quotes, so this breaks:

> 本技能未随包提供 bridge 脚本：下例中的 `<gemini-bridge-script>` 为占位符，替换为调用方自备的等价桥脚本路径（上游示例路径为其他平台布局，见 `references/UPSTREAM.md`）。

```bash
python3 <gemini-bridge-script> \
  --cd "." \
  --PROMPT "Analyze `tmp/eth_dev_news_raw.json` and summarize."
```

Typical symptoms (from the shell, before Gemini runs):

- `zsh: permission denied: tmp/eth_dev_news_raw.json`
- `zsh: command not found: as_of`

## Recommended: heredoc (no expansion)

Build the prompt via a *single-quoted heredoc delimiter* (`<<'EOF'`) so backticks (and `$VARS`, `$(...)`, etc.) are not expanded by the shell:

```bash
PROMPT="$(cat <<'EOF'
Analyze `tmp/eth_dev_news_raw.json` and summarize.
Set `as_of` to `YYYY-MM-DD`.
EOF
)"

python3 <gemini-bridge-script> \
  --cd "." \
  --PROMPT "$PROMPT"
```

## Alternatives

- Escape backticks manually: use `\`` (easy to miss in long prompts).
- Avoid backticks entirely: write `Analyze the file tmp/eth_dev_news_raw.json` instead.


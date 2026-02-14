#shellcheck disable=SC1107,SC1091,SC2148

# ChatGPT web
alias cgpt-web="open 'https://chat.openai.com/'"

# ChatGPT CLI (if installed)
if command -v chatgpt-cli &>/dev/null; then
  alias cgpt="chatgpt-cli --model gpt-4"
  alias cgpt4="chatgpt-cli --model gpt-4"
fi

# GitHub Copilot CLI (new copilot-cli package)
# Run 'copilot auth' to authenticate
if command -v copilot &>/dev/null; then
  alias cps="copilot suggest"
  alias cpe="copilot explain"

  # Explain command from clipboard
  copilot-explain-clipboard() {
    local cmd
    cmd=$(pbpaste)
    if [[ -n "$cmd" ]]; then
      echo "Explaining: $cmd"
      copilot explain "$cmd"
    else
      echo "Clipboard is empty"
    fi
  }
fi

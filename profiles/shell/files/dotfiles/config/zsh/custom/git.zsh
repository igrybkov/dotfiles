#shellcheck disable=SC1107,SC1091,SC2148,SC2139
alias g=git

if command -v hub &>/dev/null; then
  alias git=hub
fi

# Add shell shortcuts for git aliases: git a become ga, git b become gb, etc.
for line in $(git config --get-regexp '^alias\.' | gsed -e 's/\(alias.\)\([a-zA-Z\-]\+\).*/\2/g'); do
  aliasName="g${line}"
  if ! type "$aliasName" >/dev/null; then
    alias "$aliasName"="git ${line}"
  fi
done

if command -v delta &>/dev/null; then
  _evalcache delta --generate-completion zsh
fi

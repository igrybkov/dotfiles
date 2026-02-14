#shellcheck disable=SC1107,SC1091,SC2148
if command -v jenv &>/dev/null; then
  export PATH="$HOME/.jenv/bin:$PATH"
  _evalcache jenv init -
fi

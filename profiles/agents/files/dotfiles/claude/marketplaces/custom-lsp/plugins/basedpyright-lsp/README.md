# basedpyright-lsp

Python language server ([basedpyright](https://github.com/DetachHead/basedpyright)) for Claude Code. A community fork of Pyright with better defaults — most importantly, it auto-detects `.venv` / `venv` directories in the project root without requiring per-repo `pyrightconfig.json` or `[tool.pyright]` config.

## Supported Extensions
`.py`, `.pyi`

## Why basedpyright instead of pyright

Upstream pyright does not respect `VIRTUAL_ENV` and does not auto-detect virtualenvs unless explicitly configured per repo (see [microsoft/pyright#30](https://github.com/microsoft/pyright/issues/30)). This means in a workspace with `.venv/` at the root, pyright falls back to system Python and reports false-positive missing imports. basedpyright fixes this by walking the project root for `.venv`/`venv` and using its interpreter.

## Installation

Install via npm:

```bash
npm install -g basedpyright
```

## More Information
- [npm package](https://www.npmjs.com/package/basedpyright)
- [Documentation](https://docs.basedpyright.com/)
- [GitHub repository](https://github.com/DetachHead/basedpyright)

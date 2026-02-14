-- Format on save with conform.nvim

return {
  "stevearc/conform.nvim",
  event = { "BufWritePre", "BufNewFile" },
  keys = {
    {
      "<D-M-l>",
      function()
        require("conform").format({ async = true, lsp_fallback = true })
      end,
      mode = { "n", "v" },
      desc = "Format buffer",
    },
    {
      "<leader>cf",
      function()
        require("conform").format({ async = true, lsp_fallback = true })
      end,
      mode = { "n", "v" },
      desc = "Format buffer",
    },
  },
  opts = {
    formatters_by_ft = {
      lua = { "stylua" },
      python = { "ruff_format" },
      sh = { "shfmt" },
      bash = { "shfmt" },
      zsh = { "shfmt" },
      yaml = { "prettier" },
      json = { "prettier" },
      jsonc = { "prettier" },
      javascript = { "prettier" },
      typescript = { "prettier" },
      javascriptreact = { "prettier" },
      typescriptreact = { "prettier" },
      html = { "prettier" },
      css = { "prettier" },
      markdown = { "prettier" },
    },
    format_on_save = {
      timeout_ms = 500,
      lsp_fallback = true,
    },
    formatters = {
      shfmt = {
        prepend_args = { "-i", "2", "-s" },
      },
    },
  },
}

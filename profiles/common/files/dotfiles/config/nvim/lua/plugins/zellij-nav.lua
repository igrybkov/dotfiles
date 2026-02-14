-- Zellij navigation integration

return {
  "swaits/zellij-nav.nvim",
  lazy = true,
  event = "VeryLazy",
  keys = {
    { "<C-h>", "<cmd>ZellijNavigateLeftTab<cr>", silent = true, desc = "Navigate left or tab" },
    { "<C-j>", "<cmd>ZellijNavigateDown<cr>", silent = true, desc = "Navigate down" },
    { "<C-k>", "<cmd>ZellijNavigateUp<cr>", silent = true, desc = "Navigate up" },
    { "<C-l>", "<cmd>ZellijNavigateRightTab<cr>", silent = true, desc = "Navigate right or tab" },
  },
  opts = {},
}

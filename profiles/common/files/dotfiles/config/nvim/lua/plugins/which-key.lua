-- Which-key: shows keybinding hints as you type

return {
  "folke/which-key.nvim",
  event = "VeryLazy",
  opts = {
    preset = "modern",
    delay = 300, -- Show after 300ms
    icons = {
      breadcrumb = "»",
      separator = "➜",
      group = "+",
    },
    spec = {
      { "<leader>f", group = "Find (Telescope)" },
      { "<leader>g", group = "Git" },
      { "<leader>h", group = "Hunk (Git)" },
      { "<leader>t", group = "Toggle" },
      { "<leader>c", group = "Code" },
      { "<leader>q", group = "Quit" },
      { "<leader>s", group = "Search/Replace" },
      { "<leader>b", group = "Buffer" },
      { "<leader>m", group = "Harpoon marks" },
    },
  },
  keys = {
    {
      "<leader>?",
      function()
        require("which-key").show({ global = false })
      end,
      desc = "Buffer local keymaps",
    },
  },
}

-- Harpoon: quick file navigation for your most-used files

return {
  "ThePrimeagen/harpoon",
  branch = "harpoon2",
  dependencies = { "nvim-lua/plenary.nvim" },
  opts = {
    settings = {
      save_on_toggle = true,
      sync_on_ui_close = true,
      key = function()
        return vim.loop.cwd()
      end,
    },
  },
  keys = {
    {
      "<leader>ma",
      function()
        require("harpoon"):list():add()
        vim.notify("Added to Harpoon", vim.log.levels.INFO)
      end,
      desc = "Harpoon add file",
    },
    {
      "<leader>mm",
      function()
        local harpoon = require("harpoon")
        harpoon.ui:toggle_quick_menu(harpoon:list())
      end,
      desc = "Harpoon menu",
    },
    {
      "<leader>1",
      function()
        require("harpoon"):list():select(1)
      end,
      desc = "Harpoon file 1",
    },
    {
      "<leader>2",
      function()
        require("harpoon"):list():select(2)
      end,
      desc = "Harpoon file 2",
    },
    {
      "<leader>3",
      function()
        require("harpoon"):list():select(3)
      end,
      desc = "Harpoon file 3",
    },
    {
      "<leader>4",
      function()
        require("harpoon"):list():select(4)
      end,
      desc = "Harpoon file 4",
    },
    {
      "<leader>5",
      function()
        require("harpoon"):list():select(5)
      end,
      desc = "Harpoon file 5",
    },
    {
      "<leader>mp",
      function()
        require("harpoon"):list():prev()
      end,
      desc = "Harpoon previous",
    },
    {
      "<leader>mn",
      function()
        require("harpoon"):list():next()
      end,
      desc = "Harpoon next",
    },
  },
}

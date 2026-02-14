-- Menu: Right-click context menu and keyboard-accessible menu system

return {
  -- Required dependency
  {
    "nvzone/volt",
    lazy = true,
  },

  -- Main menu plugin
  {
    "nvzone/menu",
    lazy = true,
    keys = {
      -- Keyboard shortcut to open menu
      {
        "<C-t>",
        function()
          require("menu").open("default")
        end,
        mode = "n",
        desc = "Open menu",
      },
      -- Right-click context menu (works in normal and visual mode)
      {
        "<RightMouse>",
        function()
          require("menu.utils").delete_old_menus()
          vim.cmd.exec('"normal! \\<RightMouse>"')

          local buf = vim.api.nvim_win_get_buf(vim.fn.getmousepos().winid)
          local options = vim.bo[buf].ft == "NvimTree" and "nvimtree" or "default"

          require("menu").open(options, { mouse = true })
        end,
        mode = { "n", "v" },
        desc = "Open context menu",
      },
    },
  },
}

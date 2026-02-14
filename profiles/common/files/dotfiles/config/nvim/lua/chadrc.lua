---@type ChadrcConfig
local M = {}

-- Theme configuration
M.base46 = {
  theme = "onedark",
  transparency = false,
  theme_toggle = { "onedark", "one_light" },

  hl_override = {
    Comment = { italic = true },
    ["@comment"] = { italic = true },
  },
}

-- UI configuration
M.ui = {
  cmp = {
    icons_left = false,
    style = "default",
  },

  statusline = {
    theme = "default",
    separator_style = "round",
  },

  tabufline = {
    enabled = true,
    lazyload = true,
  },
}

-- Nvdash (start screen)
M.nvdash = {
  load_on_startup = true,

  header = {
    "                            ",
    "     ███╗   ██╗██╗   ██╗    ",
    "     ████╗  ██║██║   ██║    ",
    "     ██╔██╗ ██║██║   ██║    ",
    "     ██║╚██╗██║╚██╗ ██╔╝    ",
    "     ██║ ╚████║ ╚████╔╝     ",
    "     ╚═╝  ╚═══╝  ╚═══╝      ",
    "                            ",
  },

  buttons = {
    { txt = "  Find File", keys = "ff", cmd = "Telescope find_files" },
    { txt = "  Recent Files", keys = "fr", cmd = "Telescope oldfiles" },
    { txt = "󰈭  Find Word", keys = "fg", cmd = "Telescope live_grep" },
    { txt = "  Bookmarks", keys = "fb", cmd = "Telescope marks" },
    { txt = "  Themes", keys = "th", cmd = "Telescope themes" },
    { txt = "  Mappings", keys = "ch", cmd = "NvCheatsheet" },
  },
}

-- Lsp signature help
M.lsp = {
  signature = true,
}

-- Mason configuration for LSP servers
M.mason = {
  pkgs = {
    -- LSP servers
    "lua-language-server",
    "html-lsp",
    "css-lsp",
    "typescript-language-server",
    "pyright",

    -- Formatters
    "stylua",
    "prettier",
    "shfmt",
    "ruff",
  },
}

return M

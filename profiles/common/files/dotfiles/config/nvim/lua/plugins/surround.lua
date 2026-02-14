-- Nvim-surround: add/change/delete surrounding pairs

return {
  "kylechui/nvim-surround",
  version = "*",
  event = "VeryLazy",
  opts = {
    -- Use default keymaps:
    -- ys{motion}{char} - add surround (e.g., ysiw" surrounds word with quotes)
    -- ds{char} - delete surround (e.g., ds" deletes surrounding quotes)
    -- cs{old}{new} - change surround (e.g., cs"' changes " to ')
    -- Visual mode: S{char} - surround selection
    keymaps = {
      insert = "<C-g>s",
      insert_line = "<C-g>S",
      normal = "ys",
      normal_cur = "yss", -- Surround current line
      normal_line = "yS",
      normal_cur_line = "ySS",
      visual = "S",
      visual_line = "gS",
      delete = "ds",
      change = "cs",
      change_line = "cS",
    },
    aliases = {
      ["a"] = ">", -- Alias for angle brackets
      ["b"] = ")",
      ["B"] = "}",
      ["r"] = "]",
      ["q"] = { '"', "'", "`" }, -- Any quote
    },
  },
}

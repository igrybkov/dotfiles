-- Undotree: visualize and navigate undo history

return {
  "mbbill/undotree",
  cmd = "UndotreeToggle",
  keys = {
    { "<leader>u", "<cmd>UndotreeToggle<cr>", desc = "Toggle undotree" },
  },
  config = function()
    -- Show on the right side
    vim.g.undotree_WindowLayout = 3

    -- Shorter timestamps
    vim.g.undotree_ShortIndicators = 1

    -- Auto-focus the undotree window
    vim.g.undotree_SetFocusWhenToggle = 1

    -- Tree node shape
    vim.g.undotree_TreeNodeShape = "●"

    -- Show relative timestamps
    vim.g.undotree_RelativeTimestamp = 1

    -- Diff window height
    vim.g.undotree_DiffpanelHeight = 10

    -- Highlight changed text
    vim.g.undotree_HighlightChangedText = 1
  end,
}

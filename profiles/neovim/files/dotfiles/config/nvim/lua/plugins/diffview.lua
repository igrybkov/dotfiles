-- Diffview for git diffs

return {
  "sindrets/diffview.nvim",
  cmd = { "DiffviewOpen", "DiffviewFileHistory", "DiffviewClose" },
  keys = {
    { "<leader>gd", "<cmd>DiffviewOpen<cr>", desc = "Open diff view (all changes)" },
    { "<leader>gh", "<cmd>DiffviewFileHistory %<cr>", desc = "File history (current file)" },
    { "<leader>gH", "<cmd>DiffviewFileHistory<cr>", desc = "File history (all files)" },
    { "<leader>gc", "<cmd>DiffviewClose<cr>", desc = "Close diff view" },
  },
  opts = {
    diff_binaries = false,
    enhanced_diff_hl = true,
    use_icons = true,
    show_help_hints = true,
    watch_index = true,
    file_panel = {
      listing_style = "tree",
      tree_options = {
        flatten_dirs = true,
        folder_statuses = "only_folded",
      },
      win_config = {
        position = "left",
        width = 35,
      },
    },
    file_history_panel = {
      log_options = {
        git = {
          single_file = {
            diff_merges = "combined",
          },
          multi_file = {
            diff_merges = "first-parent",
          },
        },
      },
      win_config = {
        position = "bottom",
        height = 16,
      },
    },
    view = {
      default = {
        layout = "diff2_horizontal",
        winbar_info = false,
      },
      merge_tool = {
        layout = "diff3_horizontal",
        disable_diagnostics = true,
        winbar_info = true,
      },
      file_history = {
        layout = "diff2_horizontal",
        winbar_info = false,
      },
    },
    keymaps = {
      view = {
        { "n", "<tab>", "<cmd>DiffviewToggleFiles<cr>", { desc = "Toggle file panel" } },
        { "n", "q", "<cmd>DiffviewClose<cr>", { desc = "Close diffview" } },
      },
      file_panel = {
        { "n", "j", "<cmd>lua require('diffview.actions').next_entry()<cr>", { desc = "Next entry" } },
        { "n", "k", "<cmd>lua require('diffview.actions').prev_entry()<cr>", { desc = "Previous entry" } },
        { "n", "<cr>", "<cmd>lua require('diffview.actions').select_entry()<cr>", { desc = "Open diff" } },
        { "n", "o", "<cmd>lua require('diffview.actions').select_entry()<cr>", { desc = "Open diff" } },
        { "n", "s", "<cmd>lua require('diffview.actions').toggle_stage_entry()<cr>", { desc = "Stage/unstage" } },
        { "n", "S", "<cmd>lua require('diffview.actions').stage_all()<cr>", { desc = "Stage all" } },
        { "n", "U", "<cmd>lua require('diffview.actions').unstage_all()<cr>", { desc = "Unstage all" } },
        { "n", "X", "<cmd>lua require('diffview.actions').restore_entry()<cr>", { desc = "Restore entry" } },
        { "n", "R", "<cmd>lua require('diffview.actions').refresh_files()<cr>", { desc = "Refresh" } },
        { "n", "<tab>", "<cmd>DiffviewToggleFiles<cr>", { desc = "Toggle file panel" } },
        { "n", "q", "<cmd>DiffviewClose<cr>", { desc = "Close diffview" } },
      },
      file_history_panel = {
        { "n", "j", "<cmd>lua require('diffview.actions').next_entry()<cr>", { desc = "Next entry" } },
        { "n", "k", "<cmd>lua require('diffview.actions').prev_entry()<cr>", { desc = "Previous entry" } },
        { "n", "<cr>", "<cmd>lua require('diffview.actions').select_entry()<cr>", { desc = "Open diff" } },
        { "n", "o", "<cmd>lua require('diffview.actions').select_entry()<cr>", { desc = "Open diff" } },
        { "n", "q", "<cmd>DiffviewClose<cr>", { desc = "Close diffview" } },
      },
    },
  },
}

-- Bootstrap lazy.nvim
local lazypath = vim.fn.stdpath("data") .. "/lazy/lazy.nvim"

if not vim.uv.fs_stat(lazypath) then
  local repo = "https://github.com/folke/lazy.nvim.git"
  vim.fn.system({ "git", "clone", "--filter=blob:none", repo, "--branch=stable", lazypath })
end

vim.opt.rtp:prepend(lazypath)

-- Set leader key before lazy
vim.g.mapleader = " "
vim.g.maplocalleader = "\\"

-- NvChad base46 cache path
vim.g.base46_cache = vim.fn.stdpath("data") .. "/base46_cache/"

-- Ensure cache directory exists
vim.fn.mkdir(vim.g.base46_cache, "p")

-- Load lazy.nvim with NvChad
local lazy_config = require("configs.lazy")
require("lazy").setup(lazy_config)

-- Load base46 theme cache (safely)
local function load_base46_cache()
  local cache_path = vim.g.base46_cache
  if vim.uv.fs_stat(cache_path .. "defaults") then
    dofile(cache_path .. "defaults")
    dofile(cache_path .. "statusline")
    return true
  end
  return false
end

if not load_base46_cache() then
  -- Cache doesn't exist, try to generate it
  local ok, base46 = pcall(require, "base46")
  if ok then
    base46.load_all_highlights()
    load_base46_cache()
  end
end

-- Load options
require("options")

-- Load nvchad autocmds (safely)
pcall(require, "nvchad.autocmds")

vim.schedule(function()
  require("mappings")
end)

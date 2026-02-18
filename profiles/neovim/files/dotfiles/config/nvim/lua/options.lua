-- Load NvChad options if available
pcall(require, "nvchad.options")

local o = vim.o

-- Line numbers
o.relativenumber = true
o.number = true

-- Tabs and indentation
o.tabstop = 2
o.shiftwidth = 2
o.softtabstop = 2
o.expandtab = true
o.smartindent = true

-- Line wrapping
o.wrap = false

-- Search settings
o.ignorecase = true
o.smartcase = true

-- Cursor line
o.cursorline = true

-- Appearance
o.termguicolors = true
o.signcolumn = "yes"

-- Backspace
o.backspace = "indent,eol,start"

-- Clipboard
o.clipboard = "unnamedplus"

-- Split windows
o.splitright = true
o.splitbelow = true

-- Consider - as part of word
vim.opt.iskeyword:append("-")

-- Disable swapfile
o.swapfile = false

-- Persistent undo
o.undofile = true

-- Update time for CursorHold
o.updatetime = 250

-- Scroll offset
o.scrolloff = 8
o.sidescrolloff = 8

-- Pull in the wezterm API
local wezterm = require 'wezterm'

-- This will hold the configuration.
local config = wezterm.config_builder()

-- This is where you actually apply your config choices

-- ------------------------------------------------
-- Colors and fonts
-- ------------------------------------------------
config.color_scheme = 'OneDark (base16)'
wezterm.font('JetBrains Mono', { weight = 'Bold', italic = true })

config.font_size = 14.0

-- ------------------------------------------------
-- Set up workspace switcher plugin
-- ------------------------------------------------
local workspace_switcher = wezterm.plugin.require(
                               "https://github.com/MLFlexer/smart_workspace_switcher.wezterm")
workspace_switcher.apply_to_config(config)

-- ------------------------------------------------
-- Set up the tab bar plugin
-- ------------------------------------------------
-- local bar = wezterm.plugin
--                 .require("https://github.com/adriankarlen/bar.wezterm")
-- bar.apply_to_config(config, {
--     position = "top",
--     modules = {
--         tabs = {active_tab_fg = 4, inactive_tab_fg = 6},
--         workspace = {
--             enabled = true,
--             icon = wezterm.nerdfonts.cod_window,
--             color = 8
--         },
--         leader = {
--             enabled = true,
--             icon = wezterm.nerdfonts.oct_rocket,
--             color = 2
--         },
--         pane = {
--             enabled = true,
--             icon = wezterm.nerdfonts.cod_multiple_windows,
--             color = 7
--         },
--         username = {
--             enabled = false,
--             icon = wezterm.nerdfonts.fa_user,
--             color = 6
--         },
--         hostname = {
--             enabled = false,
--             icon = wezterm.nerdfonts.cod_server,
--             color = 8
--         },
--         clock = {
--             enabled = false,
--             icon = wezterm.nerdfonts.md_calendar_clock,
--             color = 5
--         },
--         cwd = {
--             enabled = true,
--             icon = wezterm.nerdfonts.oct_file_directory,
--             color = 7
--         },
--         spotify = {
--             enabled = false,
--             icon = wezterm.nerdfonts.fa_spotify,
--             color = 3,
--             max_width = 64,
--             throttle = 15
--         }
--     }
-- })

-- ------------------------------------------------
-- Do not quit when all windows are closed
-- ------------------------------------------------

config.quit_when_all_windows_are_closed = false

-- ------------------------------------------------
-- Launcher Menu
-- ------------------------------------------------
config.launch_menu = {
    {args = {'top'}}, {label = 'Bash', args = {'bash', '-l'}},
    {label = 'ZSH', args = {'zsh', '-l'}}
}

for _, app in
    ipairs(wezterm.glob('*.app', os.getenv("HOME") .. '/Applications')) do
    wezterm.log_info("Project: " .. app)
    table.insert(config.launch_menu, {label = app, args = {'open', '-na', app}})
end

-- ------------------------------------------------
-- Custom URL handling
-- ------------------------------------------------
-- Use some simple heuristics to determine if we should open it
-- with a text editor in the terminal.
-- Take note! The code in this file runs on your local machine,
-- but a URI can appear for a remote, multiplexed session.
-- WezTerm can spawn the editor in that remote session, but doesn't
-- have access to the file locally, so we can't probe inside the
-- file itself, so we are limited to simple heuristics based on
-- the filename appearance.

--- Check if a file or directory exists in this path
function is_path_exists(file)
    local ok, err, code = os.rename(file, file)
    if not ok then
        if code == 13 then
            -- Permission denied, but it exists
            return true
        end
    end
    return ok, err
end

--- Check if a directory exists in this path
function is_dir(path)
    -- "/" works on both Unix and Windows
    return is_path_exists(path .. "/")
end

function editable(filename)
    -- "foo.bar" -> ".bar"
    local extension = filename:match("^.+(%..+)$")
    if extension then
        -- ".bar" -> "bar"
        extension = extension:sub(2)
        wezterm.log_info(string.format("extension is [%s]", extension))
        local binary_extensions = {
            jpg = true,
            jpeg = true
            -- and so on
        }
        if binary_extensions[extension] then
            -- can't edit binary files
            return false
        end
    end

    if is_dir(filename) then return false end

    -- if there is no, or an unknown, extension, then assume
    -- that our trusty editor will do something reasonable

    return true
end

function extract_filename(uri)
    local start, match_end = uri:find("$EDITOR:");
    if start == 1 then
        -- skip past the colon
        return uri:sub(match_end + 1)
    end

    -- `file://hostname/path/to/file`
    local start, match_end = uri:find("file:");
    if start == 1 then
        -- skip "file://", -> `hostname/path/to/file`
        local host_and_path = uri:sub(match_end + 3)
        local start, match_end = host_and_path:find("/")
        if start then
            -- -> `/path/to/file`
            return host_and_path:sub(match_end)
        end
    end

    return nil
end

wezterm.on("open-uri", function(window, pane, uri)
    local name = extract_filename(uri)
    wezterm.log_info("open-uri: " .. uri .. " -> " .. tostring(name))
    if name then
        local action = null
        -- Note: if you change your VISUAL or EDITOR environment,
        -- you will need to restart wezterm for this to take effect,
        -- as there isn't a way for wezterm to "see into" your shell
        -- environment and capture it.
        local editor = os.getenv("VISUAL") or os.getenv("EDITOR") or "vi"

        if string.sub(name,1,2)=="~/" then
          name = os.getenv("HOME")..string.sub(name,2)
        elseif string.sub(name,1,5)=="$HOME" then
            name = os.getenv("HOME")..string.sub(name,6)
        end

        if editable(name) then
            -- To open a new window:
            action = wezterm.action {
                SpawnCommandInNewWindow = {args = {editor, name}}
            };

            -- To open in a pane instead
            --[[
            local action = wezterm.action{SplitHorizontal={
                args={editor, name}
              }};
            ]]
        else
            wezterm.log_info("Opening file using open command: " .. name)
            action = wezterm.action {
                SpawnCommandInNewWindow = {args = {"open", name}}
            };
        end

        if action then
            -- perform the action
            window:perform_action(action, pane);
        end

        -- prevent the default action from opening in a browser
        return false
    end
end)

config.hyperlink_rules = {
    -- These are the default rules, but you currently need to repeat
    -- them here when you define your own rules, as your rules override
    -- the defaults

    -- URL with a protocol
    {regex = "\\b\\w+://(?:[\\w.-]+)\\.[a-z]{2,15}\\S*\\b", format = "$0"},

    -- implicit mailto link
    {regex = "\\b\\w+@[\\w-]+(\\.[\\w-]+)+\\b", format = "mailto:$0"},

    -- new in nightly builds; automatically highly file:// URIs.
    {regex = "\\bfile://\\S*\\b", format = "$0"},
    -- Now add a new item at the bottom to match things that are probably filenames
--    {regex = "\\b*~/[a-zA-Z0-9\\s]+\\b", format = "$EDITOR:$0"}, -- File paths relative to ~/
--    {regex = "\\b*\\$HOME/\\S*\\b", format = "$EDITOR:$0"}, -- File paths relative to $HOME
--    {regex = "\\b*/\\S*\\b", format = "$EDITOR:$0"}, -- Absolute file paths

}

-- ------------------------------------------------
-- Mouse bindings
-- ------------------------------------------------
config.mouse_bindings = {
    -- Right click sends "woot" to the terminal
    {
        event = {Down = {streak = 1, button = 'Right'}},
        mods = 'NONE',
        action = wezterm.action.SendString 'woot'
    }, -- Change the default click behavior so that it only selects
    -- text and doesn't open hyperlinks
    {
        event = {Up = {streak = 1, button = 'Left'}},
        mods = 'NONE',
        action = wezterm.action.CompleteSelection 'ClipboardAndPrimarySelection'
    }, -- and make CMD-Click open hyperlinks
    {
        event = {Up = {streak = 1, button = 'Left'}},
        mods = 'CMD',
        action = wezterm.action.OpenLinkAtMouseCursor
    }
    -- NOTE that binding only the 'Up' event can give unexpected behaviors.
    -- Read more below on the gotcha of binding an 'Up' event only.
}
-- ------------------------------------------------
-- Keybindings
-- ------------------------------------------------

-- timeout_milliseconds defaults to 1000 and can be omitted
config.leader = {key = 'a', mods = 'CTRL', timeout_milliseconds = 2000}
config.keys = {
  {key = "s", mods = "LEADER", action = workspace_switcher.switch_workspace()},
  {key="Enter", mods="SHIFT", action=wezterm.action.SendString "\x1b\r" },
    {
        key = "S",
        mods = "LEADER",
        action = workspace_switcher.switch_to_prev_workspace()
    }, {
        key = 'd',
        mods = 'CMD',
        action = wezterm.action.SplitHorizontal {domain = 'CurrentPaneDomain'}
    }, {
        -- Send "CTRL-A" to the terminal when pressing CTRL-A, CTRL-A
        key = 'a',
        mods = 'LEADER|CTRL',
        action = wezterm.action.SendKey {key = 'a', mods = 'CTRL'}
    }, {
        key = 'd',
        mods = 'CMD|SHIFT',
        action = wezterm.action.SplitVertical {domain = 'CurrentPaneDomain'}
    }, {
        key = 'w',
        mods = 'CMD',
        action = wezterm.action.CloseCurrentPane {
            domain = 'CurrentPaneDomain',
            confirm = true
        }
    }, {
        key = 'w',
        mods = 'LEADER|CMD',
        action = wezterm.action.CloseCurrentTab {
            domain = 'CurrentPaneDomain',
            confirm = false
        }
    },
    {key = '1', mods = 'ALT', action = wezterm.action.ActivatePaneByIndex(0)},
    {key = '2', mods = 'ALT', action = wezterm.action.ActivatePaneByIndex(1)},
    {key = '3', mods = 'ALT', action = wezterm.action.ActivatePaneByIndex(2)},
    {key = '4', mods = 'ALT', action = wezterm.action.ActivatePaneByIndex(3)},
    {key = '5', mods = 'ALT', action = wezterm.action.ActivatePaneByIndex(4)},
    {key = '6', mods = 'ALT', action = wezterm.action.ActivatePaneByIndex(5)},
    {key = '7', mods = 'ALT', action = wezterm.action.ActivatePaneByIndex(6)},
    {key = '8', mods = 'ALT', action = wezterm.action.ActivatePaneByIndex(7)},
    {key = '9', mods = 'ALT', action = wezterm.action.ActivatePaneByIndex(8)},
    {key = '0', mods = 'ALT', action = wezterm.action.ActivatePaneByIndex(9)},
    {
        key = 'h',
        mods = 'CTRL|SHIFT',
        action = wezterm.action.ActivatePaneDirection 'Left'
    }, {
        key = 'l',
        mods = 'CTRL|SHIFT',
        action = wezterm.action.ActivatePaneDirection 'Right'
    }, {
        key = 'k',
        mods = 'CTRL|SHIFT',
        action = wezterm.action.ActivatePaneDirection 'Up'
    }, {
        key = 'j',
        mods = 'CTRL|SHIFT',
        action = wezterm.action.ActivatePaneDirection 'Down'
    }, {
        key = 'p',
        mods = 'CMD',
        action = wezterm.action.ShowLauncherArgs {
            flags = 'FUZZY|WORKSPACES|TABS|DOMAINS|LAUNCH_MENU_ITEMS|COMMANDS'
        }
    }, {
        key = ',',
        mods = 'CMD',
        action = wezterm.action.SpawnCommandInNewWindow({
            cwd = os.getenv("WEZTERM_CONFIG_DIR"),
            args = {
                os.getenv("SHELL"), "-c",
                "$EDITOR $(realpath $WEZTERM_CONFIG_FILE)"
            }
        })
    },
    -- { key = 'c', mods = 'CMD', action = wezterm.action.Copy {direction = "ToClipboard"} },
    -- { key = 'v', mods = 'CMD', action = wezterm.action.Paste {direction = "FromClipboard"} },
    -- { key = 'v', mods = 'CMD|SHIFT', action = wezterm.action.Paste {direction = "FromPrimarySelection"} },
    -- { key = 'w', mods = 'CMD', action = wezterm.action.ResetFontSize },
    -- { key = 'w', mods = 'CMD|SHIFT', action = wezterm.action.ResetFontSize },
    -- { key = 'w', mods = 'CMD|ALT', action = wezterm.action.ResetFontSize },
    -- { key = 'w', mods = 'CMD|ALT|SHIFT', action = wezterm.action.ResetFontSize },
    -- { key = 'w', mods = 'CMD|CTRL', action = wezterm.action.ResetFontSize },
    -- { key = 'w', mods = 'CMD|CTRL|SHIFT', action = wezterm.action.ResetFontSize },
    -- { key = 'w', mods = 'CMD|CTRL|ALT', action = wezterm.action.ResetFontSize },
    -- { key = 'w', mods = 'CMD|CTRL|ALT|SHIFT', action = wezterm.action.ResetFontSize },
    -- { key = 'w', mods = 'CMD|ALT|CTRL', action = wezterm.action.ResetFontSize },
    -- { key = 'w', mods = 'CMD|ALT|CTRL|SHIFT', action = wezterm.action.ResetFontSize },
    -- { key = 'w', mods = 'CMD|ALT|CTRL|ALT', action = wezterm.action.ResetFontSize },
    -- { key = 'w', mods = 'CMD|ALT|CTRL|ALT|SHIFT', action = wezterm.action.ResetFontSize },
    -- { key = 'w', mods = 'CMD|ALT|CTRL|CTRL', action = wezterm.action.ResetFontSize },
    -- { key = 'w', mods = 'CMD|ALT|CTRL|CTRL|SHIFT', action = wezterm.action.ResetFontSize },
    -- { key = 'w', mods = 'CMD|ALT|CTRL|CTRL|ALT', action = wezterm.action.ResetFontSize },
    { key = '_', mods = 'CTRL', action = wezterm.action.DecreaseFontSize },
    { key = '_', mods = 'SHIFT|CTRL', action = wezterm.action.DecreaseFontSize },
    { key = '+', mods = 'CTRL', action = wezterm.action.IncreaseFontSize },
    { key = '+', mods = 'SHIFT|CTRL', action = wezterm.action.IncreaseFontSize },
    { key = '-', mods = 'CTRL', action = wezterm.action.DecreaseFontSize },
    { key = '-', mods = 'SHIFT|CTRL', action = wezterm.action.DecreaseFontSize },
    { key = '-', mods = 'SUPER', action = wezterm.action.DecreaseFontSize },
    { key = '=', mods = 'CTRL', action = wezterm.action.IncreaseFontSize },
    { key = '=', mods = 'SHIFT|CTRL', action = wezterm.action.IncreaseFontSize },
    { key = '=', mods = 'SUPER', action = wezterm.action.IncreaseFontSize },
    { key = '0', mods = 'CTRL', action = wezterm.action.ResetFontSize },
    { key = '0', mods = 'SHIFT|CTRL', action = wezterm.action.ResetFontSize },
    { key = '0', mods = 'SUPER', action = wezterm.action.ResetFontSize },
    { key = ')', mods = 'CTRL', action = wezterm.action.ResetFontSize },
    { key = ')', mods = 'SHIFT|CTRL', action = wezterm.action.ResetFontSize },
}

-- and finally, return the configuration to wezterm
return config

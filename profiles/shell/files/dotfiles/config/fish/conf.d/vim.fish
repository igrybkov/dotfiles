# Use nvim instead of vim/vi when available
if type -q nvim
    alias vim="nvim"
    alias vi="nvim"
else if type -q vim
    alias vi="vim"
end

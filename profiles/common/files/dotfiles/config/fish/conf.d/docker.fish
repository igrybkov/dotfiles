if not type -q docker
    return
end

abbr -a d docker
abbr -a dc "docker compose"
abbr -a dsp "docker system prune"
abbr -a dcb "docker compose build"
abbr -a dce "docker compose exec"
abbr -a dcl "docker compose logs"
abbr -a dclf "docker compose logs --follow"
abbr -a dcp "docker compose ps"
abbr -a dcu "docker compose up"
abbr -a dcup "docker compose up"
abbr -a dcud "docker compose up -d"
abbr -a dcudb "docker compose up -d --build"
abbr -a dcupdb "docker compose up -d --build"
abbr -a dcupd "docker compose up -d"
abbr -a dcd "docker compose down"
abbr -a dcdv "docker compose down --volumes"
abbr -a dcr "docker compose run"
abbr -a dca "docker compose attach"
abbr -a dcr "docker compose restart"

if type -q lazydocker
    abbr -a ld lazydocker
end

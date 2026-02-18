#shellcheck disable=SC1107,SC1091,SC2148,SC2139
PRIMARY_NETWORK_INTERFACE=$(route get default | grep interface | awk '{print $2}')

# Flush Directory Service cache
alias flush="dscacheutil -flushcache"

# IP addresses
alias ip="dig +short myip.opendns.com @resolver1.opendns.com"
alias localip="ipconfig getifaddr $PRIMARY_NETWORK_INTERFACE"
alias ips="ifconfig -a | grep -o 'inet6\? \(\([0-9]\+\.[0-9]\+\.[0-9]\+\.[0-9]\+\)\|[a-fA-F0-9:]\+\)' | sed -e 's/inet6* //'"

# View HTTP traffic
alias sniff="sudo ngrep -d '$PRIMARY_NETWORK_INTERFACE' -t '^(GET|POST) ' 'tcp and port 80'"
alias httpdump="sudo tcpdump -i $PRIMARY_NETWORK_INTERFACE -n -s 0 -w - | grep -a -o -E \"Host\: .*|GET \/.*\""

# View open ports
alias used-ports="lsof -iTCP -sTCP:LISTEN -n -P"

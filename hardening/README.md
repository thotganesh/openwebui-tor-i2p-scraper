# Egress guard

Network-level defence for the containers that exit with the VPS IP
(`browser-http`, `browser-clear`, `browser-camoufox`, `camofox`, `solverr`).
It installs `OUTPUT` rules *inside each container's network namespace* (from the host,
via `nsenter`), so a compromised browser cannot remove them. Private and special ranges
(RFC1918, link-local, CGNAT, multicast, ...) are rejected; internet access, replies to
inbound connections and `browser-clear -> solverr:8191` are allowed.

Install (as root, on the Docker host):

    install -m 755 hardening/egress-guard.sh /usr/local/sbin/egress-guard.sh
    install -m 644 hardening/egress-guard.service /etc/systemd/system/egress-guard.service
    systemctl daemon-reload && systemctl enable --now egress-guard

The service re-applies the rules every 15 s, so they come back after a container is
recreated (up to 15 s without them). IPv4 only. Disable with
`systemctl disable --now egress-guard && /usr/local/sbin/egress-guard.sh off`.

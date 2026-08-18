#!/bin/sh
echo "[HOST] Starting services..."

dhcpcd -b eth0 2>/dev/null || true

/usr/sbin/sshd

snmpd -Lf /var/log/snmpd.log

echo "[HOST] Ready. eth0:"
ip addr show eth0 2>/dev/null | grep inet

exec sh

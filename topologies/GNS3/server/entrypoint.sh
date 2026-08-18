#!/bin/bash
set -e

echo "[SPECTRA] Starting services..."

echo "[SPECTRA] Configuring static network..."
ip addr show dev eth0 | grep -q "10.0.14.142/28" || ip addr add 10.0.14.142/28 dev eth0
ip addr show dev eth0 | grep -q "fd44:f1:f1:27::10/64" || ip -6 addr add fd44:f1:f1:27::10/64 dev eth0
ip link set eth0 up
ip route show default | grep -q "10.0.14.129" || ip route add default via 10.0.14.129
ip -6 route show default | grep -q "fd44:f1:f1:27::1" || ip -6 route add default via fd44:f1:f1:27::1

echo "[SPECTRA] Starting SSH..."
service ssh start

echo "[SPECTRA] Starting Syslog..."
rsyslogd

echo "[SPECTRA] Starting DNS (dnsmasq)..."
service dnsmasq start

echo "[SPECTRA] Starting NTP (chrony)..."
service chrony start

echo "[SPECTRA] Starting DHCP v4 (isc-dhcp-server)..."
rm -f /var/run/dhcpd.pid
service isc-dhcp-server start || echo "[SPECTRA] WARNING: dhcpd (v4) failed to start"

echo "[SPECTRA] Starting DHCP v6 (dhcpd -6)..."
rm -f /var/run/dhcpd6.pid
mkdir -p /var/lib/dhcp
touch /var/lib/dhcp/dhcpd6.leases
dhcpd -6 -cf /etc/dhcp/dhcpd6.conf -pf /var/run/dhcpd6.pid eth0 \
    || echo "[SPECTRA] WARNING: dhcpd (v6) failed to start"

echo "[SPECTRA] Starting TFTP (tftpd-hpa)..."
service tftpd-hpa start || true

echo "[SPECTRA] Starting PostgreSQL..."
service postgresql start
sleep 2

sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname = 'spectra'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE USER spectra WITH PASSWORD 'spectra';"
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname = 'campus_db'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE DATABASE campus_db OWNER spectra;"

PG_HBA=$(find /etc/postgresql -name pg_hba.conf | head -1)
if ! grep -q "spectra" "$PG_HBA" 2>/dev/null; then
    echo "local   campus_db   spectra   md5" >> "$PG_HBA"
    echo "host    campus_db   spectra   127.0.0.1/32   md5" >> "$PG_HBA"
    service postgresql reload
fi

echo "========================================="
echo "  S.P.E.C.T.R.A Server Online"
echo "========================================="
echo "  SSH:        port 22"
echo "  DNS:        port 53"
echo "  DHCPv4:     port 67 (UDP)"
echo "  DHCPv6:     port 547 (UDP)"
echo "  TFTP:       port 69 (UDP)"
echo "  Syslog:     port 514 (UDP)"
echo "  NTP:        port 123"
echo "  PostgreSQL: port 5432"
echo "  Flask:      port 5000 (when started)"
echo "========================================="

exec tail -f /dev/null

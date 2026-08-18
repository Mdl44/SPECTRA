#!/usr/bin/env python3
import argparse
import asyncio
import os
import re
import socket
import struct
import sys
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import paramiko  # type: ignore
from dotenv import load_dotenv
from manuf import manuf
from netmiko import ConnectHandler
from pysnmp.hlapi.v3arch.asyncio import (
    SnmpEngine,
    UsmUserData,
    CommunityData,
    UdpTransportTarget,
    ContextData,
    ObjectType,
    ObjectIdentity,
    NoSuchObject,
    NoSuchInstance,
    EndOfMibView,
    bulk_walk_cmd,
    get_cmd,
)

load_dotenv()

socket.setdefaulttimeout(3.0)


# ---- SNMP OIDs ----

SYS_DESCR = "1.3.6.1.2.1.1.1.0"
SYS_OBJECT_ID = "1.3.6.1.2.1.1.2.0"
SYS_UPTIME = "1.3.6.1.2.1.1.3.0"
SYS_NAME = "1.3.6.1.2.1.1.5.0"

IP_FORWARDING = "1.3.6.1.2.1.4.1.0"
IP_NET_TO_MEDIA_PHYS_ADDRESS = "1.3.6.1.2.1.4.22.1.2"
IP_AD_ENT_ADDR = "1.3.6.1.2.1.4.20.1.1"

DOT1D_BASE_BRIDGE_ADDRESS = "1.3.6.1.2.1.17.1.1.0"

CDP_CACHE_DEVICE_ID = "1.3.6.1.4.1.9.9.23.1.2.1.1.6"
CDP_CACHE_DEVICE_PORT = "1.3.6.1.4.1.9.9.23.1.2.1.1.7"
CDP_CACHE_PLATFORM = "1.3.6.1.4.1.9.9.23.1.2.1.1.8"
CDP_CACHE_ADDRESS = "1.3.6.1.4.1.9.9.23.1.2.1.1.4"

OSPF_NBR_STATE = "1.3.6.1.2.1.14.10.1.6"


# ---- Data models ----

@dataclass
class NeighborEdge:
    local_ip: str
    local_hostname: str | None
    protocol: str
    remote_name: str | None
    remote_port: str | None
    remote_ip: str | None


@dataclass
class EndDevice:
    mac: str
    ip: str | None = None
    hostname: str | None = None
    sys_descr: str | None = None
    vendor_guess: str = "unknown"
    switch_ip: str | None = None
    switch_port: str | None = None
    discovered_via: set = field(default_factory=set)


@dataclass
class Device:
    ip: str
    reachable: bool
    hostname: str | None = None
    sys_descr: str | None = None
    vendor: str = "unknown"
    role: str = "unknown"
    error: str | None = None
    debug: list = field(default_factory=list)
    management_ips: set = field(default_factory=set)
    own_macs: set = field(default_factory=set)


@dataclass
class DiscoveryResult:
    devices: dict
    end_devices: dict
    edges: list
    unreachable_seeds: list


# ---- SNMP client ----

class SnmpClient:
    def __init__(self, target_ip, auth_data, port=161, timeout=2, retries=1):
        self.target_ip = target_ip
        self.auth_data = auth_data
        self.port = port
        self.timeout = timeout
        self.retries = retries
        self.engine = SnmpEngine()

    async def get(self, oid, context_name=""):
        transport = await UdpTransportTarget.create(
            (self.target_ip, self.port), timeout=self.timeout, retries=self.retries
        )
        errorIndication, errorStatus, errorIndex, varBinds = await get_cmd(
            self.engine, self.auth_data, transport, ContextData(contextName=context_name),
            ObjectType(ObjectIdentity(oid)),
        )
        if errorIndication:
            return None, str(errorIndication)
        if errorStatus:
            return None, f"{errorStatus} at index {errorIndex}"
        _, val = varBinds[0]
        if isinstance(val, (NoSuchObject, NoSuchInstance)):
            return None, "OID not present on this device"
        return val, None

    async def walk(self, base_oid, context_name="", limit=500):
        transport = await UdpTransportTarget.create(
            (self.target_ip, self.port), timeout=self.timeout, retries=self.retries
        )
        rows = []
        error = None
        async for errorIndication, errorStatus, errorIndex, varBinds in bulk_walk_cmd(
            self.engine, self.auth_data, transport, ContextData(contextName=context_name),
            0, 25,
            ObjectType(ObjectIdentity(base_oid)),
            lexicographicMode=False,
        ):
            if errorIndication:
                error = str(errorIndication)
                break
            if errorStatus:
                error = f"{errorStatus} at index {errorIndex}"
                break
            done = False
            for name, val in varBinds:
                if isinstance(val, EndOfMibView):
                    done = True
                    break
                rows.append((str(name), val))
            if done or len(rows) >= limit:
                break
        return rows, error


def build_auth_data(username, auth_key, priv_key):
    from pysnmp.hlapi.v3arch.asyncio import usmHMACSHAAuthProtocol, usmAesCfb128Protocol

    return UsmUserData(
        username,
        authKey=auth_key,
        privKey=priv_key,
        authProtocol=usmHMACSHAAuthProtocol,
        privProtocol=usmAesCfb128Protocol,
    )


def build_community_data(community):
    return CommunityData(community, mpModel=1)


# ---- SSH client (CAM/FDB tables, own interface MACs) ----

_ROW_RE = re.compile(
    r"^\s*(\d+)\s+([0-9a-fA-F]{4}\.[0-9a-fA-F]{4}\.[0-9a-fA-F]{4})\s+(\S+)\s+(\S+)\s*$"
)
_TRUNK_ROW_RE = re.compile(r"^(\S+)\s+\S+\s+\S+\s+trunking\s+\S+\s*$", re.IGNORECASE)
_OWN_MAC_RE = re.compile(r"address is ([0-9a-fA-F]{4}\.[0-9a-fA-F]{4}\.[0-9a-fA-F]{4})")


def _cisco_mac_to_colon(mac: str) -> str:
    hex_only = mac.replace(".", "")
    return ":".join(hex_only[i:i + 2] for i in range(0, 12, 2)).lower()


def _parse_mac_table(raw: str):
    rows = []
    for line in raw.splitlines():
        match = _ROW_RE.match(line)
        if not match:
            continue
        vlan_id, mac, entry_type, port = match.groups()
        if entry_type.upper() not in ("DYNAMIC", "STATIC") or port.upper() in ("CPU", "ROUTER"):
            continue
        rows.append((_cisco_mac_to_colon(mac), vlan_id, port))
    return rows


def _parse_trunk_ports(raw: str):
    return {m.group(1) for line in raw.splitlines() if (m := _TRUNK_ROW_RE.match(line.strip()))}


def _parse_own_macs(raw: str):
    return {_cisco_mac_to_colon(m.group(1)) for m in _OWN_MAC_RE.finditer(raw)}


def fetch_mac_and_trunk_ports(ip: str, username: str, password: str):
    device = {
        "device_type": "cisco_ios",
        "host": ip,
        "username": username,
        "password": password,
        "timeout": 10,
    }
    try:
        conn = ConnectHandler(**device)
        try:
            mac_raw = conn.send_command("show mac address-table")
            trunk_raw = conn.send_command("show interfaces trunk")
            own_raw = conn.send_command("show interfaces | include Hardware is")
        finally:
            conn.disconnect()
    except Exception as exc:
        return [], set(), set(), str(exc)
    return (
        _parse_mac_table(str(mac_raw)),
        _parse_trunk_ports(str(trunk_raw)),
        _parse_own_macs(str(own_raw)),
        None,
    )


# ---- Vendor / role classification ----

ENTERPRISE_VENDORS = {
    "9": "Cisco",
    "2636": "Juniper",
    "11": "HP",
    "674": "Dell",
    "6027": "Foundry/Brocade",
    "1916": "Extreme Networks",
    "2011": "Huawei",
    "25506": "H3C",
    "8072": "Net-SNMP (generic agent)",
}

_ENTERPRISE_NUM_RE = re.compile(r"(?:1\.3\.6\.1\.4\.1|enterprises)\.(\d+)")

FIREWALL_SYSDESCR_KEYWORDS = [
    "adaptive security appliance",
    "fortigate",
    "palo alto",
    "pfsense",
    "srx",
]

AP_SYSDESCR_KEYWORDS = [
    "aironet",
    "access point",
    "lightweight ap",
    "unified ap",
    "unifi ap",
    "aruba ap",
    "aruba instant",
    "ruckus",
    "meraki mr",
    "omada",
]

WLC_SYSDESCR_KEYWORDS = [
    "wireless lan controller",
    "wireless controller",
    "aircontroller",
    "mobility controller",
]

_mac_parser = manuf.MacParser()


def vendor_from_sys_object_id(sys_object_id: str) -> str:
    if not sys_object_id:
        return "unknown"
    match = _ENTERPRISE_NUM_RE.search(sys_object_id)
    if not match:
        return "unknown"
    return ENTERPRISE_VENDORS.get(match.group(1), "unknown")


def is_firewall_sysdescr(sys_descr: str) -> bool:
    if not sys_descr:
        return False
    lowered = sys_descr.lower()
    return any(kw in lowered for kw in FIREWALL_SYSDESCR_KEYWORDS)


def is_ap_sysdescr(sys_descr: str) -> bool:
    if not sys_descr:
        return False
    lowered = sys_descr.lower()
    return any(kw in lowered for kw in AP_SYSDESCR_KEYWORDS)


def is_wlc_sysdescr(sys_descr: str) -> bool:
    if not sys_descr:
        return False
    lowered = sys_descr.lower()
    return any(kw in lowered for kw in WLC_SYSDESCR_KEYWORDS)


def vendor_from_mac(mac: str) -> str:
    vendor = _mac_parser.get_manuf_long(mac)
    if vendor:
        return vendor
    oui = mac.replace(":", "").replace("-", "").upper()
    first_octet = int(oui[:2], 16)
    if first_octet & 0x02:
        return "Locally administered (virtual/randomized)"
    return "unknown"


def classify_role(sys_descr: str, ip_forwarding: bool, bridge_mib_present: bool) -> str:
    if is_wlc_sysdescr(sys_descr):
        return "wireless-controller"
    if is_ap_sysdescr(sys_descr):
        return "access-point"
    if ip_forwarding and is_firewall_sysdescr(sys_descr):
        return "firewall"
    if ip_forwarding:
        return "router"
    if bridge_mib_present:
        return "switch"
    return "unknown"


# ---- DHCP lease hostname harvesting ----

_LEASE_BLOCK_RE = re.compile(r"lease (\d+\.\d+\.\d+\.\d+) \{(.*?)\n\}", re.S)
_MAC_RE = re.compile(r"hardware ethernet ([0-9a-fA-F:]+);")
_HOSTNAME_RE = re.compile(r'client-hostname "([^"]*)";')
_STATE_RE = re.compile(r"binding state (\w+);")


def parse_dhcpd_leases(text: str) -> dict:
    by_ip = {}
    for ip, body in _LEASE_BLOCK_RE.findall(text):
        mac_match = _MAC_RE.search(body)
        state_match = _STATE_RE.search(body)
        if not mac_match or not state_match:
            continue
        hostname_match = _HOSTNAME_RE.search(body)
        by_ip[ip] = {
            "mac": mac_match.group(1).lower(),
            "state": state_match.group(1),
            "hostname": hostname_match.group(1) if hostname_match else None,
        }

    mac_to_hostname = {}
    for entry in by_ip.values():
        if entry["state"] == "active" and entry["hostname"]:
            mac_to_hostname[entry["mac"]] = entry["hostname"]
    return mac_to_hostname


def fetch_dhcpd_leases_text(host, username, password, port=22, timeout=5,
                             lease_file="/var/lib/dhcp/dhcpd.leases") -> str:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(host, port=port, username=username, password=password, timeout=timeout)
        _, stdout, stderr = client.exec_command(f"cat {lease_file}")
        text = stdout.read().decode(errors="replace")
        err = stderr.read().decode(errors="replace").strip()
        if not text and err:
            raise RuntimeError(err)
        return text
    finally:
        client.close()


def fetch_dhcp_hostnames(host, username, password, port=22, timeout=5) -> dict:
    text = fetch_dhcpd_leases_text(host, username, password, port=port, timeout=timeout)
    return parse_dhcpd_leases(text)


# ---- Reverse-DNS / NetBIOS / mDNS fallback identification ----

def query_reverse_dns(ip: str) -> str | None:
    try:
        hostname, _, _ = socket.gethostbyaddr(ip)
    except (socket.herror, socket.gaierror, OSError):
        return None
    if not hostname:
        return None
    return hostname.split(".")[0]


def _encode_netbios_name(name: str) -> bytes:
    padded = name.upper().ljust(16)[:16]
    out = bytearray()
    for ch in padded.encode("ascii", errors="replace"):
        out.append(0x41 + (ch >> 4))
        out.append(0x41 + (ch & 0x0F))
    return bytes(out)


def _build_netbios_query() -> bytes:
    txn_id = 0x5350
    flags = 0x0000
    header = struct.pack(">HHHHHH", txn_id, flags, 1, 0, 0, 0)
    qname = bytes([0x20]) + _encode_netbios_name("*") + b"\x00"
    question = qname + struct.pack(">HH", 0x0021, 0x0001)
    return header + question


def _parse_netbios_response(data: bytes) -> str | None:
    if len(data) < 12:
        return None
    pos = 12
    if data[pos] & 0xC0 == 0xC0:
        pos += 2
    else:
        while pos < len(data) and data[pos] != 0:
            pos += data[pos] + 1
        pos += 1
    pos += 2 + 2 + 4
    if pos + 2 > len(data):
        return None
    rdlength = struct.unpack(">H", data[pos:pos + 2])[0]
    pos += 2
    if pos >= len(data):
        return None
    num_names = data[pos]
    pos += 1
    for _ in range(num_names):
        if pos + 18 > len(data):
            break
        raw_name = data[pos:pos + 15]
        suffix = data[pos + 15]
        flags = struct.unpack(">H", data[pos + 16:pos + 18])[0]
        pos += 18
        is_group = bool(flags & 0x8000)
        if suffix == 0x00 and not is_group:
            name = raw_name.decode("ascii", errors="replace").strip()
            if name:
                return name
    return None


def query_netbios_name(ip: str, timeout: float = 1.5) -> str | None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    try:
        sock.sendto(_build_netbios_query(), (ip, 137))
        data, _ = sock.recvfrom(2048)
    except (socket.timeout, OSError):
        return None
    finally:
        sock.close()
    try:
        return _parse_netbios_response(data)
    except Exception:
        return None


def _encode_dns_name(name: str) -> bytes:
    out = bytearray()
    for label in name.strip(".").split("."):
        out.append(len(label))
        out += label.encode("ascii")
    out.append(0)
    return bytes(out)


def _decode_dns_name(data: bytes, pos: int) -> tuple[str, int]:
    labels = []
    seen_pointer = False
    end_pos = pos
    while True:
        if pos >= len(data):
            break
        length = data[pos]
        if length == 0:
            if not seen_pointer:
                end_pos = pos + 1
            break
        if length & 0xC0 == 0xC0:
            if pos + 1 >= len(data):
                break
            pointer = ((length & 0x3F) << 8) | data[pos + 1]
            if not seen_pointer:
                end_pos = pos + 2
            seen_pointer = True
            pos = pointer
            continue
        pos += 1
        labels.append(data[pos:pos + length].decode("ascii", errors="replace"))
        pos += length
    return ".".join(labels), end_pos


def _build_mdns_ptr_query(ip: str) -> bytes:
    reversed_octets = ".".join(reversed(ip.split(".")))
    qname = f"{reversed_octets}.in-addr.arpa"
    header = struct.pack(">HHHHHH", 0, 0x0000, 1, 0, 0, 0)
    qtype = 12
    qclass = 0x8001
    question = _encode_dns_name(qname) + struct.pack(">HH", qtype, qclass)
    return header + question


def _parse_mdns_ptr_response(data: bytes) -> str | None:
    if len(data) < 12:
        return None
    ancount = struct.unpack(">H", data[6:8])[0]
    if ancount == 0:
        return None
    pos = 12
    qdcount = struct.unpack(">H", data[4:6])[0]
    for _ in range(qdcount):
        _, pos = _decode_dns_name(data, pos)
        pos += 4
    for _ in range(ancount):
        _, pos = _decode_dns_name(data, pos)
        if pos + 10 > len(data):
            return None
        rtype = struct.unpack(">H", data[pos:pos + 2])[0]
        rdlength = struct.unpack(">H", data[pos + 8:pos + 10])[0]
        pos += 10
        if rtype == 12:
            name, _ = _decode_dns_name(data, pos)
            return name.removesuffix(".local").removesuffix(".") or None
        pos += rdlength
    return None


def query_mdns_ptr(ip: str, timeout: float = 1.5) -> str | None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    try:
        sock.bind(("", 0))
        sock.sendto(_build_mdns_ptr_query(ip), ("224.0.0.251", 5353))
        data, _ = sock.recvfrom(2048)
    except (socket.timeout, OSError):
        return None
    finally:
        sock.close()
    try:
        return _parse_mdns_ptr_response(data)
    except Exception:
        return None


def resolve_fallback_hostname(ip: str) -> str | None:
    return query_reverse_dns(ip) or query_netbios_name(ip) or query_mdns_ptr(ip)


# ---- Crawl engine ----

def _hex_octetstring_to_bytes(val) -> bytes:
    text = val.prettyPrint()
    if text.startswith("0x"):
        return bytes.fromhex(text[2:])
    return bytes(val)


def _mac_from_bytes(raw: bytes) -> str:
    return ":".join(f"{b:02x}" for b in raw)


def _ip_from_bytes(raw: bytes) -> str:
    return ".".join(str(b) for b in raw)


def _index_suffix(oid_str: str, base_oid: str) -> str:
    return oid_str[len(base_oid) + 1:]


def _index_ints(oid_str: str, base_oid: str) -> list:
    return [int(x) for x in _index_suffix(oid_str, base_oid).split(".")]


async def _probe_scalars(client: SnmpClient, device: Device):
    sys_object_id, err = await client.get(SYS_OBJECT_ID)
    device.debug.append(f"sysObjectID: {'OK -> ' + sys_object_id.prettyPrint() if sys_object_id is not None else 'FAIL -> ' + str(err)}")

    sys_name, err = await client.get(SYS_NAME)
    device.debug.append(f"sysName: {'OK -> ' + sys_name.prettyPrint() if sys_name is not None else 'FAIL -> ' + str(err)}")

    ip_fwd, err = await client.get(IP_FORWARDING)
    device.debug.append(f"ipForwarding: {'OK -> ' + ip_fwd.prettyPrint() if ip_fwd is not None else 'FAIL -> ' + str(err)}")

    bridge_addr, err = await client.get(DOT1D_BASE_BRIDGE_ADDRESS)
    device.debug.append(f"dot1dBaseBridgeAddress: {'OK -> ' + bridge_addr.prettyPrint() if bridge_addr is not None else 'FAIL -> ' + str(err)}")

    device.hostname = sys_name.prettyPrint() if sys_name is not None else None
    device.vendor = vendor_from_sys_object_id(sys_object_id.prettyPrint() if sys_object_id is not None else "")

    ip_forwarding = ip_fwd is not None and ip_fwd.prettyPrint() == "1"
    bridge_mib_present = bridge_addr is not None
    if bridge_mib_present:
        try:
            device.own_macs.add(_mac_from_bytes(_hex_octetstring_to_bytes(bridge_addr)))
        except Exception:
            pass
    device.role = classify_role(device.sys_descr or "", ip_forwarding, bridge_mib_present)


async def _probe_own_ips(client: SnmpClient, device: Device):
    rows, err = await client.walk(IP_AD_ENT_ADDR)
    device.debug.append(f"ipAddrTable walk: {len(rows)} rows (err={err})")
    for _oid_str, val in rows:
        ip = val.prettyPrint()
        if ip:
            device.management_ips.add(ip)


async def _probe_arp(client: SnmpClient, device: Device, end_devices: dict):
    rows, _ = await client.walk(IP_NET_TO_MEDIA_PHYS_ADDRESS)
    for oid_str, val in rows:
        try:
            parts = _index_ints(oid_str, IP_NET_TO_MEDIA_PHYS_ADDRESS)
            ip = ".".join(str(p) for p in parts[-4:])
            mac = _mac_from_bytes(_hex_octetstring_to_bytes(val))
        except Exception:
            continue
        if mac == "00:00:00:00:00:00":
            continue
        ed = end_devices.setdefault(mac, EndDevice(mac=mac))
        ed.ip = ed.ip or ip
        ed.vendor_guess = vendor_from_mac(mac)
        ed.discovered_via.add("arp")


async def _probe_cdp(client: SnmpClient, device: Device):
    device_id_rows, err1 = await client.walk(CDP_CACHE_DEVICE_ID)
    port_rows, err2 = await client.walk(CDP_CACHE_DEVICE_PORT)
    addr_rows, err3 = await client.walk(CDP_CACHE_ADDRESS)
    device.debug.append(
        f"CDP walk: deviceId={len(device_id_rows)} rows (err={err1}), "
        f"port={len(port_rows)} rows (err={err2}), addr={len(addr_rows)} rows (err={err3})"
    )

    ports_by_index = {_index_suffix(o, CDP_CACHE_DEVICE_PORT): v.prettyPrint() for o, v in port_rows}
    addrs_by_index = {}
    for o, v in addr_rows:
        try:
            addrs_by_index[_index_suffix(o, CDP_CACHE_ADDRESS)] = _ip_from_bytes(_hex_octetstring_to_bytes(v))
        except Exception:
            continue

    edges = []
    for oid_str, val in device_id_rows:
        idx = _index_suffix(oid_str, CDP_CACHE_DEVICE_ID)
        edges.append(NeighborEdge(
            local_ip=device.ip,
            local_hostname=device.hostname,
            protocol="cdp",
            remote_name=val.prettyPrint(),
            remote_port=ports_by_index.get(idx),
            remote_ip=addrs_by_index.get(idx),
        ))
    return edges


async def _probe_ospf(client: SnmpClient, device: Device):
    rows, err = await client.walk(OSPF_NBR_STATE)
    device.debug.append(f"OSPF walk: {len(rows)} rows (err={err})")

    edges = []
    for oid_str, _val in rows:
        try:
            parts = _index_ints(oid_str, OSPF_NBR_STATE)
            neighbor_ip = ".".join(str(p) for p in parts[:4])
        except Exception:
            continue
        edges.append(NeighborEdge(
            local_ip=device.ip,
            local_hostname=device.hostname,
            protocol="ospf",
            remote_name=None,
            remote_port=None,
            remote_ip=neighbor_ip,
        ))
    return edges


async def _probe_cam(device: Device, ssh_creds, end_devices: dict):
    rows, trunk_ports, own_macs, err = await asyncio.to_thread(fetch_mac_and_trunk_ports, device.ip, ssh_creds[0], ssh_creds[1])
    device.own_macs.update(own_macs)
    device.debug.append(
        f"CAM (SSH): {len(rows)} entries, {len(trunk_ports)} trunk ports, {len(own_macs)} own interface MACs"
        + (f" (error: {err})" if err else "")
    )

    for mac, vlan_id, port_name in rows:
        ed = end_devices.setdefault(mac, EndDevice(mac=mac))
        ed.vendor_guess = vendor_from_mac(mac)
        ed.discovered_via.add("cam")
        if port_name not in trunk_ports and not port_name.lower().startswith("po"):
            ed.switch_ip = device.ip
            ed.switch_port = port_name


async def _probe_end_host(ed: EndDevice, community_auth):
    client = SnmpClient(ed.ip, community_auth)
    sys_name, _ = await client.get(SYS_NAME)
    sys_descr, _ = await client.get(SYS_DESCR)
    if sys_name is not None:
        if not ed.hostname:
            ed.hostname = sys_name.prettyPrint()
        ed.discovered_via.add("snmp")
    if sys_descr is not None:
        ed.sys_descr = sys_descr.prettyPrint()


async def _probe_end_hosts(end_devices: dict, community_auth):
    targets = [ed for ed in end_devices.values() if ed.ip]
    await asyncio.gather(*(_probe_end_host(ed, community_auth) for ed in targets), return_exceptions=True)


async def _apply_dhcp_hostnames(end_devices: dict, dhcp_creds: tuple):
    host, user, password = dhcp_creds
    hostnames = await asyncio.to_thread(fetch_dhcp_hostnames, host, user, password)
    for mac, ed in end_devices.items():
        if not ed.hostname and mac in hostnames:
            ed.hostname = hostnames[mac]
            ed.discovered_via.add("dhcp")


_FALLBACK_ID_METHODS = (
    ("dns-ptr", query_reverse_dns),
    ("netbios", query_netbios_name),
    ("mdns", query_mdns_ptr),
)


async def _probe_host_id_fallback(end_devices: dict):
    async def probe_one(ed):
        for method, query_fn in _FALLBACK_ID_METHODS:
            name = await asyncio.to_thread(query_fn, ed.ip)
            if name:
                ed.hostname = name
                ed.discovered_via.add(method)
                return

    targets = [ed for ed in end_devices.values() if ed.ip and not ed.hostname]
    await asyncio.gather(*(probe_one(ed) for ed in targets), return_exceptions=True)


def _bridge_interface_macs(interface_names) -> set:
    macs = set()
    for name in interface_names:
        try:
            mac = (Path("/sys/class/net") / name / "address").read_text().strip().lower()
        except OSError:
            continue
        if mac and mac != "00:00:00:00:00:00":
            macs.add(mac)
    return macs


async def probe_device(ip: str, auth_data, ssh_creds, end_devices: dict):
    client = SnmpClient(ip, auth_data)
    device = Device(ip=ip, reachable=False)

    sys_descr, err = await client.get(SYS_DESCR)
    if sys_descr is None:
        device.error = err
        return device, []
    device.reachable = True
    device.sys_descr = sys_descr.prettyPrint()

    await _probe_scalars(client, device)
    await _probe_own_ips(client, device)

    edges = []
    if device.vendor == "Cisco":
        edges += await _probe_cdp(client, device)
    edges += await _probe_ospf(client, device)

    await _probe_arp(client, device, end_devices)

    if device.role == "switch":
        await _probe_cam(device, ssh_creds, end_devices)

    return device, edges


async def discover(seeds, auth_data, ssh_creds, host_community_auth=None, dhcp_creds=None, bridge_interfaces=()) -> DiscoveryResult:
    seeds = list(seeds)
    queue = deque(seeds)
    visited = set()
    devices = {}
    end_devices = {}
    edges = []
    unreachable_seeds = []

    while queue:
        ip = queue.popleft()
        if ip in visited:
            continue
        visited.add(ip)

        device, new_edges = await probe_device(ip, auth_data, ssh_creds, end_devices)

        if not device.reachable:
            devices[ip] = device
            if ip in seeds:
                unreachable_seeds.append(ip)
            continue
        key = device.hostname or ip
        existing = devices.get(key)
        if existing is not None:
            existing.management_ips.add(ip)
            continue

        device.management_ips.add(ip)
        devices[key] = device

        edges.extend(new_edges)
        for edge in new_edges:
            if edge.remote_ip and edge.remote_ip not in visited:
                queue.append(edge.remote_ip)

    known_ips = {ip for d in devices.values() for ip in d.management_ips}
    known_macs = {m for d in devices.values() for m in d.own_macs} | _bridge_interface_macs(bridge_interfaces)
    end_devices = {
        mac: ed for mac, ed in end_devices.items()
        if not (ed.ip and ed.ip in known_ips)
        and mac not in known_macs
    }

    if dhcp_creds is not None and end_devices:
        try:
            await _apply_dhcp_hostnames(end_devices, dhcp_creds)
        except Exception:
            pass

    if host_community_auth is not None:
        await _probe_end_hosts(end_devices, host_community_auth)

    await _probe_host_id_fallback(end_devices)

    return DiscoveryResult(devices, end_devices, edges, unreachable_seeds)


# ---- Persistence (save a discovery run to Postgres) ----

def _upsert_device(session, ip: str, hostname: str, device_type: str, vendor: str) -> int:
    from sqlalchemy import func
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from app.models import Device as DeviceRow

    stmt = pg_insert(DeviceRow).values(
        hostname=hostname,
        management_ip=ip,
        device_type=device_type,
        vendor=vendor,
        is_active=True,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[DeviceRow.hostname],
        set_={
            "management_ip": stmt.excluded.management_ip,
            "device_type": stmt.excluded.device_type,
            "vendor": stmt.excluded.vendor,
            "is_active": True,
            "updated_at": func.now(),
        },
    ).returning(DeviceRow.id)
    return session.execute(stmt).scalar_one()


def _upsert_end_device(session, ip: str, mac: str | None, hostname: str | None, discovered_via: set) -> None:
    from sqlalchemy import delete, func, select
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from app.models import IpamAddress, IpamSubnet, UnregisteredHost

    subnet_id = session.execute(
        select(IpamSubnet.id).where(IpamSubnet.network.op(">>=")(ip)).limit(1)
    ).scalar_one_or_none()

    if subnet_id is not None:
        stmt = pg_insert(IpamAddress).values(
            subnet_id=subnet_id,
            ip_address=ip,
            mac_address=mac,
            hostname=hostname,
            status="active",
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[IpamAddress.ip_address],
            set_={
                "subnet_id": subnet_id,
                "mac_address": mac,
                "hostname": hostname,
                "status": "active",
                "last_seen": func.now(),
            },
        )
        session.execute(stmt)
        session.execute(delete(UnregisteredHost).where(UnregisteredHost.ip_address == ip))
        return
    else:
        stmt = pg_insert(UnregisteredHost).values(
            ip_address=ip,
            mac_address=mac,
            hostname=hostname,
            discovered_by=",".join(sorted(discovered_via)) or None,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[UnregisteredHost.ip_address],
            set_={
                "mac_address": mac,
                "hostname": hostname,
                "discovered_by": ",".join(sorted(discovered_via)) or None,
                "last_seen": func.now(),
            },
        )
    session.execute(stmt)


def save_discovery_result(session, result, seeds: list[str], started_at: datetime) -> dict:
    from sqlalchemy import select

    from app.models import Device as DeviceRow, Discovery

    existing_hostnames = set(session.execute(select(DeviceRow.hostname)).scalars())

    seed_device_id = None
    device_ids_by_hostname = {}
    for device in result.devices.values():
        if not device.reachable or not device.hostname:
            continue
        device_id = _upsert_device(session, device.ip, device.hostname, device.role, device.vendor)
        device_ids_by_hostname[device.hostname] = device_id
        if seed_device_id is None and (device.ip in seeds or device.management_ips & set(seeds)):
            seed_device_id = device_id

    devices_found = len(device_ids_by_hostname)
    devices_new = len(set(device_ids_by_hostname) - existing_hostnames)
    devices_known = devices_found - devices_new

    for mac, ed in result.end_devices.items():
        if not ed.ip:
            continue
        _upsert_end_device(session, ed.ip, mac, ed.hostname, ed.discovered_via)

    discovery_row = Discovery(
        seed_device_id=seed_device_id,
        method="snmp",
        status="completed",
        devices_found=devices_found,
        devices_new=devices_new,
        devices_known=devices_known,
        started_at=started_at,
        completed_at=datetime.now(timezone.utc),
    )
    session.add(discovery_row)
    session.commit()

    return {
        "devices_found": devices_found,
        "devices_new": devices_new,
        "devices_known": devices_known,
        "discovery_id": discovery_row.id,
    }


# ---- IPAM subnet seeding (one-off maintenance: --seed-ipam) ----

IPAM_SUBNETS = [
    ("10.0.0.0/21", "R&D", "10.0.0.1"),
    ("10.0.8.0/23", "SOC", "10.0.8.1"),
    ("10.0.10.0/23", "Data Center", "10.0.10.1"),
    ("10.0.12.0/24", "Guest", "10.0.12.1"),
    ("10.0.13.0/25", "Malware Lab", "10.0.13.1"),
    ("10.0.13.128/26", "Sales", "10.0.13.129"),
    ("10.0.13.192/26", "Marketing", "10.0.13.193"),
    ("10.0.14.0/26", "HR", "10.0.14.1"),
    ("10.0.14.64/27", "Finance", "10.0.14.65"),
    ("10.0.14.96/28", "QA/Testing", "10.0.14.97"),
    ("10.0.14.112/28", "IT/Helpdesk", "10.0.14.113"),
    ("10.0.14.128/28", "Mgmt/NOC", "10.0.14.129"),
    ("10.0.14.144/29", "MAN", "10.0.14.145"),
    ("10.1.0.0/24", "P2P WAN Links", None),
]


def seed_ipam():
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from app.db import get_session
    from app.models import IpamSubnet

    session = get_session()
    try:
        for network, name, gateway in IPAM_SUBNETS:
            stmt = pg_insert(IpamSubnet).values(network=network, name=name, gateway=gateway)
            stmt = stmt.on_conflict_do_update(
                index_elements=[IpamSubnet.network],
                set_={"name": stmt.excluded.name, "gateway": stmt.excluded.gateway},
            )
            session.execute(stmt)
        session.commit()
    finally:
        session.close()
    print(f"Seeded {len(IPAM_SUBNETS)} subnets into ipam_subnet.")


# ---- CLI ----

def get_auth_data():
    user = os.environ.get("SPECTRA_SNMPV3_USER", "noc-agent")
    auth_key = os.environ.get("SPECTRA_SNMPV3_AUTH_KEY")
    priv_key = os.environ.get("SPECTRA_SNMPV3_PRIV_KEY")
    if not auth_key or not priv_key:
        sys.exit(
            "Missing SPECTRA_SNMPV3_AUTH_KEY / SPECTRA_SNMPV3_PRIV_KEY.\n"
            "Copy .env.example to .env and fill in real values."
        )
    return build_auth_data(user, auth_key, priv_key)


def get_host_community_auth():
    community = os.environ.get("SPECTRA_SNMP_HOST_COMMUNITY", "public")
    return build_community_data(community)


def get_dhcp_creds():
    host = os.environ.get("SPECTRA_DHCP_SERVER_HOST")
    user = os.environ.get("SPECTRA_DHCP_SERVER_SSH_USER")
    password = os.environ.get("SPECTRA_DHCP_SERVER_SSH_PASSWORD")
    if not host or not user or not password:
        return None
    return (host, user, password)


def get_bridge_interfaces():
    raw = os.environ.get("SPECTRA_BRIDGE_INTERFACES", "")
    return [name.strip() for name in raw.split(",") if name.strip()]


def get_ssh_creds():
    user = os.environ.get("SPECTRA_SSH_USER")
    password = os.environ.get("SPECTRA_SSH_PASSWORD")
    if not user or not password:
        sys.exit(
            "Missing SPECTRA_SSH_USER / SPECTRA_SSH_PASSWORD.\n"
            "Copy .env.example to .env and fill in real values."
        )
    return user, password


def _device_category(device):
    if device.role == "switch" and device.hostname and device.hostname.lower().startswith("phys"):
        return "physical switch"
    return device.role or "unknown"


def print_summary(result):
    reachable = [d for d in result.devices.values() if d.reachable]
    unreachable = [d for d in result.devices.values() if not d.reachable]
    identified = [ed for ed in result.end_devices.values() if ed.hostname]
    unidentified = [ed for ed in result.end_devices.values() if not ed.hostname]
    total = len(result.devices) + len(result.end_devices)

    counts = {}
    for d in reachable:
        counts[_device_category(d)] = counts.get(_device_category(d), 0) + 1

    print(f"\n{'=' * 70}\nSUMMARY\n{'=' * 70}")
    print(f"  {total} devices total on this crawl")
    print(f"  {len(result.end_devices)} end devices  ({len(identified)} identified, {len(unidentified)} unidentified)")
    for category, n in sorted(counts.items()):
        print(f"  {n} {category}{'es' if category.endswith('h') else 's'}")
    if unreachable:
        print(f"  {len(unreachable)} unreachable (likely the network's edge/boundary)")


def print_report(result, verbose=False):
    print_summary(result)

    if not verbose:
        print(f"\n{'=' * 70}\nMANAGED DEVICES ({len(result.devices)})\n{'=' * 70}")
        for device in sorted(result.devices.values(), key=lambda d: d.ip):
            if not device.reachable:
                print(f"  {device.ip:<16} UNREACHABLE")
                continue
            print(f"  {device.ip:<16} {device.role:<10} {device.hostname or '?'}")

        print(f"\n{'=' * 70}\nEND DEVICES ({len(result.end_devices)})\n{'=' * 70}")
        for mac, ed in sorted(result.end_devices.items()):
            if not ed.hostname:
                continue
            print(f"  {ed.ip or '?':<16} {ed.hostname:<20} ({mac})")
        n_hidden = sum(1 for ed in result.end_devices.values() if not ed.hostname)
        if n_hidden:
            print(f"  ... plus {n_hidden} more with no known name/IP yet (run with -v to see them)")

        print(f"\nRun with -v for full per-device diagnostics, CDP/OSPF topology edges, and every end device.")
        if result.unreachable_seeds:
            print(f"\nWARNING: {len(result.unreachable_seeds)} seed(s) never responded: {result.unreachable_seeds}")
        return

    print(f"\n{'=' * 70}\nMANAGED DEVICES ({len(result.devices)})\n{'=' * 70}")
    for device in sorted(result.devices.values(), key=lambda d: d.ip):
        if not device.reachable:
            print(f"  {device.ip:<16} UNREACHABLE -> {device.error}")
            continue
        first_line = device.sys_descr.splitlines()[0] if device.sys_descr else ""
        other_ips = sorted(device.management_ips - {device.ip})
        ip_label = device.ip + (f" (+{len(other_ips)} more IP{'s' if len(other_ips) != 1 else ''})" if other_ips else "")
        print(f"  {ip_label:<28} {device.role:<10} {device.vendor:<10} {device.hostname or '?'}")
        print(f"                              {first_line}")
        if other_ips:
            print(f"                              [debug] also reachable at: {', '.join(other_ips)}")
        for line in device.debug:
            print(f"                              [debug] {line}")

    print(f"\n{'=' * 70}\nTOPOLOGY EDGES ({len(result.edges)})\n{'=' * 70}")
    seen = set()
    for edge in result.edges:
        key = (edge.local_ip, edge.remote_name, edge.remote_ip, edge.remote_port, edge.protocol)
        if key in seen:
            continue
        seen.add(key)
        if edge.remote_name and edge.remote_ip and edge.remote_name != edge.remote_ip:
            remote = f"{edge.remote_name} ({edge.remote_ip})"
        else:
            remote = edge.remote_name or edge.remote_ip or "?"
        local = edge.local_hostname or edge.local_ip
        print(f"  [{edge.protocol.upper():<4}] {local} -- {remote}  (remote port: {edge.remote_port or '?'})")

    print(f"\n{'=' * 70}\nEND DEVICES ({len(result.end_devices)})\n{'=' * 70}")
    for mac, ed in sorted(result.end_devices.items()):
        if ed.switch_ip:
            location = f"{ed.switch_ip} / {ed.switch_port}"
        elif "cam" in ed.discovered_via:
            location = "seen via a trunk/uplink port only -- true access port not yet known"
        else:
            location = "location unknown (ARP only)"
        via = ",".join(sorted(ed.discovered_via))
        print(f"  {mac}  ip={ed.ip or '?':<15} host={ed.hostname or '?':<16} vendor={ed.vendor_guess:<20} via={via:<8} @ {location}")

    if result.unreachable_seeds:
        print(f"\nWARNING: {len(result.unreachable_seeds)} seed(s) never responded: {result.unreachable_seeds}")


def main():
    parser = argparse.ArgumentParser(description="SNMPv3 network discovery crawl.")
    parser.add_argument("seeds", nargs="*", help="Seed IP(s) to start the crawl from")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print per-device SNMP diagnostics")
    parser.add_argument("--save", action="store_true", help="Persist results to the app database")
    parser.add_argument("--seed-ipam", action="store_true", help="Seed IPAM subnets into the DB and exit (no crawl)")
    args = parser.parse_args()

    if args.seed_ipam:
        seed_ipam()
        return

    if not args.seeds:
        parser.error("at least one seed IP is required unless --seed-ipam is given")

    auth_data = get_auth_data()
    ssh_creds = get_ssh_creds()
    host_community_auth = get_host_community_auth()
    dhcp_creds = get_dhcp_creds()
    bridge_interfaces = get_bridge_interfaces()
    started_at = datetime.now(timezone.utc)
    result = asyncio.run(discover(args.seeds, auth_data, ssh_creds, host_community_auth, dhcp_creds, bridge_interfaces))
    print_report(result, verbose=args.verbose)

    if args.save:
        from app.db import get_session

        session = get_session()
        try:
            summary = save_discovery_result(session, result, args.seeds, started_at)
        finally:
            session.close()
        print(
            f"\nSaved to DB: {summary['devices_found']} devices "
            f"({summary['devices_new']} new, {summary['devices_known']} known), "
            f"discovery id={summary['discovery_id']}"
        )


if __name__ == "__main__":
    main()

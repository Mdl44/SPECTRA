# S.P.E.C.T.R.A Network Topology

## 1. Departments and VLANs (LAN)

| Department | VLAN | Required Hosts | IPv4 Subnet (/Mask) | IPv4 Gateway | IPv4 DHCP Range | IPv6 Gateway | IPv6 DHCPv6 Range | Router |
|---|---|---|---|---|---|---|---|---|
| R&D | 20 | 1024 | /21 (`10.0.0.0`) | `10.0.0.1` | `.21` - `10.0.7.254` | `fd44:f1:f1:20::1` | `::10` - `::ffff` | R-RD |
| SOC | 21 | 510 | /23 (`10.0.8.0`) | `10.0.8.1` | `.21` - `10.0.9.254` | `fd44:f1:f1:21::1` | `::10` - `::ffff` | R-SOC |
| Data Center | 22 | 255 | /23 (`10.0.10.0`) | `10.0.10.1` | `.21` - `10.0.11.254` | `fd44:f1:f1:22::1` | `::10` - `::ffff` | R-DC |
| Guest | 24 | 127 | /24 (`10.0.12.0`) | `10.0.12.1` | `.21` - `10.0.12.254` | `fd44:f1:f1:24::1` | `::10` - `::ffff` | R-Guest |
| Malware Lab | 23 | 126 | /25 (`10.0.13.0`) | `10.0.13.1` | `.21` - `10.0.13.126` | `fd44:f1:f1:23::1` | `::10` - `::ffff` | R-MalwareLab |
| Sales | 10 | 62 | /26 (`10.0.13.128`) | `10.0.13.129` | `.140` - `.190` | `fd44:f1:f1:10::1` | `::10` - `::ffff` | R-Corp |
| Marketing | 11 | 62 | /26 (`10.0.13.192`) | `10.0.13.193` | `.200` - `.254` | `fd44:f1:f1:11::1` | `::10` - `::ffff` | R-Corp |
| HR | 12 | 31 | /26 (`10.0.14.0`) | `10.0.14.1` | `.10` - `.62` | `fd44:f1:f1:12::1` | `::10` - `::ffff` | R-Corp |
| Finance | 13 | 30 | /27 (`10.0.14.64`) | `10.0.14.65` | `.75` - `.94` | `fd44:f1:f1:13::1` | `::10` - `::ffff` | R-Corp |
| QA/Testing | 25 | 14 | /28 (`10.0.14.96`) | `10.0.14.97` | `.100` - `.110` | `fd44:f1:f1:25::1` | `::10` - `::ffff` | R-QA |
| IT/Helpdesk | 26 | 14 | /28 (`10.0.14.112`) | `10.0.14.113` | `.116` - `.126` | `fd44:f1:f1:26::1` | `::10` - `::ffff` | R-IT |
| Mgmt/NOC | 27 | 14 | /28 (`10.0.14.128`) | `10.0.14.129` | STATIC ONLY | `fd44:f1:f1:27::1` | STATIC ONLY | R-Mgmt |
| MAN (Internal)| 99 | - | /29 (`10.0.14.144`) | `10.0.14.145` | STATIC ONLY | `fd44:f1:f1:99::1` | STATIC ONLY | R-Corp |

---

## 2. P2P Links (Inter-Router)

**IPv4 Block:** `10.1.0.0/24` (Subnetted to `/30`)
**IPv6 Block:** `fd44:f1:f1:c04e::/64` (Subnetted to `/127`)

| Connection | IPv4 Subnet (/30) | Device A IPv4 | Device B IPv4 | IPv6 Subnet (/127) | Device A IPv6 | Device B IPv6 |
|---|---|---|---|---|---|---|
| R-Corp ↔ Core 1 | `10.1.0.12` | `10.1.0.13` | `10.1.0.14` | `...:c04e::6` | `::6` | `::7` |
| R-Corp ↔ Core 2 | `10.1.0.16` | `10.1.0.17` | `10.1.0.18` | `...:c04e::8` | `::8` | `::9` |
| Core 1 ↔ Core 2 | `10.1.0.0` | `10.1.0.1` | `10.1.0.2` | `...:c04e::0` | `::0` | `::1` |
| Firewall ↔ Core 1 | `10.1.0.4` | `10.1.0.5` | `10.1.0.6` | `...:c04e::2` | `::2` | `::3` |
| R-RD ↔ Core 1 | `10.1.0.20` | `10.1.0.21` | `10.1.0.22` | `...:c04e::a` | `::a` | `::b` |
| R-SOC ↔ Core 1 | `10.1.0.28` | `10.1.0.29` | `10.1.0.30` | `...:c04e::e` | `::e` | `::f` |
| R-DC ↔ Core 1 | `10.1.0.36` | `10.1.0.37` | `10.1.0.38` | `...:c04e::12` | `::12` | `::13` |
| R-MalwareLab ↔ Core1 | `10.1.0.44` | `10.1.0.45` | `10.1.0.46` | `...:c04e::16` | `::16` | `::17` |
| R-Guest ↔ Core 1 | `10.1.0.52` | `10.1.0.53` | `10.1.0.54` | `...:c04e::1a` | `::1a` | `::1b` |
| R-QA ↔ Core 1 | `10.1.0.60` | `10.1.0.61` | `10.1.0.62` | `...:c04e::1e` | `::1e` | `::1f` |
| R-IT ↔ Core 1 | `10.1.0.68` | `10.1.0.69` | `10.1.0.70` | `...:c04e::22` | `::22` | `::23` |
| R-Mgmt ↔ Core 1 | `10.1.0.76` | `10.1.0.77` | `10.1.0.78` | `...:c04e::26` | `::26` | `::27` |
| Firewall ↔ Core 2 | `10.1.0.8` | `10.1.0.9` | `10.1.0.10` | `...:c04e::4` | `::4` | `::5` |
| R-RD ↔ Core 2 | `10.1.0.24` | `10.1.0.25` | `10.1.0.26` | `...:c04e::c` | `::c` | `::d` |
| R-SOC ↔ Core 2 | `10.1.0.32` | `10.1.0.33` | `10.1.0.34` | `...:c04e::10` | `::10` | `::11` |
| R-DC ↔ Core 2 | `10.1.0.40` | `10.1.0.41` | `10.1.0.42` | `...:c04e::14` | `::14` | `::15` |
| R-MalwareLab ↔ Core2 | `10.1.0.48` | `10.1.0.49` | `10.1.0.50` | `...:c04e::18` | `::18` | `::19` |
| R-Guest ↔ Core 2 | `10.1.0.56` | `10.1.0.57` | `10.1.0.58` | `...:c04e::1c` | `::1c` | `::1d` |
| R-QA ↔ Core 2 | `10.1.0.64` | `10.1.0.65` | `10.1.0.66` | `...:c04e::20` | `::20` | `::21` |
| R-IT ↔ Core 2 | `10.1.0.72` | `10.1.0.73` | `10.1.0.74` | `...:c04e::24` | `::24` | `::25` |
| R-Mgmt ↔ Core 2 | `10.1.0.80` | `10.1.0.81` | `10.1.0.82` | `...:c04e::28` | `::28` | `::29` |
| ISP ↔ Firewall | `203.0.113.0` | `203.0.113.2` | `203.0.113.1` | - | - | - |

---

## 3. Hardware / Platforms

- **L2/L3 Switches:** Cisco Catalyst 3650 (IOS XE)
- **Routers:** Cisco ISR 4431 (IOS XE)
- **Firewall:** Cisco ASA 5505

## 4. OSPF Areas (Multi-Area Hierarchy)

| Router | Assigned OSPF Area | Description |
|---|---|---|
| **Core 1 / Core 2** | `Area 0` | Backbone (transit `/30` links only) |
| **R-Corp** | `Area 10` | Corporate LANs (Sales, Mktg, HR, Fin, MAN) |
| **R-RD** | `Area 20` | R&D LAN |
| **R-SOC** | `Area 21` | SOC LAN |
| **R-DC** | `Area 22` | Data Center LAN |
| **R-MalwareLab** | `Area 23` | Malware Lab LAN |
| **R-Guest** | `Area 24` | Guest LAN |
| **R-QA** | `Area 25` | QA / Testing LAN |
| **R-IT** | `Area 26` | IT / Helpdesk LAN |
| **R-Mgmt** | `Area 27` | Management / NOC LAN |

*(Note: All WAN P2P links remain in Area 0 to form the Backbone. Only the LAN segments are placed in their respective non-zero areas.)*

## 5. Detailed Interface Mapping
| Device | Interface | IPv4 / Mask | IPv6 | VLAN | Destination / Description |
|---|---|---|---|---|---|
| **SwAcc1** | range g0/0-1 | - | - | 10 | - |
| **SwAcc1** | range g0/2-3 | - | - | 11 | - |
| **SwAcc1** | range g1/0-1 | - | - | 12 | - |
| **SwAcc1** | range g1/2-3 | - | - | 13 | - |
| **SwAcc1** | range g2/2-3 | - | - | 98 | - |
| **SwAcc1** | range g3/1-3 | - | - | 98 | - |
| **SwAcc1** | vlan 99 | 10.0.14.146 255.255.255.248 | fd44:f1:f1:99::2/64 | - | Management SVI |
| **SwAcc2** | range g0/0-1 | - | - | 10 | - |
| **SwAcc2** | range g0/2-3 | - | - | 11 | - |
| **SwAcc2** | range g1/0-1 | - | - | 12 | - |
| **SwAcc2** | range g1/2-3 | - | - | 13 | - |
| **SwAcc2** | range g2/2-3 | - | - | 98 | - |
| **SwAcc2** | range g3/1-3 | - | - | 98 | - |
| **SwAcc2** | vlan 99 | 10.0.14.147 255.255.255.248 | fd44:f1:f1:99::3/64 | - | Management SVI |
| **SwD1** | range g0/0-1 | - | - | 10 | - |
| **SwD1** | range g0/2-3 | - | - | 11 | - |
| **SwD1** | range g1/0-1 | - | - | 12 | - |
| **SwD1** | range g1/2-3 | - | - | 13 | - |
| **SwD1** | range g3/1-3 | - | - | 98 | - |
| **SwD1** | vlan 99 | 10.0.14.148 255.255.255.248 | fd44:f1:f1:99::4/64 | - | Management SVI |
| **SwD2** | range g0/0-1 | - | - | 10 | - |
| **SwD2** | range g0/2-3 | - | - | 11 | - |
| **SwD2** | range g1/0-1 | - | - | 12 | - |
| **SwD2** | range g1/2-3 | - | - | 13 | - |
| **SwD2** | range g3/1-3 | - | - | 98 | - |
| **SwD2** | vlan 99 | 10.0.14.149 255.255.255.248 | fd44:f1:f1:99::5/64 | - | Management SVI |
| **SwC** | range g0/0-1 | - | - | 10 | - |
| **SwC** | range g0/2-3 | - | - | 11 | - |
| **SwC** | range g1/0-1 | - | - | 12 | - |
| **SwC** | range g1/2-3 | - | - | 13 | - |
| **SwC** | range g3/1-3 | - | - | 98 | - |
| **SwC** | vlan 99 | 10.0.14.150 255.255.255.248 | fd44:f1:f1:99::6/64 | - | Management SVI |
| **R-Corp** | GigabitEthernet0/0 | - | - | - | Link to Core Switch SwC |
| **R-Corp** | GigabitEthernet0/0.98 | - | - | 98 | Native/Null VLAN 98 |
| **R-Corp** | GigabitEthernet0/0.10 | 10.0.13.129 255.255.255.192 | fd44:f1:f1:10::1/64 | 10 | Sales VLAN 10 |
| **R-Corp** | GigabitEthernet0/0.11 | 10.0.13.193 255.255.255.192 | fd44:f1:f1:11::1/64 | 11 | Marketing VLAN 11 |
| **R-Corp** | GigabitEthernet0/0.12 | 10.0.14.1 255.255.255.192 | fd44:f1:f1:12::1/64 | 12 | HR VLAN 12 |
| **R-Corp** | GigabitEthernet0/0.13 | 10.0.14.65 255.255.255.224 | fd44:f1:f1:13::1/64 | 13 | Finance VLAN 13 |
| **R-Corp** | GigabitEthernet0/0.99 | 10.0.14.145 255.255.255.248 | fd44:f1:f1:99::1/64 | 99 | MAN VLAN 99 |
| **R-Corp** | GigabitEthernet0/1 | 10.1.0.14 255.255.255.252 | fd44:f1:f1:c04e::7/127 | - | WAN Link to Core 1 |
| **R-Corp** | GigabitEthernet0/2 | 10.1.0.18 255.255.255.252 | fd44:f1:f1:c04e::9/127 | - | WAN Link to Core 2 |
| **R-Corp** | range GigabitEthernet0/3 - 7 | - | - | - | UNUSED |
| **R-Corp** | range GigabitEthernet0/8 - 15 | - | - | - | UNUSED |
| **Core1** | GigabitEthernet0/0 | 10.1.0.1 255.255.255.252 | fd44:f1:f1:c04e::0/127 | - | Link to Core 2 |
| **Core1** | GigabitEthernet0/1 | 10.1.0.5 255.255.255.252 | fd44:f1:f1:c04e::2/127 | - | Link to Firewall |
| **Core1** | GigabitEthernet0/2 | 10.1.0.13 255.255.255.252 | fd44:f1:f1:c04e::6/127 | - | Link to R-Corp |
| **Core1** | GigabitEthernet0/3 | 10.1.0.21 255.255.255.252 | fd44:f1:f1:c04e::a/127 | - | Link to R-RD |
| **Core1** | GigabitEthernet0/4 | 10.1.0.29 255.255.255.252 | fd44:f1:f1:c04e::e/127 | - | Link to R-SOC |
| **Core1** | GigabitEthernet0/5 | 10.1.0.37 255.255.255.252 | fd44:f1:f1:c04e::12/127 | - | Link to R-DC |
| **Core1** | GigabitEthernet0/6 | 10.1.0.45 255.255.255.252 | fd44:f1:f1:c04e::16/127 | - | Link to R-MalwareLab |
| **Core1** | GigabitEthernet0/7 | 10.1.0.53 255.255.255.252 | fd44:f1:f1:c04e::1a/127 | - | Link to R-Guest |
| **Core1** | GigabitEthernet0/8 | 10.1.0.61 255.255.255.252 | fd44:f1:f1:c04e::1e/127 | - | Link to R-QA |
| **Core1** | GigabitEthernet0/9 | 10.1.0.69 255.255.255.252 | fd44:f1:f1:c04e::22/127 | - | Link to R-IT |
| **Core1** | GigabitEthernet0/10 | 10.1.0.77 255.255.255.252 | fd44:f1:f1:c04e::26/127 | - | Link to R-Mgmt |
| **Core1** | range GigabitEthernet0/11 - 15 | - | - | - | UNUSED |
| **Core2** | GigabitEthernet0/0 | 10.1.0.2 255.255.255.252 | fd44:f1:f1:c04e::1/127 | - | Link to Core 1 |
| **Core2** | GigabitEthernet0/1 | 10.1.0.9 255.255.255.252 | fd44:f1:f1:c04e::4/127 | - | Link to Firewall |
| **Core2** | GigabitEthernet0/2 | 10.1.0.17 255.255.255.252 | fd44:f1:f1:c04e::8/127 | - | Link to R-Corp |
| **Core2** | GigabitEthernet0/3 | 10.1.0.25 255.255.255.252 | fd44:f1:f1:c04e::c/127 | - | Link to R-RD |
| **Core2** | GigabitEthernet0/4 | 10.1.0.33 255.255.255.252 | fd44:f1:f1:c04e::10/127 | - | Link to R-SOC |
| **Core2** | GigabitEthernet0/5 | 10.1.0.41 255.255.255.252 | fd44:f1:f1:c04e::14/127 | - | Link to R-DC |
| **Core2** | GigabitEthernet0/6 | 10.1.0.49 255.255.255.252 | fd44:f1:f1:c04e::18/127 | - | Link to R-MalwareLab |
| **Core2** | GigabitEthernet0/7 | 10.1.0.57 255.255.255.252 | fd44:f1:f1:c04e::1c/127 | - | Link to R-Guest |
| **Core2** | GigabitEthernet0/8 | 10.1.0.65 255.255.255.252 | fd44:f1:f1:c04e::20/127 | - | Link to R-QA |
| **Core2** | GigabitEthernet0/9 | 10.1.0.73 255.255.255.252 | fd44:f1:f1:c04e::24/127 | - | Link to R-IT |
| **Core2** | GigabitEthernet0/10 | 10.1.0.81 255.255.255.252 | fd44:f1:f1:c04e::28/127 | - | Link to R-Mgmt |
| **Core2** | range GigabitEthernet0/11 - 15 | - | - | - | UNUSED |
| **Firewall** | GigabitEthernet0/0 | 10.1.0.6 255.255.255.252 | fd44:f1:f1:c04e::3/127 | - | - |
| **Firewall** | GigabitEthernet0/1 | 10.1.0.10 255.255.255.252 | fd44:f1:f1:c04e::5/127 | - | - |
| **Firewall** | GigabitEthernet0/2 | 203.0.113.1 255.255.255.252 | - | - | - |
| **ISP** | GigabitEthernet0/0 | 203.0.113.2 255.255.255.252 | - | - | Link to Firewall |
| **ISP** | Loopback0 | 8.8.8.8 255.255.255.255 | - | - | Simulated 8.8.8.8 server |
| **ISP** | range GigabitEthernet0/1 - 7 | - | - | - | UNUSED |
| **ISP** | range GigabitEthernet0/8 - 15 | - | - | - | UNUSED |
| **R-RD** | GigabitEthernet0/0 | 10.0.0.1 255.255.248.0 | fd44:f1:f1:20::1/64 | - | LAN R&D VLAN 20 |
| **R-RD** | GigabitEthernet0/1 | 10.1.0.22 255.255.255.252 | fd44:f1:f1:c04e::b/127 | - | WAN Link to Core 1 |
| **R-RD** | GigabitEthernet0/2 | 10.1.0.26 255.255.255.252 | fd44:f1:f1:c04e::d/127 | - | WAN Link to Core 2 |
| **R-RD** | range GigabitEthernet0/3 - 7 | - | - | - | UNUSED |
| **R-RD** | range GigabitEthernet0/8 - 15 | - | - | - | UNUSED |
| **SwRD** | g0/0 | - | - | 20 | - |
| **SwRD** | range g0/1-3, g1/0-3, g2/0-3, g3/0-3 | - | - | 20 | - |
| **SwRD** | vlan 20 | 10.0.0.2 255.255.248.0 | fd44:f1:f1:20::2/64 | - | Management SVI RD |
| **R-SOC** | GigabitEthernet0/0 | 10.0.8.1 255.255.254.0 | fd44:f1:f1:21::1/64 | - | LAN SOC VLAN 21 |
| **R-SOC** | GigabitEthernet0/1 | 10.1.0.30 255.255.255.252 | fd44:f1:f1:c04e::f/127 | - | WAN Link to Core 1 |
| **R-SOC** | GigabitEthernet0/2 | 10.1.0.34 255.255.255.252 | fd44:f1:f1:c04e::11/127 | - | WAN Link to Core 2 |
| **R-SOC** | range GigabitEthernet0/3 - 7 | - | - | - | UNUSED |
| **R-SOC** | range GigabitEthernet0/8 - 15 | - | - | - | UNUSED |
| **SwSOC** | g0/0 | - | - | 21 | - |
| **SwSOC** | range g0/1-3, g1/0-3, g2/0-3, g3/0-3 | - | - | 21 | - |
| **SwSOC** | vlan 21 | 10.0.8.2 255.255.254.0 | fd44:f1:f1:21::2/64 | - | Management SVI SOC |
| **R-DC** | GigabitEthernet0/0 | 10.0.10.1 255.255.254.0 | fd44:f1:f1:22::1/64 | - | LAN DC VLAN 22 |
| **R-DC** | GigabitEthernet0/1 | 10.1.0.38 255.255.255.252 | fd44:f1:f1:c04e::13/127 | - | WAN Link to Core 1 |
| **R-DC** | GigabitEthernet0/2 | 10.1.0.42 255.255.255.252 | fd44:f1:f1:c04e::15/127 | - | WAN Link to Core 2 |
| **R-DC** | range GigabitEthernet0/3 - 7 | - | - | - | UNUSED |
| **R-DC** | range GigabitEthernet0/8 - 15 | - | - | - | UNUSED |
| **SwDC** | g0/0 | - | - | 22 | - |
| **SwDC** | range g0/1-3, g1/0-3, g2/0-3, g3/0-3 | - | - | 22 | - |
| **SwDC** | vlan 22 | 10.0.10.2 255.255.254.0 | fd44:f1:f1:22::2/64 | - | Management SVI DC |
| **R-MalwareLab** | GigabitEthernet0/0 | 10.0.13.1 255.255.255.128 | fd44:f1:f1:23::1/64 | - | LAN MalwareLab VLAN 23 |
| **R-MalwareLab** | GigabitEthernet0/1 | 10.1.0.46 255.255.255.252 | fd44:f1:f1:c04e::17/127 | - | WAN Link to Core 1 |
| **R-MalwareLab** | GigabitEthernet0/2 | 10.1.0.50 255.255.255.252 | fd44:f1:f1:c04e::19/127 | - | WAN Link to Core 2 |
| **R-MalwareLab** | range GigabitEthernet0/3 - 7 | - | - | - | UNUSED |
| **R-MalwareLab** | range GigabitEthernet0/8 - 15 | - | - | - | UNUSED |
| **SwMalwareLab** | g0/0 | - | - | 23 | - |
| **SwMalwareLab** | range g0/1-3, g1/0-3, g2/0-3, g3/0-3 | - | - | 23 | - |
| **SwMalwareLab** | vlan 23 | 10.0.13.2 255.255.255.128 | fd44:f1:f1:23::2/64 | - | Management SVI MalwareLab |
| **R-Guest** | GigabitEthernet0/0 | 10.0.12.1 255.255.255.0 | fd44:f1:f1:24::1/64 | - | LAN Guest VLAN 24 |
| **R-Guest** | GigabitEthernet0/1 | 10.1.0.54 255.255.255.252 | fd44:f1:f1:c04e::1b/127 | - | WAN Link to Core 1 |
| **R-Guest** | GigabitEthernet0/2 | 10.1.0.58 255.255.255.252 | fd44:f1:f1:c04e::1d/127 | - | WAN Link to Core 2 |
| **R-Guest** | range GigabitEthernet0/3 - 7 | - | - | - | UNUSED |
| **R-Guest** | range GigabitEthernet0/8 - 15 | - | - | - | UNUSED |
| **SwGuest** | g0/0 | - | - | 24 | - |
| **SwGuest** | range g0/1-3, g1/0-3, g2/0-3, g3/0-3 | - | - | 24 | - |
| **SwGuest** | vlan 24 | 10.0.12.2 255.255.255.0 | fd44:f1:f1:24::2/64 | - | Management SVI Guest |
| **R-QA** | GigabitEthernet0/0 | 10.0.14.97 255.255.255.240 | fd44:f1:f1:25::1/64 | - | LAN QA VLAN 25 |
| **R-QA** | GigabitEthernet0/1 | 10.1.0.62 255.255.255.252 | fd44:f1:f1:c04e::1f/127 | - | WAN Link to Core 1 |
| **R-QA** | GigabitEthernet0/2 | 10.1.0.66 255.255.255.252 | fd44:f1:f1:c04e::21/127 | - | WAN Link to Core 2 |
| **R-QA** | range GigabitEthernet0/3 - 7 | - | - | - | UNUSED |
| **R-QA** | range GigabitEthernet0/8 - 15 | - | - | - | UNUSED |
| **SwQA** | g0/0 | - | - | 25 | - |
| **SwQA** | range g0/1-3, g1/0-3, g2/0-3, g3/0-3 | - | - | 25 | - |
| **SwQA** | vlan 25 | 10.0.14.98 255.255.255.240 | fd44:f1:f1:25::2/64 | - | Management SVI QA |
| **R-IT** | GigabitEthernet0/0 | 10.0.14.113 255.255.255.240 | fd44:f1:f1:26::1/64 | - | LAN IT VLAN 26 |
| **R-IT** | GigabitEthernet0/1 | 10.1.0.70 255.255.255.252 | fd44:f1:f1:c04e::23/127 | - | WAN Link to Core 1 |
| **R-IT** | GigabitEthernet0/2 | 10.1.0.74 255.255.255.252 | fd44:f1:f1:c04e::25/127 | - | WAN Link to Core 2 |
| **R-IT** | range GigabitEthernet0/3 - 7 | - | - | - | UNUSED |
| **R-IT** | range GigabitEthernet0/8 - 15 | - | - | - | UNUSED |
| **SwIT** | g0/0 | - | - | 26 | - |
| **SwIT** | range g0/1-3, g1/0-3, g2/0-3, g3/0-3 | - | - | 26 | - |
| **SwIT** | vlan 26 | 10.0.14.114 255.255.255.240 | fd44:f1:f1:26::2/64 | - | Management SVI IT |
| **R-Mgmt** | GigabitEthernet0/0 | 10.0.14.129 255.255.255.240 | fd44:f1:f1:27::1/64 | - | LAN Mgmt VLAN 27 |
| **R-Mgmt** | GigabitEthernet0/1 | 10.1.0.78 255.255.255.252 | fd44:f1:f1:c04e::27/127 | - | WAN Link to Core 1 |
| **R-Mgmt** | GigabitEthernet0/2 | 10.1.0.82 255.255.255.252 | fd44:f1:f1:c04e::29/127 | - | WAN Link to Core 2 |
| **R-Mgmt** | range GigabitEthernet0/3 - 7 | - | - | - | UNUSED |
| **R-Mgmt** | range GigabitEthernet0/8 - 15 | - | - | - | UNUSED |
| **SwMgmt** | range g0/0-1 | - | - | 27 | - |
| **SwMgmt** | range g0/2-3, g1/0-3, g2/0-3, g3/0-3 | - | - | 27 | - |
| **SwMgmt** | vlan 27 | 10.0.14.130 255.255.255.240 | fd44:f1:f1:27::2/64 | - | Management SVI Mgmt |

---

## 6. Physical Infrastructure Extension

These physical devices are connected to the GNS3 topology via a Cloud node bridged to the host's physical network interface (e.g., `eth0`). They are part of the Mgmt/NOC LAN (`10.0.14.128/28`).

| Device | Platform | Management IP (VLAN 27) | Gateway | Notes |
|---|---|---|---|---|
| **Phys_SwAcc1** | Catalyst 2960-X | `10.0.14.131/28` | `10.0.14.129` | Access Switch. Connect Laptop/Cloud to `Gi1/0/1` |
| **Phys_SwC1** | Catalyst 9200L | `10.0.14.132/28` | `10.0.14.129` | Core Switch |
| **Phys_SwD1** | Catalyst 9200L | `10.0.14.133/28` | `10.0.14.129` | Distribution Switch |

**Physical Connectivity:**
1. **Laptop (GNS3 Cloud Node)** connects to **Phys_SwAcc1** on port `Gi1/0/1`. (Ensure port is in `vlan 27`).
2. **Phys_SwAcc1** connects to **Phys_SwD1** via EtherChannel (Trunk).
3. **Phys_SwD1** connects to **Phys_SwC1** via EtherChannel (Trunk).


## 7. Inventory - 54 total
- 24 end devices
- 13 switches + 3 physical
- 11 routers
- 1 isp router
- 1 firewall
- 1 laptop
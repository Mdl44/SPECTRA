# S.P.E.C.T.R.A 🕸️
**Secure Platform for Enterprise Campus Topology, Reconnaissance & Automation**

S.P.E.C.T.R.A is a comprehensive network engineering and automation project combining a highly structured, multi-area OSPF enterprise network topology with a Python-based intelligent crawler designed to map, analyze, and monitor the infrastructure.

## 🏗️ Infrastructure Overview
The network topology represents a modern, resilient enterprise architecture built and simulated using **GNS3**, integrated seamlessly with **real physical Cisco hardware** (Catalyst 9200L & 2960-X switches).

### Key Networking Features:
- **Hierarchical Design:** Core, Distribution, and Access layers.
- **Multi-Area OSPF:** Backbone Area 0 interconnecting 10+ departmental LANs (Areas 10-27).
- **Redundancy & L2/L3 Loop Prevention:** EtherChannel (LACP) trunks, Rapid-PVST+.
- **Robust Security:** Dynamic ARP Inspection (DAI), DHCP Snooping, BPDU Guard, Port-Security.
- **Perimeter Security:** Cisco ASA Firewall with NAT, Stateful ICMP/UDP Inspection, and secure internet routing.
- **Hybrid Environment:** Bridged connection between GNS3 virtual nodes and physical desktop switches.

## 📂 Repository Structure
- `tools/` - The three Python tools: `discover.py` (network discovery/crawler), `audit_configs.py` (config snapshot + drift detection), `wipe_and_restore.py` (GNS3 wipe + restore).
- `app/` - Shared database layer (SQLAlchemy models, session handling) used by the tools above.
- `db/` - Database schema and ER diagram.
- `SPECTRA/` - The live GNS3 project file and its runtime project-files.
- `assets/configs/gns3/` - Startup configurations for all virtual Cisco routers, switches, and firewalls in the GNS3 lab.
- `assets/configs/physical/` - Hardened hardware configurations for the physical Catalyst switches on the management desk.
- `assets/images/` - Architecture diagrams and custom SVG icons for GNS3 nodes.
- `topologies/` - Markdown documentation, IP addressing schemas, and port mappings, plus the GNS3 host/server container definitions.
- `topologies/old/` - Legacy Packet Tracer and IOSv iterations of the project.

## 🚀 The S.P.E.C.T.R.A Crawler (In Development)
The core software component of this repository is a Python-driven intelligent network crawler.
Currently undergoing a major refactor, the upcoming version will feature:
1. **Automated Discovery:** SSH/Netmiko integration to autonomously map CDP/LLDP neighbors and build an adjacency matrix.
2. **PostgreSQL Integration:** Storing real-time interface metrics, VLAN databases, and routing tables.
3. **Data Visualization:** A web dashboard for visualizing the live topology and OSPF health.

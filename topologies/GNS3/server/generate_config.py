#!/usr/bin/env python3
from jinja2 import Environment, FileSystemLoader

env = Environment(loader=FileSystemLoader("templates"))
template = env.get_template("router-base.j2")

device_vars = {
    "hostname": "R-RD",
    "admin_password": "Admin01pa55",
    "vlans": [{"id": 20, "name": "RD_DATA"}],
    "interfaces": [
        {"name": "GigabitEthernet0/0", "description": "LAN R&D", "ip": "10.0.0.1", "mask": "255.255.248.0"},
    ],
}

rendered = template.render(**device_vars)

out_path = f"/srv/tftp/configs/{device_vars['hostname'].lower()}.cfg"
with open(out_path, "w") as f:
    f.write(rendered)

print(f"[SPECTRA] Config generat: {out_path}")

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import argparse
import hashlib
import os
from concurrent.futures import ThreadPoolExecutor
from difflib import unified_diff

from dotenv import load_dotenv
from netmiko import ConnectHandler
from sqlalchemy import select

from app.db import get_session
from app.models import Alert, Config, Device

load_dotenv()

NETMIKO_TYPE_BY_DEVICE_TYPE = {
    "firewall": "cisco_asa",
}
DEFAULT_NETMIKO_TYPE = "cisco_ios"
MAX_WORKERS = 12

VOLATILE_LINE_MARKERS = (
    "Last configuration change",
    "NVRAM config last updated",
    "ntp clock-period",
    "Current configuration :",
    "No configuration change since last restart",
)


def normalize_config(config_text: str) -> str:
    return "\n".join(
        line for line in config_text.splitlines()
        if not any(marker in line for marker in VOLATILE_LINE_MARKERS)
    )


def fetch_running_config(ip: str, netmiko_type: str, username: str, password: str) -> str:
    conn = ConnectHandler(
        device_type=netmiko_type,
        host=ip,
        username=username,
        password=password,
        timeout=15,
    )
    try:
        return str(conn.send_command("show running-config"))
    finally:
        conn.disconnect()


def fetch_device_config(device: Device, username: str, password: str):
    netmiko_type = NETMIKO_TYPE_BY_DEVICE_TYPE.get(device.device_type, DEFAULT_NETMIKO_TYPE)
    try:
        return fetch_running_config(device.management_ip, netmiko_type, username, password), None
    except Exception as exc:
        return None, str(exc)


def store_backup(session, device: Device, config_text: str) -> str:
    normalized_current = normalize_config(config_text)
    config_hash = hashlib.sha256(normalized_current.encode()).hexdigest()

    latest = session.execute(
        select(Config)
        .where(Config.device_id == device.id, Config.config_type == "running")
        .order_by(Config.collected_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    diff_text = None
    if latest is not None:
        normalized_latest = normalize_config(latest.config_text)
        latest_hash = hashlib.sha256(normalized_latest.encode()).hexdigest()
        if latest_hash == config_hash:
            return "unchanged"

        diff_text = "".join(unified_diff(
            normalized_latest.splitlines(keepends=True),
            normalized_current.splitlines(keepends=True),
            fromfile=f"{device.hostname} (previous, {latest.collected_at})",
            tofile=f"{device.hostname} (current)",
        ))

    session.add(Config(
        device_id=device.id,
        config_type="running",
        config_text=config_text,
        config_hash=config_hash,
        diff_text=diff_text,
    ))

    if latest is None:
        return "baseline saved"

    session.add(Alert(
        device_id=device.id,
        severity="warning",
        category="config_drift",
        message=f"Running config changed on {device.hostname}",
    ))
    return "CHANGED"


def main():
    parser = argparse.ArgumentParser(description="Back up running-config for every active device and flag drift.")
    parser.add_argument("hostnames", nargs="*", help="Restrict to these device hostnames (default: all active)")
    args = parser.parse_args()

    username = os.environ.get("SPECTRA_SSH_USER")
    password = os.environ.get("SPECTRA_SSH_PASSWORD")
    if not username or not password:
        sys.exit(
            "Missing SPECTRA_SSH_USER / SPECTRA_SSH_PASSWORD.\n"
            "Copy .env.example to .env and fill in real values."
        )

    session = get_session()
    try:
        query = select(Device).where(Device.is_active.is_(True))
        if args.hostnames:
            query = query.where(Device.hostname.in_(args.hostnames))
        devices = session.execute(query).scalars().all()

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            fetched = list(pool.map(
                lambda d: fetch_device_config(d, username, password), devices
            ))

        results = []
        for device, (config_text, error) in zip(devices, fetched):
            if error is not None:
                results.append((device.hostname, f"FAILED: {error}"))
                continue
            assert config_text is not None
            status = store_backup(session, device, config_text)
            results.append((device.hostname, status))
        session.commit()
    finally:
        session.close()

    print(f"\n{'=' * 60}\nCONFIG BACKUP ({len(results)} device(s))\n{'=' * 60}")
    for hostname, status in sorted(results):
        print(f"  {hostname:<20} {status}")

    changed = [h for h, s in results if s == "CHANGED"]
    if changed:
        print(f"\n{len(changed)} device(s) drifted from their last backed-up config: {changed}")


if __name__ == "__main__":
    main()

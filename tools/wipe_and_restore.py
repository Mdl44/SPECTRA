#!/usr/bin/env python3
import json
import os
import re
import socket
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv
from netmiko import ConnectHandler

load_dotenv()

GNS3_BASE_URL = os.environ.get("GNS3_BASE_URL", "http://localhost:3080")
GNS3_USER = os.environ.get("GNS3_USER")
GNS3_PASSWORD = os.environ.get("GNS3_PASSWORD")


# ---- GNS3 controller API client ----

class Gns3Client:
    def __init__(self, gns3_file, base_url=GNS3_BASE_URL):
        self.base_url = base_url.rstrip("/")
        self.auth = (GNS3_USER, GNS3_PASSWORD or "") if GNS3_USER else None

        with open(gns3_file) as fh:
            data = json.load(fh)
        self.project_id = data["project_id"]
        self.name_to_id = {n["name"]: n["node_id"] for n in data["topology"]["nodes"]}

    def _node_id(self, name):
        node_id = self.name_to_id.get(name)
        if node_id is None:
            raise ValueError(f"No GNS3 node named {name!r} in this project")
        return node_id

    def _url(self, node_id, suffix=""):
        return f"{self.base_url}/v2/projects/{self.project_id}/nodes/{node_id}{suffix}"

    def status(self, name):
        r = requests.get(self._url(self._node_id(name)), auth=self.auth, timeout=10)
        r.raise_for_status()
        return r.json().get("status")

    def stop(self, name):
        r = requests.post(self._url(self._node_id(name), "/stop"), auth=self.auth, timeout=15)
        if r.status_code not in (200, 201, 204, 409):
            r.raise_for_status()

    def start(self, name):
        r = requests.post(self._url(self._node_id(name), "/start"), auth=self.auth, timeout=15)
        if r.status_code not in (200, 201, 204, 409):
            r.raise_for_status()

    def wait_until_stopped(self, name, timeout=15):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.status(name) == "stopped":
                return True
            time.sleep(1)
        return False

    def restart(self, name):
        self.stop(name)
        self.wait_until_stopped(name, timeout=15)
        time.sleep(1)
        self.start(name)


# ---- Raw telnet console automation (setup dialog, config bootstrap, crash detection) ----

IAC_RE = re.compile(rb"\xff[\xfb-\xfe].")

CONSOLE_LOG_DIR = Path(__file__).resolve().parent / "console_logs"
CONFIG_PUSH_LIMIT = threading.Semaphore(2)
CRASH_RE = re.compile(
    r"grub>|can't find command|CPU exception occurred|Unexpected exception to CPU",
    re.IGNORECASE,
)

GRUB_MENU_RE = re.compile(r"GNU GRUB|setparams", re.IGNORECASE)
BOOT_PROGRESS_RE = re.compile(
    r"Booting `|%PNP-|%CVAC-|%SPANTREE-|%SYS-5-RESTART|IOS Software",
    re.IGNORECASE,
)


def _stuck_at_grub_menu(buf):
    matches = list(GRUB_MENU_RE.finditer(buf))
    if not matches:
        return False
    return not BOOT_PROGRESS_RE.search(buf[matches[-1].end():])


class DeviceCrashed(Exception):
    pass


class BootTimeout(RuntimeError):
    pass


class ConsoleSession:
    def __init__(self, host, port, name=None, timeout=5):
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self._log_fh = None
        if name:
            CONSOLE_LOG_DIR.mkdir(exist_ok=True)
            self._log_fh = open(CONSOLE_LOG_DIR / f"{name}.log", "a")
            self._log_fh.write(f"\n=== session opened {datetime.now().isoformat()} ===\n")
            self._log_fh.flush()

    def _strip_iac(self, data):
        return IAC_RE.sub(b"", data)

    def _log(self, text):
        if self._log_fh and text:
            self._log_fh.write(text)
            self._log_fh.flush()

    def wait_for(self, pattern, max_wait=60.0, quiet_time=1.5, poll_interval=0.3, nudge=False, nudge_interval=20.0):
        buf = ""
        overall_deadline = time.time() + max_wait
        last_nudge = time.time()
        while time.time() < overall_deadline:
            last_data = time.time()
            self.sock.settimeout(poll_interval)
            while time.time() < overall_deadline:
                try:
                    chunk = self.sock.recv(4096)
                    if chunk:
                        text = self._strip_iac(chunk).decode(errors="replace")
                        buf += text
                        self._log(text)
                        last_data = time.time()
                        if CRASH_RE.search(buf):
                            raise DeviceCrashed(f"device dropped to GRUB: {buf[-200:]!r}")
                except socket.timeout:
                    pass
                now = time.time()
                if nudge and now - last_data >= nudge_interval and now - last_nudge >= nudge_interval:
                    self.send_line("")
                    last_nudge = now
                if now - last_data >= quiet_time:
                    break
            if re.search(pattern, buf, re.IGNORECASE | re.MULTILINE):
                return buf
        return buf

    def send_line(self, line=""):
        self.sock.sendall(line.encode() + b"\r\n")

    def close(self):
        try:
            self.sock.close()
        except Exception:
            pass
        if self._log_fh:
            self._log_fh.close()


def get_console_info(gns3, name):
    node_id = gns3._node_id(name)
    r = requests.get(gns3._url(node_id), auth=gns3.auth, timeout=10)
    r.raise_for_status()
    info = r.json()
    return info["console_host"], info["console"]


PROMPT_RE = r"[\w.-]+[>#]\s*$"


def quick_answer_dialog(name, gns3, log=print, max_wait=200):
    try:
        host, port = get_console_info(gns3, name)
    except Exception as e:
        log(f"[{name}] quick-answer: couldn't get console info: {e}")
        return
    console = ConsoleSession(host, port, name=name)
    try:
        console.send_line("")
        out = console.wait_for(r"initial configuration dialog|" + PROMPT_RE, max_wait=max_wait, nudge=True)
        if "initial configuration dialog" in out.lower():
            console.send_line("no")
            console.wait_for(r"press return|" + PROMPT_RE, max_wait=30, nudge=True)
            log(f"[{name}] quick-answer: setup dialog declined")
        elif re.search(PROMPT_RE, out, re.MULTILINE):
            log(f"[{name}] quick-answer: already past the dialog, nothing to do")
        else:
            log(f"[{name}] quick-answer: never saw the dialog or a prompt within {max_wait}s, got: {out[-200:]!r}")
    except DeviceCrashed as e:
        log(f"[{name}] quick-answer: device crashed: {e}")
    finally:
        console.close()


def _extract_con0_password(config_text):
    lines = config_text.splitlines()
    in_block = False
    for line in lines:
        if line.strip() == "line con 0":
            in_block = True
            continue
        if in_block:
            if not line.startswith(" "):
                break
            m = re.match(r"\s*password\s+(\S+)", line)
            if m:
                return m.group(1)
    return None


def _extract_enable_secret(config_text):
    m = re.search(r"^\s*enable secret\s+(\S+)", config_text, re.MULTILINE)
    return m.group(1) if m else None


def _bootstrap_once(name, gns3, config_text, log):
    host, port = get_console_info(gns3, name)
    log(f"[{name}] console at {host}:{port} (full transcript: console_logs/{name}.log)")
    console = ConsoleSession(host, port, name=name)
    try:
        console.send_line("")
        out = console.wait_for(r"initial configuration dialog|Password:|" + PROMPT_RE, max_wait=150, nudge=True)
        log(f"[{name}] initial state -> {out[-300:]!r}")
        if re.search(r"Password:\s*$", out, re.IGNORECASE | re.MULTILINE) and not re.search(PROMPT_RE, out, re.MULTILINE):
            con_password = _extract_con0_password(config_text)
            if not con_password:
                raise BootTimeout(
                    f"hit a console login prompt but this config has no 'line con 0' password to answer "
                    f"it with, got: {out[-300:]!r}"
                )
            log(f"[{name}] hit a console login prompt (already configured from an earlier run) -- authenticating")
            console.send_line(con_password)
            out = console.wait_for(PROMPT_RE, max_wait=30, nudge=True)
            if not re.search(PROMPT_RE, out, re.MULTILINE):
                raise BootTimeout(f"console password didn't reach a prompt, got: {out[-300:]!r}")
            log(f"[{name}] already configured -- config will be re-applied (idempotent)")
        elif not re.search(r"initial configuration dialog|" + PROMPT_RE, out, re.IGNORECASE | re.MULTILINE):
            if _stuck_at_grub_menu(out):
                raise DeviceCrashed(f"stuck at the GRUB boot menu, auto-boot never fired: {out[-300:]!r}")
            raise BootTimeout(f"never reached a prompt or the setup dialog after connecting, got: {out[-300:]!r}")

        if "initial configuration dialog" in out.lower():
            console.send_line("no")
            out = console.wait_for(r"press return|" + PROMPT_RE, max_wait=360, nudge=True)
            log(f"[{name}] after 'no' -> {out[-300:]!r}")
            if not re.search(r"press return|" + PROMPT_RE, out, re.IGNORECASE | re.MULTILINE):
                if _stuck_at_grub_menu(out):
                    raise DeviceCrashed(f"stuck at the GRUB boot menu, auto-boot never fired: {out[-300:]!r}")
                console.send_line("")
                out = console.wait_for(r"press return|" + PROMPT_RE, max_wait=60, nudge=True)
                if not re.search(r"press return|" + PROMPT_RE, out, re.IGNORECASE | re.MULTILINE):
                    if _stuck_at_grub_menu(out):
                        raise DeviceCrashed(f"stuck at the GRUB boot menu, auto-boot never fired: {out[-300:]!r}")
                    raise BootTimeout(f"never reached a prompt after answering the setup dialog, got: {out[-300:]!r}")

        if "press return" in out.lower():
            console.send_line("")
            out = console.wait_for(PROMPT_RE, max_wait=60, nudge=True)
            log(f"[{name}] after RETURN -> {out[-300:]!r}")
            if not re.search(PROMPT_RE, out, re.MULTILINE):
                if _stuck_at_grub_menu(out):
                    raise DeviceCrashed(f"stuck at the GRUB boot menu, auto-boot never fired: {out[-300:]!r}")
                raise BootTimeout(f"never reached a prompt after RETURN, got: {out[-300:]!r}")

        with CONFIG_PUSH_LIMIT:
            console.send_line("enable")
            out = console.wait_for(r"Password:|[\w.-]+#\s*$", max_wait=20)
            log(f"[{name}] after 'enable' -> {out[-300:]!r}")
            if re.search(r"Password:\s*$", out, re.IGNORECASE | re.MULTILINE) and not re.search(r"[\w.-]+#\s*$", out, re.MULTILINE):
                enable_secret = _extract_enable_secret(config_text)
                if not enable_secret:
                    raise BootTimeout(
                        f"'enable' asked for a password but this config has no 'enable secret' to answer "
                        f"it with, got: {out[-300:]!r}"
                    )
                console.send_line(enable_secret)
                out = console.wait_for(r"[\w.-]+#\s*$", max_wait=20)
                log(f"[{name}] after enable password -> {out[-300:]!r}")
            if not re.search(r"[\w.-]+#\s*$", out, re.MULTILINE):
                raise BootTimeout(f"never reached privileged prompt after 'enable', got: {out[-300:]!r}")

            console.send_line("configure terminal")
            out = console.wait_for(r"\(config\)#\s*$", max_wait=20)
            log(f"[{name}] after 'configure terminal' -> {out[-300:]!r}")
            if not re.search(r"\(config\)#\s*$", out, re.MULTILINE):
                raise BootTimeout(f"never reached config prompt, got: {out[-300:]!r}")

            lines = [l for l in config_text.splitlines() if l.strip() and not l.strip().startswith("!")]
            for line in lines:
                console.send_line(line)
                time.sleep(0.08)
            out = console.wait_for(r"%GRUB-5-CONFIG_WRITTEN", max_wait=120)
            log(f"[{name}] after full config paste -> {out[-500:]!r}")

            hostname_match = re.search(r"^\s*hostname\s+(\S+)", config_text, re.MULTILINE)
            expected_hostname = hostname_match.group(1) if hostname_match else name
            if "%GRUB-5-CONFIG_WRITTEN" not in out:
                console.send_line("")
                verify = console.wait_for(re.escape(expected_hostname) + r"#\s*$", max_wait=30)
                if not re.search(re.escape(expected_hostname) + r"#", verify):
                    raise BootTimeout(
                        f"never saw the GRUB-5-CONFIG_WRITTEN disk-write confirmation, and a "
                        f"follow-up prompt check didn't show hostname {expected_hostname!r} "
                        f"either -- config may not have fully persisted, got: {out[-300:]!r}"
                    )
                log(f"[{name}] didn't see the GRUB-5-CONFIG_WRITTEN line, but the prompt already "
                    f"shows hostname {expected_hostname!r} -- treating as success")
            elif not re.search(re.escape(expected_hostname) + r"#", out):
                raise BootTimeout(
                    f"disk-write confirmed but prompt doesn't show hostname {expected_hostname!r}, "
                    f"got: {out[-300:]!r}"
                )

        return True
    finally:
        console.close()


def bootstrap_config(name, gns3, config_text, log=print, max_attempts=3):
    for attempt in range(1, max_attempts + 1):
        try:
            return _bootstrap_once(name, gns3, config_text, log)
        except DeviceCrashed as e:
            log(f"[{name}] attempt {attempt}/{max_attempts}: {e} -- power-cycling via GNS3 API and retrying")
            if attempt == max_attempts:
                raise RuntimeError(f"gave up after {max_attempts} attempts (repeated crashes): {e}")
            gns3.restart(name)
            time.sleep(3)
        except BootTimeout as e:
            log(f"[{name}] {e} -- see console_logs/{name}.log for the full transcript. Not auto-restarting: "
                f"the device may just be slow, and a restart would only discard its boot progress.")
            raise


# ---- NVRAM wipe (SSH-based, requires the device already running IOS) ----

GNS3_PROJECT_FILE = Path(__file__).resolve().parent / "SPECTRA" / "SPECTRA.gns3"
CONFIGS_DIR = Path(__file__).resolve().parent / "assets" / "configs" / "gns3"

SWITCHES = [
    ("SwIT", "10.0.14.114"),
    ("SwQA", "10.0.14.98"),
    ("SwGuest", "10.0.12.2"),
    ("SwDC", "10.0.10.2"),
    ("SwSOC", "10.0.8.2"),
    ("SwRD", "10.0.0.2"),
    ("SwMalwareLab", "10.0.13.2"),
    ("SwAcc1", "10.0.14.146"),
    ("SwAcc2", "10.0.14.147"),
    ("SwD1", "10.0.14.148"),
    ("SwD2", "10.0.14.149"),
    ("SwC", "10.0.14.150"),
    ("SwMgmt", "10.0.14.130"),
]

LEAF_ROUTERS = [
    ("R-IT", "10.0.14.113"),
    ("R-QA", "10.0.14.97"),
    ("R-Guest", "10.0.12.1"),
    ("R-DC", "10.0.10.1"),
    ("R-SOC", "10.0.8.1"),
    ("R-RD", "10.0.0.1"),
    ("R-Corp", "10.0.13.129"),
    ("R-MalwareLab", "10.0.13.1"),
]

CORE = [
    ("R-Core1", "10.1.0.1"),
    ("R-Core2", "10.1.0.2"),
]

GATEWAY = [
    ("R-Mgmt", "10.0.14.129"),
]

DEVICES = SWITCHES + LEAF_ROUTERS + CORE + GATEWAY
SWITCH_NAMES = {name for name, _ in SWITCHES}
CORE_NAMES = {name for name, _ in CORE}
STP_CONVERGENCE_WAIT = 60
CORE_REBOOT_WAIT = 30
REBOOT_STAGGER_WAIT = 20

RESTORE_DEVICES = {
    "SwIT": "24. SwIT.txt",
    "SwQA": "22. SwQA.txt",
    "SwGuest": "20. SwGuest.txt",
    "SwDC": "16. SwDC.txt",
    "SwSOC": "14. SwSOC.txt",
    "SwRD": "12. SwRD.txt",
    "SwMalwareLab": "18. SwMalwareLab.txt",
    "SwAcc1": "1. SwAcc1.txt",
    "SwAcc2": "2. SwAcc2.txt",
    "SwD1": "3. SwD1.txt",
    "SwD2": "4. SwD2.txt",
    "SwC": "5. SwC.txt",
    "SwMgmt": "26. SwMgmt.txt",
    "R-IT": "23. R-IT.txt",
    "R-QA": "21. R-QA.txt",
    "R-Guest": "19. R-Guest.txt",
    "R-DC": "15. R-DC.txt",
    "R-SOC": "13. R-SOC.txt",
    "R-RD": "11. R-RD.txt",
    "R-Corp": "6. R-Corp.txt",
    "R-MalwareLab": "17. R-MalwareLab.txt",
    "R-Core1": "7. Core1.txt",
    "R-Core2": "8. Core2.txt",
    "R-Mgmt": "25. R-Mgmt.txt",
}
RESTORE_MAX_WORKERS = 24


def dump(name, label, text):
    print(f"    [{name}] {label} raw buffer -> {text!r}")


def erase_nvram(name, ip):
    device = {
        "device_type": "cisco_ios",
        "ip": ip,
        "username": "Admin01",
        "password": "Admin01pa55",
        "secret": "ciscosecpa55",
        "timeout": 25,
    }
    conn = ConnectHandler(**device)
    try:
        conn.enable()
        prompt = conn.find_prompt()
        print(f"    [{name}] prompt after enable() -> {prompt!r}")

        conn.write_channel("write erase\n")
        out = conn.read_channel_timing(read_timeout=8)
        dump(name, "after 'write erase'", out)

        conn.write_channel("\n")
        out = conn.read_channel_timing(read_timeout=8)
        dump(name, "after erase-confirm", out)
        if "erase of nvram: complete" not in out.lower():
            raise RuntimeError(f"never saw 'Erase of nvram: complete', got: {out!r}")
    finally:
        try:
            conn.disconnect()
        except Exception:
            pass


def erase_with_retry(name, ip, max_attempts=3):
    for attempt in range(1, max_attempts + 1):
        print(f"[{name} / {ip}] connecting... (attempt {attempt}/{max_attempts})")
        try:
            erase_nvram(name, ip)
            return True
        except Exception as e:
            print(f"[{name} / {ip}] SSH/erase FAILED: {e}")
            if attempt == max_attempts:
                return False
            time.sleep(8)


def erase_wave(wave, max_workers=None):
    if max_workers is None:
        max_workers = len(wave)
    results = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(erase_with_retry, name, ip): name for name, ip in wave}
        for fut in as_completed(futures):
            name = futures[fut]
            try:
                results[name] = fut.result()
            except Exception as e:
                print(f"[{name}] erase raised unexpectedly: {e}")
                results[name] = False
    return results


def restart_wave(wave, erase_results, gns3, results, stagger=REBOOT_STAGGER_WAIT):
    for i, (name, ip) in enumerate(wave):
        if erase_results.get(name):
            print(f"[{name}] nvram erased, restarting via GNS3 API...")
            try:
                gns3.restart(name)
                print(f"[{name}] restarted.")
                results[name] = True
            except Exception as e:
                print(f"[{name}] GNS3 restart FAILED: {e}")
                results[name] = False
        else:
            results[name] = False
        if i + 1 < len(wave):
            time.sleep(stagger)


def answer_dialogs(wave, gns3, max_workers=12):
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(quick_answer_dialog, name, gns3, print) for name, _ip in wave]
        for fut in as_completed(futures):
            fut.result()


def wipe_and_reload(name, ip, gns3, max_attempts=3):
    if not erase_with_retry(name, ip, max_attempts=max_attempts):
        return False
    print(f"[{name}] nvram erased, restarting via GNS3 API...")
    try:
        gns3.restart(name)
        print(f"[{name}] restarted.")
        return True
    except Exception as e:
        print(f"[{name}] GNS3 restart FAILED: {e}")
        return False


def cmd_wipe(targets):
    single_device_mode = targets is not None
    all_targets = targets if single_device_mode else DEVICES

    gns3 = Gns3Client(GNS3_PROJECT_FILE)

    print(f"About to WRITE ERASE + RESTART {len(all_targets)} device(s):")
    for name, ip in all_targets:
        print(f"  {name:<16} {ip}")
    confirm = input("\nType 'yes' to continue: ")
    if confirm.strip().lower() != "yes":
        print("Aborted.")
        return

    results = {}
    if single_device_mode:
        for i, (name, ip) in enumerate(all_targets):
            results[name] = wipe_and_reload(name, ip, gns3)

            is_switch = name in SWITCH_NAMES
            next_is_router = i + 1 < len(all_targets) and all_targets[i + 1][0] not in SWITCH_NAMES
            is_core = name in CORE_NAMES
            next_is_core_too = i + 1 < len(all_targets) and all_targets[i + 1][0] in CORE_NAMES

            if is_switch and next_is_router:
                print(f"\nWaiting {STP_CONVERGENCE_WAIT}s for switch uplinks to reconverge (STP) before touching any router...")
                time.sleep(STP_CONVERGENCE_WAIT)
            elif is_core and next_is_core_too:
                print(f"\nWaiting {CORE_REBOOT_WAIT}s for {name} to finish rebooting before touching the other core router...")
                time.sleep(CORE_REBOOT_WAIT)
            elif i + 1 < len(all_targets):
                time.sleep(REBOOT_STAGGER_WAIT)
    else:
        print(f"\nErasing {len(SWITCHES)} switches in parallel...")
        switch_erase = erase_wave(SWITCHES)
        restart_wave(SWITCHES, switch_erase, gns3, results)
        print(f"\nWaiting {STP_CONVERGENCE_WAIT}s for switch uplinks to reconverge (STP) before touching any router...")
        time.sleep(STP_CONVERGENCE_WAIT)

        print(f"\nErasing {len(LEAF_ROUTERS)} leaf routers in parallel...")
        leaf_erase = erase_wave(LEAF_ROUTERS)
        restart_wave(LEAF_ROUTERS, leaf_erase, gns3, results)
        print(f"\nAnswering setup dialogs for leaf routers (prevents an internal self-reload if left unanswered too long)...")
        answer_dialogs([(n, ip) for n, ip in LEAF_ROUTERS if results.get(n)], gns3)
        time.sleep(REBOOT_STAGGER_WAIT)

        for i, (name, ip) in enumerate(CORE):
            results[name] = wipe_and_reload(name, ip, gns3)
            if i + 1 < len(CORE):
                print(f"\nWaiting {CORE_REBOOT_WAIT}s for {name} to finish rebooting before touching the other core router...")
                time.sleep(CORE_REBOOT_WAIT)
        answer_dialogs([(n, ip) for n, ip in CORE if results.get(n)], gns3)
        time.sleep(REBOOT_STAGGER_WAIT)

        for name, ip in GATEWAY:
            results[name] = wipe_and_reload(name, ip, gns3)
        answer_dialogs([(n, ip) for n, ip in GATEWAY if results.get(n)], gns3)

    failed = [name for name, ok in results.items() if not ok]
    print("\n--- Summary ---")
    for name, _ip in all_targets:
        print(f"  {name:<16} {'OK' if results.get(name) else 'FAILED'}")
    if failed:
        print(f"\n{len(failed)}/{len(all_targets)} FAILED: {failed}")
    else:
        print(f"\nAll {len(all_targets)} device(s) wiped and restarted.")


def restore_one(name, gns3):
    log_lines = []
    config_text = (CONFIGS_DIR / RESTORE_DEVICES[name]).read_text()
    try:
        bootstrap_config(name, gns3, config_text, log=log_lines.append)
        return name, "OK", log_lines
    except Exception as e:
        log_lines.append(f"[{name}] FAILED: {e}")
        return name, f"FAILED: {e}", log_lines


def cmd_restore(names):
    targets = names if names else list(RESTORE_DEVICES.keys())
    unknown = [t for t in targets if t not in RESTORE_DEVICES]
    if unknown:
        sys.exit(f"Unknown device name(s): {unknown}")

    print(f"About to restore config on {len(targets)} device(s), up to {RESTORE_MAX_WORKERS} in parallel: {targets}")
    confirm = input("Type 'yes' to continue: ")
    if confirm.strip().lower() != "yes":
        sys.exit("Aborted.")

    gns3 = Gns3Client(GNS3_PROJECT_FILE)

    results = {}
    with ThreadPoolExecutor(max_workers=RESTORE_MAX_WORKERS) as pool:
        futures = {pool.submit(restore_one, name, gns3): name for name in targets}
        for future in as_completed(futures):
            name, result, log_lines = future.result()
            print(f"\n=== {name} ===")
            for line in log_lines:
                print(line)
            results[name] = result

    print("\n--- Summary ---")
    for name in targets:
        print(f"  {name:<16} {results.get(name, 'MISSING')}")


# ---- CLI ----

def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("wipe", "restore"):
        sys.exit(
            "usage: wipe_and_restore.py wipe [device ...]\n"
            "       wipe_and_restore.py restore [device ...]\n"
            "\n"
            "wipe    -- write erase + restart devices via the GNS3 API (all devices if none named)\n"
            "restore -- push saved configs back onto devices already running IOS (all devices if none named)"
        )
    subcommand, names = sys.argv[1], sys.argv[2:]
    if subcommand == "wipe":
        wanted = set(names) if names else None
        targets = None
        if wanted is not None:
            targets = [(n, ip) for n, ip in DEVICES if n in wanted]
            if not targets:
                sys.exit(f"No matching device name(s) in {names}")
        cmd_wipe(targets)
    else:
        cmd_restore(names)


if __name__ == "__main__":
    main()

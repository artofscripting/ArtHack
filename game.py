"""Curses front-end + game loop for ART — the dungeon escape."""
from __future__ import annotations

import curses
import random
import re
import textwrap

from board import (BLOCKING, DIRS, VOID, WORLD_H, WORLD_W, Board, Item,
                   NUM_LEVELS, _LEVEL_NAMES, RANGED_WEAPON_RANGE,
                   RANGED_ENCHANTMENT_SWIFT)

SIDEBAR = 28
LOGH = 8
MIN_W = 64
MIN_H = 20
CLUES_FOR_PORTAL = 3

COLOR = {
    "#": 1, ".": 2, "@": 3, "+": 4, "=": 9, "<": 4, ">": 8,
    "k": 5, "*": 5, "$": 5, "!": 5, "&": 5, "O": 7, "V": 4, "T": 6,
    "X": 3, "A": 11, "F": 8, "/": 3, ":": 11, "-": 11, "^": 7,
    "%": 8, "~": 5,
}

DIFFICULTY_ORDER = ["easy", "normal", "hard", "nightmare"]
MODULE_TO_TOOL = {
    # -- Tier 1: initial access & handshake tools --
    "sniffer_patch":    "capture_handshake",   # T1040  — Network Sniffing
    "cipher_kernel":    "crack_password",       # T1110  — Brute Force
    "radio_firmware":   "signal_spoof",         # T1583  — Acquire Infrastructure (spoof)
    "logic_probe":      "circuit_bypass",       # T1574  — Hijack Execution Flow
    # -- Tier 2: escalation & persistence --
    "kernel_implant":   "privilege_escalation", # T1068  — Exploitation for Privilege Esc.
    "override_bus":     "door_override",        # T1098  — Account Manipulation
    "daemon_rootkit":   "root_shell",           # T1014  — Rootkit
    "chest_decoder":    "loot_decrypt",         # T1560  — Archive Collected Data
    # -- Tier 3: credential & lateral movement --
    "mimikatz_stub":    "credential_dump",      # T1003  — OS Credential Dumping
    "keylog_implant":   "keylogger",            # T1056  — Input Capture
    "hash_extractor":   "pass_the_hash",        # T1550.002 — Pass the Hash
    "ssh_tunneler":     "pivot_relay",          # T1572  — Protocol Tunneling
    # -- Tier 4: evasion & discovery --
    "log_wiper":        "erase_logs",           # T1070  — Indicator Removal
    "process_mask":     "process_spoof",        # T1036  — Masquerading
    "port_scanner":     "port_scan",            # T1046  — Network Service Scanning
    "arp_sweep_kit":    "host_discovery",       # T1018  — Remote System Discovery
    # -- Tier 5: exploitation & impact --
    "buffer_exploit":   "exploit_vuln",         # T1203  — Exploitation for Client Exec.
    "sql_injector":     "sql_inject",           # T1190  — Exploit Public-Facing App
    "cam_jammer":       "camera_blind",         # T1562  — Impair Defenses
    "arp_spoofer":      "arp_poison",           # T1557  — Adversary-in-the-Middle
    # -- Tier 6: credential forgery --
    "kerberoast_kit":   "kerberoast",           # T1558.003 — Kerberoasting
    "golden_ticket":    "forge_token",          # T1558.001 — Golden Ticket
    "pass_ticket":      "pass_the_ticket",      # T1550.003 — Pass the Ticket
    # -- Tier 6: code execution & UAC --
    "shellcode_loader": "shellcode_exec",       # T1055.001 — Process Injection
    "uac_bypass":       "uac_escape",           # T1548.002 — Bypass UAC
    "wmi_implant":      "wmi_exec",             # T1047   — WMI Execution
    # -- Tier 6: lateral movement --
    "rdp_hijack":       "remote_desktop",       # T1021.001 — RDP
    "psexec_kit":       "remote_exec",          # T1021.002 — SMB/PsExec
    # -- Tier 6: persistence & exfil --
    "cron_backdoor":    "persist_cron",         # T1053.003 — Cron Job
    "startup_hook":     "persist_boot",         # T1547.001 — Boot Autostart
    "dns_tunnel":       "dns_exfil",            # T1071.004 — DNS C2/Exfil
    "firmware_patch":   "flash_firmware",       # T1601   — Modify System Image
    # -- Tier 7: relay & living-off-the-land --
    "ntlm_relay":       "force_auth",           # T1187   — Forced Authentication (NTLM Relay)
    "lolbin_wrapper":   "lolbin_exec",          # T1218   — System Binary Proxy Execution
    "token_stealer":    "token_impersonate",    # T1134   — Access Token Manipulation
    "bits_scheduler":   "bits_job",             # T1197   — BITS Jobs
    # -- Tier 7: evasion & obfuscation --
    "obfuscator_kit":   "obfuscate",            # T1027   — Obfuscated Files or Information
    "dcom_exploit":     "dcom_exec",            # T1021.003 — Distributed COM
    # -- Tier 7: collection & intel --
    "screen_cap":       "screenshot",           # T1113   — Screen Capture
    "cookie_stealer":   "steal_cookie",         # T1539   — Steal Web Session Cookie
    "browser_dump":     "browser_creds",        # T1555   — Credentials from Password Stores
    "icmp_tunnel":      "icmp_covert",          # T1095   — Non-Application Layer Protocol
    "share_scanner":    "share_harvest",        # T1039   — Data from Network Shared Drive
    "env_harvester":    "env_creds",            # T1552   — Unsecured Credentials
}
TOOL_DESCRIPTIONS = {
    # base tools
    "wifi_scan":           "scan local CastleNet access points",
    "capture_handshake":   "T1040 — capture 4-way auth handshake for offline crack",
    "crack_password":      "T1110 — derive WPA key via dictionary/brute-force attack",
    "signal_spoof":        "T1583 — spoof a trusted BSSID to slip through MAC filters",
    "circuit_bypass":      "T1574 — hijack execution flow in terminal relay firmware",
    "privilege_escalation":"T1068 — exploit kernel vuln for root on target process",
    "door_override":       "T1098 — issue forged actuator commands to lock servos",
    "root_shell":          "T1014 — plant rootkit, obtain persistent supervisory shell",
    "loot_decrypt":        "T1560 — reverse sealed cache AES envelope and extract keys",
    # tier 3 tools
    "credential_dump":     "T1003 — dump LSASS/SAM hashes from terminal memory",
    "keylogger":           "T1056 — intercept keystrokes from terminal operator session",
    "pass_the_hash":       "T1550.002 — relay stolen NTLM hash to authenticate as admin",
    "pivot_relay":         "T1572 — tunnel traffic through compromised CastleNet host",
    # tier 4 tools
    "erase_logs":          "T1070 — wipe EVTX/syslog artifacts post-exploitation",
    "process_spoof":       "T1036 — masquerade payload PID as a trusted system process",
    "port_scan":           "T1046 — enumerate open ports and running services on subnet",
    "host_discovery":      "T1018 — map live hosts via ARP sweep and ICMP ping probe",
    # tier 5 tools
    "exploit_vuln":        "T1203 — exploit unpatched binary vuln (stack/heap overflow)",
    "sql_inject":          "T1190 — inject malformed SQL to extract or corrupt DB data",
    "camera_blind":        "T1562 — blind CCTV daemon by overwriting frame buffer hooks",
    "arp_poison":          "T1557 — ARP-poison the subnet gateway for MitM intercept",
    # tier 6: credential forgery
    "kerberoast":          "T1558.003 — offline crack service-account Kerberos hashes",
    "forge_token":         "T1558.001 — forge Golden Ticket TGT using krbtgt hash",
    "pass_the_ticket":     "T1550.003 — inject forged TGT into session for auth bypass",
    # tier 6: code execution
    "shellcode_exec":      "T1055.001 — inject position-independent shellcode into process",
    "uac_escape":          "T1548.002 — auto-elevate via COM object UAC bypass",
    "wmi_exec":            "T1047 — execute payload via WMI subscription/CIM call",
    # tier 6: lateral movement
    "remote_desktop":      "T1021.001 — hijack idle RDP session via sticky-key injection",
    "remote_exec":         "T1021.002 — push executable via SMB share + PsExec service",
    # tier 6: persistence & exfil
    "persist_cron":        "T1053.003 — plant cron job for recurring payload execution",
    "persist_boot":        "T1547.001 — hook HKCU\\Run for autostart on terminal login",
    "dns_exfil":           "T1071.004 — exfiltrate data encoded in DNS TXT query stream",
    "flash_firmware":      "T1601 — overwrite embedded firmware image in flash memory",
    # tier 7: relay & LOLBins
    "force_auth":          "T1187 — coerce NetNTLM auth via UNC path to capture hash relay",
    "lolbin_exec":         "T1218 — proxy execution via certutil/mshta/regsvr32 (LOLBin)",
    "token_impersonate":   "T1134 — steal & impersonate process token for priv context swap",
    "bits_job":            "T1197 — schedule BITS job for stealthy background download/exec",
    # tier 7: evasion & obfuscation
    "obfuscate":           "T1027 — pack/encode payload to defeat AV signature scanning",
    "dcom_exec":           "T1021.003 — instantiate COM object on remote host for RCE",
    # tier 7: collection & intel
    "screenshot":          "T1113 — capture terminal framebuffer for operator session recon",
    "steal_cookie":        "T1539 — extract session cookies from browser/daemon cookie jar",
    "browser_creds":       "T1555 — dump plaintext creds from browser credential store",
    "icmp_covert":         "T1095 — encode C2 data in ICMP echo payload (covert channel)",
    "share_harvest":       "T1039 — enumerate SMB shares and stage files for exfiltration",
    "env_creds":           "T1552 — grep process env, config files, and scripts for secrets",
}

POTION_EFFECTS = {
    "healing draught": {"heal": 18, "duration": 0, "attack": 0, "defense": 0, "regen": 0},
    "night-sight tonic": {"heal": 0, "duration": 22, "attack": 1, "defense": 1, "regen": 0},
    "potion of vigor": {"heal": 8, "duration": 18, "attack": 2, "defense": 0, "regen": 1},
    "tonic vial": {"heal": 0, "duration": 16, "attack": 1, "defense": 0, "regen": 0},
}

BASE_PLAYER_HP = 60
BASE_INV_SLOTS = 20          # main-inventory item-slot limit (backpack adds bag_capacity on top)
SHOP_RESTOCK_INTERVAL = (30, 90)  # min/max turns between restocks

# Which hacking sub-skill each mode exercises.
_MODE_SKILL: dict[str, str] = {
    "recon":       "recon",
    "stealth":     "evasion",
    "spoof":       "evasion",
    "evasion":     "evasion",
    "lolbin":      "evasion",
    "bruteforce":  "creds",
    "kerberos":    "creds",
    "ntlm":        "creds",
    "exploit":     "exploit",
    "pivot":       "lateral",
    "wmi":         "lateral",
    "social":      "social",
    "balanced":    "exploit",  # default mode exercises general exploitation
}

# Base skill-level requirements per terminal control type.
# Values are (recon, exploit, creds, lateral, persist, evasion).
# Scaled by tier multiplier at runtime.
_CTRL_SKILL_BASE: dict[str, tuple[int,...]] = {
    #                      recon  exploit  creds  lateral  persist  evasion
    "doors":              (  0,     1,       1,      0,       0,       0  ),
    "locks":              (  0,     1,       1,      0,       0,       0  ),
    "loot":               (  0,     1,       1,      0,       0,       0  ),
    "gates":              (  0,     2,       2,      1,       0,       0  ),
    "dungeon":            (  1,     2,       2,      1,       1,       1  ),
    "security":           (  1,     2,       1,      1,       1,       2  ),
    "cameras":            (  1,     2,       1,      1,       1,       2  ),
    "alarms":             (  1,     2,       1,      1,       1,       2  ),
    "comm":               (  1,     2,       2,      2,       1,       1  ),
    "power":              (  1,     3,       1,      1,       2,       1  ),
    "db":                 (  2,     2,       3,      1,       1,       1  ),
    "vault":              (  2,     2,       3,      2,       1,       2  ),
    "auth":               (  2,     3,       5,      4,       2,       2  ),
    "scada":              (  2,     4,       2,      2,       2,       2  ),
    "radio":              (  2,     3,       1,      2,       2,       3  ),
    "firmware":           (  2,     3,       1,      1,       3,       2  ),
    "backup":             (  2,     2,       3,      2,       2,       1  ),
    "cloud":              (  3,     3,       3,      4,       3,       2  ),
    "registry":           (  2,     3,       2,      3,       3,       3  ),
    "webshell":           (  2,     4,       2,      3,       4,       4  ),
    "vpn":                (  3,     3,       3,      4,       3,       3  ),
    "container":          (  3,     5,       2,      4,       3,       4  ),
}

# Services exposed per terminal control type (proto, port).
# Revealed by portscan command; used by vulnscan to map CVEs.
_CONTROL_SERVICES: dict[str, list[tuple[str, int]]] = {
    "doors":     [("smb", 445), ("ldap", 389), ("msrpc", 135)],
    "locks":     [("smb", 445), ("winrm", 5985), ("msrpc", 135)],
    "gates":     [("ldap", 389), ("kerberos", 88), ("msrpc", 135)],
    "security":  [("rtsp", 554), ("http", 80), ("snmp", 161)],
    "cameras":   [("rtsp", 554), ("onvif", 2020), ("http", 80)],
    "alarms":    [("modbus", 502), ("http", 80), ("snmp", 161)],
    "loot":      [("ftp", 21), ("smb", 445), ("https", 443)],
    "vault":     [("https", 443), ("smb", 445), ("mssql", 1433)],
    "dungeon":   [("ssh", 22), ("telnet", 23), ("rdp", 3389)],
    "comm":      [("smtp", 25), ("imap", 143), ("rdp", 3389)],
    "power":     [("modbus", 502), ("dnp3", 20000), ("http", 80)],
    "db":        [("mysql", 3306), ("mssql", 1433), ("postgresql", 5432)],
    "auth":      [("kerberos", 88), ("ldap", 389), ("ntlm", 445)],
    "scada":     [("modbus", 502), ("dnp3", 20000), ("s7comm", 102)],
    "radio":     [("rf", 433), ("zigbee", 2400), ("bluetooth", 2401)],
    "firmware":  [("tftp", 69), ("http", 80), ("snmp", 161)],
    "backup":    [("smb", 445), ("rsync", 873), ("https", 443)],
    "cloud":     [("https", 443), ("s3api", 9000), ("grpc", 50051)],
    "registry":  [("smb", 445), ("winrm", 5985), ("rdp", 3389)],
    "webshell":  [("http", 80), ("https", 443), ("ssh", 22)],
    "vpn":       [("openvpn", 1194), ("ipsec", 500), ("l2tp", 1701)],
    "container": [("docker", 2375), ("k8s", 6443), ("https", 443)],
}

# CVE/finding per (proto, port): (description, tool_needed)
_SERVICE_VULNS: dict[tuple[str, int], tuple[str, str]] = {
    ("smb", 445):      ("MS17-010 EternalBlue — unauthenticated RCE",       "exploit_vuln"),
    ("ldap", 389):     ("Null bind — unauthenticated LDAP enumeration",      "credential_dump"),
    ("kerberos", 88):  ("AS-REP roasting — TGT without pre-auth flag",       "kerberoast"),
    ("msrpc", 135):    ("MS-RPC endpoint enum — map internal services",      "port_scan"),
    ("winrm", 5985):   ("WinRM default creds — PS remoting foothold",        "wmi_exec"),
    ("rdp", 3389):     ("BlueKeep CVE-2019-0708 — pre-auth RCE",            "exploit_vuln"),
    ("ssh", 22):       ("Weak key exchange — brute-forceable cipher",        "crack_password"),
    ("telnet", 23):    ("Plaintext protocol — credential sniff in transit",  "keylogger"),
    ("http", 80):      ("Unauth file-upload endpoint — web shell drop",      "exploit_vuln"),
    ("https", 443):    ("SSL strip + cred harvest via AiTM proxy",           "credential_dump"),
    ("ftp", 21):       ("Anonymous FTP — world-readable loot staging",       "loot_decrypt"),
    ("rtsp", 554):     ("Default creds on RTSP stream — camera takeover",    "camera_blind"),
    ("onvif", 2020):   ("ONVIF auth bypass — token replay for PTZ control",  "pass_the_ticket"),
    ("modbus", 502):   ("No-auth Modbus FC3 — register read/write",          "circuit_bypass"),
    ("dnp3", 20000):   ("DNP3 replay attack — spoofed SCADA commands",       "signal_spoof"),
    ("s7comm", 102):   ("Siemens S7 stop command — PLCBlaster RCE",          "shellcode_exec"),
    ("tftp", 69):      ("Unauthenticated TFTP pull — firmware dump",         "flash_firmware"),
    ("snmp", 161):     ("SNMPv1 community 'public' — full MIB read",         "host_discovery"),
    ("mysql", 3306):   ("MySQL weak root password — unauthenticated DB",     "sql_inject"),
    ("mssql", 1433):   ("xp_cmdshell enabled — OS command execution",        "sql_inject"),
    ("postgresql", 5432): ("Postgres trust auth — no password required",     "credential_dump"),
    ("smtp", 25):      ("Open relay + header injection — exfil channel",     "dns_exfil"),
    ("imap", 143):     ("Plaintext cred transmission — capture in transit",  "keylogger"),
    ("ntlm", 445):     ("NTLM relay via UNC path coercion",                  "force_auth"),
    ("rf", 433):       ("RF replay attack — rolling code capture",           "signal_spoof"),
    ("zigbee", 2400):  ("Zigbee key extraction via touchlink reset",         "arp_poison"),
    ("bluetooth", 2401): ("BLESA spoofing — reconnect vulnerability",        "signal_spoof"),
    ("rsync", 873):    ("Anonymous rsync module — plaintext file access",    "loot_decrypt"),
    ("s3api", 9000):   ("Misconfigured S3 bucket — public read/write ACL",   "credential_dump"),
    ("grpc", 50051):   ("Unauthenticated gRPC reflection — full API enum",   "port_scan"),
    ("openvpn", 1194): ("Shared key compromise — client cert bypass",        "pivot_relay"),
    ("ipsec", 500):    ("Aggressive mode IKE — PSK hash capture & relay",    "force_auth"),
    ("l2tp", 1701):    ("L2TP/IPSec weak PSK — offline brute-force",         "crack_password"),
    ("docker", 2375):  ("Unauthenticated Docker socket — full host access",  "shellcode_exec"),
    ("k8s", 6443):     ("Anonymous kubectl — pod creation / host escape",    "uac_escape"),
}

# Tools that require a hardware/infrastructure resource to function.
# Resources are unlocked by hacking the corresponding terminal types.
_TOOL_RESOURCE: dict[str, str] = {
    "crack_password": "gpu",     # brute-forcing password hashes needs GPU compute
    "kerberoast":     "cloud",   # Kerberoast needs auth server reachability
    "forge_token":    "cloud",   # Golden Ticket needs KDC signing material
    "force_auth":     "relay",   # NTLM relay needs a listening responder relay
    "shellcode_exec": "compute", # shellcode injection needs local compute staging
    "exploit_vuln":   "compute", # binary exploits need compute to stage payload
    "wmi_exec":       "relay",   # WMI lateral needs existing foothold relay
    "remote_exec":    "relay",   # PsExec needs relay/pivot point
}

# Which resource type each control type provides when hacked.
_TERMINAL_RESOURCE: dict[str, str] = {
    "security":  "gpu",
    "cameras":   "gpu",
    "scada":     "gpu",
    "cloud":     "cloud",
    "backup":    "cloud",
    "auth":      "cloud",
    "comm":      "relay",
    "vpn":       "relay",
    "webshell":  "relay",
    "power":     "compute",
    "firmware":  "compute",
    "dungeon":   "compute",
}
RING_SLOT_COUNT = 10
RING_SLOTS = tuple(f"ring_{i}" for i in range(1, RING_SLOT_COUNT + 1))

# Crafting recipes. inputs use material categories (wood/clay/metal/gem).
# station None means craftable anywhere; otherwise an anvil or table must be near.
CRAFT_RECIPES = [
    {"name": "Torch Bundle", "inputs": {"wood": 1}, "station": None,
     "result": {"char": "$", "name": "torch bundle", "kind": "item", "slot": "none",
                "desc": "bundled torches for the dark", "attack": 0, "defense": 0,
                "sight_bonus": 0, "quality": "common", "rarity": "common",
                "weight": 0.5, "value_cp": 40}},
    {"name": "Iron Dagger", "inputs": {"metal": 1}, "station": "table",
     "result": {"char": "$", "name": "iron dagger", "kind": "weapon", "slot": "weapon",
                "desc": "a quickly forged blade", "attack": 4, "defense": 0,
                "sight_bonus": 0, "quality": "sturdy", "rarity": "common",
                "weight": 1.0, "value_cp": 120}},
    {"name": "Sharpened Spear", "inputs": {"wood": 1, "metal": 1}, "station": "table",
     "result": {"char": "$", "name": "sharpened spear", "kind": "weapon", "slot": "weapon",
                "desc": "a spear with a forged tip", "attack": 7, "defense": 0,
                "sight_bonus": 0, "quality": "sturdy", "rarity": "uncommon",
                "weight": 2.5, "value_cp": 200}},
    {"name": "Wooden Buckler", "inputs": {"wood": 2}, "station": "table",
     "result": {"char": "$", "name": "wooden buckler", "kind": "armor", "slot": "shield",
                "desc": "a light crafted shield", "attack": 0, "defense": 3,
                "sight_bonus": 0, "quality": "sturdy", "rarity": "common",
                "weight": 2.5, "value_cp": 120}},
    {"name": "Iron Helm", "inputs": {"metal": 2}, "station": "anvil",
     "result": {"char": "$", "name": "forged iron helm", "kind": "armor", "slot": "armor_head",
                "desc": "a hammered iron helm", "attack": 0, "defense": 4,
                "sight_bonus": 0, "quality": "sturdy", "rarity": "uncommon",
                "weight": 1.6, "value_cp": 220}},
    {"name": "Iron Greaves", "inputs": {"metal": 2}, "station": "anvil",
     "result": {"char": "$", "name": "forged greaves", "kind": "armor", "slot": "armor_legs",
                "desc": "sturdy leg plates", "attack": 0, "defense": 5,
                "sight_bonus": 0, "quality": "sturdy", "rarity": "uncommon",
                "weight": 4.6, "value_cp": 260}},
    {"name": "Iron Cuirass", "inputs": {"metal": 3}, "station": "anvil",
     "result": {"char": "$", "name": "forged cuirass", "kind": "armor", "slot": "armor_chest",
                "desc": "a solid breastplate", "attack": 0, "defense": 7,
                "sight_bonus": 0, "quality": "fine", "rarity": "uncommon",
                "weight": 8.0, "value_cp": 360}},
    {"name": "Reinforced Plate", "inputs": {"metal": 4, "clay": 1}, "station": "anvil",
     "result": {"char": "$", "name": "reinforced plate", "kind": "armor", "slot": "armor_chest",
                "desc": "clay-tempered heavy plate", "attack": 0, "defense": 11,
                "sight_bonus": 0, "quality": "fine", "rarity": "rare",
                "weight": 9.5, "value_cp": 560}},
    {"name": "Clay Healing Flask", "inputs": {"clay": 2}, "station": "table",
     "result": {"char": "*", "name": "healing draught", "kind": "potion", "slot": "none",
                "desc": "a crafted healing draught", "attack": 0, "defense": 0,
                "sight_bonus": 0, "quality": "fine", "rarity": "uncommon",
                "weight": 0.4, "value_cp": 120}},
    {"name": "Gemmed Sight Ring", "inputs": {"gem": 1, "metal": 1}, "station": "anvil",
     "result": {"char": "$", "name": "gemmed ring", "kind": "jewelry", "slot": "ring",
                "desc": "a ring set to sharpen sight", "attack": 0, "defense": 0,
                "sight_bonus": 3, "quality": "fine", "rarity": "rare",
                "weight": 0.2, "value_cp": 260}},
    {"name": "Warding Amulet", "inputs": {"gem": 2, "metal": 1}, "station": "anvil",
     "result": {"char": "$", "name": "warding amulet", "kind": "jewelry", "slot": "amulet",
                "desc": "an amulet of guard and vision", "attack": 0, "defense": 2,
                "sight_bonus": 2, "quality": "fine", "rarity": "rare",
                "weight": 0.3, "value_cp": 320}},
    # Electronics → module crafting
    {"name": "Sniffer Patch", "inputs": {"electronics": 1}, "station": None,
     "result": {"char": "$", "name": "sniffer_patch module", "kind": "module",
                "slot": "none", "desc": "unlocks capture_handshake", "attack": 0,
                "defense": 0, "sight_bonus": 0, "quality": "fine", "rarity": "uncommon",
                "weight": 0.2, "value_cp": 180}},
    {"name": "Radio Firmware", "inputs": {"electronics": 1, "metal": 1}, "station": "table",
     "result": {"char": "$", "name": "radio_firmware module", "kind": "module",
                "slot": "none", "desc": "unlocks signal_spoof", "attack": 0,
                "defense": 0, "sight_bonus": 0, "quality": "fine", "rarity": "uncommon",
                "weight": 0.2, "value_cp": 220}},
    {"name": "Cipher Kernel", "inputs": {"electronics": 2}, "station": "table",
     "result": {"char": "$", "name": "cipher_kernel module", "kind": "module",
                "slot": "none", "desc": "unlocks crack_password", "attack": 0,
                "defense": 0, "sight_bonus": 0, "quality": "fine", "rarity": "rare",
                "weight": 0.2, "value_cp": 280}},
    {"name": "Logic Probe", "inputs": {"electronics": 1, "metal": 2}, "station": "table",
     "result": {"char": "$", "name": "logic_probe module", "kind": "module",
                "slot": "none", "desc": "unlocks circuit_bypass", "attack": 0,
                "defense": 0, "sight_bonus": 0, "quality": "fine", "rarity": "rare",
                "weight": 0.2, "value_cp": 320}},
    {"name": "Override Bus", "inputs": {"electronics": 2, "metal": 1}, "station": "anvil",
     "result": {"char": "$", "name": "override_bus module", "kind": "module",
                "slot": "none", "desc": "unlocks door_override", "attack": 0,
                "defense": 0, "sight_bonus": 0, "quality": "fine", "rarity": "rare",
                "weight": 0.2, "value_cp": 340}},
    {"name": "Chest Decoder", "inputs": {"electronics": 2, "gem": 1}, "station": "anvil",
     "result": {"char": "$", "name": "chest_decoder module", "kind": "module",
                "slot": "none", "desc": "unlocks loot_decrypt", "attack": 0,
                "defense": 0, "sight_bonus": 0, "quality": "fine", "rarity": "rare",
                "weight": 0.2, "value_cp": 360}},
    {"name": "Daemon Rootkit", "inputs": {"electronics": 3}, "station": "anvil",
     "result": {"char": "$", "name": "daemon_rootkit module", "kind": "module",
                "slot": "none", "desc": "unlocks root_shell", "attack": 0,
                "defense": 0, "sight_bonus": 0, "quality": "fine", "rarity": "epic",
                "weight": 0.2, "value_cp": 480}},
    {"name": "Kernel Implant", "inputs": {"electronics": 3, "metal": 2}, "station": "anvil",
     "result": {"char": "$", "name": "kernel_implant module", "kind": "module",
                "slot": "none", "desc": "unlocks privilege_escalation", "attack": 0,
                "defense": 0, "sight_bonus": 0, "quality": "fine", "rarity": "epic",
                "weight": 0.2, "value_cp": 520}},
    # -- Tier 3: credential & lateral movement modules --
    {"name": "Mimikatz Stub", "inputs": {"electronics": 2, "metal": 1}, "station": "table",
     "result": {"char": "$", "name": "mimikatz_stub module", "kind": "module",
                "slot": "none", "desc": "T1003 — unlocks credential_dump", "attack": 0,
                "defense": 0, "sight_bonus": 0, "quality": "fine", "rarity": "rare",
                "weight": 0.2, "value_cp": 300}},
    {"name": "Keylog Implant", "inputs": {"electronics": 2}, "station": "table",
     "result": {"char": "$", "name": "keylog_implant module", "kind": "module",
                "slot": "none", "desc": "T1056 — unlocks keylogger", "attack": 0,
                "defense": 0, "sight_bonus": 0, "quality": "fine", "rarity": "rare",
                "weight": 0.2, "value_cp": 260}},
    {"name": "Hash Extractor", "inputs": {"electronics": 2, "gem": 1}, "station": "anvil",
     "result": {"char": "$", "name": "hash_extractor module", "kind": "module",
                "slot": "none", "desc": "T1550.002 — unlocks pass_the_hash", "attack": 0,
                "defense": 0, "sight_bonus": 0, "quality": "fine", "rarity": "rare",
                "weight": 0.2, "value_cp": 380}},
    {"name": "SSH Tunneler", "inputs": {"electronics": 2, "metal": 1}, "station": "anvil",
     "result": {"char": "$", "name": "ssh_tunneler module", "kind": "module",
                "slot": "none", "desc": "T1572 — unlocks pivot_relay", "attack": 0,
                "defense": 0, "sight_bonus": 0, "quality": "fine", "rarity": "rare",
                "weight": 0.2, "value_cp": 360}},
    # -- Tier 4: evasion & discovery modules --
    {"name": "Log Wiper", "inputs": {"electronics": 1, "clay": 1}, "station": "table",
     "result": {"char": "$", "name": "log_wiper module", "kind": "module",
                "slot": "none", "desc": "T1070 — unlocks erase_logs", "attack": 0,
                "defense": 0, "sight_bonus": 0, "quality": "fine", "rarity": "uncommon",
                "weight": 0.2, "value_cp": 200}},
    {"name": "Process Mask", "inputs": {"electronics": 2}, "station": "table",
     "result": {"char": "$", "name": "process_mask module", "kind": "module",
                "slot": "none", "desc": "T1036 — unlocks process_spoof", "attack": 0,
                "defense": 0, "sight_bonus": 0, "quality": "fine", "rarity": "rare",
                "weight": 0.2, "value_cp": 280}},
    {"name": "Port Scanner", "inputs": {"electronics": 1}, "station": None,
     "result": {"char": "$", "name": "port_scanner module", "kind": "module",
                "slot": "none", "desc": "T1046 — unlocks port_scan", "attack": 0,
                "defense": 0, "sight_bonus": 0, "quality": "fine", "rarity": "common",
                "weight": 0.2, "value_cp": 140}},
    {"name": "ARP Sweep Kit", "inputs": {"electronics": 1, "metal": 1}, "station": "table",
     "result": {"char": "$", "name": "arp_sweep_kit module", "kind": "module",
                "slot": "none", "desc": "T1018 — unlocks host_discovery", "attack": 0,
                "defense": 0, "sight_bonus": 0, "quality": "fine", "rarity": "uncommon",
                "weight": 0.2, "value_cp": 180}},
    # -- Tier 5: exploitation & impact modules --
    {"name": "Buffer Exploit", "inputs": {"electronics": 3}, "station": "anvil",
     "result": {"char": "$", "name": "buffer_exploit module", "kind": "module",
                "slot": "none", "desc": "T1203 — unlocks exploit_vuln", "attack": 0,
                "defense": 0, "sight_bonus": 0, "quality": "fine", "rarity": "epic",
                "weight": 0.2, "value_cp": 500}},
    {"name": "SQL Injector", "inputs": {"electronics": 2, "gem": 1}, "station": "anvil",
     "result": {"char": "$", "name": "sql_injector module", "kind": "module",
                "slot": "none", "desc": "T1190 — unlocks sql_inject", "attack": 0,
                "defense": 0, "sight_bonus": 0, "quality": "fine", "rarity": "epic",
                "weight": 0.2, "value_cp": 460}},
    {"name": "Cam Jammer", "inputs": {"electronics": 2, "metal": 1}, "station": "anvil",
     "result": {"char": "$", "name": "cam_jammer module", "kind": "module",
                "slot": "none", "desc": "T1562 — unlocks camera_blind", "attack": 0,
                "defense": 0, "sight_bonus": 0, "quality": "fine", "rarity": "rare",
                "weight": 0.2, "value_cp": 340}},
    {"name": "ARP Spoofer", "inputs": {"electronics": 2, "metal": 2}, "station": "anvil",
     "result": {"char": "$", "name": "arp_spoofer module", "kind": "module",
                "slot": "none", "desc": "T1557 — unlocks arp_poison", "attack": 0,
                "defense": 0, "sight_bonus": 0, "quality": "fine", "rarity": "epic",
                "weight": 0.2, "value_cp": 440}},
    # -- Tier 6: credential forgery --
    {"name": "Kerberoast Kit", "inputs": {"electronics": 3, "gem": 1}, "station": "anvil",
     "result": {"char": "$", "name": "kerberoast_kit module", "kind": "module",
                "slot": "none", "desc": "T1558.003 — unlocks kerberoast", "attack": 0,
                "defense": 0, "sight_bonus": 0, "quality": "fine", "rarity": "epic",
                "weight": 0.2, "value_cp": 580}},
    {"name": "Golden Ticket", "inputs": {"electronics": 3, "gem": 2}, "station": "anvil",
     "result": {"char": "$", "name": "golden_ticket module", "kind": "module",
                "slot": "none", "desc": "T1558.001 — unlocks forge_token", "attack": 0,
                "defense": 0, "sight_bonus": 0, "quality": "fine", "rarity": "legendary",
                "weight": 0.2, "value_cp": 700}},
    {"name": "Pass Ticket", "inputs": {"electronics": 2, "metal": 1}, "station": "anvil",
     "result": {"char": "$", "name": "pass_ticket module", "kind": "module",
                "slot": "none", "desc": "T1550.003 — unlocks pass_the_ticket", "attack": 0,
                "defense": 0, "sight_bonus": 0, "quality": "fine", "rarity": "rare",
                "weight": 0.2, "value_cp": 400}},
    # -- Tier 6: code execution --
    {"name": "Shellcode Loader", "inputs": {"electronics": 2, "metal": 1}, "station": "table",
     "result": {"char": "$", "name": "shellcode_loader module", "kind": "module",
                "slot": "none", "desc": "T1055.001 — unlocks shellcode_exec", "attack": 0,
                "defense": 0, "sight_bonus": 0, "quality": "fine", "rarity": "rare",
                "weight": 0.2, "value_cp": 380}},
    {"name": "UAC Bypass", "inputs": {"electronics": 2}, "station": "table",
     "result": {"char": "$", "name": "uac_bypass module", "kind": "module",
                "slot": "none", "desc": "T1548.002 — unlocks uac_escape", "attack": 0,
                "defense": 0, "sight_bonus": 0, "quality": "fine", "rarity": "rare",
                "weight": 0.2, "value_cp": 320}},
    {"name": "WMI Implant", "inputs": {"electronics": 2, "metal": 1}, "station": "table",
     "result": {"char": "$", "name": "wmi_implant module", "kind": "module",
                "slot": "none", "desc": "T1047 — unlocks wmi_exec", "attack": 0,
                "defense": 0, "sight_bonus": 0, "quality": "fine", "rarity": "rare",
                "weight": 0.2, "value_cp": 360}},
    # -- Tier 6: lateral movement --
    {"name": "RDP Hijack", "inputs": {"electronics": 2, "gem": 1}, "station": "anvil",
     "result": {"char": "$", "name": "rdp_hijack module", "kind": "module",
                "slot": "none", "desc": "T1021.001 — unlocks remote_desktop", "attack": 0,
                "defense": 0, "sight_bonus": 0, "quality": "fine", "rarity": "epic",
                "weight": 0.2, "value_cp": 480}},
    {"name": "PsExec Kit", "inputs": {"electronics": 2, "metal": 2}, "station": "anvil",
     "result": {"char": "$", "name": "psexec_kit module", "kind": "module",
                "slot": "none", "desc": "T1021.002 — unlocks remote_exec", "attack": 0,
                "defense": 0, "sight_bonus": 0, "quality": "fine", "rarity": "epic",
                "weight": 0.2, "value_cp": 460}},
    # -- Tier 6: persistence & exfil --
    {"name": "Cron Backdoor", "inputs": {"electronics": 1, "clay": 1}, "station": "table",
     "result": {"char": "$", "name": "cron_backdoor module", "kind": "module",
                "slot": "none", "desc": "T1053.003 — unlocks persist_cron", "attack": 0,
                "defense": 0, "sight_bonus": 0, "quality": "fine", "rarity": "uncommon",
                "weight": 0.2, "value_cp": 210}},
    {"name": "Startup Hook", "inputs": {"electronics": 2}, "station": "table",
     "result": {"char": "$", "name": "startup_hook module", "kind": "module",
                "slot": "none", "desc": "T1547.001 — unlocks persist_boot", "attack": 0,
                "defense": 0, "sight_bonus": 0, "quality": "fine", "rarity": "rare",
                "weight": 0.2, "value_cp": 290}},
    {"name": "DNS Tunnel", "inputs": {"electronics": 2, "metal": 1}, "station": "table",
     "result": {"char": "$", "name": "dns_tunnel module", "kind": "module",
                "slot": "none", "desc": "T1071.004 — unlocks dns_exfil", "attack": 0,
                "defense": 0, "sight_bonus": 0, "quality": "fine", "rarity": "rare",
                "weight": 0.2, "value_cp": 340}},
    {"name": "Firmware Patch", "inputs": {"electronics": 3, "metal": 2}, "station": "anvil",
     "result": {"char": "$", "name": "firmware_patch module", "kind": "module",
                "slot": "none", "desc": "T1601 — unlocks flash_firmware", "attack": 0,
                "defense": 0, "sight_bonus": 0, "quality": "fine", "rarity": "legendary",
                "weight": 0.2, "value_cp": 660}},
    # -- Tier 7: relay & LOLBins --
    {"name": "NTLM Relay", "inputs": {"electronics": 2, "metal": 1}, "station": "table",
     "result": {"char": "$", "name": "ntlm_relay module", "kind": "module",
                "slot": "none", "desc": "T1187 — unlocks force_auth (relay, no crack needed)",
                "attack": 0, "defense": 0, "sight_bonus": 0, "quality": "fine",
                "rarity": "rare", "weight": 0.2, "value_cp": 380}},
    {"name": "LOLBin Wrapper", "inputs": {"electronics": 2}, "station": "table",
     "result": {"char": "$", "name": "lolbin_wrapper module", "kind": "module",
                "slot": "none", "desc": "T1218 — unlocks lolbin_exec (certutil/mshta/regsvr32)",
                "attack": 0, "defense": 0, "sight_bonus": 0, "quality": "fine",
                "rarity": "rare", "weight": 0.2, "value_cp": 340}},
    {"name": "Token Stealer", "inputs": {"electronics": 2, "gem": 1}, "station": "anvil",
     "result": {"char": "$", "name": "token_stealer module", "kind": "module",
                "slot": "none", "desc": "T1134 — unlocks token_impersonate",
                "attack": 0, "defense": 0, "sight_bonus": 0, "quality": "fine",
                "rarity": "epic", "weight": 0.2, "value_cp": 460}},
    {"name": "BITS Scheduler", "inputs": {"electronics": 1, "clay": 1}, "station": "table",
     "result": {"char": "$", "name": "bits_scheduler module", "kind": "module",
                "slot": "none", "desc": "T1197 — unlocks bits_job (background transfer evasion)",
                "attack": 0, "defense": 0, "sight_bonus": 0, "quality": "fine",
                "rarity": "uncommon", "weight": 0.2, "value_cp": 220}},
    # -- Tier 7: evasion & obfuscation --
    {"name": "Obfuscator Kit", "inputs": {"electronics": 2, "clay": 1}, "station": "table",
     "result": {"char": "$", "name": "obfuscator_kit module", "kind": "module",
                "slot": "none", "desc": "T1027 — unlocks obfuscate (AV evasion via packing)",
                "attack": 0, "defense": 0, "sight_bonus": 0, "quality": "fine",
                "rarity": "rare", "weight": 0.2, "value_cp": 310}},
    {"name": "DCOM Exploit", "inputs": {"electronics": 2, "metal": 2}, "station": "anvil",
     "result": {"char": "$", "name": "dcom_exploit module", "kind": "module",
                "slot": "none", "desc": "T1021.003 — unlocks dcom_exec (remote COM exec)",
                "attack": 0, "defense": 0, "sight_bonus": 0, "quality": "fine",
                "rarity": "epic", "weight": 0.2, "value_cp": 470}},
    # -- Tier 7: collection & intel --
    {"name": "Screen Cap", "inputs": {"electronics": 1, "metal": 1}, "station": "table",
     "result": {"char": "$", "name": "screen_cap module", "kind": "module",
                "slot": "none", "desc": "T1113 — unlocks screenshot (framebuffer intel)",
                "attack": 0, "defense": 0, "sight_bonus": 0, "quality": "fine",
                "rarity": "uncommon", "weight": 0.2, "value_cp": 240}},
    {"name": "Cookie Stealer", "inputs": {"electronics": 2}, "station": "table",
     "result": {"char": "$", "name": "cookie_stealer module", "kind": "module",
                "slot": "none", "desc": "T1539 — unlocks steal_cookie (session hijack)",
                "attack": 0, "defense": 0, "sight_bonus": 0, "quality": "fine",
                "rarity": "rare", "weight": 0.2, "value_cp": 330}},
    {"name": "Browser Dump", "inputs": {"electronics": 2, "metal": 1}, "station": "table",
     "result": {"char": "$", "name": "browser_dump module", "kind": "module",
                "slot": "none", "desc": "T1555 — unlocks browser_creds (saved password dump)",
                "attack": 0, "defense": 0, "sight_bonus": 0, "quality": "fine",
                "rarity": "rare", "weight": 0.2, "value_cp": 360}},
    {"name": "ICMP Tunnel", "inputs": {"electronics": 2, "metal": 1}, "station": "anvil",
     "result": {"char": "$", "name": "icmp_tunnel module", "kind": "module",
                "slot": "none", "desc": "T1095 — unlocks icmp_covert (covert ICMP channel)",
                "attack": 0, "defense": 0, "sight_bonus": 0, "quality": "fine",
                "rarity": "rare", "weight": 0.2, "value_cp": 350}},
    {"name": "Share Scanner", "inputs": {"electronics": 1, "metal": 2}, "station": "table",
     "result": {"char": "$", "name": "share_scanner module", "kind": "module",
                "slot": "none", "desc": "T1039 — unlocks share_harvest (SMB enum + stage)",
                "attack": 0, "defense": 0, "sight_bonus": 0, "quality": "fine",
                "rarity": "uncommon", "weight": 0.2, "value_cp": 250}},
    {"name": "Env Harvester", "inputs": {"electronics": 1}, "station": None,
     "result": {"char": "$", "name": "env_harvester module", "kind": "module",
                "slot": "none", "desc": "T1552 — unlocks env_creds (grep env for secrets)",
                "attack": 0, "defense": 0, "sight_bonus": 0, "quality": "fine",
                "rarity": "common", "weight": 0.2, "value_cp": 150}},
]

# Which glyph wins a downsampled minimap block (higher = more important).
_MINI_PR = {".": 0, "#": 1, "T": 2, "<": 5, "k": 3, "*": 3, "$": 3,
            "!": 4, "&": 4, "+": 4, "=": 4, ">": 5, "V": 5, "O": 6,
            "X": 4, "A": 4, "F": 4, "~": 3, "%": 4}

# ── Alert / Heat system ──────────────────────────────────────────────────────
# Heat is a float 0.0–5.0; integer level gates each tier of effect.
_HEAT_SIGHT_BONUS   = [0, 1, 2, 3, 4, 5]       # extra tiles added to enemy sight_radius
_HEAT_SPAWN_INTVL   = [9999, 9999, 9999, 15, 10, 5]  # turns between reinforcement spawns
_HEAT_HACK_PENALTY  = [0.0, 0.0, 0.05, 0.08, 0.12, 0.20]  # subtracted from hack chance
_HEAT_LABELS        = ["clear", "edgy", "tense", "ALERT", "HEAVY ALERT", "LOCKDOWN"]
_HEAT_ESCALATION_MSG = [
    "",
    "Guards grow edgy — patrols sharpen their eyes.",
    "Tension rising. Patrols tighten throughout the castle.",
    "ALERT: commander has called reinforcements to your position!",
    "HEAVY ALERT: lockdown protocols engaged. Terminal security hardened.",
    "LOCKDOWN: every guard in the castle is hunting you.",
]
# How much heat each hack mode generates / removes on attempt
_MODE_HEAT: dict[str, float] = {
    "balanced":   0.30,
    "stealth":    0.00,
    "spoof":      0.10,
    "bruteforce": 0.80,
    "exploit":    0.50,
    "pivot":      0.10,
    "evasion":   -0.50,   # negative = lowers heat
    "recon":      0.00,
    "social":     0.05,
    "kerberos":   0.30,
    "wmi":        0.20,
    "ntlm":       0.30,
    "lolbin":    -0.30,
}
# Reinforcement guard names by heat level
_REINFORCE_NAMES = {
    3: ["patrol guard", "sentry"],
    4: ["enforcer", "veteran guard"],
    5: ["elite operative", "castle commander"],
}

# Starting archetypes — each shapes skills, starting modules, wallet, and one passive
_ARCHETYPES: dict[str, dict] = {
    "infiltrator": {
        "label":   "INFILTRATOR",
        "desc":    "Move unseen. Strike first, leave no trace.",
        "skills":  {"evasion": 4, "recon": 2},
        "modules": ["log_wiper", "process_mask"],
        "wallet":  160,
        "passive": "Stealth bonus +2 tiles. Guards lose alert 20% faster.",
    },
    "combat_specialist": {
        "label":   "COMBAT SPECIALIST",
        "desc":    "Survive anything. Hit harder.",
        "skills":  {"melee": 6, "ranged": 3},
        "modules": ["override_bus"],
        "wallet":  220,
        "passive": "+2 base melee attack. Killing blow drops bonus coin.",
    },
    "netrunner": {
        "label":   "NETRUNNER",
        "desc":    "Every terminal is a weapon.",
        "skills":  {"recon": 4, "exploit": 2, "creds": 1},
        "modules": ["sniffer_patch", "cipher_kernel", "port_scanner"],
        "wallet":  180,
        "passive": "Terminals within 5 tiles reveal type without scanning.",
    },
}


class Game:
    def __init__(self, start_bonus: bool = False):
        self.b = Board()
        self.log: list[tuple[str, str]] = []
        self.started = False
        self.cmd_mode = False
        self.cmd_buf = ""
        self.overlay = None          # None | help | commands | inventory | map | journal
        self.won = False
        self.clues = 0
        self.journal: list[str] = []
        self.escaped = False
        self.portal_armed = False
        self.portal_placed = False
        self.tick = 0
        self.status_note = ""
        self.difficulty = "normal"
        self.start_bonus = start_bonus
        self.xp_mult = 3 if start_bonus else 1
        self.modules: set[str] = set()
        self.tools: set[str] = {"wifi_scan"}
        self.wallet_cp = 260
        self.max_weight = 108.0
        self.max_hp = BASE_PLAYER_HP
        self.hp = BASE_PLAYER_HP
        self.active_effects: list[dict] = []
        self.turn_count = 0
        self.inv_cursor = 0
        self.inv_scroll = 0
        self.inv_tab = "gear"  # gear|jewelry
        self.shop_cursor = 0
        self.shop_scroll = 0
        self.shop_mode = "stock"  # stock|bag
        self.craft_cursor = 0
        self.craft_scroll = 0
        self.craft_tab = "recipes"      # recipes|socket
        self.craft_filter = False       # show only craftable recipes
        self.craft_gem_step: str | None = None  # "pick" | "confirm"
        self.craft_gem_item: tuple | None = None
        self.craft_gem_cursor = 0
        self.craft_gem_choice = None
        self.shoot_mode = False
        # melee/ranged: XP counters (3 XP = 1 level)
        # hacking sub-skills: direct levels (1 successful use = 1 level)
        # "tech" is kept as a read-only aggregate for display; not stored directly.
        self.skills: dict[str, int] = {
            "melee": 0, "ranged": 0,
            "recon": 0, "exploit": 0, "creds": 0,
            "lateral": 0, "persist": 0, "evasion": 0, "social": 0,
        }
        self.next_restock_turn: int = random.randint(*SHOP_RESTOCK_INTERVAL)
        self.valid_credentials: bool = False   # T1078: set by hacking auth terminal
        self.firmware_bonus: float = 0.0       # T1601: set by hacking firmware terminal
        # Alert / heat system
        self.heat: float = 0.0                 # 0.0–5.0; drives enemy aggro and terminal difficulty
        self._last_heat_spawn: int = 0         # turn when last reinforcement was spawned
        # Stealth system
        self.stealth_mode: bool = False        # v key toggles; halves enemy detection range
        self._stealth_strike: bool = False     # set before combat if attacking from stealth
        self.archetype: str = "netrunner"      # set by _archetype_select before dungeon gen
        # Resource pools unlocked by hacking terminals that provide infrastructure.
        # Keys: "gpu", "cloud", "relay", "compute" — values: set of provider ssids.
        self.resources: dict[str, set[str]] = {"gpu": set(), "cloud": set(),
                                                "relay": set(), "compute": set()}
        self.equipped: dict[str, object] = {
            "weapon": None,
            "armor_head": None,
            "armor_chest": None,
            "armor_legs": None,
            "shield": None,
            "amulet": None,
            "back": None,
        }
        for slot in RING_SLOTS:
            self.equipped[slot] = None
        self.backpack_inv: list = []   # items stored in the worn backpack

    # ===================================================================
    #  entry
    # ===================================================================
    def run(self):
        curses.wrapper(self._main)

    def _main(self, scr):
        self.scr = scr
        curses.curs_set(0)
        scr.nodelay(True)
        scr.timeout(110)
        self._init_colors()
        self._archetype_select(scr)
        self._apply_archetype()
        self.b.generate_dungeon()
        if self.start_bonus:
            self._apply_start_bonus()
        self.b.compute_visible(radius=self._vision_radius())
        self._offline("initial", {})
        while True:
            self.tick += 1
            self._draw()
            try:
                ch = scr.getch()
            except curses.error:
                ch = -1
            if ch == -1:
                continue
            if self.won:
                break
            if self.overlay:
                if not self._handle_overlay_key(ch):
                    break
                continue
            if self.cmd_mode:
                self._handle_cmd_key(ch)
                continue
            if not self._handle_key(ch):
                break

    def _handle_overlay_key(self, ch) -> bool:
        if self.overlay == "inventory":
            return self._handle_inventory_overlay_key(ch)
        if self.overlay == "shop":
            return self._handle_shop_overlay_key(ch)
        if self.overlay == "craft":
            return self._handle_craft_overlay_key(ch)
        self.overlay = None   # non-interactive overlays dismiss on any key
        return True

    # ===================================================================
    #  archetype selection
    # ===================================================================
    _ARCH_ORDER = ["infiltrator", "combat_specialist", "netrunner"]

    def _archetype_select(self, scr) -> None:
        """Blocking pre-game overlay: player picks a starting archetype."""
        scr.nodelay(False)
        scr.timeout(-1)
        cursor = 0
        order = self._ARCH_ORDER
        while True:
            scr.erase()
            h, w = scr.getmaxyx()
            bold = curses.A_BOLD
            rev  = curses.A_REVERSE
            try:
                title = "===  CHOOSE YOUR ARCHETYPE  ==="
                tx = max(0, w // 2 - len(title) // 2)
                scr.addstr(1, tx, title, bold)
                for i, key in enumerate(order):
                    info = _ARCHETYPES[key]
                    y0 = 3 + i * 6
                    attr = rev | bold if i == cursor else bold
                    marker = "> " if i == cursor else "  "
                    scr.addstr(y0,     4, f"{marker}[{i+1}] {info['label']}", attr)
                    scr.addstr(y0 + 1, 8, info["desc"])
                    sk = "  ".join(f"{k}+{v}" for k, v in info["skills"].items())
                    scr.addstr(y0 + 2, 8, f"Skills: {sk}")
                    mods = "  ".join(info["modules"])
                    scr.addstr(y0 + 3, 8, f"Modules: {mods}")
                    scr.addstr(y0 + 4, 8, f"Passive: {info['passive']}")
                footer = "arrow keys / 1-2-3 to select     Enter to confirm"
                scr.addstr(min(h - 2, 3 + len(order) * 6 + 1), 4, footer)
            except curses.error:
                pass
            scr.refresh()
            ch = scr.getch()
            if ch in (curses.KEY_UP, ord("w"), ord("k")):
                cursor = (cursor - 1) % len(order)
            elif ch in (curses.KEY_DOWN, ord("s"), ord("j")):
                cursor = (cursor + 1) % len(order)
            elif ch == ord("1"):
                cursor = 0
            elif ch == ord("2"):
                cursor = 1
            elif ch == ord("3"):
                cursor = 2
            elif ch in (10, 13, ord(" ")):
                self.archetype = order[cursor]
                break
            elif ch in (27, ord("q")):
                self.archetype = "netrunner"
                break
        scr.nodelay(True)
        scr.timeout(110)

    def _apply_start_bonus(self) -> None:
        """Spawn a debug kit when launched with --start-bonus."""
        def _it(char, name, desc, kind, **fields) -> Item:
            it = Item(self.b._id("it"), 0, 0, char, name, desc, kind)
            for k, v in fields.items():
                setattr(it, k, v)
            return it

        # Level 3 backpack
        self.b.inventory.append(_it(
            "[", "leather haversack", "a well-stitched leather haversack", "backpack",
            slot="back", weight=2.5, value_cp=720, rarity="rare",
            carry_bonus=56.0, bag_capacity=40,
        ))

        # Weapon with 25+ attack
        self.b.inventory.append(_it(
            "$", "war axe", "heavy axe, keen edge still bright", "weapon",
            slot="weapon", attack=25, weight=3.5, value_cp=600,
            quality="fine", rarity="rare",
        ))

        # 2 citrine gems (+4 bag slots each)
        for _ in range(2):
            self.b.inventory.append(_it(
                "^", "citrine", "a cut gem (socket into backpack: +4 slots)", "material",
                material="gem", bag_slots=4, weight=0.2, value_cp=200,
            ))

        # 2 amethyst gems (+16 carry each)
        for _ in range(2):
            self.b.inventory.append(_it(
                "^", "amethyst", "a cut gem (socket into armor/backpack: +16 carry)", "material",
                material="gem", carry_bonus=16.0, weight=0.2, value_cp=200,
            ))

        # 10 random gems
        _gem_pool = [
            ("^", "ruby",     "a cut gem (socket into armor: +2 atk)",         {"attack": 2}),
            ("^", "garnet",   "a cut gem (socket into armor: +2 atk)",         {"attack": 2}),
            ("^", "sapphire", "a cut gem (socket into armor: +2 def)",         {"defense": 2}),
            ("^", "onyx",     "a cut gem (socket into armor: +2 def)",         {"defense": 2}),
            ("^", "emerald",  "a cut gem (socket into armor: +2 sight)",       {"sight_bonus": 2}),
            ("^", "topaz",    "a cut gem (socket into armor: +2 sight)",       {"sight_bonus": 2}),
            ("^", "diamond",  "a cut gem (socket into armor: +1 atk/def/sight)", {"attack": 1, "defense": 1, "sight_bonus": 1}),
            ("^", "amethyst", "a cut gem (socket into armor/backpack: +8 carry)", {"carry_bonus": 8.0}),
            ("^", "citrine",  "a cut gem (socket into backpack: +2 slots)",    {"bag_slots": 2}),
        ]
        for _ in range(10):
            char, name, desc, fields = random.choice(_gem_pool)
            self.b.inventory.append(_it(char, name, desc, "material",
                                        material="gem", weight=0.2, value_cp=140, **fields))

        # 10 starter modules
        for mod in list(MODULE_TO_TOOL.keys())[:10]:
            self._unlock_module(mod, "start bonus")

        self._sys("Start bonus: haversack, war axe, 14 gems, 10 modules — XP ×3.")

    def _apply_archetype(self) -> None:
        """Apply starting bonuses for the chosen archetype."""
        arch = _ARCHETYPES[self.archetype]
        for skill, val in arch["skills"].items():
            self.skills[skill] = val
        for mod in arch["modules"]:
            self.modules.add(mod)
            tool = MODULE_TO_TOOL.get(mod)
            if tool:
                self.tools.add(tool)
        self.wallet_cp = arch["wallet"]

    def _init_colors(self):
        self.has_color = curses.has_colors()
        if not self.has_color:
            return
        curses.start_color()
        try:
            curses.use_default_colors()
            bg = -1
        except curses.error:
            bg = curses.COLOR_BLACK
        fg = {
            1: curses.COLOR_WHITE, 2: curses.COLOR_BLUE, 3: curses.COLOR_YELLOW,
            4: curses.COLOR_YELLOW, 5: curses.COLOR_CYAN, 6: curses.COLOR_RED,
            7: curses.COLOR_MAGENTA, 8: curses.COLOR_GREEN, 9: curses.COLOR_RED,
            10: curses.COLOR_GREEN, 11: curses.COLOR_WHITE,
        }
        for pair, color in fg.items():
            try:
                curses.init_pair(pair, color, bg)
            except curses.error:
                pass

    def _attr(self, pair, bold=False):
        if not self.has_color:
            return curses.A_BOLD if bold else 0
        a = curses.color_pair(pair)
        return a | curses.A_BOLD if bold else a

    # ===================================================================
    #  input
    # ===================================================================
    def _handle_key(self, ch) -> bool:
        if ch in (ord("q"), ord("Q")):
            return False
        if ch == ord("?"):
            self.overlay = "help"
            return True
        if ch in (ord("c"), ord("C")):
            self.overlay = "commands"
            return True
        if not self.started:
            return True
        # -- shoot mode: next directional key fires in that direction ----------
        if self.shoot_mode:
            if ch == 27:
                self.shoot_mode = False
            else:
                d = self._key_to_dir(ch)
                if d:
                    self.shoot_mode = False
                    self._shoot_direction(*d)
            return True
        # -- overlays (panels you can pop up any time) --------------------
        if ch in (ord("i"), ord("I")):
            self.overlay = "inventory"
            return True
        if ch in (ord("p"), ord("P")):
            self.overlay = "toolkit"
            return True
        if ch in (ord("m"), ord("M")):
            self.overlay = "map"
            return True
        if ch in (ord("n"), ord("N")):
            self.overlay = "journal"
            return True
        if ch in (ord("g"), ord("G")):
            self._open_craft()
            return True
        # -- actions -----------------------------------------------------
        if ch in (ord("t"), ord("/")):
            self.cmd_mode = True
            self.cmd_buf = ""
            return True
        if ch in (ord("l"), ord("L")):
            self._offline("examine", {"target": "look slowly around the area"})
            self._advance_turn()
            return True
        if ch in (ord("e"), ord("E"), ord(" ")):
            self._offline("examine",
                           {"target": "search the area for anything hidden",
                            "search": True})
            self._advance_turn()
            return True
        if ch in (ord("r"), ord("R")):
            self._offline("examine",
                           {"target": "rest a moment and listen to the castle",
                            "rest": True})
            self._advance_turn()
            return True
        if ch in (ord("f"), ord("F")):
            self._confront()
            return True
        if ch in (ord("z"), ord("Z")):
            if self._ranged_weapon():
                self.shoot_mode = True
            else:
                self._sys("Equip a bow, crossbow, or slingshot to shoot (z).")
            return True
        if ch in (ord("u"), ord("U")):
            self.overlay = "skills"
            return True
        if ch in (ord("v"), ord("V")):
            self.stealth_mode = not self.stealth_mode
            if self.stealth_mode:
                bonus = self._stealth_bonus()
                self._sys(f"[SNEAK] Moving quietly — detection range −{bonus} tiles. "
                          f"First strike gives +50% damage. Breaks on attack.")
            else:
                self._sys("[SNEAK OFF] Moving normally.")
            return True
        if ch in (ord("x"), ord("X")):
            self._hack_terminal_action()
            return True
        move = self._key_to_dir(ch)
        if move:
            self._try_move(*move)
        return True

    def _confront(self):
        b = self.b
        nearest, best = None, 999
        for e in b.entities.values():
            d = abs(e.x - b.px) + abs(e.y - b.py)
            if d < best:
                best, nearest = d, e
        if nearest is None or best > 6:
            self._sys("There is no one here to confront.")
            return
        defeated = self._resolve_confront_loot(nearest, best)
        if defeated:
            self._offline("examine",
                           {"target": f"after defeating {nearest.name}, search remains",
                            "entity_id": nearest.id})
        else:
            self._offline("examine",
                           {"target": f"survive confrontation with {nearest.name}",
                            "entity_id": nearest.id})
        self._advance_turn()

    def _resolve_confront_loot(self, ent, distance):
        if not ent.hostile:
            self._sys(f"{ent.name} is not immediately hostile.")
            return False

        # Mark stealth strike if sneaking and enemy hasn't spotted us yet
        if self.stealth_mode and not ent.alerted:
            self._stealth_strike = True
        if not self._combat_encounter(ent):
            return False

        self.b.entities.pop(ent.id, None)
        self._gm(f"You defeat {ent.name} and strip useful hardware from the remains.")
        module = self._module_for_entity(ent.name)
        if module:
            self._unlock_module(module, ent.name)
        coin = random.randint(35, 140)
        if self.archetype == "combat_specialist":
            coin += random.randint(10, 30)
        self.wallet_cp += coin
        self._sys(f"Recovered {self._coins_text(coin)} from the encounter.")
        return True

    def _module_for_entity(self, name: str) -> str | None:
        low = name.lower()
        wild = ("rat", "bat", "wolf", "hound", "boar")
        villains = ("guard", "captain", "jailer", "bandit", "warlord", "mercenary")
        monsters = ("skeleton", "wraith", "ghoul", "ogre", "necromancer")
        techs = ("hacker", "operative", "engineer", "technician", "drone")
        if any(k in low for k in wild):
            # T1040/T1046/T1053/T1552 — basic sensors + env cred scraping
            pool = ["sniffer_patch", "radio_firmware", "port_scanner", "arp_sweep_kit",
                    "log_wiper", "cron_backdoor", "startup_hook", "cipher_kernel",
                    "env_harvester", "screen_cap", "bits_scheduler"]
        elif any(k in low for k in techs):
            # T1003/T1056/T1550/T1572/T1021/T1187/T1218/T1134 — advanced ops
            pool = ["mimikatz_stub", "keylog_implant", "hash_extractor", "ssh_tunneler",
                    "process_mask", "arp_spoofer", "shellcode_loader", "wmi_implant",
                    "rdp_hijack", "psexec_kit", "dns_tunnel", "uac_bypass",
                    "ntlm_relay", "lolbin_wrapper", "token_stealer", "dcom_exploit",
                    "cookie_stealer", "browser_dump", "icmp_tunnel", "obfuscator_kit"]
        elif any(k in low for k in villains):
            # T1574/T1098/T1036/T1547/T1539/T1197 — persistence + evasion
            pool = ["cipher_kernel", "logic_probe", "override_bus",
                    "process_mask", "cam_jammer", "log_wiper",
                    "startup_hook", "cron_backdoor", "uac_bypass",
                    "obfuscator_kit", "bits_scheduler", "cookie_stealer"]
        elif any(k in low for k in monsters):
            # T1014/T1203/T1190/T1558/T1601/T1039/T1555 — rootkit + deep exfil
            pool = ["override_bus", "kernel_implant", "daemon_rootkit", "chest_decoder",
                    "buffer_exploit", "sql_injector", "cam_jammer", "arp_spoofer",
                    "kerberoast_kit", "golden_ticket", "pass_ticket", "firmware_patch",
                    "share_scanner", "browser_dump", "icmp_tunnel", "token_stealer"]
        else:
            pool = list(MODULE_TO_TOOL.keys())
        random.shuffle(pool)
        for module in pool:
            if module not in self.modules:
                return module
        return None

    def _unlock_module(self, module: str, source_name: str):
        if module in self.modules:
            return
        self.modules.add(module)
        tool = MODULE_TO_TOOL.get(module)
        if tool:
            self.tools.add(tool)
            self._sys(f"Looted module from {source_name}: {module} -> unlocked {tool}.")
        else:
            self._sys(f"Looted module from {source_name}: {module}.")

    def _handle_local_command(self, text: str) -> bool:
        low = text.lower().strip()
        if not low:
            return True

        if low.startswith("equip "):
            self._equip_by_name(text[6:].strip())
            return True
        if low.startswith("drink ") or low.startswith("use "):
            name = text.split(" ", 1)[1].strip() if " " in text else ""
            self._drink_potion(name)
            return True
        if low.startswith("unequip"):
            parts = low.split(maxsplit=1)
            slot = parts[1].strip() if len(parts) > 1 else "weapon"
            self._unequip_slot(slot)
            return True
        if low == "shop":
            self._show_shop()
            return True
        if low.startswith("buy "):
            self._buy_shop_item(low[4:].strip())
            return True
        if low.startswith("sell "):
            self._sell_shop_item(text[5:].strip())
            return True

        if low in ("help hack", "hack help", "i am confused", "confused"):
            self._emit_hacking_instructions()
            return True
        if low in ("toolkit", "show toolkit", "open toolkit"):
            self.overlay = "toolkit"
            return True
        if low.startswith("practice"):
            skill_arg = low[8:].strip() if len(low) > 8 else ""
            if skill_arg:
                self._practice_on_rooted(skill_arg)
            else:
                self._sys("practice: specify a skill — recon exploit creds lateral persist evasion social")
            return True
        if low.startswith("botnet") or low in ("bot", "implant", "install botnet"):
            self._install_botnet()
            return True
        if low.startswith("vulnscan") or low in ("vs", "vuln"):
            self._vuln_scan_terminal()
            return True
        if low.startswith("portscan") or low in ("ps", "ports"):
            self._port_scan_terminal()
            return True
        if low.startswith("scan"):
            self._scan_nearby_terminals()
            return True
        if low.startswith("hack"):
            self._hack_terminal_action(self._hack_mode_from_text(low))
            return True

        if any(k in low for k in ("too hard", "frustrat", "decrease difficulty", "make it easier")):
            self._step_difficulty(-1)
            return True
        if any(k in low for k in ("too easy", "increase difficulty", "make it harder")):
            self._step_difficulty(1)
            return True

        m = re.search(r"\bdifficulty\s*(?:to|=)?\s*(easy|normal|hard|nightmare)\b", low)
        if m:
            self._set_difficulty(m.group(1))
            return True
        return False

    def _hack_mode_from_text(self, text: str) -> str:
        if any(k in text for k in ("social", "phish", "engineer", "pretex")):
            return "social"
        if any(k in text for k in ("kerberos", "kerberoast", "golden", "ticket", "tgt")):
            return "kerberos"
        if any(k in text for k in ("wmi", "windows management", "cim")):
            return "wmi"
        if any(k in text for k in ("ntlm", "relay", "responder", "coerce")):
            return "ntlm"
        if any(k in text for k in ("lolbin", "lol", "certutil", "mshta", "living")):
            return "lolbin"
        if any(k in text for k in ("brute", "force")):
            return "bruteforce"
        if "stealth" in text:
            return "stealth"
        if any(k in text for k in ("spoof",)):
            return "spoof"
        if any(k in text for k in ("exploit", "bypass", "logic")):
            return "exploit"
        if any(k in text for k in ("pivot", "tunnel", "lateral")):
            return "pivot"
        if any(k in text for k in ("evasion", "evade", "erase", "wipe", "cover")):
            return "evasion"
        if any(k in text for k in ("recon", "enum", "discover", "passive")):
            return "recon"
        return "balanced"

    def _scan_nearby_terminals(self):
        """Passive wifi scan — lists nearby terminal SSIDs with basic metadata."""
        found = []
        for (x, y), spec in self.b.specials.items():
            if spec.get("kind") != "terminal":
                continue
            d = abs(x - self.b.px) + abs(y - self.b.py)
            if d <= 18:
                if spec.get("botnet"):
                    state = "botnet"
                elif spec.get("hacked"):
                    state = "rooted"
                else:
                    state = "locked"
                pscan = "portscan:done" if "services" in spec else "portscan:pending"
                found.append((d, spec.get("ssid", "CastleNet"),
                              spec.get("control", "doors"), state,
                              spec.get("tier", 1), pscan))
        if not found:
            self._sys("wifi_scan: no terminals in range (max 18 tiles).")
            return
        found.sort(key=lambda t: t[0])
        self._sys("wifi_scan results (type 'portscan' when adjacent for services):")
        for d, ssid, control, state, tier, pscan in found[:8]:
            res = _TERMINAL_RESOURCE.get(control, "")
            res_tag = f" [provides:{res}]" if res else ""
            self._sys(f"  {ssid:<18} ctrl={control:<10} T{tier} dist={d:2} {state}{res_tag}")
        self._sys(f"  Tip: 'portscan' → open ports  |  'vulnscan' → CVEs + tool reqs")

    def _nearest_terminal(self, max_dist: int = 2) -> tuple[tuple[int, int], dict] | None:
        """Return (pos, spec) of closest terminal within max_dist, or None."""
        best = None
        best_d = max_dist + 1
        for (x, y), spec in self.b.specials.items():
            if spec.get("kind") != "terminal":
                continue
            d = abs(x - self.b.px) + abs(y - self.b.py)
            if d < best_d:
                best_d = d
                best = ((x, y), spec)
        return best

    def _ensure_services(self, term: dict):
        """Lazily generate port/service list for a terminal (persists on the dict)."""
        if "services" in term:
            return
        control = term.get("control", "doors")
        base = list(_CONTROL_SERVICES.get(control, [("ssh", 22), ("http", 80)]))
        # Add 0-1 extra services from adjacent control types for variety
        all_svcs = [s for svcs in _CONTROL_SERVICES.values() for s in svcs]
        extras = [s for s in all_svcs if s not in base]
        if extras and random.random() < 0.45:
            base.append(random.choice(extras))
        random.shuffle(base)
        term["services"] = base

    def _practice_on_rooted(self, skill_arg: str):
        """Practice a specific hacking skill on an adjacent rooted terminal.
        Safe (no failure), always grants 1 XP. Higher rate than unguided practice."""
        hit = self._nearest_terminal(max_dist=2)
        if not hit:
            self._sys("practice: no terminal within 2 tiles.")
            return
        pos, term = hit
        ssid = term.get("ssid", "CastleNet")
        if not term.get("hacked"):
            self._sys(f"practice: {ssid} not rooted — you need root to run safe exercises.")
            self._sys("  (On a locked terminal, just attempt to hack — practice is automatic.)")
            return
        HACK_SKILLS = ("recon", "exploit", "creds", "lateral", "persist", "evasion", "social")
        # Accept partial names
        match = next((s for s in HACK_SKILLS if skill_arg.startswith(s[:3])), None)
        if not match:
            self._sys(f"practice: unknown skill '{skill_arg}'.")
            self._sys(f"  Available: {', '.join(HACK_SKILLS)}")
            return
        self._ensure_skill_reqs(term)
        reqs = term["skill_reqs"]
        req = reqs.get(match, 0)
        current = self.skills.get(match, 0)
        # Controlled lab environment: always gain 1 XP
        self.skills[match] = current + 1
        new_lv = self.skills[match]
        self._sys(f"T1059: Controlled {match} drill on {ssid}. "
                  f"+1 {match} XP → Lv{new_lv}.")
        if req > 0:
            gap = max(0, req - new_lv)
            if gap == 0:
                self._sys(f"  This terminal's {match} requirement now met (Lv{req}). Ready to hack.")
            else:
                self._sys(f"  This terminal requires {match} Lv{req} — {gap} more levels needed.")
        # Chance of lab discovery: find a missing module
        if random.random() < 0.10:
            req_tools = self._required_tools_for_terminal(term, "balanced")
            missing_tools = [t for t in req_tools if t not in self.tools]
            if missing_tools:
                tool = random.choice(missing_tools)
                for mod, tool_key in MODULE_TO_TOOL.items():
                    if tool_key == tool and mod not in self.modules:
                        self._unlock_module(mod, f"lab session on {ssid}")
                        break
        self._advance_turn()

    def _install_botnet(self):
        """Install a C2 botnet node on an adjacent rooted terminal to bring its resource online.
        Requires: a persistence tool (persist_cron or persist_boot) + a C2 channel (dns_exfil or icmp_covert).
        TTP: T1053.003 / T1547.001 persistence + T1071.004 / T1095 C2 channel."""
        hit = self._nearest_terminal(max_dist=2)
        if not hit:
            self._sys("botnet: no terminal within 2 tiles — move adjacent to a rooted ! terminal.")
            return
        pos, term = hit
        ssid = term.get("ssid", "CastleNet")
        control = term.get("control", "doors")
        if not term.get("hacked"):
            self._sys(f"botnet: {ssid} not rooted — gain root first (hack it).")
            return
        if term.get("botnet"):
            res_type = _TERMINAL_RESOURCE.get(control, "none")
            self._sys(f"botnet: C2 node already running on {ssid} [{res_type}].")
            return
        # Need a persistence mechanism
        persist_tools = {"persist_cron", "persist_boot"}
        c2_tools = {"dns_exfil", "icmp_covert"}
        missing = []
        if not (persist_tools & self.tools):
            missing.append("persistence (craft cron_backdoor or startup_hook module)")
        if not (c2_tools & self.tools):
            missing.append("C2 channel (craft dns_tunnel or icmp_tunnel module)")
        if missing:
            self._sys("botnet: missing required tools:")
            for m in missing:
                self._sys(f"  — {m}")
            return
        # Install
        term["botnet"] = True
        res_type = _TERMINAL_RESOURCE.get(control)
        persist_used = next(t for t in ("persist_cron", "persist_boot") if t in self.tools)
        c2_used = next(t for t in ("dns_exfil", "icmp_covert") if t in self.tools)
        self._sys(f"T1053/T1071: Dropping implant on {ssid} via {persist_used} + {c2_used}...")
        self._sys(f"  Botnet node installed. Beacon interval: {random.randint(30, 300)}s.")
        if res_type:
            self.resources[res_type].add(ssid)
            self._sys(f"  [{res_type.upper()}] resource now online — available for future hacks.")
        else:
            self._sys(f"  {ssid} ({control}) does not provide a resource type.")
        self.skills["persist"] = self.skills.get("persist", 0) + 1
        self._sys(f"  +1 persist XP (now Lv{self.skills['persist']}).")
        self._advance_turn()

    def _port_scan_terminal(self):
        """portscan — reveal open services on the nearest terminal."""
        hit = self._nearest_terminal(max_dist=2)
        if not hit:
            self._sys("portscan: no terminal within 2 tiles — move adjacent to a ! and retry.")
            return
        pos, term = hit
        ssid = term.get("ssid", "CastleNet")
        self._ensure_services(term)
        svcs = term["services"]
        self._sys(f"portscan {ssid} ({pos[0]},{pos[1]}) — {len(svcs)} open port(s):")
        for proto, port in svcs:
            known_vuln = proto in [p for p, _ in _SERVICE_VULNS]
            flag = " [CVE known]" if (proto, port) in _SERVICE_VULNS else ""
            self._sys(f"  {port:>5}/tcp  {proto:<12}{flag}")
        self._sys("  Run 'vulnscan' (needs port_scan tool) to map CVEs → required tools.")
        self._advance_turn()

    def _vuln_scan_terminal(self):
        """vulnscan — map open ports to CVEs and required tools. Needs port_scan tool."""
        if "port_scan" not in self.tools:
            self._sys("vulnscan: requires port_scan tool (craft port_scanner module at g).")
            return
        hit = self._nearest_terminal(max_dist=2)
        if not hit:
            self._sys("vulnscan: no terminal within 2 tiles.")
            return
        pos, term = hit
        ssid = term.get("ssid", "CastleNet")
        if "services" not in term:
            self._sys(f"vulnscan: {ssid} not yet port-scanned — run 'portscan' first.")
            return
        self._ensure_skill_reqs(term)
        reqs = term["skill_reqs"]
        self._sys(f"vulnscan {ssid} — vulnerability assessment:")
        tools_needed: set[str] = set()
        resources_needed: set[str] = set()
        for proto, port in term["services"]:
            vuln = _SERVICE_VULNS.get((proto, port))
            if vuln:
                desc, tool = vuln
                have_tool = "✓" if tool in self.tools else "✗"
                self._sys(f"  {port:>5}/{proto:<10} {have_tool} {desc}")
                # Show which mode uses this tool and player's skill vs requirement
                for mode_name, sk in _MODE_SKILL.items():
                    mode_req_tools = self._required_tools_for_terminal(term, mode_name)
                    if tool in mode_req_tools:
                        sk_req = reqs.get(sk, 0)
                        sk_lv = self.skills.get(sk, 0)
                        skill_mark = "✓" if sk_lv >= sk_req else f"✗ need {sk} Lv{sk_req}"
                        self._sys(f"             → tool:{tool}  mode:{mode_name}  {skill_mark}")
                        break
                else:
                    self._sys(f"             → tool: {tool}")
                tools_needed.add(tool)
                res = _TOOL_RESOURCE.get(tool)
                if res:
                    resources_needed.add(res)
            else:
                self._sys(f"  {port:>5}/{proto:<10}   (no known exploit in database)")
        # Resource gaps
        if resources_needed:
            self._sys("  Resources required:")
            for res in sorted(resources_needed):
                providers = self.resources.get(res, set())
                if providers:
                    self._sys(f"    {res:>8}: AVAILABLE ({', '.join(list(providers)[:2])})")
                else:
                    src = [c for c, r in _TERMINAL_RESOURCE.items() if r == res]
                    self._sys(f"    {res:>8}: MISSING — hack a {'/'.join(src)} terminal first")
        # Summary
        missing_tools = [t for t in tools_needed if t not in self.tools]
        if missing_tools:
            self._sys("  Missing tools summary:")
            for t in missing_tools:
                mod = next((m for m, tl in MODULE_TO_TOOL.items() if tl == t), None)
                hint = f" (craft {mod} module)" if mod else ""
                self._sys(f"    ✗ {t}{hint}")
        else:
            self._sys("  All required tools present. Ready to hack.")
        self._advance_turn()

    def _step_difficulty(self, delta: int):
        idx = DIFFICULTY_ORDER.index(self.difficulty)
        idx = max(0, min(len(DIFFICULTY_ORDER) - 1, idx + delta))
        self._set_difficulty(DIFFICULTY_ORDER[idx])

    def _set_difficulty(self, level: str):
        if level not in DIFFICULTY_ORDER:
            self._sys("Difficulty must be easy, normal, hard, or nightmare.")
            return
        self.difficulty = level
        self._gm(f"Difficulty adjusted to {level}. Tell me if you want it easier or harder.")

    def _coins_text(self, cp: int) -> str:
        cp = max(0, int(cp))
        pp, rem = divmod(cp, 1000)
        gp, rem = divmod(rem, 100)
        sp, cpv = divmod(rem, 10)
        parts = []
        if pp:
            parts.append(f"{pp}pp")
        if gp:
            parts.append(f"{gp}gp")
        if sp:
            parts.append(f"{sp}sp")
        if cpv or not parts:
            parts.append(f"{cpv}cp")
        return " ".join(parts)

    def _item_weight(self, item) -> float:
        return float(getattr(item, "weight", 1.0) or 1.0)

    @staticmethod
    def _is_jewelry_slot(slot: str) -> bool:
        return slot == "amulet" or slot.startswith("ring")

    def _is_jewelry_item(self, it) -> bool:
        slot = str(getattr(it, "slot", "none") or "none")
        kind = str(getattr(it, "kind", "") or "")
        return kind == "jewelry" or slot in ("ring", "amulet") or self._is_jewelry_slot(slot)

    def _core_slots(self) -> tuple[str, ...]:
        return ("weapon", "armor_head", "armor_chest", "armor_legs", "shield")

    def _sight_bonus(self) -> int:
        return sum(int(getattr(it, "sight_bonus", 0) or 0)
                   for it in self.equipped.values() if it)

    def _vision_radius(self) -> int:
        return max(8, min(44, 16 + self._sight_bonus()))

    def _carry_bonus(self) -> float:
        """Extra carry capacity from worn backpack + socketed amethyst gems."""
        bonus = 0.0
        bp = self.equipped.get("back")
        if bp:
            bonus += float(getattr(bp, "carry_bonus", 0.0) or 0.0)
        for it in self.equipped.values():
            if it:
                for sock in (getattr(it, "sockets", []) or []):
                    bonus += float(sock.get("carry_bonus", 0.0) or 0.0)
        return bonus

    def _effective_max_weight(self) -> float:
        return self.max_weight + self._carry_bonus()

    def _backpack_capacity(self) -> int:
        bp = self.equipped.get("back")
        if not bp:
            return 0
        base = int(getattr(bp, "bag_capacity", 0) or 0)
        socket_bonus = sum(int(s.get("bag_slots", 0)) for s in (getattr(bp, "sockets", []) or []))
        return base + socket_bonus

    def _carry_weight(self) -> float:
        inv = sum(self._item_weight(it) for it in self.b.inventory)
        bp  = sum(self._item_weight(it) for it in self.backpack_inv)
        eq  = sum(self._item_weight(it) for it in self.equipped.values() if it)
        return inv + bp + eq

    def _combat_power(self) -> tuple[int, int]:
        atk = sum(int(getattr(it, "attack", 0) or 0) for it in self.equipped.values() if it)
        dfn = sum(int(getattr(it, "defense", 0) or 0) for it in self.equipped.values() if it)
        for fx in self.active_effects:
            atk += int(fx.get("attack", 0))
            dfn += int(fx.get("defense", 0))
        return atk, dfn

    def _effect_regen(self) -> int:
        return sum(int(fx.get("regen", 0)) for fx in self.active_effects)

    def _advance_turn(self):
        self.turn_count += 1

        regen = self._effect_regen()
        if regen > 0 and self.hp < self.max_hp:
            old = self.hp
            self.hp = min(self.max_hp, self.hp + regen)
            if self.turn_count % 3 == 0 and self.hp > old:
                self._sys(f"Potion effects restore {self.hp - old} HP.")

        expired = []
        for fx in self.active_effects:
            if fx.get("duration", 0) <= 0:
                continue
            fx["duration"] -= 1
            if fx["duration"] <= 0:
                expired.append(fx.get("name", "effect"))
        if expired:
            self.active_effects = [fx for fx in self.active_effects if fx.get("duration", 0) > 0]
            self._sys("Effects faded: " + ", ".join(expired) + ".")

        if self.turn_count >= self.next_restock_turn:
            self._restock_shops()
            self.next_restock_turn = self.turn_count + random.randint(*SHOP_RESTOCK_INTERVAL)

        self._update_enemies()

    def _update_enemies(self):
        b = self.b
        px, py = b.px, b.py
        visible = b.visible
        heat_lv = self._heat_level()
        stealth_cut = self._stealth_bonus() if self.stealth_mode else 0

        for ent in list(b.entities.values()):
            if not ent.hostile:
                continue

            dist = abs(ent.x - px) + abs(ent.y - py)
            eff_sight = max(1, ent.sight_radius + _HEAT_SIGHT_BONUS[heat_lv] - stealth_cut)

            if (ent.x, ent.y) in visible and dist <= eff_sight:
                if not ent.alerted:
                    ent.alerted = True
                    self._raise_heat(1.0)
                    if self.stealth_mode:
                        self.stealth_mode = False
                        self._sys(f"The {ent.name} spots you! Stealth broken.")
                    else:
                        self._sys(f"The {ent.name} spots you!")

            if not ent.alerted:
                self._patrol_move(ent)
                continue

            # Infiltrator passive: alerted guards that can't see you have a
            # 12% per-turn chance to give up and return to patrol.
            if (self.archetype == "infiltrator"
                    and ((ent.x, ent.y) not in visible or dist > eff_sight)
                    and random.random() < 0.12):
                ent.alerted = False

            if dist <= 1:
                self._enemy_attack(ent)
            else:
                self._enemy_move_toward(ent, px, py)

        # Passive heat decay: -0.1 per 20 turns
        if self.turn_count % 20 == 0 and self.heat > 0:
            self._lower_heat(0.1)

        # Reinforcement spawns at heat 3+
        intvl = _HEAT_SPAWN_INTVL[heat_lv]
        if heat_lv >= 3 and (self.turn_count - self._last_heat_spawn) >= intvl:
            self._spawn_reinforcement()
            self._last_heat_spawn = self.turn_count

    def _patrol_move(self, ent):
        """Move a non-alerted guard slowly along a patrol route."""
        if not getattr(ent, "patrol", None):
            # Generate a simple 2-point patrol anchored to spawn position
            ox, oy = ent.x, ent.y
            candidates = []
            for dx, dy in [(6, 0), (-6, 0), (0, 5), (0, -5), (4, 3), (-4, 3)]:
                nx, ny = ox + dx, oy + dy
                if self.b.get(nx, ny) == ".":
                    candidates.append((nx, ny))
            random.shuffle(candidates)
            ent.patrol = candidates[:2] or [(ox, oy)]
            ent.patrol_idx = 0

        # Guards patrol at half speed (move every 2 turns)
        if self.turn_count % 2 != 0:
            return

        tx, ty = ent.patrol[ent.patrol_idx % len(ent.patrol)]
        if abs(ent.x - tx) + abs(ent.y - ty) < 2:
            ent.patrol_idx = (ent.patrol_idx + 1) % len(ent.patrol)
            return
        self._enemy_move_toward(ent, tx, ty)

    def _spawn_reinforcement(self):
        """Spawn an alerted guard at a position 10–20 tiles from the player."""
        b = self.b
        px, py = b.px, b.py
        candidates = []
        for dy in range(-20, 21):
            for dx in range(-20, 21):
                x, y = px + dx, py + dy
                dist = abs(dx) + abs(dy)
                if 10 <= dist <= 20 and b.get(x, y) == "." and not b.entity_at(x, y):
                    candidates.append((x, y))
        if not candidates:
            return
        x, y = random.choice(candidates)
        heat_lv = self._heat_level()
        pool = _REINFORCE_NAMES.get(heat_lv, _REINFORCE_NAMES[3])
        name = random.choice(pool)
        eid = b._id("reinforce")
        from board import Entity
        ent = Entity(id=eid, x=x, y=y, name=name, char=name[0].upper(),
                     hostile=True, sight_radius=8, alerted=True)
        ent.hp = 26; ent.max_hp = 26
        b.entities[eid] = ent
        self._sys(f"[HEAT {heat_lv}] {name.title()} dispatched to your position!")

    def _enemy_attack(self, ent):
        _, enemy_atk, _ = self._enemy_profile(ent)
        _, p_def = self._combat_power()
        damage = max(1, enemy_atk + random.randint(0, 3) - p_def)
        self.hp -= damage
        self._sys(
            f"{ent.name} strikes you for {damage} damage! "
            f"(HP {max(0, self.hp)}/{self.max_hp})"
        )
        if self.hp <= 0:
            loss = max(25, self.wallet_cp // 5)
            self.wallet_cp = max(0, self.wallet_cp - loss)
            self.hp = max(10, self.max_hp // 3)
            self._gm(
                f"{ent.name} beats you down. You crawl away, losing "
                f"{self._coins_text(loss)}."
            )

    def _enemy_move_toward(self, ent, px, py):
        b = self.b
        dx = px - ent.x
        dy = py - ent.y

        # Primary axis is whichever has the larger gap; secondary is the other.
        if abs(dx) >= abs(dy):
            steps = [(1 if dx > 0 else -1, 0), (0, 1 if dy > 0 else -1 if dy < 0 else 0)]
        else:
            steps = [(0, 1 if dy > 0 else -1), (1 if dx > 0 else -1 if dx < 0 else 0, 0)]

        for sdx, sdy in steps:
            if sdx == 0 and sdy == 0:
                continue
            nx, ny = ent.x + sdx, ent.y + sdy
            # Don't walk into the player's cell (attack handled separately).
            if (nx, ny) == (px, py):
                continue
            if not b.is_blocked(nx, ny):
                ent.x, ent.y = nx, ny
                break

    # ===================================================================
    #  ranged combat
    # ===================================================================
    def _ranged_weapon(self):
        w = self.equipped.get("weapon")
        return w if w and getattr(w, "range", 0) > 0 else None

    def _effective_shoot_range(self, weapon) -> int:
        return (getattr(weapon, "range", 0) + getattr(weapon, "range_bonus", 0)
                + self._ranged_skill_range_bonus())

    # ── Heat helpers ────────────────────────────────────────────────────────

    def _heat_level(self) -> int:
        return min(5, int(self.heat))

    def _raise_heat(self, amount: float, reason: str = ""):
        if amount <= 0:
            return
        old_lv = self._heat_level()
        self.heat = min(5.0, self.heat + amount)
        new_lv = self._heat_level()
        if new_lv > old_lv:
            self._sys(_HEAT_ESCALATION_MSG[new_lv])

    def _lower_heat(self, amount: float):
        if amount <= 0:
            return
        old_lv = self._heat_level()
        self.heat = max(0.0, self.heat - amount)
        new_lv = self._heat_level()
        if new_lv < old_lv:
            self._sys(f"[HEAT {new_lv}: {_HEAT_LABELS[new_lv]}] Situation cooling.")

    # ── Stealth helpers ──────────────────────────────────────────────────────

    def _stealth_bonus(self) -> int:
        """Tiles subtracted from enemy detection radius when sneaking."""
        base = 3 + self.skills.get("evasion", 0) // 4
        return base + (2 if self.archetype == "infiltrator" else 0)

    def _hack_gem_bonus(self) -> int:
        """Total hack_bonus from gems socketed into any equipped item."""
        total = 0
        for it in self.equipped.values():
            if it:
                for sock in (getattr(it, "sockets", []) or []):
                    total += int(sock.get("hack_bonus", 0) or 0)
        return total

    def _skill_level(self, name: str) -> int:
        hack_names = ("recon", "exploit", "creds", "lateral", "persist", "evasion", "social")
        gem_bonus = self._hack_gem_bonus() if name in hack_names or name == "tech" else 0
        if name == "tech":
            base = sum(self.skills.get(n, 0) for n in hack_names) // len(hack_names)
            return base + gem_bonus
        if name in ("melee", "ranged"):
            return self.skills.get(name, 0) // 3
        if name in hack_names:
            return self.skills.get(name, 0) + gem_bonus
        return self.skills.get(name, 0)

    def _melee_skill_atk_bonus(self) -> int:
        return self._skill_level("melee") // 2

    def _ranged_skill_range_bonus(self) -> int:
        return self._skill_level("ranged") // 3

    def _ensure_skill_reqs(self, term: dict):
        """Lazily generate per-skill requirements for a terminal (stored on the dict)."""
        if "skill_reqs" in term:
            return
        control = term.get("control", "doors")
        tier = int(term.get("tier", 1))
        level = getattr(self.b, "level", 0)
        bases = _CTRL_SKILL_BASE.get(control, (1, 1, 1, 1, 1, 1))
        depth_bonus = level // 3
        scale = 1 + (tier - 1) * 0.5
        names = ("recon", "exploit", "creds", "lateral", "persist", "evasion")
        reqs = {}
        for name, base in zip(names, bases):
            reqs[name] = max(0, int((base + depth_bonus) * scale))
        reqs["social"] = max(0, tier - 1)  # social always low
        term["skill_reqs"] = reqs

    def _hack_skill_req(self, term: dict, mode: str) -> tuple[str, int, int]:
        """Return (skill_name, required_level, player_level) for the given mode."""
        self._ensure_skill_reqs(term)
        skill_name = _MODE_SKILL.get(mode, "exploit")
        req = term["skill_reqs"].get(skill_name, 0)
        # tech_override can lower overall requirement
        if "tech_override" in term:
            reduction = int(term["tech_override"])
            req = max(0, req - reduction)
        player_lv = self.skills.get(skill_name, 0)
        return skill_name, req, player_lv

    def _tech_required_for_terminal(self, term: dict) -> int:
        """Legacy aggregate gate — minimum recon skill to even attempt the terminal."""
        self._ensure_skill_reqs(term)
        return term["skill_reqs"].get("recon", 0)

    def _init_entity_hp(self, ent):
        if ent.hp < 0:
            hp, _, _ = self._enemy_profile(ent)
            ent.hp = hp
            ent.max_hp = hp

    def _kill_entity(self, ent, cause: str = "shot"):
        self.b.entities.pop(ent.id, None)
        self._gm(f"You {cause} {ent.name}!")
        module = self._module_for_entity(ent.name)
        if module:
            self._unlock_module(module, ent.name)
        coin = random.randint(25, 100)
        if self.archetype == "combat_specialist":
            coin += random.randint(10, 30)
        self.wallet_cp += coin
        self._sys(f"Looted {self._coins_text(coin)} from the remains.")

    def _shoot_direction(self, dx: int, dy: int):
        weapon = self._ranged_weapon()
        if weapon is None:
            self._sys("No ranged weapon equipped.")
            return
        shoot_range = self._effective_shoot_range(weapon)
        b = self.b
        target = None
        for r in range(1, shoot_range + 1):
            cx, cy = b.px + dx * r, b.py + dy * r
            if not b.in_bounds(cx, cy):
                break
            if b.get(cx, cy) in BLOCKING:
                break
            ent = b.entity_at(cx, cy)
            if ent:
                target = ent
                break

        if target is None:
            self._sys(f"Your shot vanishes into the dark (range {shoot_range}).")
            # Missed shots still cost a turn (no swift quiver benefit for misses).
            self._advance_turn()
            return

        # Damage = weapon attack + gem attack bonuses + random variance.
        sock_atk = sum(int(s.get("attack", 0)) for s in (getattr(weapon, "sockets", []) or []))
        dmg = max(1, getattr(weapon, "attack", 0) + sock_atk + random.randint(0, 3))
        self._init_entity_hp(target)
        target.hp -= dmg
        dist = abs(target.x - b.px) + abs(target.y - b.py)
        self._sys(
            f"You shoot {target.name} for {dmg} damage! "
            f"(dist {dist}, HP {max(0, target.hp)}/{target.max_hp})"
        )
        target.alerted = True
        self._raise_heat(0.5)
        self.stealth_mode = False  # ranged shot breaks stealth

        if target.hp <= 0:
            self.skills["ranged"] += 2 * self.xp_mult  # kill = 2 pts (hit already counted below)
            self._raise_heat(0.5)       # kill is noisier than a hit
            self._kill_entity(target, "shoot down")
            self._advance_turn()
            return

        self.skills["ranged"] += self.xp_mult  # non-kill hit = 1 pt
        is_swift = getattr(weapon, "enchantment", "") == RANGED_ENCHANTMENT_SWIFT
        if is_swift:
            self._sys("Swift Quiver — you can still move this turn!")
            # Don't advance turn: player keeps their movement action.
        else:
            self._advance_turn()

    def _drink_potion(self, needle: str):
        if not needle:
            self._sys("Usage: drink <potion name>")
            return
        it = self._find_inventory_item(needle)
        if it is None:
            self._sys("That potion is not in your inventory.")
            return
        self._drink_item(it)

    def _drink_item(self, it):
        if it.kind != "potion":
            self._sys("That item is not a potion.")
            return

        key = it.name.lower().strip()
        spec = POTION_EFFECTS.get(key)
        if not spec:
            # fallback generic potion profile
            spec = {"heal": 6, "duration": 10, "attack": 1, "defense": 0, "regen": 0}

        self.b.inventory.remove(it)
        self.hp = min(self.max_hp, self.hp + int(spec.get("heal", 0)))
        duration = int(spec.get("duration", 0))
        if duration > 0:
            self.active_effects.append({
                "name": it.name,
                "duration": duration,
                "attack": int(spec.get("attack", 0)),
                "defense": int(spec.get("defense", 0)),
                "regen": int(spec.get("regen", 0)),
            })
            self._sys(f"You drink {it.name}. Effect active for {duration} turns.")
        else:
            self._sys(f"You drink {it.name}.")
        self._advance_turn()

    def _enemy_profile(self, ent) -> tuple[int, int, int]:
        name = ent.name.lower()
        hp, atk, arm = 18, 6, 1
        if any(k in name for k in ("captain", "ogre", "wraith", "necromancer")):
            hp, atk, arm = 34, 10, 4
        elif any(k in name for k in ("guard", "mercenary", "orc", "jailer")):
            hp, atk, arm = 26, 8, 3
        elif any(k in name for k in ("wolf", "hound", "rat", "bat")):
            hp, atk, arm = 16, 7, 1

        diff_mul = {"easy": 0.85, "normal": 1.0, "hard": 1.2, "nightmare": 1.35}
        mul = diff_mul.get(self.difficulty, 1.0)
        hp = max(8, int(hp * mul))
        atk = max(3, int(atk * mul))
        arm = max(0, int(arm * mul))
        return hp, atk, arm

    def _combat_encounter(self, ent) -> bool:
        self._init_entity_hp(ent)
        max_hp, enemy_atk, enemy_arm = self._enemy_profile(ent)
        # Carry over any prior ranged damage dealt to this entity.
        enemy_hp = ent.hp
        p_atk, p_def = self._combat_power()
        base_player_atk = 3 + p_atk + self._melee_skill_atk_bonus() + (2 if self.archetype == "combat_specialist" else 0)
        rounds = 0
        # Stealth first strike: +50% damage on round 1, no heat from engagement
        first_strike = self._stealth_strike
        self._stealth_strike = False
        self.stealth_mode = False  # always break stealth on combat
        if first_strike:
            self._sys(f"Ambush! You strike {ent.name} from the shadows (+50% damage).")
        else:
            self._raise_heat(1.0)
            ent.alerted = True
        self._sys(f"Combat begins with {ent.name}! (enemy HP {enemy_hp}/{ent.max_hp})")
        while enemy_hp > 0 and self.hp > 0 and rounds < 10:
            rounds += 1
            strike_bonus = int(base_player_atk * 0.5) if (first_strike and rounds == 1) else 0
            outgoing = max(1, base_player_atk + strike_bonus + random.randint(0, 4) - enemy_arm)
            enemy_hp -= outgoing
            tag = " [AMBUSH]" if strike_bonus else ""
            self._sys(f"Round {rounds}: you hit {ent.name} for {outgoing}{tag}.")
            if enemy_hp <= 0:
                break
            incoming_raw = enemy_atk + random.randint(0, 4)
            incoming = max(1, incoming_raw - p_def)
            self.hp -= incoming
            self._raise_heat(0.3)
            self._sys(f"{ent.name} hits you for {incoming}. (HP {max(0, self.hp)}/{self.max_hp})")

        ent.hp = max(0, enemy_hp)

        if self.hp <= 0:
            loss = max(25, self.wallet_cp // 5)
            self.wallet_cp = max(0, self.wallet_cp - loss)
            self.hp = max(10, self.max_hp // 3)
            self._gm(f"You are battered and forced back. You lose {self._coins_text(loss)} in the chaos.")
            return False

        if enemy_hp > 0:
            self._sys(f"{ent.name} retreats into the shadows.")
            return False
        self._sys(f"{ent.name} is defeated.")
        self.skills["melee"] += self.xp_mult
        return True

    def _find_inventory_item(self, needle: str):
        n = needle.lower().strip()
        for it in self.b.inventory:
            if n in it.name.lower():
                return it
        for it in self.backpack_inv:
            if n in it.name.lower():
                return it
        return None

    _INV_KIND_ORDER = ("weapon", "armor", "backpack", "potion", "module", "material")
    _SHOP_KIND_ORDER = ("weapon", "armor", "backpack", "jewelry", "potion", "module", "material", "item")
    _SHOP_KIND_LABELS = {
        "weapon": "WEAPONS", "armor": "ARMOR", "backpack": "BACKPACKS",
        "jewelry": "JEWELRY", "potion": "POTIONS", "module": "MODULES",
        "material": "MATERIALS", "item": "MISC",
    }
    _CRAFT_KIND_ORDER = ("item", "weapon", "armor", "potion", "jewelry", "module")
    _CRAFT_KIND_LABELS = {
        "item": "MISC", "weapon": "WEAPONS", "armor": "ARMOR",
        "potion": "POTIONS", "jewelry": "JEWELRY", "module": "MODULES",
    }

    def _inventory_entries(self) -> list[dict]:
        entries: list[dict] = []
        if self.inv_tab == "modules":
            for it in self.b.inventory:
                if it.kind == "module":
                    entries.append({"origin": "bag", "slot": "none", "item": it})
            return entries
        if self.inv_tab == "jewelry":
            for slot in ("amulet",) + RING_SLOTS:
                it = self.equipped.get(slot)
                if it is not None:
                    entries.append({"origin": "equipped", "slot": slot, "item": it})
            for it in self.b.inventory:
                if self._is_jewelry_item(it):
                    entries.append({"origin": "bag", "slot": getattr(it, "slot", "none"), "item": it})
            return entries

        for slot in self._core_slots():
            it = self.equipped.get(slot)
            if it is not None:
                entries.append({"origin": "equipped", "slot": slot, "item": it})
        # Back slot (backpack) is selectable as an equipped item
        bp = self.equipped.get("back")
        if bp is not None:
            entries.append({"origin": "equipped", "slot": "back", "item": bp})
        bag = [it for it in self.b.inventory if not self._is_jewelry_item(it)]
        for kind in self._INV_KIND_ORDER:
            for it in bag:
                if it.kind == kind:
                    entries.append({"origin": "bag", "slot": getattr(it, "slot", "none"), "item": it})
        for it in bag:
            if it.kind not in self._INV_KIND_ORDER:
                entries.append({"origin": "bag", "slot": getattr(it, "slot", "none"), "item": it})
        # Backpack sub-inventory items are also selectable (for inspect/drop)
        for it in self.backpack_inv:
            entries.append({"origin": "backpack", "slot": getattr(it, "slot", "none"), "item": it})
        return entries

    def _current_inventory_entry(self):
        entries = self._inventory_entries()
        if not entries:
            self.inv_cursor = 0
            return None
        self.inv_cursor = max(0, min(self.inv_cursor, len(entries) - 1))
        return entries[self.inv_cursor]

    def _handle_inventory_overlay_key(self, ch) -> bool:
        entries = self._inventory_entries()
        if ch in (27, ord("q"), ord("Q"), ord("i"), ord("I")):
            self.overlay = None
            return True
        if ch == 9:  # Tab cycles through inventory tabs
            _tabs = ("gear", "jewelry", "modules")
            self.inv_tab = _tabs[(_tabs.index(self.inv_tab) + 1) % len(_tabs)]
            self.inv_cursor = 0
            return True
        if ch in (curses.KEY_UP, ord("k"), ord("K")):
            if entries:
                self.inv_cursor = max(0, self.inv_cursor - 1)
            return True
        if ch in (curses.KEY_DOWN, ord("j"), ord("J")):
            if entries:
                self.inv_cursor = min(len(entries) - 1, self.inv_cursor + 1)
            return True

        entry = self._current_inventory_entry()
        if entry is None:
            return True
        item = entry["item"]
        origin = entry["origin"]

        if ch in (10, 13, ord("x"), ord("X")):
            self._inspect_item(item)
            return True
        if ch in (ord("e"), ord("E")):
            if origin == "bag":
                self._equip_item(item)
            else:
                self._unequip_slot(entry["slot"])
            self._advance_turn()
            return True
        if ch in (ord("u"), ord("U")):
            if origin == "bag":
                self._use_item(item)
            else:
                self._sys("Unequip this item before using it.")
            return True
        return True

    def _equip_by_name(self, needle: str):
        if not needle:
            self._sys("Usage: equip <item name>")
            return
        it = self._find_inventory_item(needle)
        if it is None:
            self._sys("That item is not in your inventory.")
            return
        self._equip_item(it)

    def _equip_item(self, it):
        slot = getattr(it, "slot", "none")
        if slot == "ring":
            target = next((s for s in RING_SLOTS if self.equipped.get(s) is None), None)
            if target is None:
                self._sys("All ring slots are occupied. Unequip a ring slot first.")
                return
            self.b.inventory.remove(it)
            self.equipped[target] = it
            self._sys(f"Equipped {it.name} in {target}.")
            self.b.compute_visible(radius=self._vision_radius())
            return
        if slot == "back":
            new_cap = int(getattr(it, "bag_capacity", 0) or 0)
            if len(self.backpack_inv) > new_cap:
                self._sys(
                    f"Cannot equip {it.name}: it holds {new_cap} items but your "
                    f"backpack has {len(self.backpack_inv)}. Empty it first."
                )
                return
            old_bp = self.equipped.get("back")
            self.b.inventory.remove(it)
            if old_bp is not None:
                self.b.inventory.append(old_bp)
            self.equipped["back"] = it
            carry = float(getattr(it, "carry_bonus", 0.0) or 0.0)
            self._sys(
                f"Equipped {it.name} (back) — {new_cap} slots, +{carry:.0f} carry. "
                f"Contents transferred ({len(self.backpack_inv)} items)."
            )
            self.b.compute_visible(radius=self._vision_radius())
            return
        if slot not in self.equipped:
            self._sys("That item cannot be equipped.")
            return
        current = self.equipped.get(slot)
        if current is it:
            self._sys(f"{it.name} is already equipped.")
            return
        self.b.inventory.remove(it)
        if current is not None:
            self.b.inventory.append(current)
        self.equipped[slot] = it
        self._sys(f"Equipped {it.name} in {slot}.")
        self.b.compute_visible(radius=self._vision_radius())

    def _use_item(self, it):
        if getattr(it, "kind", "") == "potion":
            self._drink_item(it)
            return
        if getattr(it, "kind", "") == "module":
            low = it.name.lower()
            mod_key = next((k for k in MODULE_TO_TOOL if k in low), None)
            if mod_key:
                if mod_key in self.modules:
                    self._sys(f"{mod_key} is already installed.")
                else:
                    self._unlock_module(mod_key, it.name)
                    self.b.inventory.remove(it)
                    self.inv_cursor = max(0, self.inv_cursor - 1)
            else:
                self._sys(f"Cannot identify module in '{it.name}'.")
            return
        self._sys("That item has no direct use right now.")

    def _inspect_item(self, it):
        if it is None:
            return
        lines = [f"Inspect: {it.name}"]
        if getattr(it, "desc", ""):
            lines.append(f"  {it.desc}")
        if getattr(it, "kind", "") == "clue":
            lines.append("  Clue text:")
            lines.append(f"  '{it.desc or it.name}'")
        if getattr(it, "attack", 0) or getattr(it, "defense", 0):
            lines.append(f"  Stats: ATK {it.attack}  DEF {it.defense}")
            lines.append(f"  Quality: {getattr(it, 'quality', 'common')}  Rarity: {getattr(it, 'rarity', 'common')}")
        if getattr(it, "range", 0):
            total_range = getattr(it, "range", 0) + getattr(it, "range_bonus", 0)
            bonus_txt = f" (+{it.range_bonus} gems)" if getattr(it, "range_bonus", 0) else ""
            lines.append(f"  Range: {total_range}{bonus_txt}")
            if getattr(it, "enchantment", "") == RANGED_ENCHANTMENT_SWIFT:
                lines.append("  [Swift Quiver: shoot + move in the same turn]")
        if getattr(it, "sight_bonus", 0):
            lines.append(f"  Sight bonus: +{int(getattr(it, 'sight_bonus', 0))}")
        if getattr(it, "material", ""):
            lines.append(f"  Material: {it.material}")
        socks = getattr(it, "sockets", []) or []
        if socks:
            gems = ", ".join(s.get("gem", "gem") for s in socks)
            lines.append(f"  Sockets: {len(socks)} ({gems})")
        if getattr(it, "enchantment", ""):
            lines.append(f"  Enchantment: {it.enchantment}")
        cb = float(getattr(it, "carry_bonus", 0.0) or 0.0)
        cap = int(getattr(it, "bag_capacity", 0) or 0)
        if cb:
            lines.append(f"  Carry bonus: +{cb:.0f}")
        if cap:
            lines.append(f"  Bag slots: {cap}")
        lines.append(f"  Weight: {getattr(it, 'weight', 1.0):.1f}")
        lines.append(f"  Value: {self._coins_text(getattr(it, 'value_cp', 0))}")
        if getattr(it, "kind", "") == "potion":
            spec = POTION_EFFECTS.get(it.name.lower(), {"heal": 0, "duration": 0, "attack": 0, "defense": 0, "regen": 0})
            lines.append(
                f"  Potion effect: heal {spec.get('heal', 0)}, atk+{spec.get('attack', 0)}, "
                f"def+{spec.get('defense', 0)}, regen {spec.get('regen', 0)}, {spec.get('duration', 0)} turns"
            )
        for ln in lines:
            self._sys(ln)

    def _unequip_slot(self, slot: str):
        alias = {
            "head": "armor_head", "chest": "armor_chest", "legs": "armor_legs",
            "armor": "armor_chest", "shield": "shield", "weapon": "weapon",
            "amulet": "amulet", "backpack": "back", "pack": "back", "satchel": "back",
        }
        slot = alias.get(slot, slot)
        if slot == "back":
            bp = self.equipped.get("back")
            if bp is None:
                self._sys("No backpack equipped.")
                return
            if self.backpack_inv:
                free = BASE_INV_SLOTS - len(self.b.inventory)
                if free < len(self.backpack_inv):
                    self._sys(
                        f"Cannot unequip: backpack has {len(self.backpack_inv)} items but "
                        f"main inventory only has {free} free slot(s). Empty the backpack first."
                    )
                    return
                self.b.inventory.extend(self.backpack_inv)
                self.backpack_inv.clear()
            self.equipped["back"] = None
            self.b.inventory.append(bp)
            self._sys(f"Unequipped {bp.name}. Contents moved to main inventory.")
            self.b.compute_visible(radius=self._vision_radius())
            return
        if slot == "ring":
            slot = next((s for s in reversed(RING_SLOTS) if self.equipped.get(s) is not None), "ring")
        m = re.fullmatch(r"ring\s*(\d+)", slot)
        if m:
            slot = f"ring_{max(1, min(RING_SLOT_COUNT, int(m.group(1))))}"
        if slot not in self.equipped:
            self._sys("Unknown slot. Try weapon, head, chest, legs, shield, amulet, back, or ring1..ring10.")
            return
        it = self.equipped.get(slot)
        if it is None:
            self._sys(f"Nothing equipped in {slot}.")
            return
        self.equipped[slot] = None
        self.b.inventory.append(it)
        self._sys(f"Unequipped {it.name}.")
        self.b.compute_visible(radius=self._vision_radius())

    def _nearby_shop(self):
        choices = [(self.b.px, self.b.py)]
        choices.extend((self.b.px + dx, self.b.py + dy) for dx, dy in DIRS.values())
        for x, y in choices:
            spec = self.b.specials.get((x, y), {})
            if spec.get("kind") == "shop":
                return (x, y), spec
        return None, None

    def _show_shop(self):
        _, shop = self._nearby_shop()
        if not shop:
            self._sys("No shop nearby. Stand on % or next to it.")
            return
        self.shop_mode = "stock"
        self.shop_cursor = 0
        self.overlay = "shop"

    def _shop_stock_entries(self) -> list[dict]:
        _, shop = self._nearby_shop()
        if not shop:
            return []
        return list(shop.get("stock", []))

    def _shop_bag_entries(self) -> list:
        return list(self.b.inventory)

    def _shop_display_order(self) -> list[int]:
        """Entry indices in grouped display order for the active shop tab."""
        is_buy = (self.shop_mode == "stock")
        entries = self._shop_stock_entries() if is_buy else self._shop_bag_entries()
        from collections import defaultdict
        groups: dict[str, list[int]] = defaultdict(list)
        for i, e in enumerate(entries):
            k = e.get("kind", "item") if is_buy else getattr(e, "kind", "item")
            if k not in self._SHOP_KIND_ORDER:
                k = "item"
            groups[k].append(i)
        order: list[int] = []
        for kind in self._SHOP_KIND_ORDER:
            order.extend(groups.get(kind, []))
        return order

    def _handle_shop_overlay_key(self, ch) -> bool:
        if ch in (27, ord("q"), ord("Q"), ord("s"), ord("S")):
            self.overlay = None
            return True

        if ch == 9:  # Tab toggles stock/bag list focus
            self.shop_mode = "bag" if self.shop_mode == "stock" else "stock"
            self.shop_cursor = 0
            self.shop_scroll = 0
            return True

        display_order = self._shop_display_order()
        n = len(display_order)

        if ch in (curses.KEY_UP, ord("k"), ord("K")):
            if n:
                self.shop_cursor = max(0, self.shop_cursor - 1)
            return True
        if ch in (curses.KEY_DOWN, ord("j"), ord("J")):
            if n:
                self.shop_cursor = min(n - 1, self.shop_cursor + 1)
            return True
        if not n:
            return True

        self.shop_cursor = max(0, min(self.shop_cursor, n - 1))
        entry_idx = display_order[self.shop_cursor]
        is_buy = (self.shop_mode == "stock")
        entries = self._shop_stock_entries() if is_buy else self._shop_bag_entries()

        if ch in (10, 13, ord("b"), ord("B")):
            if is_buy:
                self._buy_shop_item(str(entry_idx + 1))
            else:
                self._sell_shop_item(entries[entry_idx].name)
            return True
        if ch in (ord("x"), ord("X"), ord("i"), ord("I")):
            if is_buy:
                self._inspect_shop_entry(entries[entry_idx])
            else:
                self._inspect_item(entries[entry_idx])
            return True
        return True

    def _inspect_shop_entry(self, entry: dict):
        lines = [f"Shop item: {entry.get('name', 'item')}"]
        if entry.get("desc"):
            lines.append(f"  {entry.get('desc')}")
        lines.append(f"  Kind: {entry.get('kind', 'item')}  Slot: {entry.get('slot', 'none')}")
        lines.append(f"  Stats: ATK {entry.get('attack', 0)}  DEF {entry.get('defense', 0)}")
        if int(entry.get("range", 0) or 0):
            lines.append(f"  Shoot range: {int(entry.get('range', 0) or 0)}")
        if int(entry.get("sight_bonus", 0) or 0):
            lines.append(f"  Sight bonus: +{int(entry.get('sight_bonus', 0) or 0)}")
        if entry.get("enchantment"):
            lines.append(f"  Enchantment: {entry.get('enchantment')}")
        lines.append(f"  Weight: {float(entry.get('weight', 1.0)):.1f}")
        lines.append(f"  Price: {self._coins_text(int(entry.get('value_cp', 0) or 0))}")
        for ln in lines:
            self._sys(ln)

    def _shop_entry_from_item(self, it) -> dict:
        return {
            "char": getattr(it, "char", "$"),
            "name": getattr(it, "name", "item"),
            "desc": getattr(it, "desc", ""),
            "kind": getattr(it, "kind", "item"),
            "slot": getattr(it, "slot", "none"),
            "attack": int(getattr(it, "attack", 0) or 0),
            "defense": int(getattr(it, "defense", 0) or 0),
            "quality": getattr(it, "quality", "common"),
            "rarity": getattr(it, "rarity", "common"),
            "enchantment": getattr(it, "enchantment", ""),
            "sight_bonus": int(getattr(it, "sight_bonus", 0) or 0),
            "weight": float(getattr(it, "weight", 1.0) or 1.0),
            "value_cp": int(getattr(it, "value_cp", 80) or 80),
            "range": int(getattr(it, "range", 0) or 0),
        }

    def _sell_shop_item(self, needle: str):
        _, shop = self._nearby_shop()
        if not shop:
            self._sys("No shop nearby. Stand on % or next to it.")
            return
        if not needle:
            self._sys("Use: sell <item name>")
            return
        it = self._find_inventory_item(needle)
        if it is None:
            self._sys("That item is not in your inventory.")
            return
        if it.kind in ("clue", "key"):
            self._sys("The quartermaster refuses to buy mission-critical items.")
            return

        value = int(getattr(it, "value_cp", 80) or 80)
        payout = max(1, int(value * 0.6))
        self.b.inventory.remove(it)
        self.wallet_cp += payout
        stock = shop.setdefault("stock", [])
        sold = self._shop_entry_from_item(it)
        sold["value_cp"] = max(1, int(value * 0.85))
        stock.append(sold)
        self._sys(f"Sold {it.name} for {self._coins_text(payout)}.")
        self._advance_turn()

    def _generate_shop_entry(self, level_num: int) -> dict:
        rarity_pool = ["common", "common", "uncommon", "rare", "epic"]
        rarity = random.choice(rarity_pool[min(level_num, len(rarity_pool) - 1):] + rarity_pool[:3])
        q_pool = ["worn", "sturdy", "fine", "masterwork"]
        quality = random.choice(q_pool[: min(4, 2 + level_num)])
        tier = {
            "common": 1.0, "uncommon": 1.3, "rare": 1.8, "epic": 2.4,
        }.get(rarity, 1.0) * {"worn": 0.8, "sturdy": 1.0, "fine": 1.25, "masterwork": 1.5}.get(quality, 1.0)

        pick = random.random()
        if pick < 0.3:
            melee = ["arming sword", "war axe", "mace", "spear"]
            ranged = ["longbow", "crossbow", "hand crossbow", "slingshot", "shortbow"]
            name = random.choice(melee + ranged)
            base_range = RANGED_WEAPON_RANGE.get(name, 0)
            atk = max(2, int(random.randint(4, 8) * tier))
            swift = (base_range > 0 and rarity in ("epic", "legendary")
                     and random.random() < 0.35)
            ench = RANGED_ENCHANTMENT_SWIFT if swift else ""
            desc = f"{quality} {rarity} {name}"
            if base_range:
                desc += f", range {base_range}"
            if ench:
                desc += f" [{ench}]"
            return {
                "char": "$", "name": name, "desc": desc,
                "kind": "weapon", "slot": "weapon", "attack": atk, "defense": 0,
                "quality": quality, "rarity": rarity, "enchantment": ench, "weight": 3.0,
                "value_cp": int(220 * tier + base_range * 8),
                "range": base_range,
            }
        if pick < 0.58:
            armors = [
                ("iron helm", "armor_head", 3, 1.6),
                ("chain hauberk", "armor_chest", 7, 6.2),
                ("plate cuirass", "armor_chest", 10, 8.5),
                ("mail chausses", "armor_legs", 5, 4.8),
                ("heater shield", "shield", 6, 5.0),
            ]
            nm, slot, dv, wt = random.choice(armors)
            return {
                "char": "$", "name": nm, "desc": f"{quality} {rarity} {nm}",
                "kind": "armor", "slot": slot, "attack": 0, "defense": max(1, int(dv * tier)),
                "quality": quality, "rarity": rarity, "enchantment": "", "weight": wt,
                "value_cp": int(260 * tier),
            }
        if pick < 0.78:
            potion = random.choice(["healing draught", "night-sight tonic", "potion of vigor"])
            return {
                "char": "*", "name": potion, "desc": "alchemical tonic",
                "kind": "potion", "slot": "none", "attack": 0, "defense": 0,
                "quality": "fine", "rarity": "uncommon", "enchantment": "",
                "sight_bonus": 0, "weight": 0.4, "value_cp": random.randint(120, 200),
            }
        if pick < 0.9:
            rarity = random.choice(["uncommon", "rare", "epic"])
            quality = random.choice(["sturdy", "fine", "masterwork"])
            tier = {
                "uncommon": 1.2, "rare": 1.6, "epic": 2.2,
            }.get(rarity, 1.0) * {"sturdy": 1.0, "fine": 1.2, "masterwork": 1.45}.get(quality, 1.0)
            if random.random() < 0.75:
                base = random.choice(["moon ring", "sunstone ring", "obsidian ring", "storm ring"])
                slot = "ring"
                sight = max(1, int(random.randint(1, 3) * tier))
            else:
                base = random.choice(["amulet of dawn", "pendant of watchfires", "seer's torque"])
                slot = "amulet"
                sight = max(2, int(random.randint(2, 4) * tier))
            return {
                "char": "$", "name": base, "desc": f"{quality} {rarity} jewelry humming with ward-light",
                "kind": "jewelry", "slot": slot, "attack": 0, "defense": 0,
                "quality": quality, "rarity": rarity, "enchantment": "warded",
                "sight_bonus": sight, "weight": 0.2, "value_cp": int(180 * tier + sight * 40),
            }
        module = random.choice(list(MODULE_TO_TOOL.keys()))
        return {
            "char": "$", "name": f"{module} module", "desc": f"unlocks {MODULE_TO_TOOL[module]}",
            "kind": "module", "module": module, "slot": "none", "attack": 0, "defense": 0,
            "quality": "fine", "rarity": "rare", "enchantment": "", "weight": 0.2,
            "value_cp": random.randint(300, 620),
        }

    def _restock_shops(self):
        for spec in self.b.specials.values():
            if spec.get("kind") != "shop":
                continue
            stock = spec.setdefault("stock", [])
            if len(stock) >= 20:
                continue
            add_n = random.randint(2, 5)
            for _ in range(add_n):
                stock.append(self._generate_shop_entry(self.b.level))
        self._sys("Quartermasters quietly refresh their stock.")

    def _buy_shop_item(self, token: str):
        _, shop = self._nearby_shop()
        if not shop:
            self._sys("No shop nearby. Stand on % or next to it.")
            return
        try:
            idx = int(token) - 1
        except ValueError:
            self._sys("Use: buy <number> (from the shop list).")
            return
        stock = shop.get("stock", [])
        if idx < 0 or idx >= len(stock):
            self._sys("No such shop item.")
            return
        entry = stock[idx]
        cost = int(entry.get("value_cp", 0))
        if self.wallet_cp < cost:
            self._sys("Not enough coin.")
            return
        if entry.get("kind") != "module":
            next_weight = self._carry_weight() + float(entry.get("weight", 1.0))
            if next_weight > self._effective_max_weight():
                self._sys("Too heavy to carry. Equip a backpack or drop gear.")
                return

        self.wallet_cp -= cost
        bought = stock.pop(idx)
        if bought.get("kind") == "module":
            module = bought.get("module", "")
            if module:
                self._unlock_module(module, shop.get("name", "shopkeeper"))
            self._sys(f"Bought module for {self._coins_text(cost)}.")
            self._advance_turn()
            return

        px, py = self.b.px, self.b.py
        under = self.b.get(px, py)
        it = self.b.add_item(
            px, py, bought.get("char", "$"), bought.get("name", "item"),
            bought.get("desc", ""), bought.get("kind", "item"),
            slot=bought.get("slot", "none"),
            attack=bought.get("attack", 0),
            defense=bought.get("defense", 0),
            quality=bought.get("quality", "common"),
            rarity=bought.get("rarity", "common"),
            enchantment=bought.get("enchantment", ""),
            sight_bonus=bought.get("sight_bonus", 0),
            weight=bought.get("weight", 1.0),
            value_cp=bought.get("value_cp", 0),
            range=bought.get("range", 0),
        )
        self.b.items.pop(it.id, None)
        self.b.setc(px, py, under)
        self.b.inventory.append(it)
        self._sys(f"Bought {it.name} for {self._coins_text(cost)}.")
        self._advance_turn()

    # ===================================================================
    #  crafting + socketing
    # ===================================================================
    def _open_craft(self):
        self.craft_tab = "recipes"
        self.craft_cursor = 0
        self.craft_scroll = 0
        self.craft_gem_step = None
        self.craft_gem_choice = None
        self.overlay = "craft"

    def _nearby_stations(self) -> set:
        b = self.b
        kinds: set = set()
        choices = [(b.px, b.py)]
        choices.extend((b.px + dx, b.py + dy) for dx, dy in DIRS.values())
        for x, y in choices:
            sp = b.specials.get((x, y), {})
            if sp.get("kind") == "station":
                kinds.add(sp.get("station"))
        return kinds

    def _material_counts(self) -> dict:
        counts: dict[str, int] = {}
        for it in self.b.inventory:
            if getattr(it, "kind", "") == "material":
                m = getattr(it, "material", "") or "misc"
                counts[m] = counts.get(m, 0) + 1
        return counts

    def _recipe_status(self, recipe: dict) -> tuple[bool, str]:
        counts = self._material_counts()
        for mat, need in recipe["inputs"].items():
            if counts.get(mat, 0) < need:
                return False, "need mats"
        station = recipe.get("station")
        if station and station not in self._nearby_stations():
            return False, f"need {station}"
        return True, "ready"

    def _consume_materials(self, inputs: dict):
        for mat, need in inputs.items():
            removed = 0
            for it in list(self.b.inventory):
                if removed >= need:
                    break
                if (getattr(it, "kind", "") == "material"
                        and getattr(it, "material", "") == mat):
                    self.b.inventory.remove(it)
                    removed += 1

    def _craft_recipe(self, recipe: dict):
        ok, reason = self._recipe_status(recipe)
        if not ok:
            self._sys(f"Cannot craft {recipe['name']}: {reason}.")
            return
        res = recipe["result"]
        is_module = res.get("kind") == "module"
        if not is_module and self._carry_weight() + float(res.get("weight", 1.0)) > self._effective_max_weight():
            self._sys("Too heavy to craft that right now.")
            return
        self._consume_materials(recipe["inputs"])
        px, py = self.b.px, self.b.py
        under = self.b.get(px, py)
        it = self.b.add_item(
            px, py, res.get("char", "$"), res.get("name", "item"),
            res.get("desc", ""), res.get("kind", "item"),
            slot=res.get("slot", "none"), attack=res.get("attack", 0),
            defense=res.get("defense", 0), quality=res.get("quality", "common"),
            rarity=res.get("rarity", "common"), enchantment=res.get("enchantment", ""),
            sight_bonus=res.get("sight_bonus", 0), weight=res.get("weight", 1.0),
            value_cp=res.get("value_cp", 0), material=res.get("material", ""),
            range=res.get("range", 0))
        self.b.items.pop(it.id, None)
        self.b.setc(px, py, under)
        # Module crafting: auto-install rather than carry
        if it.kind == "module":
            low = it.name.lower()
            mod_key = next((k for k in MODULE_TO_TOOL if k in low), None)
            if mod_key:
                self._unlock_module(mod_key, f"crafted {it.name}")
                self._advance_turn()
                return
        self.b.inventory.append(it)
        self._gm(f"You craft {it.name}.")
        self._advance_turn()

    def _inspect_recipe(self, recipe: dict):
        res = recipe["result"]
        self._sys(f"Recipe: {recipe['name']}")
        inputs = ", ".join(f"{n}x {m}" for m, n in recipe["inputs"].items())
        station = f" @ {recipe['station']}" if recipe.get("station") else " (no station)"
        self._sys(f"  Needs: {inputs}{station}")
        bits = []
        if res.get("attack"):
            bits.append(f"ATK {res['attack']}")
        if res.get("defense"):
            bits.append(f"DEF {res['defense']}")
        if res.get("sight_bonus"):
            bits.append(f"sight +{res['sight_bonus']}")
        self._sys(f"  Makes: {res.get('name', 'item')} ({res.get('kind', 'item')}) "
                  + " ".join(bits))

    def _socketable_armor(self) -> list:
        items = []
        # Ranged weapon can be socketed: attack gems → damage, sight gems → range.
        rw = self._ranged_weapon()
        if rw is not None:
            items.append(("equipped", "weapon", rw))
        for slot in ("armor_head", "armor_chest", "armor_legs", "shield"):
            it = self.equipped.get(slot)
            if it is not None:
                items.append(("equipped", slot, it))
        # Equipped backpack can be socketed: amethyst → carry weight, citrine → bag slots.
        bp = self.equipped.get("back")
        if bp is not None:
            items.append(("equipped", "back", bp))
        for it in self.b.inventory:
            if getattr(it, "kind", "") == "armor":
                items.append(("bag", getattr(it, "slot", "none"), it))
            elif getattr(it, "kind", "") == "weapon" and getattr(it, "range", 0) > 0:
                items.append(("bag", "weapon", it))
            elif getattr(it, "kind", "") == "backpack":
                items.append(("bag", "back", it))
        return items

    def _available_gems(self) -> list:
        return [it for it in self.b.inventory
                if getattr(it, "kind", "") == "material"
                and getattr(it, "material", "") == "gem"]

    def _socket_gem(self, item, gem=None):
        if "anvil" not in self._nearby_stations():
            self._sys("You need an anvil nearby to socket gems.")
            return
        gems = self._available_gems()
        if not gems:
            self._sys("You have no gems to socket. Find or mine more.")
            return
        if gem is None or gem not in gems:
            gem = gems[0]
        ga = int(getattr(gem, "attack", 0) or 0)
        gd = int(getattr(gem, "defense", 0) or 0)
        gs = int(getattr(gem, "sight_bonus", 0) or 0)
        gc = float(getattr(gem, "carry_bonus", 0.0) or 0.0)
        gb = int(getattr(gem, "bag_slots", 0) or 0)
        gh = int(getattr(gem, "hack_bonus", 0) or 0)
        self.b.inventory.remove(gem)
        if not getattr(item, "sockets", None):
            item.sockets = []
        item.value_cp = int(getattr(item, "value_cp", 0) or 0) + int(getattr(gem, "value_cp", 0) or 0)

        is_backpack = getattr(item, "kind", "") == "backpack"
        is_ranged = (not is_backpack) and getattr(item, "range", 0) > 0

        if is_backpack:
            item.sockets.append({"gem": gem.name, "carry_bonus": gc, "bag_slots": gb, "hack_bonus": gh})
            parts = []
            if gc: parts.append(f"+{gc:.0f} carry")
            if gb: parts.append(f"+{gb} slots")
            if gh: parts.append(f"+{gh} hack")
            self._gm(
                f"You socket the {gem.name} into {item.name} "
                f"({', '.join(parts) or 'no bonus'}). "
                f"Backpack now {self._backpack_capacity()} slots, "
                f"+{self._carry_bonus():.0f} carry total."
            )
        elif is_ranged:
            item.attack = int(getattr(item, "attack", 0) or 0) + ga
            item.range_bonus = int(getattr(item, "range_bonus", 0) or 0) + gs
            item.sockets.append({"gem": gem.name, "attack": ga, "range": gs, "carry_bonus": gc, "hack_bonus": gh})
            parts = []
            if ga: parts.append(f"+{ga} dmg")
            if gs: parts.append(f"+{gs} range")
            if gc: parts.append(f"+{gc:.0f} carry")
            if gh: parts.append(f"+{gh} hack")
            self._gm(
                f"You socket {gem.name} into {item.name} "
                f"({', '.join(parts) or 'no bonus'}). "
                f"Range now {self._effective_shoot_range(item)}, "
                f"sockets: {len(item.sockets)}."
            )
        else:
            item.attack = int(getattr(item, "attack", 0) or 0) + ga
            item.defense = int(getattr(item, "defense", 0) or 0) + gd
            item.sight_bonus = int(getattr(item, "sight_bonus", 0) or 0) + gs
            item.sockets.append({"gem": gem.name, "attack": ga, "defense": gd, "sight": gs,
                                  "carry_bonus": gc, "hack_bonus": gh})
            parts = [f"+{ga} atk" if ga else "", f"+{gd} def" if gd else "",
                     f"+{gs} sight" if gs else "", f"+{gc:.0f} carry" if gc else "",
                     f"+{gh} hack" if gh else ""]
            self._gm(f"You socket the {gem.name} into {item.name} "
                     f"({', '.join(p for p in parts if p)}). "
                     f"It now has {len(item.sockets)} gem(s).")

        self.b.compute_visible(radius=self._vision_radius())
        self._advance_turn()

    def _open_loot_chest(self, pos):
        spec = self.b.specials.get(pos, {})
        if spec.get("kind") != "loot_chest":
            return
        self.b.specials.pop(pos, None)
        self.b.setc(pos[0], pos[1], ".")
        names = []
        for s in spec.get("loot", []):
            x, y = self._free_near(self.b.px, self.b.py)
            self.b.add_item(
                x, y, s.get("char", "$"), s.get("name", "loot"),
                s.get("desc", ""), s.get("kind", "item"),
                slot=s.get("slot", "none"), attack=s.get("attack", 0),
                defense=s.get("defense", 0), quality=s.get("quality", "common"),
                rarity=s.get("rarity", "common"), enchantment=s.get("enchantment", ""),
                sight_bonus=s.get("sight_bonus", 0), weight=s.get("weight", 1.0),
                value_cp=s.get("value_cp", 0), material=s.get("material", ""))
            names.append(s.get("name", "loot"))
        if names:
            self._gm("You pry open a loot chest: " + ", ".join(names) + ".")
        else:
            self._sys("The chest is empty.")

    def _craft_recipe_order(self) -> list[int]:
        """Recipe indices in grouped display order, optionally filtered to craftable only."""
        from collections import defaultdict
        groups: dict[str, list[int]] = defaultdict(list)
        for i, r in enumerate(CRAFT_RECIPES):
            if self.craft_filter and not self._recipe_status(r)[0]:
                continue
            k = r.get("result", {}).get("kind", "item")
            if k not in self._CRAFT_KIND_ORDER:
                k = "item"
            groups[k].append(i)
        order: list[int] = []
        for kind in self._CRAFT_KIND_ORDER:
            order.extend(groups.get(kind, []))
        return order

    def _gem_preview_lines(self, item, gem) -> list[str]:
        """Lines showing what socketing gem into item will change."""
        ga = int(getattr(gem, "attack", 0) or 0)
        gd = int(getattr(gem, "defense", 0) or 0)
        gs = int(getattr(gem, "sight_bonus", 0) or 0)
        gc = float(getattr(gem, "carry_bonus", 0.0) or 0.0)
        gb = int(getattr(gem, "bag_slots", 0) or 0)
        gh = int(getattr(gem, "hack_bonus", 0) or 0)
        n_socks = len(getattr(item, "sockets", []) or [])
        lines = [f"  Gem:  {gem.name}"]
        is_bp = getattr(item, "kind", "") == "backpack"
        is_rng = (not is_bp) and getattr(item, "range", 0) > 0
        if is_bp:
            cap = self._backpack_capacity()
            carry = self._carry_bonus()
            lines.append(f"  Slots: {cap} → {cap + gb}")
            if gc:
                lines.append(f"  Carry: +{carry:.0f} → +{carry + gc:.0f}")
            if gh:
                lines.append(f"  Hack bonus: +{gh}")
        elif is_rng:
            atk = int(getattr(item, "attack", 0) or 0)
            rng = self._effective_shoot_range(item)
            parts = []
            if ga:
                parts.append(f"ATK {atk} → {atk + ga}")
            if gs:
                parts.append(f"range {rng} → {rng + gs}")
            if gc:
                parts.append(f"+{gc:.0f} carry")
            lines.append("  Effect: " + (", ".join(parts) or "none"))
        else:
            atk  = int(getattr(item, "attack", 0) or 0)
            dfn  = int(getattr(item, "defense", 0) or 0)
            sb   = int(getattr(item, "sight_bonus", 0) or 0)
            parts = []
            if ga:
                parts.append(f"ATK {atk}→{atk+ga}")
            if gd:
                parts.append(f"DEF {dfn}→{dfn+gd}")
            if gs:
                parts.append(f"sight+{sb}→+{sb+gs}")
            if gc:
                parts.append(f"+{gc:.0f} carry")
            if gh:
                parts.append(f"+{gh} hack")
            lines.append("  Effect: " + (", ".join(parts) or "none"))
        lines.append(f"  Sockets: {n_socks} → {n_socks + 1}")
        return lines

    def _handle_craft_overlay_key(self, ch) -> bool:
        # Gem sub-modal takes priority
        if self.craft_gem_step == "pick":
            return self._handle_gem_pick_key(ch)
        if self.craft_gem_step == "confirm":
            return self._handle_gem_confirm_key(ch)

        if ch in (27, ord("q"), ord("Q"), ord("g"), ord("G")):
            self.overlay = None
            return True
        if ch == 9:  # Tab switches recipes/socket
            self.craft_tab = "socket" if self.craft_tab == "recipes" else "recipes"
            self.craft_cursor = 0
            self.craft_scroll = 0
            return True

        if self.craft_tab == "recipes":
            # F toggles available-only filter
            if ch in (ord("f"), ord("F")):
                self.craft_filter = not self.craft_filter
                self.craft_cursor = 0
                self.craft_scroll = 0
                return True
            order = self._craft_recipe_order()
            n = len(order)
            if ch in (curses.KEY_UP, ord("k"), ord("K")):
                self.craft_cursor = max(0, self.craft_cursor - 1)
                return True
            if ch in (curses.KEY_DOWN, ord("j"), ord("J")):
                self.craft_cursor = min(n - 1, self.craft_cursor + 1) if n else 0
                return True
            if not n:
                return True
            self.craft_cursor = max(0, min(self.craft_cursor, n - 1))
            recipe_idx = order[self.craft_cursor]
            if ch in (10, 13, ord("c"), ord("C")):
                self._craft_recipe(CRAFT_RECIPES[recipe_idx])
            elif ch in (ord("x"), ord("X")):
                self._inspect_recipe(CRAFT_RECIPES[recipe_idx])
        else:  # socket tab
            entries = self._socketable_armor()
            n = len(entries)
            if ch in (curses.KEY_UP, ord("k"), ord("K")):
                self.craft_cursor = max(0, self.craft_cursor - 1)
                return True
            if ch in (curses.KEY_DOWN, ord("j"), ord("J")):
                self.craft_cursor = min(n - 1, self.craft_cursor + 1) if n else 0
                return True
            if not n:
                return True
            self.craft_cursor = max(0, min(self.craft_cursor, n - 1))
            if ch in (10, 13, ord("c"), ord("C")):
                gems = self._available_gems()
                if not gems:
                    self._sys("No gems in inventory.")
                elif "anvil" not in self._nearby_stations():
                    self._sys("Need an anvil to socket gems.")
                else:
                    self.craft_gem_item = entries[self.craft_cursor]
                    self.craft_gem_cursor = 0
                    self.craft_gem_step = "pick"
            elif ch in (ord("x"), ord("X")):
                self._inspect_item(entries[self.craft_cursor][2])
        return True

    def _handle_gem_pick_key(self, ch) -> bool:
        gems = self._available_gems()
        n = len(gems)
        if ch in (27, ord("q"), ord("Q")):
            self.craft_gem_step = None
            return True
        if ch in (curses.KEY_UP, ord("k"), ord("K")):
            self.craft_gem_cursor = max(0, self.craft_gem_cursor - 1)
            return True
        if ch in (curses.KEY_DOWN, ord("j"), ord("J")):
            self.craft_gem_cursor = min(n - 1, self.craft_gem_cursor + 1) if n else 0
            return True
        if ch in (10, 13) and n:
            self.craft_gem_cursor = max(0, min(self.craft_gem_cursor, n - 1))
            self.craft_gem_choice = gems[self.craft_gem_cursor]
            self.craft_gem_step = "confirm"
        return True

    def _handle_gem_confirm_key(self, ch) -> bool:
        if ch in (27, ord("q"), ord("Q"), ord("n"), ord("N")):
            self.craft_gem_step = None
            self.craft_gem_choice = None
            return True
        if ch in (10, 13, ord("y"), ord("Y")):
            if self.craft_gem_item and self.craft_gem_choice:
                _, _, item = self.craft_gem_item
                self._socket_gem(item, gem=self.craft_gem_choice)
            self.craft_gem_step = None
            self.craft_gem_choice = None
        return True

    def _nearby_terminal(self):
        b = self.b
        choices = [(b.px, b.py)]
        choices.extend((b.px + dx, b.py + dy) for dx, dy in DIRS.values())
        for x, y in choices:
            spec = b.specials.get((x, y), {})
            if spec.get("kind") == "terminal":
                return (x, y), spec
        return None, None

    def _hack_terminal_action(self, mode: str = "balanced"):
        pos, term = self._nearby_terminal()
        if not term:
            self._sys("No odd terminal nearby. Stand on ! or next to one, then press x.")
            return
        if term.get("hacked"):
            self._sys(f"Terminal {term.get('ssid', 'CastleNet')} already rooted.")
            return
        self._attempt_terminal_hack(pos, term, mode)
        self._advance_turn()

    def _required_tools_for_terminal(self, term: dict, mode: str) -> list[str]:
        # T1187 NTLM relay: coerce auth rather than cracking — swap crack_password for force_auth
        if mode == "ntlm":
            req = ["wifi_scan", "capture_handshake", "force_auth"]
        else:
            req = ["wifi_scan", "capture_handshake", "crack_password"]
        control = term.get("control", "doors")

        # Original control types
        if control in ("gates", "dungeon"):
            req.append("door_override")
        if control in ("locks", "security"):
            req.append("circuit_bypass")
        if control == "loot":
            req.append("loot_decrypt")
        if control == "dungeon":
            req.append("root_shell")

        # New control types — TTP-based
        if control == "cameras":       # T1562 — Impair Defenses
            req += ["credential_dump", "camera_blind"]
        elif control == "alarms":      # T1036 + T1583 — Masquerade + Spoof
            req += ["signal_spoof", "process_spoof"]
        elif control == "comm":        # T1572 + T1557 — Tunnel + AiTM
            req += ["pivot_relay", "arp_poison"]
        elif control == "vault":       # T1560 + T1550 — Archive + PtH
            req += ["loot_decrypt", "pass_the_hash"]
        elif control == "power":       # T1574 + T1203 — Hijack + Exploit
            req += ["circuit_bypass", "exploit_vuln"]
        elif control == "db":          # T1190 + T1003 — SQLi + Cred dump
            req += ["sql_inject", "credential_dump"]
        elif control == "auth":        # T1558 — Kerberoasting + Token Forge
            req += ["kerberoast", "forge_token"]
        elif control == "scada":       # T1574 + T1203 — ICS/OT exploitation
            req += ["circuit_bypass", "exploit_vuln", "shellcode_exec"]
        elif control == "radio":       # T1557 + T1583 — RF AiTM + BSSID spoof
            req += ["arp_poison", "signal_spoof", "dns_exfil"]
        elif control == "firmware":    # T1601 — flash device firmware
            req += ["flash_firmware", "exploit_vuln"]
        elif control == "backup":      # T1550.003 + T1560 — PtT + decrypt
            req += ["pass_the_ticket", "loot_decrypt"]
        elif control == "cloud":       # T1021.002 + T1003 — remote exec + cred
            req += ["remote_exec", "credential_dump"]
        elif control == "registry":    # T1112 — Modify Registry hive
            req += ["lolbin_exec", "token_impersonate"]
        elif control == "webshell":    # T1505 — Server Software Component
            req += ["exploit_vuln", "persist_boot", "obfuscate"]
        elif control == "vpn":         # T1090 — Proxy / VPN concentrator
            req += ["pivot_relay", "force_auth", "icmp_covert"]
        elif control == "container":   # T1611 — Escape to Host
            req += ["shellcode_exec", "uac_escape", "privilege_escalation"]

        # Hack modes — each mode requires additional tools
        if mode == "stealth":          # T1583 — low footprint via spoof
            req.append("signal_spoof")
        elif mode == "bruteforce":     # T1110 — force root via PrivEsc
            req.append("privilege_escalation")
        elif mode == "exploit":        # T1203 + T1068 — binary exploit chain
            req += ["circuit_bypass", "privilege_escalation"]
        elif mode == "pivot":          # T1572 — enter via tunnelled relay
            req.append("pivot_relay")
        elif mode == "evasion":        # T1070 + T1036 — cover tracks
            req += ["erase_logs", "process_spoof"]
        elif mode == "recon":          # T1046 + T1018 — passive enum only
            req += ["port_scan", "host_discovery"]
        elif mode == "kerberos":       # T1558 — Kerberoasting + Golden Ticket
            req += ["kerberoast", "forge_token"]
        elif mode == "wmi":            # T1047 — WMI lateral exec
            req.append("wmi_exec")
        elif mode == "lolbin":         # T1218 — Living-off-the-Land
            req.append("lolbin_exec")
        # ntlm mode: base req already swapped at top; no additional tools here
        # social mode: handled early in _attempt_terminal_hack (no extra tools)

        tier = int(term.get("tier", 1))
        if tier >= 3 and "root_shell" not in req:
            req.append("root_shell")
        # Preserve order while deduplicating.
        return list(dict.fromkeys(req))

    def _practice_hack(self, pos, term: dict, skill_focus: str | None = None):
        """Unguided practice on a locked terminal. Always grants 1 XP in the weakest needed skill."""
        self._ensure_skill_reqs(term)
        reqs = term["skill_reqs"]
        # Find which skill the player is furthest below on this terminal
        if skill_focus and skill_focus in reqs:
            chosen = skill_focus
        else:
            gaps = {sk: max(0, reqs.get(sk, 0) - self.skills.get(sk, 0))
                    for sk in _MODE_SKILL.values()}
            chosen = max(gaps, key=lambda k: gaps[k]) if gaps else "exploit"
        self.skills[chosen] = self.skills.get(chosen, 0) + 1
        self._sys(f"Practice: +1 {chosen} (now Lv{self.skills[chosen]}).")
        # 1-in-20 bonus: lower a skill req or grant a missing module
        if random.random() < 0.05:
            if random.random() < 0.5:
                reqs[chosen] = max(0, reqs.get(chosen, 1) - 1)
                self._sys(f"Practice insight! {chosen} requirement on this terminal lowered "
                          f"(now Lv{reqs[chosen]}).")
            else:
                req_tools = self._required_tools_for_terminal(term, "balanced")
                missing_tools = [t for t in req_tools if t not in self.tools]
                granted = False
                for tool in missing_tools:
                    for mod, tool_key in MODULE_TO_TOOL.items():
                        if tool_key == tool and mod not in self.modules:
                            self._unlock_module(mod, "practice session")
                            granted = True
                            break
                    if granted:
                        break
                if not granted:
                    self._sys("Bonus: practice deepens your intuition.")

    def _attempt_terminal_hack(self, pos, term: dict, mode: str):
        ssid = term.get("ssid", "CastleNet")
        control = term.get("control", "doors")
        tech_req = self._tech_required_for_terminal(term)
        tech_lv = self._skill_level("tech")

        self._sys(f"ArtHackToolKit -> target {ssid}, profile={control}, mode={mode}.")

        # Social engineering (T1566): no tools needed, low fixed chance
        if mode == "social":
            tier = int(term.get("tier", 1))
            social_lv = self.skills.get("social", 0)
            social_req, _, _ = self._hack_skill_req(term, "social")
            # Social skill raises the base chance slightly
            chance = max(0.04, 0.15 - 0.04 * (tier - 1) + social_lv * 0.01)
            success = random.random() < chance
            if not success:
                self._gm("T1566: Social engineering failed — operator didn't take the bait.")
                self.skills["social"] += self.xp_mult  # always learn something from a failed attempt
                if random.random() < 0.10:
                    self._practice_hack(pos, term)
                return
            self.skills["social"] += self.xp_mult
            term["hacked"] = True
            self._apply_terminal_effect(pos, term)
            self._gm("T1566: Operator phished. Payload executed under their authenticated session.")
            return

        # Per-mode skill gate
        skill_name, skill_req, player_skill_lv = self._hack_skill_req(term, mode)
        if player_skill_lv < skill_req:
            self._sys(
                f"{skill_name} skill too low (Lv{player_skill_lv}, need Lv{skill_req}). "
                f"Type 'practice {skill_name}' on a rooted terminal, or attempt to practice here."
            )
            self.skills[skill_name] = self.skills.get(skill_name, 0)  # ensure exists
            self._practice_hack(pos, term)
            return

        req = self._required_tools_for_terminal(term, mode)
        # T1078: Valid Accounts — credential tools implicitly available
        effective_tools = set(self.tools)
        if self.valid_credentials:
            effective_tools |= {"credential_dump", "pass_the_hash", "forge_token",
                                 "pass_the_ticket", "kerberoast"}
        missing = [t for t in req if t not in effective_tools]

        chain = "force_auth" if mode == "ntlm" else "crack_password"
        self._sys(f"Running: wifi_scan -> capture_handshake -> {chain} -> payload")

        if missing:
            self._sys("Missing tools: " + ", ".join(missing) + ". Practicing...")
            self._emit_hacking_instructions()
            self._practice_hack(pos, term)
            return

        # Resource gate: certain tools require infrastructure (GPU/cloud/relay/compute)
        missing_res: list[tuple[str, str]] = []
        for tool in req:
            res = _TOOL_RESOURCE.get(tool)
            if res and not self.resources.get(res):
                missing_res.append((tool, res))
        if missing_res:
            self._sys("Missing infrastructure resources:")
            for tool, res in missing_res:
                providers = [c for c, r in _TERMINAL_RESOURCE.items() if r == res]
                self._sys(f"  {tool} needs [{res}] — hack a {'/'.join(providers)} terminal first")
            self._sys("Tip: hack terminals that provide resources, then they host them remotely.")
            self._practice_hack(pos, term)
            return

        # Recon mode: passive enumeration, no control effect applied
        if mode == "recon":
            self._apply_recon(pos, term)
            self.skills["recon"] = self.skills.get("recon", 0) + 1
            return

        base = {"easy": 0.9, "normal": 0.72, "hard": 0.55, "nightmare": 0.38}
        mode_bonus = {
            "balanced":   0.0,
            "stealth":   -0.08,   # T1583: spoofing adds latency — harder
            "spoof":      0.03,
            "bruteforce": 0.08,   # T1110: brute force is reliable but loud
            "exploit":    0.04,   # T1203: binary exploit — medium bonus
            "pivot":     -0.05,   # T1572: tunnel adds complexity
            "evasion":   -0.12,   # T1070: cover tracks while exploiting — hardest
            "kerberos":   0.15,   # T1558: forged TGT is highly trusted
            "wmi":        0.10,   # T1047: WMI is built-in, often un-logged
            "ntlm":       0.07,   # T1187: relay is reliable, no crack step
            "lolbin":    (0.12 if control in ("security", "alarms", "cameras")
                          else 0.05),  # T1218: trusted binaries evade EDR best at security terminals
        }
        cred_bonus = 0.06 if self.valid_credentials else 0.0  # T1078 advantage
        tier_penalty = 0.08 * max(0, int(term.get("tier", 1)) - 1)
        heat_penalty = _HEAT_HACK_PENALTY[self._heat_level()]
        chance = max(0.08, base.get(self.difficulty, 0.72)
                     + mode_bonus.get(mode, 0.0) + cred_bonus
                     + self.firmware_bonus - tier_penalty - heat_penalty)
        success = random.random() < chance
        if not success:
            noise = _MODE_HEAT.get(mode, 0.3)
            if noise > 0:
                self._raise_heat(noise * 0.5)   # failed loud attempt still makes noise
            self._gm("The terminal rejects your packet burst. Encryption rotates and locks you out.")
            return

        # Apply heat delta for the mode (negative modes lower heat on success)
        heat_delta = _MODE_HEAT.get(mode, 0.0)
        if heat_delta > 0:
            self._raise_heat(heat_delta)
        else:
            self._lower_heat(-heat_delta)

        # Award XP in the skill this mode exercises
        skill_name = _MODE_SKILL.get(mode, "exploit")
        self.skills[skill_name] = self.skills.get(skill_name, 0) + 1
        # Evasion mode: don't mark terminal as permanently hacked (T1070 — no forensic trace)
        if mode != "evasion":
            term["hacked"] = True
        self._apply_terminal_effect(pos, term)

        # Prompt player to install botnet if this terminal provides a resource
        res_type = _TERMINAL_RESOURCE.get(control)
        if res_type and mode != "evasion":
            self._sys(f"Root obtained on {term.get('ssid', 'CastleNet')}. "
                      f"Type 'botnet' to install a C2 node and bring [{res_type}] online.")

        # Mode-specific post-hack effects
        if mode == "pivot":
            # T1572: lateral entry — de-alert nearby patrol
            count = sum(1 for e in self.b.entities.values()
                        if e.hostile and e.alerted
                        and abs(e.x - self.b.px) + abs(e.y - self.b.py) <= 12)
            for ent in self.b.entities.values():
                if ent.hostile and ent.alerted:
                    if abs(ent.x - self.b.px) + abs(ent.y - self.b.py) <= 12:
                        ent.alerted = False
            self._sys(f"T1572: Pivot entry complete. {count} patrol units lost your trace.")
        elif mode == "evasion":
            self._sys("T1070/T1036: Logs purged, process masked. Terminal shows no breach.")
        elif mode == "wmi":
            # T1047: chain to adjacent terminals — reduce their tier
            chained = 0
            for dx in range(-2, 3):
                for dy in range(-2, 3):
                    adj = self.b.specials.get((pos[0] + dx, pos[1] + dy), {})
                    if adj.get("kind") == "terminal" and not adj.get("hacked"):
                        adj["tier"] = max(1, int(adj.get("tier", 1)) - 1)
                        chained += 1
            if chained:
                self._sys(f"T1047: WMI lateral propagation — {chained} adjacent terminals de-tiered.")
        elif mode == "kerberos":
            # T1558: Kerberos tickets valid domain-wide
            self._sys("T1558: Golden Ticket injected — valid_credentials active this session.")
        elif mode == "ntlm":
            # T1187: NTLM relay captured a hash — automatically activates cred tools
            self.valid_credentials = True
            self._sys("T1187: NetNTLM hash captured and relayed. valid_credentials now active.")
        elif mode == "lolbin":
            # T1218: trusted binary exec — no alert triggered in nearby guards
            count = 0
            for ent in self.b.entities.values():
                if ent.hostile and ent.alerted:
                    dist = abs(ent.x - self.b.px) + abs(ent.y - self.b.py)
                    if dist <= 8:
                        ent.alerted = False
                        count += 1
            self._sys(f"T1218: LOLBin execution signed by OS — no EDR alert. "
                      f"{count} nearby units not triggered.")

    def _apply_recon(self, pos, term: dict):
        control = term.get("control", "doors")
        tier = term.get("tier", 1)
        ssid = term.get("ssid", "CastleNet")
        self._sys(f"RECON T1046 — {ssid}")
        self._sys(f"  Control: {control}  |  Tier: {tier}")
        # Show services if portscan was run
        if "services" in term:
            svcs = term["services"]
            self._sys(f"  Open ports ({len(svcs)}):")
            for proto, port in svcs:
                vuln = _SERVICE_VULNS.get((proto, port))
                if vuln:
                    _, tool = vuln
                    have = "✓" if tool in self.tools else "✗"
                    self._sys(f"    {port:>5}/{proto:<10} {have} {tool}")
                else:
                    self._sys(f"    {port:>5}/{proto:<10}   (no exploit in DB)")
        else:
            self._sys("  Services: unknown — run 'portscan' first for port details")
        req = self._required_tools_for_terminal(term, "balanced")
        have = [t for t in req if t in self.tools]
        miss = [t for t in req if t not in self.tools]
        self._sys(f"  Required tools (balanced): {', '.join(req)}")
        if have:
            self._sys(f"  Have:    {', '.join(have)}")
        if miss:
            self._sys(f"  Missing: {', '.join(miss)}")
            for t in miss:
                mod = next((m for m, tl in MODULE_TO_TOOL.items() if tl == t), None)
                if mod:
                    self._sys(f"    → craft {mod} module (g → recipes)")
        else:
            self._sys("  All tools present — 'hack' to attack.")
        # Resource gaps
        needed_res = {_TOOL_RESOURCE[t] for t in req if t in _TOOL_RESOURCE}
        for res in sorted(needed_res):
            providers = self.resources.get(res, set())
            if providers:
                self._sys(f"  [{res}] available via {', '.join(list(providers)[:2])}")
            else:
                src = [c for c, r in _TERMINAL_RESOURCE.items() if r == res]
                self._sys(f"  [{res}] MISSING — hack a {'/'.join(src)} terminal first")
        # Per-mode skill breakdown
        self._ensure_skill_reqs(term)
        reqs = term["skill_reqs"]
        self._sys("  Skill requirements per mode:")
        for mode_name, sk in sorted(set(_MODE_SKILL.items()), key=lambda x: x[1]):
            r = reqs.get(sk, 0)
            p = self.skills.get(sk, 0)
            mark = "✓" if p >= r else "✗"
            self._sys(f"    {mode_name:<12} {sk:<8} need Lv{r:2d}  you Lv{p:2d}  {mark}")

    def _apply_terminal_effect(self, pos, term: dict):
        control = term.get("control", "doors")
        ssid = term.get("ssid", "CastleNet")
        if control == "doors":
            opened = 0
            for (dx, dy), info in self.b.doors.items():
                if info.get("locked") and not info.get("hack_locked"):
                    info["locked"] = False
                    if self.b.get(dx, dy) == "=":
                        self.b.setc(dx, dy, "+")
                    opened += 1
            opened += self._unlock_terminal_security(ssid, pos)
            self._gm(f"Door-control daemon compromised. {opened} locked doors cycle open.")
            return

        if control == "gates":
            for (dx, dy), info in self.b.doors.items():
                if info.get("locked") and not info.get("hack_locked"):
                    info["locked"] = False
                    if self.b.get(dx, dy) == "=":
                        self.b.setc(dx, dy, "+")
            self._unlock_terminal_security(ssid, pos)
            if self.b.phase in ("escape", "flee"):
                self.b.phase = "flee"
            self._gm("Gate subnet rooted. Castle gate servos respond to your toolkit now.")
            return

        if control in ("locks", "loot", "security"):
            if control == "security":
                self._lower_heat(1.0)
            opened = self._unlock_terminal_security(ssid, pos)
            self._gm(f"Security lattice bypassed. {opened} terminal-linked locks and caches open.")
            return

        if control == "cameras":
            # T1562 — Impair Defenses: blind the CCTV subnet, disrupt patrol
            count = 0
            for ent in self.b.entities.values():
                if ent.hostile:
                    ent.alerted = False
                    ent.sight_radius = max(3, ent.sight_radius - 4)
                    count += 1
            self._lower_heat(1.5)
            opened = self._unlock_terminal_security(ssid, pos)
            self._gm(
                f"T1562: CCTV frame-buffer hooks overwritten. {count} patrol units blinded. "
                f"Sight radius reduced. {opened} camera-linked locks disengaged. Heat -1.5"
            )
            return

        if control == "alarms":
            # T1036+T1583 — Masquerade + spoof alarm buses
            count = 0
            for ent in self.b.entities.values():
                if ent.hostile and ent.alerted:
                    ent.alerted = False
                    count += 1
            self._lower_heat(2.0)
            opened = self._unlock_terminal_security(ssid, pos)
            self._gm(
                f"T1036/T1583: Alarm daemon spoofed. "
                f"{count} alerted patrols stand down. {opened} alarm-linked gates open. Heat -2.0"
            )
            return

        if control == "comm":
            # T1572+T1557 — Tunnel + AiTM: jam radio coordination
            count = 0
            for ent in self.b.entities.values():
                if ent.hostile:
                    ent.alerted = False
                    count += 1
            self.b.entities = {k: v for k, v in self.b.entities.items()
                               if not (v.hostile and random.random() < 0.2)}
            self._gm(
                f"T1572/T1557: CastleNet comm stack ARP-poisoned and pivoted. "
                f"{count} units lose coordination. Some patrols rerouted off-level."
            )
            return

        if control == "vault":
            # T1560+T1550 — Decrypt archive + PtH into vault
            for _ in range(3):
                fx, fy = self._free_near(self.b.px, self.b.py)
                self.b.add_item(fx, fy, "$", "vault cache",
                                "high-value items from the secured vault", "item",
                                value_cp=random.randint(200, 600))
            opened = self._unlock_terminal_security(ssid, pos)
            self._gm(
                f"T1560/T1550: Pass-the-Hash auth accepted. Vault subnet decrypted. "
                f"{opened} secured caches spill their contents."
            )
            return

        if control == "power":
            # T1574+T1203 — Hijack exec flow + exploit power grid firmware
            for (dx, dy), info in self.b.doors.items():
                if info.get("locked") and not info.get("hack_locked"):
                    info["locked"] = False
                    if self.b.get(dx, dy) == "=":
                        self.b.setc(dx, dy, "+")
            px2, py2 = self.b.px, self.b.py
            for ry in range(max(0, py2 - 25), min(WORLD_H, py2 + 25)):
                for rx in range(max(0, px2 - 25), min(WORLD_W, px2 + 25)):
                    if self.b.get(rx, ry) != VOID:
                        self.b.seen.add((rx, ry))
            self._unlock_terminal_security(ssid, pos)
            self._gm(
                "T1574/T1203: Power-grid firmware exploited. Emergency lighting fires across the wing. "
                "All unlocked doors snap open. Surrounding architecture illuminated."
            )
            return

        if control == "db":
            # T1190+T1003 — SQLi + credential dump from internal database
            if self.clues < CLUES_FOR_PORTAL:
                self.clues += 2
            self.journal.append(
                f"DB dump from {ssid}: internal routing tables and guard schedules extracted."
            )
            opened = self._unlock_terminal_security(ssid, pos)
            self._gm(
                f"T1190/T1003: SQL injection extracted credential hashes. "
                f"Internal DB reveals hidden passages. Clues +2. {opened} DB-linked caches open."
            )
            return

        if control == "auth":
            # T1558 — Kerberoasting + Golden Ticket: forge domain auth tokens
            self.valid_credentials = True
            opened = self._unlock_terminal_security(ssid, pos)
            self._gm(
                f"T1558.001/T1558.003: krbtgt hash extracted, Golden Ticket forged. "
                f"Domain credentials valid — credential tools auto-satisfied for this session. "
                f"{opened} auth-linked locks cycled."
            )
            return

        if control == "scada":
            # T1574+T1203+T1055 — ICS/OT exploitation
            # Open all doors and reveal trap/trapdoor locations
            for (dx, dy), info in self.b.doors.items():
                if info.get("locked") and not info.get("hack_locked"):
                    info["locked"] = False
                    if self.b.get(dx, dy) == "=":
                        self.b.setc(dx, dy, "+")
            for (sx, sy), spec in self.b.specials.items():
                if spec.get("kind") == "trapdoor":
                    self.b.seen.add((sx, sy))
            opened = self._unlock_terminal_security(ssid, pos)
            self._gm(
                f"T1574/T1203: SCADA process injection complete. Physical plant override engaged. "
                f"All actuators unlocked. Trapdoor locations exposed. {opened} ICS-linked locks open."
            )
            return

        if control == "radio":
            # T1557+T1583+T1071.004 — RF subnet takeover
            # Reveal all entities and silence all patrols
            for ent in self.b.entities.values():
                self.b.seen.add((ent.x, ent.y))
                if ent.hostile:
                    ent.alerted = False
            opened = self._unlock_terminal_security(ssid, pos)
            self._gm(
                f"T1557/T1583: RF subnet ARP-poisoned, BSSID spoofed, DNS exfil channel up. "
                f"All entity positions triangulated. Enemy comms jammed. {opened} radio-linked locks open."
            )
            return

        if control == "firmware":
            # T1601 — flash device firmware: permanent toolkit upgrade
            self.firmware_bonus = min(0.20, self.firmware_bonus + 0.05)
            px2, py2 = self.b.px, self.b.py
            for ry in range(max(0, py2 - 20), min(WORLD_H, py2 + 20)):
                for rx in range(max(0, px2 - 20), min(WORLD_W, px2 + 20)):
                    if self.b.get(rx, ry) != VOID:
                        self.b.seen.add((rx, ry))
            self._gm(
                f"T1601: Firmware image reflashed with backdoored build. "
                f"ArtHackToolKit success rate permanently +5% (now +{int(self.firmware_bonus*100)}% total). "
                "Surrounding sector illuminated by diagnostic broadcast."
            )
            return

        if control == "backup":
            # T1550.003+T1560 — PtT into backup server, decrypt archive
            self.hp = self.max_hp
            for y in range(WORLD_H):
                for x in range(WORLD_W):
                    if self.b.get(x, y) != VOID:
                        self.b.seen.add((x, y))
            opened = self._unlock_terminal_security(ssid, pos)
            self._gm(
                f"T1550.003/T1560: Pass-the-Ticket accepted by backup daemon. "
                f"Full system snapshot decrypted — complete level map revealed. "
                f"Emergency restore signal repaired your wounds (HP fully restored). "
                f"{opened} archive-linked caches open."
            )
            return

        if control == "cloud":
            # T1021.002+T1003 — PsExec + cred dump into cloud management
            for _ in range(4):
                fx, fy = self._free_near(self.b.px, self.b.py)
                rarity = random.choice(["rare", "epic", "legendary"])
                self.b.add_item(fx, fy, "$", "cloud cache drop",
                                f"high-value {rarity} item exfiltrated from cloud tenant", "item",
                                value_cp=random.randint(300, 800),
                                rarity=rarity)
            opened = self._unlock_terminal_security(ssid, pos)
            self._gm(
                f"T1021.002/T1003: PsExec shell on cloud host, credential hashes extracted. "
                f"Cloud tenant storage exfiltrated — 4 high-value items materialise nearby. "
                f"{opened} cloud-linked locks disengaged."
            )
            return

        if control == "registry":
            # T1112 — Modify Registry: rewrite system config to impair defenses
            # All enemy sight radii permanently reduced, alarm-linked doors open
            for ent in self.b.entities.values():
                if ent.hostile:
                    ent.sight_radius = max(2, ent.sight_radius - 3)
            for (dx, dy), info in self.b.doors.items():
                if info.get("locked") and not info.get("hack_locked"):
                    info["locked"] = False
                    if self.b.get(dx, dy) == "=":
                        self.b.setc(dx, dy, "+")
            self._lower_heat(1.0)
            opened = self._unlock_terminal_security(ssid, pos)
            self._gm(
                "T1112: Registry hive modified — HKLM\\System\\CurrentControlSet\\Services "
                "rewritten. Patrol sight range permanently -3 tiles. Heat -1.0. "
                f"{opened} registry-linked doors unlatched."
            )
            return

        if control == "webshell":
            # T1505 — Server Software Component: plant web shell for persistent re-access
            # Reset nearby hacked terminals so they can be hacked again
            reset = 0
            for spec in self.b.specials.values():
                if spec.get("kind") == "terminal" and spec.get("hacked"):
                    spec["hacked"] = False
                    spec["tier"] = max(1, int(spec.get("tier", 1)) - 1)
                    reset += 1
            fx, fy = self._free_near(self.b.px, self.b.py)
            self.b.add_item(fx, fy, "$", "web shell access token",
                            "persistent reverse shell into CastleNet management layer", "item",
                            value_cp=500, rarity="epic")
            self._gm(
                f"T1505: Web shell planted in /var/www/cgi-bin. "
                f"{reset} previously hacked terminals reset (re-hackable at lower tier). "
                "Web shell token materialised nearby."
            )
            return

        if control == "vpn":
            # T1090 — Proxy: compromise VPN concentrator, tunnel to new segments
            # Reveal 60% of map + unlock all doors on current level
            px2, py2 = self.b.px, self.b.py
            for ry in range(WORLD_H):
                for rx in range(WORLD_W):
                    if self.b.get(rx, ry) != VOID and random.random() < 0.65:
                        self.b.seen.add((rx, ry))
            for (dx, dy), info in self.b.doors.items():
                if info.get("locked") and not info.get("hack_locked"):
                    info["locked"] = False
                    if self.b.get(dx, dy) == "=":
                        self.b.setc(dx, dy, "+")
            opened = self._unlock_terminal_security(ssid, pos)
            self._gm(
                "T1090: VPN concentrator rooted. Split-tunnel policy deleted — all traffic "
                "now routes through attacker relay. Level topology 65% revealed. "
                f"{opened} VPN-linked security doors forced open."
            )
            return

        if control == "container":
            # T1611 — Escape to Host: break out of containerised process
            # Teleport player to random open cell + spawn legendary loot
            floor_cells = [(x, y) for y in range(WORLD_H) for x in range(WORLD_W)
                           if self.b.get(x, y) == "." and not self.b.entity_at(x, y)]
            if floor_cells:
                self.b.px, self.b.py = random.choice(floor_cells)
            for _ in range(2):
                fx, fy = self._free_near(self.b.px, self.b.py)
                self.b.add_item(fx, fy, "$", "host-layer artefact",
                                "stolen from the hypervisor — outside normal loot tables",
                                "item", value_cp=random.randint(600, 1200), rarity="legendary")
            self.b.compute_visible(radius=self._vision_radius())
            self._gm(
                "T1611: Container namespace escape via runc CVE exploit. "
                "Attained host context — teleported to new position. "
                "2 hypervisor-layer legendary artefacts extracted."
            )
            return

        # Dungeon control: reveal architecture and reward progress.
        for y in range(WORLD_H):
            for x in range(WORLD_W):
                if self.b.get(x, y) != VOID:
                    self.b.seen.add((x, y))
        self._unlock_terminal_security(ssid, pos)
        if self.b.phase in ("return", "portal") and self.clues < CLUES_FOR_PORTAL:
            x, y = self._free_near(self.b.px, self.b.py)
            self.b.add_item(x, y, "*", "network topology scrap",
                            "service tunnels map a path to a hidden sanctum",
                            "clue")
        self._gm("Dungeon-core service hacked. Old walls redraw themselves in your mind.")

    def _unlock_terminal_security(self, ssid: str, pos) -> int:
        unlocked = 0
        tx, ty = pos
        for (dx, dy), info in self.b.doors.items():
            if info.get("hack_ssid") != ssid:
                continue
            if abs(dx - tx) + abs(dy - ty) > 16:
                continue
            info["locked"] = False
            info["hack_locked"] = False
            if self.b.get(dx, dy) == "=":
                self.b.setc(dx, dy, "+")
            unlocked += 1

        for (cx, cy), spec in list(self.b.specials.items()):
            if spec.get("kind") != "hack_chest":
                continue
            if spec.get("ssid") != ssid or not spec.get("locked", True):
                continue
            if abs(cx - tx) + abs(cy - ty) > 16:
                continue
            loot = spec.get("loot", {})
            self.b.setc(cx, cy, ".")
            self.b.add_item(cx, cy,
                            loot.get("char", "$"),
                            loot.get("name", "cache loot"),
                            loot.get("desc", "salvaged from a terminal-bound chest"),
                            loot.get("kind", "item"))
            spec["locked"] = False
            unlocked += 1
        return unlocked

    def _emit_hacking_instructions(self):
        self._sys("Workflow: portscan → vulnscan → hack → botnet → (resource online)")
        self._sys("  portscan  — open ports on adjacent ! (no tools needed)")
        self._sys("  vulnscan  — CVEs + tool/resource gaps (needs port_scan tool)")
        self._sys("  hack      — gain root; x=balanced or 'hack <mode>'")
        self._sys("  botnet    — install C2 implant AFTER root to activate resource")
        self._sys("              needs: persist_cron/boot + dns_exfil/icmp_covert")
        self._sys("Resources unlocked by botnet install on rooted terminal:")
        self._sys("  [gpu]     crack_password  — security/cameras/scada terminals")
        self._sys("  [cloud]   kerberoast/forge_token — cloud/backup/auth terminals")
        self._sys("  [relay]   force_auth/wmi — comm/vpn/webshell terminals")
        self._sys("  [compute] exploit/shellcode — power/firmware/dungeon terminals")
        self._sys("Examples: 'difficulty easy', 'too hard', 'scan', 'hack exploit'.")

    @staticmethod
    def _key_to_dir(ch):
        m = {
            curses.KEY_UP: (0, -1), ord("w"): (0, -1), ord("k"): (0, -1),
            curses.KEY_DOWN: (0, 1), ord("s"): (0, 1), ord("j"): (0, 1),
            curses.KEY_LEFT: (-1, 0), ord("a"): (-1, 0), ord("h"): (-1, 0),
            curses.KEY_RIGHT: (1, 0), ord("d"): (1, 0),
        }
        return m.get(ch)

    def _handle_cmd_key(self, ch):
        if ch in (27,):  # ESC
            self.cmd_mode = False
            self.cmd_buf = ""
        elif ch in (curses.KEY_ENTER, 10, 13):
            text = self.cmd_buf.strip()
            self.cmd_mode = False
            self.cmd_buf = ""
            if text:
                if not self._handle_local_command(text):
                    self._offline("command", {"text": text})
                    self._advance_turn()
        elif ch in (curses.KEY_BACKSPACE, 127, 8):
            self.cmd_buf = self.cmd_buf[:-1]
        elif 32 <= ch < 127 and len(self.cmd_buf) < 80:
            self.cmd_buf += chr(ch)

    # ===================================================================
    #  movement & interaction
    # ===================================================================
    def _try_move(self, dx, dy):
        b = self.b
        nx, ny = b.px + dx, b.py + dy
        ent = b.entity_at(nx, ny)
        if ent:
            self._offline("examine",
                           {"target": f"{ent.name} ({ent.desc})",
                            "entity_id": ent.id})
            self._advance_turn()
            return
        target = b.get(nx, ny)
        if target == "=":
            self._try_unlock(nx, ny)
            return
        if target in BLOCKING:
            # Pushing from a door into the void = explore a new area.
            cur = b.get(b.px, b.py)
            if target == VOID and cur in "+":
                self._explore_from(b.px, b.py, dx, dy)
            return
        b.px, b.py = nx, ny
        self._post_move()

    def _try_unlock(self, x, y):
        info = self.b.doors.get((x, y))
        if info and info.get("hack_locked"):
            ssid = info.get("hack_ssid", "nearby terminal")
            self._sys(f"This lock is terminal-bound ({ssid}). Hack a nearby ! terminal.")
            return
        key = next((i for i in self.b.inventory if i.kind == "key"), None)
        if key:
            self.b.inventory.remove(key)
            self.b.setc(x, y, "+")
            if info:
                info["locked"] = False
            self._sys(f"The {key.name} turns. The lock clicks open.")
        else:
            self._sys("The door is locked. You need a key.")

    def _explore_from(self, dx_door, dy_door, dx, dy):
        info = self.b.doors.get((dx_door, dy_door))
        if info and info.get("explored"):
            return
        direction = {(0, -1): "north", (0, 1): "south",
                     (-1, 0): "west", (1, 0): "east"}[(dx, dy)]
        desc = info.get("desc", "doorway") if info else "doorway"
        self._offline("explore",
                       {"door": (dx_door, dy_door), "direction": direction,
                        "door_desc": desc})

    def _post_move(self):
        self.b.compute_visible(radius=self._vision_radius())
        b = self.b
        it = b.item_at(b.px, b.py)
        if it:
            if it.kind == "currency":
                b.items.pop(it.id, None)
                b.setc(b.px, b.py, ".")
                self.wallet_cp += int(getattr(it, "value_cp", 0) or 0)
                self._sys(f"You collect coin: {self._coins_text(it.value_cp)}.")
            else:
                next_weight = self._carry_weight() + self._item_weight(it)
                if next_weight > self._effective_max_weight():
                    self._sys("Too heavy to pick up — over total carry limit.")
                    it = None
                elif len(b.inventory) < BASE_INV_SLOTS:
                    b.items.pop(it.id, None)
                    b.inventory.append(it)
                    b.setc(b.px, b.py, ".")
                    self._sys(f"You pick up the {it.name}.")
                    if it.kind == "clue":
                        self.clues += 1
                        self.journal.append(it.desc or it.name)
                        self._maybe_arm_portal()
                    elif it.kind == "module":
                        mod = ""
                        low = it.name.lower()
                        for key in MODULE_TO_TOOL:
                            if key in low:
                                mod = key
                                break
                        if mod:
                            self._unlock_module(mod, "found loot")
                elif self._backpack_capacity() > len(self.backpack_inv):
                    b.items.pop(it.id, None)
                    self.backpack_inv.append(it)
                    b.setc(b.px, b.py, ".")
                    cap = self._backpack_capacity()
                    self._sys(
                        f"Bag full — {it.name} → backpack "
                        f"({len(self.backpack_inv)}/{cap} slots)."
                    )
                    if it.kind == "clue":
                        self.clues += 1
                        self.journal.append(it.desc or it.name)
                        self._maybe_arm_portal()
                    elif it.kind == "module":
                        low = it.name.lower()
                        for key in MODULE_TO_TOOL:
                            if key in low:
                                self._unlock_module(key, "found loot")
                                break
                else:
                    hint = " Equip a backpack to carry more." if not self.equipped.get("back") else ""
                    self._sys(f"Inventory full ({BASE_INV_SLOTS} items + backpack).{hint}")
                    it = None
        cell = b.get(b.px, b.py)
        if cell == "O":
            self._win()
        elif cell == ">":
            self._cross_gate()
        elif cell == "%":
            self._sys("Quartermaster nearby. Type 'shop' to browse and 'buy <n>' to purchase.")
        elif cell == "!":
            term = b.specials.get((b.px, b.py), {})
            ssid = term.get("ssid", "CastleNet")
            self._sys(f"Odd terminal detected on {ssid}. Press x to hack.")
        elif cell == "&":
            chest = b.specials.get((b.px, b.py), {})
            if chest.get("kind") == "hack_chest" and chest.get("locked", True):
                self._sys("Locked cache chest. Hack a nearby linked terminal to open it.")
        elif cell == "X":
            self._open_loot_chest((b.px, b.py))
        elif cell in ("A", "F"):
            station = "anvil" if cell == "A" else "crafting table"
            self._sys(f"A {station} stands here. Press g to open the crafting panel.")
        elif cell in ("<", "V", "T"):
            self._transition_level()
        self._advance_turn()

    def _maybe_arm_portal(self):
        if (self.b.phase == "return" and self.clues >= CLUES_FOR_PORTAL
                and not self.portal_armed):
            self.portal_armed = True
            self.b.phase = "portal"
            self._gm("The clues align in your mind. Somewhere in these walls a "
                     "hidden room hums with a way home. Find it.")

    def _cross_gate(self):
        if not self.escaped and self.b.phase in ("escape", "flee"):
            self.escaped = True
            self.b.phase = "return"
            self._gm("Night air. You are OUTSIDE the castle walls — free. "
                     "But the only way truly home lies back inside. Steel "
                     "yourself and return to hunt for its secret.")

    def _transition_level(self):
        b = self.b
        cell = b.get(b.px, b.py)
        key = (b.px, b.py, b.level)
        link = b.stair_links.get(key)
        if link is None:
            self._sys("The passage is blocked.")
            return
        tx, ty, target = link
        b.transition_to_level(tx, ty, target)
        b.compute_visible(radius=self._vision_radius())
        level_name = _LEVEL_NAMES[target]
        if cell == "<":
            self._gm(f"You climb up into the {level_name}.")
        elif cell == "V":
            self._gm(f"You descend into the {level_name}.")
        elif cell == "T":
            self._gm(f"The floor gives way! You crash down into the {level_name}.")
        self._offline('populate', {'level': target, 'level_name': _LEVEL_NAMES[target]})

    def _spawn_room_near_player(self, spec):
        room = self.b.room_at(self.b.px, self.b.py)
        if not room:
            return
        for (dx, dy), info in list(self.b.doors.items()):
            if info["room"] == room.id and not info["explored"]:
                d = self._void_dir(dx, dy)
                if d:
                    self.b.connect_room((dx, dy), d, spec)
                    self._maybe_place_portal(self.b.room_at(dx + DIRS[d][0],
                                                            dy + DIRS[d][1]))
                    return

    def _void_dir(self, x, y):
        for name, (ddx, ddy) in DIRS.items():
            if self.b.get(x + ddx, y + ddy) == VOID:
                return name
        return None

    def _maybe_place_portal(self, room):
        if room is None or self.portal_placed:
            return
        if self.b.phase == "portal" or self.portal_armed:
            fx, fy = self.b._first_floor(room)
            self.b.setc(fx, fy, "O")
            self.b.specials[(fx, fy)] = {"tag": "portal"}
            self.portal_placed = True
            self._gm("A ring of cold light tears the air open — a PORTAL. "
                     "Step through it to go home.")

    # ===================================================================
    #  offline fallbacks (no model / model failed)
    # ===================================================================
    def _offline(self, kind, payload):
        if kind == "initial":
            if not self.b.dungeon_generated:
                self.b.place_start_room(self._offline_start_spec())
                self.b.compute_visible(radius=self._vision_radius())
            self._gm("You wake on cold stone. Iron bars, straw, and the drip "
                     "of water. You are Art, and this dungeon is not your home.")
            self.started = True
        elif kind == "populate":
            lname = payload.get("level_name", _LEVEL_NAMES[self.b.level])
            self._sys(f"The {lname} stirs with hidden dangers.")
        elif kind == "explore":
            # Place up to 12 procedural rooms, branching BFS across frontier doors.
            placed = self.b.connect_cluster(
                payload["door"], payload["direction"], [None] * 12)
            if not placed:
                self._sys("Rubble blocks the way. That passage is sealed.")
                return
            self._gm(f"You press on into the {placed[0].name.lower()}.")
            if len(placed) > 1:
                names = ", ".join(r.name for r in placed[1:])
                self._sys(f"The wing also holds: {names}.")
            for room in placed:
                self._maybe_place_portal(room)
            self.b.compute_visible(radius=self._vision_radius())
        elif kind == "examine":
            self._offline_examine(payload)
        elif kind == "command":
            self._offline_command(payload)

    def _offline_start_spec(self):
        return {
            "id": "cell", "name": "Dungeon Cell",
            "grid": ["#########",
                     "#.......#",
                     "#.......+",
                     "#.......#",
                     "#########"],
            "start": [2, 2],
            "narration": "You wake on cold stone in a cramped cell.",
        }

    def _offline_examine(self, payload):
        if payload.get("rest"):
            self._gm(random.choice([
                "You breathe slow and listen. Distant footsteps, then silence.",
                "You wait. Water drips, a torch gutters. Nothing comes — yet.",
                "You steady yourself. The old castle holds its breath with you."]))
            return
        if payload.get("entity_id"):
            self._gm(random.choice([
                "It eyes you, then looks away. Best not to linger.",
                "You hold your breath and slip past, unseen.",
                "A low grunt. You press yourself to the wall and wait."]))
            return
        if payload.get("search"):
            if self.b.phase == "return" and random.random() < 0.7:
                x, y = self._free_near(self.b.px, self.b.py)
                self.b.add_item(x, y, "*", "scrap of parchment",
                                random.choice([
                                    "the throne hides what the king feared",
                                    "behind the tapestry, a cold draft",
                                    "count the candles to find the door"]),
                                "clue")
                self._gm("Your fingers find a loose stone — and a hidden note.")
                return
            if self.b.phase in ("escape", "flee") and random.random() < 0.4:
                x, y = self._free_near(self.b.px, self.b.py)
                self.b.add_item(x, y, "k", "iron key", "heavy and cold", "key")
                self._gm("Half-buried in the straw: a key.")
                return
            self._gm("You search, but find only dust and old fear.")
        else:
            room = self.b.room_at(self.b.px, self.b.py)
            self._gm(f"You are in {room.name if room else 'a dim passage'}. "
                     "Shadows pool in the corners; an exit beckons.")

    def _offline_command(self, payload):
        text = payload["text"].lower()
        if any(w in text for w in ("look", "search", "examine", "inspect")):
            self._offline_examine({"search": "search" in text})
        else:
            self._gm("You try that. The castle answers only with echoes — "
                     "keep moving, Art.")

    # ===================================================================
    #  helpers
    # ===================================================================
    def _free_near(self, cx, cy):
        for r in range(1, 8):
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    x, y = cx + dx, cy + dy
                    if (self.b.get(x, y) == "." and (x, y) != (cx, cy)
                            and not self.b.entity_at(x, y)
                            and not self.b.item_at(x, y)):
                        return x, y
        return cx, cy

    def _set_phase(self, phase):
        _phases = {"escape", "flee", "return", "portal", "win"}
        if phase in _phases:
            if phase == "win":
                self._win()
            else:
                self.b.phase = phase

    def _gm(self, text):
        self.log.append(("gm", str(text).strip().replace("\n", " ")))
        self._trim_log()

    def _sys(self, text):
        self.log.append(("sys", text))
        self._trim_log()

    def _trim_log(self):
        if len(self.log) > 200:
            self.log = self.log[-200:]

    def _win(self):
        self.won = True
        self.b.phase = "win"

    # ===================================================================
    #  rendering
    # ===================================================================
    def _draw(self):
        scr = self.scr
        scr.erase()
        h, w = scr.getmaxyx()
        if w < MIN_W or h < MIN_H:
            self._put(0, 0, f"Enlarge the terminal to at least {MIN_W}x{MIN_H} "
                            f"(now {w}x{h}).", self._attr(6, True))
            scr.refresh()
            return
        if self.won:
            self._draw_win(h, w)
            scr.refresh()
            return
        if self.overlay:
            self._draw_overlay(h, w)
            scr.refresh()
            return

        map_w = w - SIDEBAR
        map_h = h - LOGH - 1
        self._draw_title(w)
        if not self.started:
            self._draw_loading(map_h, map_w)
        else:
            self._draw_map(1, 0, map_h, map_w)
        self._draw_sidebar(1, map_w + 1, map_h, w)
        self._draw_log(h - LOGH + 1, 0, LOGH - 2, w)
        self._draw_prompt(h - 1, 0, w)
        scr.refresh()

    def _draw_title(self, w):
        title = " ART — escape the castle, find the way home "
        self._put(0, 0, title.center(w, "─"), self._attr(10, True))

    def _draw_loading(self, map_h, map_w):
        msg = "building the dungeon…"
        self._put(1 + map_h // 2, max(0, (map_w - len(msg)) // 2), msg,
                  self._attr(11, True))

    def _draw_map(self, top, left, map_h, map_w):
        b = self.b
        cam_x = _clamp(b.px - map_w // 2, 0, max(0, WORLD_W - map_w))
        cam_y = _clamp(b.py - map_h // 2, 0, max(0, WORLD_H - map_h))
        seen = b.seen
        visible = b.visible
        dim_attr = self._attr(11)  # seen-but-not-visible: dim white, no bold
        for sy in range(map_h):
            wy = cam_y + sy
            if wy >= WORLD_H:
                break
            row = b.grid[wy]
            for sx in range(map_w):
                wx = cam_x + sx
                if wx >= WORLD_W:
                    break
                ch = row[wx]
                if ch == VOID:
                    continue
                pos = (wx, wy)
                if pos not in seen:
                    continue           # never seen — keep dark
                if pos in visible:
                    self._put(top + sy, left + sx, ch, self._glyph_attr(ch))
                else:
                    self._put(top + sy, left + sx, ch, dim_attr)  # remembered
        # Entities are only shown when currently visible (they may have moved).
        for e in b.entities.values():
            if (e.x, e.y) not in visible:
                continue
            sx, sy = e.x - cam_x, e.y - cam_y
            if 0 <= sx < map_w and 0 <= sy < map_h:
                self._put(top + sy, left + sx, e.char[0], self._attr(6, True))
        self._put(top + (b.py - cam_y), left + (b.px - cam_x), "@",
                  self._attr(3, True))

    def _glyph_attr(self, ch):
        pair = COLOR.get(ch, 6 if ch.isalpha() else 2)
        bold = ch in "@O>k*$<&!%X^~" or (ch.isalpha() and ch not in "VT")
        return self._attr(pair, bold)

    def _draw_sidebar(self, top, left, map_h, w):
        for y in range(top, top + map_h):
            self._put(y, left - 1, "│", self._attr(11))
        y = top
        phase_txt = {
            "escape": "Escape the dungeon",
            "flee": "Flee the castle",
            "return": "Return for clues",
            "portal": "Find the portal",
            "win": "Home",
        }.get(self.b.phase, self.b.phase)
        arch_label = _ARCHETYPES.get(self.archetype, {}).get("label", "")
        y = self._side(left, y, f"QUEST  [{arch_label}]", self._attr(10, True))
        y = self._side(left, y, f" {phase_txt}", self._attr(1))
        if self.b.dungeon_generated:
            lv = self.b.level
            y = self._side(left, y, f" Level {lv}: {_LEVEL_NAMES[lv]}", self._attr(11))
        atk, dfn = self._combat_power()
        fxn = len(self.active_effects)
        fx_lbl = f" fx:{fxn}" if fxn else ""
        hp_attr = self._attr(9 if self.hp < self.max_hp * 0.35 else 8, True)
        y = self._side(left, y, f" HP {self.hp}/{self.max_hp}{fx_lbl}", hp_attr)
        y = self._side(left, y, f" ATK {atk}  DEF {dfn}", self._attr(11))
        y = self._side(left, y, f" Sight {self._vision_radius()} (+{self._sight_bonus()})", self._attr(11))
        # Heat bar
        heat_lv = self._heat_level()
        heat_bar = "▓" * heat_lv + "░" * (5 - heat_lv)
        heat_attr = self._attr(3 if heat_lv <= 1 else (8 if heat_lv <= 3 else 9), heat_lv >= 3)
        y = self._side(left, y, f" HEAT [{heat_bar}] {_HEAT_LABELS[heat_lv]}", heat_attr)
        # Stealth indicator
        if self.stealth_mode:
            snk = self._stealth_bonus()
            y = self._side(left, y, f" [SNEAK  -{snk} detect]", self._attr(5, True))
        # Netrunner passive: reveals nearest terminal type within 5 tiles
        if self.archetype == "netrunner":
            hit = self._nearest_terminal(max_dist=5)
            if hit:
                _, term = hit
                ctrl = term.get("control", "?")
                rooted = " [ROOTED]" if term.get("rooted") else ""
                y = self._side(left, y, f" NET: {ctrl}{rooted}", self._attr(3, True))
        y = self._side(left, y, f" coin: {self._coins_text(self.wallet_cp)}", self._attr(5))
        y = self._side(left, y,
                       f" load: {self._carry_weight():.1f}/{self._effective_max_weight():.1f}",
                       self._attr(11))
        if self.b.phase in ("return", "portal"):
            y = self._side(left, y, f" clues: {self.clues}/{CLUES_FOR_PORTAL}",
                           self._attr(5))
        y += 1
        y = self._side(left, y, "INVENTORY", self._attr(10, True))
        if self.b.inventory:
            for it in self.b.inventory[-6:]:
                y = self._side(left, y, f" {it.char} {it.name}", self._attr(5))
        else:
            y = self._side(left, y, " (empty)", self._attr(11))
        y += 1
        y = self._side(left, y, "LEGEND", self._attr(10, True))
        for line in ("@ you   # wall   + door",
                     "= lock   k key   * clue",
                     "> gate   O portal  $ loot",
                     "< up   V down   T trapdoor",
                     "! terminal  & cache  % shop",
                     "X chest  A anvil  F table",
                     "/ wood : clay - metal ^ gem",
                     "~ electronics"):
            y = self._side(left, y, " " + line, self._attr(11))
        y += 1
        y = self._side(left, y, "KEYS", self._attr(10, True))
        for line in ("move WASD/arrows", "z shoot  v sneak",
                     "x hack terminal (!)",
                     "u skills   p toolkit  g craft",
                     "l look   e search   f fight",
                     "equip <name> / drink <name>", "shop / buy <n> / sell <name>",
                     "t type an action", "? help   q quit"):
            y = self._side(left, y, " " + line, self._attr(11))

    def _side(self, left, y, text, attr):
        self._put(y, left, text, attr)
        return y + 1

    def _draw_log(self, top, left, height, w):
        self._put(top - 1, 0, "─" * w, self._attr(11))
        lines: list[tuple[str, str]] = []
        for speaker, text in self.log:
            wrapped = textwrap.wrap(text, w - 2) or [""]
            for ln in wrapped:
                lines.append((speaker, ln))
        for i, (speaker, ln) in enumerate(lines[-height:]):
            attr = self._attr(1, True) if speaker == "gm" else self._attr(11)
            prefix = "» " if speaker == "gm" else "· "
            self._put(top + i, left, prefix + ln, attr)

    def _draw_prompt(self, y, left, w):
        if self.cmd_mode:
            txt = "action> " + self.cmd_buf
            self._put(y, left, txt[:w - 1], self._attr(3, True))
            self._put(y, left + min(len(txt), w - 2), "▏", self._attr(3, True))
        elif self.shoot_mode:
            rw = self._ranged_weapon()
            rng = self._effective_shoot_range(rw) if rw else 0
            self._put(y, left,
                      f"SHOOT direction: WASD/arrows  (range {rng})  Esc=cancel"[:w - 1],
                      self._attr(6, True))
        elif self.status_note:
            self._put(y, left, self.status_note[:w - 1], self._attr(3))
        else:
            hint = ("[WASD] move  [l]ook  [e]search  [t]ype  [c]ommands  "
                    "[x]hack  [p]toolkit  [?]help  [q]uit")
            self._put(y, left, hint[:w - 1], self._attr(11))

    def _draw_overlay(self, h, w):
        if self.overlay == "help":
            self._draw_help(h, w)
        elif self.overlay == "commands":
            self._panel(h, w, "COMMANDS", self._command_lines())
        elif self.overlay == "inventory":
            self._draw_inventory_overlay(h, w)
        elif self.overlay == "shop":
            self._draw_shop_overlay(h, w)
        elif self.overlay == "craft":
            self._draw_craft_overlay(h, w)
        elif self.overlay == "toolkit":
            self._panel(h, w, "ARTHACKTOOLKIT", self._toolkit_lines())
        elif self.overlay == "journal":
            self._panel(h, w, "JOURNAL — clues", self._journal_lines())
        elif self.overlay == "map":
            self._draw_minimap(h, w)
        elif self.overlay == "skills":
            self._panel(h, w, "SKILLS", self._skills_lines())

    def _draw_inventory_overlay(self, h, w):
        lines = self._inventory_lines()
        title = "INVENTORY"
        inner = max(len(title), max((len(ln) for ln in lines), default=0), 24)
        inner = min(inner, w - 6)
        bw = inner + 4

        max_content = h - 4  # lines that fit between borders/title/footer
        need_scroll = len(lines) > max_content
        content_h = max_content if need_scroll else len(lines)
        bh = content_h + 4

        # Find which line is currently selected (starts with "> ")
        cursor_line = next((i for i, ln in enumerate(lines) if ln[:2] == "> "), None)

        if need_scroll and cursor_line is not None:
            if cursor_line < self.inv_scroll:
                self.inv_scroll = cursor_line
            elif cursor_line >= self.inv_scroll + content_h:
                self.inv_scroll = cursor_line - content_h + 1
        elif not need_scroll:
            self.inv_scroll = 0
        self.inv_scroll = max(0, min(self.inv_scroll, len(lines) - content_h))

        visible = lines[self.inv_scroll:self.inv_scroll + content_h]

        top = max(0, (h - bh) // 2)
        left = max(0, (w - bw) // 2)
        acc = self._attr(10, True)
        self._put(top, left, "+" + "-" * (bw - 2) + "+", acc)
        self._put(top, left + 3, f" {title} ", acc)
        for i in range(1, bh - 1):
            self._put(top + i, left, "|", acc)
            self._put(top + i, left + bw - 1, "|", acc)
        self._put(top + bh - 1, left, "+" + "-" * (bw - 2) + "+", acc)

        for i, ln in enumerate(visible):
            if ln.startswith("──"):
                attr = self._attr(10, True)
            elif ln[:1].isalpha() and ln == ln.upper() and ln.strip():
                attr = self._attr(8, True)
            else:
                attr = self._attr(1)
            self._put(top + 2 + i, left + 2, ln[:inner], attr)

        if need_scroll:
            if self.inv_scroll > 0:
                self._put(top + 1, left + bw - 2, "^", acc)
            if self.inv_scroll + content_h < len(lines):
                self._put(top + bh - 2, left + bw - 2, "v", acc)
            foot = f" {self.inv_scroll + 1}-{self.inv_scroll + content_h}/{len(lines)} "
        else:
            foot = " press any key "
        self._put(top + bh - 1, left + bw - 2 - len(foot), foot, self._attr(11))

    def _draw_shop_overlay(self, h, w):
        _, shop = self._nearby_shop()
        if not shop:
            self.overlay = None
            return

        stock = self._shop_stock_entries()
        bag = self._shop_bag_entries()
        title = f"SHOP — {shop.get('name', 'Quartermaster')}"
        is_buy = (self.shop_mode == "stock")
        entries = stock if is_buy else bag

        # Get display order (same grouping used by key handler) and resolve cursor entry
        display_order = self._shop_display_order()
        n = len(display_order)
        self.shop_cursor = max(0, min(self.shop_cursor, n - 1)) if n else 0
        cursor_entry_idx = display_order[self.shop_cursor] if n else -1

        # Group entries by kind for rendering
        from collections import defaultdict
        groups: dict[str, list[tuple[int, object]]] = defaultdict(list)
        for i, e in enumerate(entries):
            k = e.get("kind", "item") if is_buy else getattr(e, "kind", "item")
            if k not in self._SHOP_KIND_ORDER:
                k = "item"
            groups[k].append((i, e))

        # Build display lines (with group headers); track which display line the cursor is on
        display_lines: list[str] = []
        cursor_display_line = 0
        for kind in self._SHOP_KIND_ORDER:
            group = groups.get(kind, [])
            if not group:
                continue
            label = self._SHOP_KIND_LABELS.get(kind, kind.upper())
            display_lines.append(f"── {label} ──")
            for entry_idx, e in group:
                if entry_idx == cursor_entry_idx:
                    cursor_display_line = len(display_lines)
                mark = ">" if entry_idx == cursor_entry_idx else " "
                if is_buy:
                    cost = self._coins_text(int(e.get("value_cp", 0) or 0))
                    display_lines.append(
                        f"{mark} {entry_idx + 1:02d} {e.get('name', 'item')} [{e.get('rarity', 'common')}] {cost}"
                    )
                else:
                    payout = max(1, int(int(getattr(e, "value_cp", 80) or 80) * 0.6))
                    display_lines.append(
                        f"{mark} {e.name} ({e.kind})  → {self._coins_text(payout)}"
                    )
        if not display_lines:
            display_lines = ["  (sold out)" if is_buy else "  (nothing to sell)"]

        # Fixed header / footer text
        buy_lbl   = "[BUY]"  if is_buy else " BUY "
        sell_lbl  = "[SELL]" if not is_buy else " SELL"
        wallet_ln = f"Wallet: {self._coins_text(self.wallet_cp)}"
        tab_ln    = f"  {buy_lbl}  {sell_lbl}  (Tab to switch)"
        action    = "buy" if is_buy else "sell"
        ctrl_ln   = f"Up/Down: move   Enter: {action}   X: inspect   Tab: switch   S/Esc: close"

        # Box width
        all_text = [wallet_ln, tab_ln, ctrl_ln] + display_lines
        inner = max(len(title), max((len(ln) for ln in all_text), default=0), 36)
        inner = min(inner, w - 6)
        bw = inner + 4

        # Box layout (rows from top of box):
        #   0          : top border + title
        #   1          : wallet_ln
        #   2          : tab_ln (tab bar)
        #   3          : separator ────
        #   4..4+sh-1  : scrollable display_lines (sh rows)
        #   4+sh       : ctrl_ln (controls)
        #   4+sh+1     : bottom border + footer text
        # Total bh = sh + 6
        scroll_h = max(1, h - 6)
        bh = scroll_h + 6
        if bh > h:
            bh = h
            scroll_h = max(1, bh - 6)

        # Auto-scroll to keep cursor visible (using display line, not entry index)
        need_scroll = len(display_lines) > scroll_h
        if need_scroll:
            if cursor_display_line < self.shop_scroll:
                self.shop_scroll = cursor_display_line
            elif cursor_display_line >= self.shop_scroll + scroll_h:
                self.shop_scroll = cursor_display_line - scroll_h + 1
            self.shop_scroll = max(0, min(self.shop_scroll, len(display_lines) - scroll_h))
        else:
            self.shop_scroll = 0

        visible = display_lines[self.shop_scroll:self.shop_scroll + scroll_h]

        # Render
        top  = max(0, (h - bh) // 2)
        left = max(0, (w - bw) // 2)
        acc  = self._attr(10, True)
        sep  = "─" * inner

        # Box borders
        self._put(top, left, "+" + "-" * (bw - 2) + "+", acc)
        self._put(top, left + 3, f" {title} ", acc)
        for i in range(1, bh - 1):
            self._put(top + i, left, "|", acc)
            self._put(top + i, left + bw - 1, "|", acc)
        self._put(top + bh - 1, left, "+" + "-" * (bw - 2) + "+", acc)

        # Fixed header rows
        self._put(top + 1, left + 2, wallet_ln[:inner], self._attr(1))
        self._put(top + 2, left + 2, tab_ln[:inner],    self._attr(8, True))
        self._put(top + 3, left + 2, sep[:inner],        acc)

        # Scroll indicators: ^ on separator row, v on ctrl row
        if need_scroll:
            if self.shop_scroll > 0:
                self._put(top + 3, left + bw - 2, "^", acc)
            if self.shop_scroll + scroll_h < len(display_lines):
                self._put(top + 4 + scroll_h, left + bw - 2, "v", acc)

        # Scrollable display lines
        for i, ln in enumerate(visible):
            if ln.startswith("──"):
                attr = self._attr(10, True)
            elif ln[:1] == ">":
                attr = self._attr(3, True)
            else:
                attr = self._attr(1)
            self._put(top + 4 + i, left + 2, ln[:inner], attr)

        # Fixed footer row (controls)
        self._put(top + 4 + scroll_h, left + 2, ctrl_ln[:inner], self._attr(11))

        # Bottom border footer text
        if need_scroll:
            foot = f" {self.shop_scroll + 1}-{min(self.shop_scroll + scroll_h, len(display_lines))}/{len(display_lines)} "
        else:
            n = len(entries)
            foot = f" {n} item{'s' if n != 1 else ''} "
        self._put(top + bh - 1, left + bw - 2 - len(foot), foot, self._attr(11))

    def _draw_craft_overlay(self, h, w):
        stations = self._nearby_stations()
        st_txt = ", ".join(sorted(stations)) if stations else "none nearby"
        counts = self._material_counts()
        mat_txt = "  ".join(f"{m}:{counts.get(m, 0)}"
                            for m in ("wood", "clay", "metal", "gem", "electronics"))
        is_recipes = (self.craft_tab == "recipes")
        tab_ln  = f"  {'[RECIPES]' if is_recipes else ' RECIPES '}  {'[SOCKET]' if not is_recipes else ' SOCKET '}  (Tab)"
        flt_ln  = f"  Filter: {'ON — available only' if self.craft_filter else 'off (all recipes)'}  (F to toggle)"
        stat_ln = f"Stations: {st_txt}   {mat_txt}"
        ctrl_ln = ("Up/Down move  Enter craft  X inspect  F filter  Tab switch  G/Q/Esc close"
                   if is_recipes else
                   "Up/Down move  Enter pick gem  X inspect  Tab switch  G/Q/Esc close")

        # Build scrollable list
        display_lines: list[str] = []
        cursor_display_line = 0

        if is_recipes:
            order = self._craft_recipe_order()
            self.craft_cursor = max(0, min(self.craft_cursor, len(order) - 1)) if order else 0
            from collections import defaultdict
            groups: dict[str, list[int]] = defaultdict(list)
            for ri in order:
                k = CRAFT_RECIPES[ri].get("result", {}).get("kind", "item")
                if k not in self._CRAFT_KIND_ORDER:
                    k = "item"
                groups[k].append(ri)
            pos_in_order = {ri: i for i, ri in enumerate(order)}
            for kind in self._CRAFT_KIND_ORDER:
                grp = groups.get(kind, [])
                if not grp:
                    continue
                display_lines.append(f"── {self._CRAFT_KIND_LABELS[kind]} ──")
                for ri in grp:
                    r = CRAFT_RECIPES[ri]
                    cur_pos = pos_in_order[ri]
                    if cur_pos == self.craft_cursor:
                        cursor_display_line = len(display_lines)
                    mark = ">" if cur_pos == self.craft_cursor else " "
                    ok, reason = self._recipe_status(r)
                    need = ", ".join(f"{n}{m[:1]}" for m, n in r["inputs"].items())
                    st = f"@{r['station']}" if r.get("station") else ""
                    tag = "" if ok else f" <{reason}>"
                    display_lines.append(f"{mark} {r['name']} [{need}{' ' + st if st else ''}]{tag}")
            if not display_lines:
                display_lines = ["  (no recipes available with current materials)"]
        else:
            armor = self._socketable_armor()
            self.craft_cursor = max(0, min(self.craft_cursor, len(armor) - 1)) if armor else 0
            gem_count = len(self._available_gems())
            display_lines.append(f"  Gems in bag: {gem_count}   (needs anvil to socket)")
            display_lines.append(f"  jade/obsidian → +hack   amethyst → +carry   citrine → +slots")
            display_lines.append("")
            if not armor:
                display_lines.append("  (no socketable gear — equip or carry armor/backpack/ranged weapon)")
            for i, (origin, slot, it) in enumerate(armor):
                if i == self.craft_cursor:
                    cursor_display_line = len(display_lines)
                mark = ">" if i == self.craft_cursor else " "
                socks = len(getattr(it, "sockets", []) or [])
                kind = getattr(it, "kind", "")
                if kind == "backpack":
                    cap = self._backpack_capacity() if self.equipped.get("back") is it else int(getattr(it, "bag_capacity", 0))
                    display_lines.append(f"{mark} {it.name} [{origin}] {cap} slots  sockets:{socks}")
                elif getattr(it, "range", 0) > 0:
                    total_r = self._effective_shoot_range(it)
                    display_lines.append(f"{mark} {it.name} [{origin}] ATK {it.attack} range {total_r}  sockets:{socks}")
                else:
                    sb = int(getattr(it, "sight_bonus", 0) or 0)
                    display_lines.append(f"{mark} {it.name} [{origin}] DEF {it.defense} sight+{sb}  sockets:{socks}")

        # Box sizing — same layout as shop overlay
        title = "CRAFTING"
        header_lines = [stat_ln, tab_ln] + ([flt_ln] if is_recipes else [])
        n_header = len(header_lines)  # rows 1..n_header inside box
        all_text = header_lines + [ctrl_ln] + display_lines
        inner = max(len(title), max((len(ln) for ln in all_text), default=0), 36)
        inner = min(inner, w - 6)
        bw = inner + 4

        # rows: 0=border+title, 1..n_header=header, n_header+1..n_header+sh=scroll, n_header+sh+1=ctrl, n_header+sh+2=border
        scroll_h = max(1, h - n_header - 4)
        bh = n_header + scroll_h + 4
        if bh > h:
            bh = h
            scroll_h = max(1, bh - n_header - 4)

        need_scroll = len(display_lines) > scroll_h
        if need_scroll:
            if cursor_display_line < self.craft_scroll:
                self.craft_scroll = cursor_display_line
            elif cursor_display_line >= self.craft_scroll + scroll_h:
                self.craft_scroll = cursor_display_line - scroll_h + 1
            self.craft_scroll = max(0, min(self.craft_scroll, len(display_lines) - scroll_h))
        else:
            self.craft_scroll = 0
        visible = display_lines[self.craft_scroll:self.craft_scroll + scroll_h]

        top  = max(0, (h - bh) // 2)
        left = max(0, (w - bw) // 2)
        acc  = self._attr(10, True)

        # Box borders
        self._put(top, left, "+" + "-" * (bw - 2) + "+", acc)
        self._put(top, left + 3, f" {title} ", acc)
        for i in range(1, bh - 1):
            self._put(top + i, left, "|", acc)
            self._put(top + i, left + bw - 1, "|", acc)
        self._put(top + bh - 1, left, "+" + "-" * (bw - 2) + "+", acc)

        # Fixed header rows
        for hi, ln in enumerate(header_lines):
            attr = self._attr(8, True) if hi == 1 else self._attr(1)
            self._put(top + 1 + hi, left + 2, ln[:inner], attr)
        # Separator after header
        sep_row = top + 1 + n_header
        self._put(sep_row, left + 2, ("─" * inner)[:inner], acc)

        # Scroll indicators
        if need_scroll:
            if self.craft_scroll > 0:
                self._put(sep_row, left + bw - 2, "^", acc)
            if self.craft_scroll + scroll_h < len(display_lines):
                self._put(top + bh - 2, left + bw - 2, "v", acc)

        # Scrollable list
        scroll_top = sep_row + 1
        for i, ln in enumerate(visible):
            if ln.startswith("──"):
                attr = self._attr(10, True)
            elif ln[:1] == ">":
                attr = self._attr(3, True)
            else:
                attr = self._attr(1)
            self._put(scroll_top + i, left + 2, ln[:inner], attr)

        # Fixed footer (controls)
        self._put(top + bh - 2, left + 2, ctrl_ln[:inner], self._attr(11))

        # Bottom border footer text
        if need_scroll:
            foot = f" {self.craft_scroll+1}-{min(self.craft_scroll+scroll_h, len(display_lines))}/{len(display_lines)} "
        else:
            foot = " press any key "
        self._put(top + bh - 1, left + bw - 2 - len(foot), foot, self._attr(11))

        # Gem sub-modal (drawn on top)
        if self.craft_gem_step:
            self._draw_gem_submodal(h, w, top, left, bw, bh, inner)

    def _draw_gem_submodal(self, h, w, craft_top, craft_left, craft_bw, craft_bh, inner):
        gems = self._available_gems()
        acc = self._attr(10, True)

        if self.craft_gem_step == "pick":
            lines = [f"  {i+1}. {g.name}  ({g.desc})" for i, g in enumerate(gems)]
            if not lines:
                lines = ["  (no gems available)"]
            title2 = "PICK GEM TO SOCKET"
            sub_inner = max(len(title2), max((len(ln) for ln in lines), default=0), 28)
            sub_inner = min(sub_inner, w - 6)
            sbw = sub_inner + 4
            sbh = len(lines) + 4
            stop = max(0, craft_top + (craft_bh - sbh) // 2)
            sleft = max(0, craft_left + (craft_bw - sbw) // 2)
            self._put(stop, sleft, "+" + "-" * (sbw - 2) + "+", acc)
            self._put(stop, sleft + 3, f" {title2} ", acc)
            for i in range(1, sbh - 1):
                self._put(stop + i, sleft, "|", acc)
                self._put(stop + i, sleft + sbw - 1, "|", acc)
            self._put(stop + sbh - 1, sleft, "+" + "-" * (sbw - 2) + "+", acc)
            for i, ln in enumerate(lines):
                cursor_here = i == self.craft_gem_cursor
                attr = self._attr(3, True) if cursor_here else self._attr(1)
                mark = ">" if cursor_here else " "
                self._put(stop + 2 + i, sleft + 2, (mark + ln[1:])[:sub_inner], attr)
            foot2 = " Enter select   Esc cancel "
            self._put(stop + sbh - 1, sleft + sbw - 2 - len(foot2), foot2, self._attr(11))

        elif self.craft_gem_step == "confirm" and self.craft_gem_choice and self.craft_gem_item:
            _, _, item = self.craft_gem_item
            gem = self.craft_gem_choice
            preview = self._gem_preview_lines(item, gem)
            title2 = "CONFIRM SOCKET"
            header = f"  Socket into: {item.name}"
            lines = [header] + preview + ["", "  Enter: confirm    Esc: cancel"]
            sub_inner = max(len(title2), max((len(ln) for ln in lines), default=0), 32)
            sub_inner = min(sub_inner, w - 6)
            sbw = sub_inner + 4
            sbh = len(lines) + 4
            stop = max(0, craft_top + (craft_bh - sbh) // 2)
            sleft = max(0, craft_left + (craft_bw - sbw) // 2)
            self._put(stop, sleft, "+" + "-" * (sbw - 2) + "+", acc)
            self._put(stop, sleft + 3, f" {title2} ", acc)
            for i in range(1, sbh - 1):
                self._put(stop + i, sleft, "|", acc)
                self._put(stop + i, sleft + sbw - 1, "|", acc)
            self._put(stop + sbh - 1, sleft, "+" + "-" * (sbw - 2) + "+", acc)
            for i, ln in enumerate(lines):
                attr = self._attr(3, True) if i == 0 else self._attr(1)
                self._put(stop + 2 + i, sleft + 2, ln[:sub_inner], attr)
            foot2 = " Y/Enter=yes   N/Esc=no "
            self._put(stop + sbh - 1, sleft + sbw - 2 - len(foot2), foot2, self._attr(11))

    def _command_lines(self):
        return [
            "MOVEMENT",
            "  Arrow keys / W A S D     move Art (@)   (also h j k)",
            "  onto a + door, push on   open a new area in the dark",
            "",
            "ACTIONS",
            "  l   look around          e / Space  search for hidden things",
            "  f   confront whoever is near (talk / distract / slip past)",
            "  x   hack nearby terminal (!) with ArtHackToolKit",
            "  r   rest and listen a moment",
            "  t or /   type a free action for the game master",
            "",
            "TOOLKIT + DIFFICULTY",
            "  p   open toolkit panel (modules, tools, quickstart)",
            "  typed examples: 'scan', 'hack stealth', 'hack exploit',",
            "                  'hack pivot', 'hack evasion', 'hack recon'",
            "  drink <name>   use <name>",
            "  equip <name>   unequip <weapon|head|chest|legs|shield|amulet|ringN>",
            "  shop           buy <number>   sell <name>",
            "",
            "CRAFTING",
            "  g   open crafting panel (Tab: recipes / socket gems)",
            "  gather wood / : clay - metal ^ gem from rooms and X chests",
            "  craft at an anvil (A) or crafting table (F); socket gems into armor",
            "",
            "PANELS",
            "  i   inventory     m   map of where you've been",
            "  n   journal of clues you've found",
            "  u   skills panel (melee / ranged / tech levels)",
            "  c   this list     ?   help & story",
            "",
            "  q   quit",
        ]

    _INV_KIND_LABELS = {
        "weapon": "WEAPONS", "armor": "ARMOR", "backpack": "BACKPACKS",
        "potion": "POTIONS", "module": "MODULES", "material": "MATERIALS",
    }

    def _inventory_lines(self):
        entries = self._inventory_entries()
        if entries:
            self.inv_cursor = max(0, min(self.inv_cursor, len(entries) - 1))
        tab_name = {"gear": "GEAR", "jewelry": "JEWELRY", "modules": "MODULES"}.get(self.inv_tab, "GEAR")
        lines = [
            f"Coin: {self._coins_text(self.wallet_cp)}",
            f"HP: {self.hp}/{self.max_hp}",
            f"Sight: {self._vision_radius()} (+{self._sight_bonus()})",
            f"Carry: {self._carry_weight():.1f}/{self._effective_max_weight():.1f}",
            f"Tab: {tab_name} (Tab to switch)",
            "",
        ]

        idx = 0
        if self.inv_tab == "modules":
            installed = sorted(self.modules)
            lines.append(f"Installed ({len(installed)}):")
            if installed:
                for mod in installed:
                    tool = MODULE_TO_TOOL.get(mod, "?")
                    desc = TOOL_DESCRIPTIONS.get(tool, "")
                    lines.append(f"  {mod}  →  {tool}")
                    if desc:
                        lines.append(f"      {desc}")
            else:
                lines.append("  none yet — hack terminals and loot enemies to unlock modules")

            bag_mods = [it for it in self.b.inventory if it.kind == "module"]
            lines += ["", f"In bag ({len(bag_mods)}):"]
            if not bag_mods:
                lines.append("  none")
            else:
                for it in bag_mods:
                    mark = ">" if idx == self.inv_cursor else " "
                    low = it.name.lower()
                    mod_key = next((k for k in MODULE_TO_TOOL if k in low), None)
                    status = " (already installed)" if (mod_key and mod_key in self.modules) else " (U to install)"
                    lines.append(f"{mark} {it.char} {it.name}{status}")
                    idx += 1
            lines += ["", "Module controls:",
                      "  Tab switch tab  Up/Down select",
                      "  U install  X inspect  I/Q/Esc close"]

        elif self.inv_tab == "jewelry":
            lines.append("Equipped:")
            for slot in ("amulet",) + RING_SLOTS:
                it = self.equipped.get(slot)
                if it:
                    mark = ">" if idx == self.inv_cursor else " "
                    sb = int(getattr(it, "sight_bonus", 0) or 0)
                    lines.append(f"{mark} {slot}: {it.name} (sight +{sb})")
                    idx += 1
                else:
                    lines.append(f"  {slot}: -")
            lines += ["", "Jewelry bag:"]
            bag_items = [it for it in self.b.inventory if self._is_jewelry_item(it)]
            if not bag_items:
                lines.append("  empty")
            else:
                for it in bag_items:
                    sb = int(getattr(it, "sight_bonus", 0) or 0)
                    mark = ">" if idx == self.inv_cursor else " "
                    lines.append(f"{mark} {it.char} {it.name} (sight +{sb}) {it.weight:.1f}w")
                    idx += 1
            if self.active_effects:
                lines += ["", "Active effects:"]
                for fx in self.active_effects:
                    lines.append(f"  {fx.get('name', 'effect')} ({fx.get('duration', 0)} turns)")
            lines += ["", "Inventory controls:",
                      "  Tab switch tab  Up/Down move",
                      "  Enter/X inspect  E equip/unequip  U use item",
                      "  I/Q/Esc close"]

        else:  # gear
            lines.append("Equipped:")
            for slot in self._core_slots():
                it = self.equipped.get(slot)
                if it:
                    mark = ">" if idx == self.inv_cursor else " "
                    lines.append(f"{mark} {slot}: {it.name} (ATK {it.attack} DEF {it.defense})")
                    idx += 1
                else:
                    lines.append(f"  {slot}: -")
            # Back slot (backpack)
            bp = self.equipped.get("back")
            if bp:
                mark = ">" if idx == self.inv_cursor else " "
                cap = int(getattr(bp, "bag_capacity", 0) or 0)
                cb  = float(getattr(bp, "carry_bonus", 0.0) or 0.0)
                lines.append(
                    f"{mark} back: {bp.name} "
                    f"({len(self.backpack_inv)}/{cap} slots, +{cb:.0f} carry)"
                )
                idx += 1
            else:
                lines.append("  back: - (equip a backpack for extra slots)")

            def _fmt_item(it):
                tail = f" — {it.desc}" if it.desc else ""
                stats = f" (ATK {it.attack} DEF {it.defense})" if (it.attack or it.defense) else ""
                sb = int(getattr(it, "sight_bonus", 0) or 0)
                sight = f" (sight +{sb})" if sb else ""
                return f"{it.char} {it.name}{stats}{sight} {it.weight:.1f}w{tail}"

            # Main inventory
            lines += ["", f"Inventory ({len(self.b.inventory)}/{BASE_INV_SLOTS}):"]
            bag_items = [it for it in self.b.inventory if not self._is_jewelry_item(it)]
            if not bag_items:
                lines.append("  empty")
            else:
                for kind in self._INV_KIND_ORDER:
                    group = [it for it in bag_items if it.kind == kind]
                    if not group:
                        continue
                    lines.append(f"── {self._INV_KIND_LABELS[kind]} ──")
                    for it in group:
                        mark = ">" if idx == self.inv_cursor else " "
                        lines.append(f"{mark} {_fmt_item(it)}")
                        idx += 1
                other = [it for it in bag_items if it.kind not in self._INV_KIND_ORDER]
                if other:
                    lines.append("── OTHER ──")
                    for it in other:
                        mark = ">" if idx == self.inv_cursor else " "
                        lines.append(f"{mark} {_fmt_item(it)}")
                        idx += 1

            # Backpack sub-inventory
            if bp:
                cap = int(getattr(bp, "bag_capacity", 0) or 0)
                lines += ["", f"── BACKPACK ({len(self.backpack_inv)}/{cap} slots) ──"]
                if not self.backpack_inv:
                    lines.append("  empty")
                else:
                    for it in self.backpack_inv:
                        mark = ">" if idx == self.inv_cursor else " "
                        lines.append(f"{mark} {_fmt_item(it)}")
                        idx += 1

            if self.active_effects:
                lines += ["", "Active effects:"]
                for fx in self.active_effects:
                    lines.append(f"  {fx.get('name', 'effect')} ({fx.get('duration', 0)} turns)")
            lines += ["", "Inventory controls:",
                      "  Tab switch tab  Up/Down move",
                      "  Enter/X inspect  E equip/unequip  U use item",
                      "  I/Q/Esc close"]

        return lines

    def _journal_lines(self):
        if not self.journal:
            return ["No clues yet.",
                    "Once you're back inside the castle, SEARCH rooms (e)",
                    "to find notes that point to the hidden portal."]
        lines = [f"Clues found: {self.clues}/{CLUES_FOR_PORTAL}", ""]
        for i, c in enumerate(self.journal, 1):
            lines.append(f"{i}. {c}")
        if self.clues >= CLUES_FOR_PORTAL:
            lines += ["", "The clues align — find the hidden room with the portal (O)."]
        return lines

    def _skills_lines(self):
        def bar(lv: int, cap: int = 20) -> str:
            filled = min(lv, cap)
            return "[" + "█" * filled + "░" * (cap - filled) + f"] Lv{lv}"

        m_lv = self._skill_level("melee")
        r_lv = self._skill_level("ranged")
        m_atk = self._melee_skill_atk_bonus()
        r_rng = self._ranged_skill_range_bonus()

        hack_skills = [
            ("recon",   "port scanning, enumeration, passive intel"),
            ("exploit", "binary vulns, CVE chains, SQLi, web shells"),
            ("creds",   "password cracking, PtH, Kerberoast, NTLM"),
            ("lateral", "pivot, WMI, RDP, PsExec, relay movement"),
            ("persist", "botnet, cron jobs, startup hooks, rootkits"),
            ("evasion", "log wipe, obfuscation, LOLBins, masquerade"),
            ("social",  "phishing, pretexting, credential luring"),
        ]
        mode_map = {
            "recon":    ["recon mode"],
            "exploit":  ["exploit mode", "balanced mode"],
            "creds":    ["bruteforce", "kerberos", "ntlm"],
            "lateral":  ["pivot", "wmi"],
            "persist":  ["botnet install", "evasion mode"],
            "evasion":  ["stealth", "spoof", "lolbin"],
            "social":   ["social mode"],
        }

        snk_bonus = self._stealth_bonus()
        heat_lv = self._heat_level()
        heat_bar = "▓" * heat_lv + "░" * (5 - heat_lv)
        lines = ["WEAPON SKILLS",
                 f"  Melee   {bar(m_lv)}  +{m_atk} ATK bonus",
                 f"  Ranged  {bar(r_lv)}  +{r_rng} range bonus",
                 f"    (3 uses = 1 level; +1 range per 3 levels, +1 ATK per 2 levels)",
                 "",
                 f"ALERT / HEAT  [{heat_bar}] {heat_lv}/5 — {_HEAT_LABELS[heat_lv]}",
                 f"  Raised by: combat, loud hacks (bruteforce/exploit), guard spotting",
                 f"  Lowered by: cameras/alarms/registry hacks, evasion/lolbin modes",
                 f"  Lv3+: reinforcements spawn every {_HEAT_SPAWN_INTVL[max(3,heat_lv)]} turns",
                 f"  Lv3+: hack success −{int(_HEAT_HACK_PENALTY[max(3,heat_lv)]*100)}%  "
                 f"Lv5: LOCKDOWN (−20%)",
                 "",
                 f"STEALTH  (v to toggle — currently {'ACTIVE' if self.stealth_mode else 'off'})",
                 f"  Detection range −{snk_bonus} tiles  (base 3 + evasion÷4)",
                 f"  First-strike ambush: +50% damage, no heat from engagement",
                 f"  Stealth breaks on attack, shooting, or being spotted",
                 "", "HACKING SKILLS  (1 successful use = 1 level)"]
        for sk, desc in hack_skills:
            lv = self.skills.get(sk, 0)
            modes = ", ".join(mode_map.get(sk, []))
            lines.append(f"  {sk:<8} {bar(lv)}")
            lines.append(f"           → {desc}")
            lines.append(f"           → levelled by: {modes}")
        lines += [
            "",
            "HOW TO LEVEL HACKING SKILLS",
            "  On any ! terminal: attempt hack in matching mode",
            "    — skill too low → auto-practice (+1 XP in that skill)",
            "    — success → +1 XP in mode's skill",
            "  On a ROOTED terminal: 'practice <skill>'",
            "    — always +1 XP, safe, no risk of lock-out",
            "    — 1-in-10 chance to find a missing module",
            "  Available: recon exploit creds lateral persist evasion social",
            "",
            "ELECTRONICS  (~)",
            "  Found as loot; craft into modules at tables (g).",
        ]
        return lines

    def _toolkit_lines(self):
        lines = [
            "ArtHackToolKit is a handheld device for terminal intrusions.",
            f"Difficulty: {self.difficulty}",
            "",
            "Unlocked modules:",
        ]
        if self.modules:
            lines.extend(f"  - {m}" for m in sorted(self.modules))
        else:
            lines.append("  - none yet (loot from monsters/villains/animals)")
        lines += ["", "Unlocked tools:"]
        for tool in sorted(self.tools):
            lines.append(f"  - {tool}: {TOOL_DESCRIPTIONS.get(tool, 'loaded')}")
        cred_str = "ACTIVE (T1078 — cred tools auto-satisfied)" if self.valid_credentials else "none"
        fw_str = f"+{int(self.firmware_bonus*100)}% (T1601)" if self.firmware_bonus else "0%"
        # Resource pool status
        res_lines = []
        res_providers = {
            "gpu":     ("security/cameras/scada", "crack_password / bruteforce mode"),
            "cloud":   ("cloud/backup/auth",       "kerberoast / forge_token"),
            "relay":   ("comm/vpn/webshell",        "force_auth / wmi_exec / ntlm mode"),
            "compute": ("power/firmware/dungeon",   "exploit_vuln / shellcode_exec"),
        }
        for res_key, (src, usage) in res_providers.items():
            pool = self.resources.get(res_key, set())
            if pool:
                res_lines.append(f"  [{res_key:>8}] ONLINE  ({', '.join(list(pool)[:2])}) — {usage}")
            else:
                res_lines.append(f"  [{res_key:>8}] OFFLINE — hack {src}, then 'botnet'")
        heat_lv = self._heat_level()
        heat_bar = "▓" * heat_lv + "░" * (5 - heat_lv)
        heat_pen = _HEAT_HACK_PENALTY[heat_lv]
        lines += [
            "",
            f"Valid Credentials: {cred_str}",
            f"Firmware bonus:    {fw_str}",
            f"Tech Skill:        Lv{self.skills['tech']}",
            f"Alert Level:       [{heat_bar}] {heat_lv}/5 {_HEAT_LABELS[heat_lv]}"
            + (f" (−{int(heat_pen*100)}% hack chance)" if heat_pen else ""),
            f"Stealth:           {'ACTIVE (−' + str(self._stealth_bonus()) + ' detect)' if self.stealth_mode else 'off (v to toggle)'}",
            "",
            "Infrastructure Resources (from formerly hacked terminals):",
        ] + res_lines + [
            "",
            f"Coin: {self._coins_text(self.wallet_cp)}",
            f"Carry load: {self._carry_weight():.1f}/{self._effective_max_weight():.1f}",
            "",
            "Terminal workflow:",
            "  scan       — list nearby terminals (dist, control, tier)",
            "  portscan   — reveal open ports on adjacent ! terminal",
            "  vulnscan   — CVEs + tool/resource gaps (needs port_scan tool)",
            "  hack recon — tool+resource preview, no hack effect",
            "  hack <mode>— attempt breach (x key = balanced mode)",
            "  botnet     — after gaining root: install C2 node to bring",
            "               resource online (needs persist_cron/boot + dns/icmp)",
            "  Modes: balanced stealth bruteforce exploit spoof pivot",
            "         evasion social kerberos wmi ntlm lolbin",
            "",
            "Terminal control types (tiered by depth):",
            "  Lv0-1:  doors locks loot gates dungeon security",
            "  Lv2-4:  cameras alarms comm vault power db",
            "  Lv5+:   auth scada radio firmware backup cloud",
            "  Lv7+:   registry webshell vpn container",
        ]
        return lines

    def _panel(self, h, w, title, lines):
        inner = max(len(title), max((len(l) for l in lines), default=0), 24)
        inner = min(inner, w - 6)
        bw, bh = inner + 4, len(lines) + 4
        top = max(0, (h - bh) // 2)
        left = max(0, (w - bw) // 2)
        acc = self._attr(10, True)
        self._put(top, left, "+" + "-" * (bw - 2) + "+", acc)
        self._put(top, left + 3, f" {title} ", acc)
        for i in range(1, bh - 1):
            self._put(top + i, left, "|", acc)
            self._put(top + i, left + bw - 1, "|", acc)
        self._put(top + bh - 1, left, "+" + "-" * (bw - 2) + "+", acc)
        for i, ln in enumerate(lines):
            head = ln[:1].isalpha() and ln == ln.upper() and ln.strip()
            attr = self._attr(8, True) if head else self._attr(1)
            self._put(top + 2 + i, left + 2, ln[:inner], attr)
        foot = " press any key "
        self._put(top + bh - 1, left + bw - 2 - len(foot), foot, self._attr(11))

    def _draw_minimap(self, h, w):
        b = self.b
        seen = b.seen
        self._put(0, 0, " MAP — where you've wandered ".center(w, "─"),
                  self._attr(10, True))
        if not seen:
            self._put(h // 2, max(0, (w - 18) // 2), "Nothing mapped yet.",
                      self._attr(11))
            return
        # Compute bounds from seen set (only discovered terrain).
        xs = [x for x, _ in seen]
        ys = [y for _, y in seen]
        minx, maxx = min(xs), max(xs)
        miny, maxy = min(ys), max(ys)
        bw, bh = maxx - minx + 1, maxy - miny + 1
        scale = max(1, -(-bw // (w - 4)), -(-bh // (h - 4)))
        ow, oh = -(-bw // scale), -(-bh // scale)
        top = max(2, (h - oh) // 2)
        left = max(2, (w - ow) // 2)
        for oy in range(oh):
            for ox in range(ow):
                ch, pr = " ", -1
                for y in range(miny + oy * scale,
                               min(miny + (oy + 1) * scale, maxy + 1)):
                    for x in range(minx + ox * scale,
                                   min(minx + (ox + 1) * scale, maxx + 1)):
                        if (x, y) not in seen:
                            continue  # only show terrain Art has seen
                        if (x, y) == (b.px, b.py):
                            ch, pr = "@", 99
                        else:
                            c = b.grid[y][x]
                            p = _MINI_PR.get(c, -1)
                            if p > pr:
                                ch, pr = c, p
                if ch != " ":
                    self._put(top + oy, left + ox, ch, self._glyph_attr(ch))
        legend = f"@ you  ! term  & cache  % shop  O portal  > gate  < up  V dn  1:{scale}"
        self._put(h - 1, max(0, (w - len(legend)) // 2), legend, self._attr(11))

    def _draw_help(self, h, w):
        lines = [
            "ART — the dungeon escape",
            "",
            "Art wakes in a medieval dungeon. Your journey, in three acts:",
            "  1. ESCAPE the dungeon and slip out of the castle (reach a > gate).",
            "  2. RETURN inside and SEARCH for clues (* notes) — find three.",
            "  3. The clues reveal a hidden room with a PORTAL (O). Step in to win.",
            "",
            "Odd terminals (!) sit on hackable castle wifi networks.",
            "Use your ArtHackToolKit (x) to compromise them and control doors,",
            "gates, and parts of the dungeon itself.",
            "Some locks and cache chests (&) are terminal-bound and cannot be",
            "opened by keys alone.",
            "Shops (%) on each level trade in copper/silver/gold/platinum value,",
            "letting you buy modules, potions, weapons, armor, and utility loot.",
            "Terminal modules are loot from monsters, villains, and wild animals.",
            "",
            "Controls:",
            "  Move ............ Arrow keys or W A S D (also h j k)",
            "  Open new area ... walk onto a + door, then push into the dark beyond",
            "  Look l   Search e/Space   Confront f   Hack x   Rest r   Type t",
            "  Panels .......... i inventory   p toolkit   m map   n journal",
            "  Gear ............ equip <name> / unequip <slot> (ring1..ring10)",
            "  Jewelry ......... rings and amulets can increase sight radius",
            "  Potions ......... drink <name> (active timed effects)",
            "  Shops ........... shop / buy <n> / sell <name> while near %",
            "  Crafting ........ press g near an anvil (A) or table (F) to craft",
            "  Gems ............ socket gems (^) into armor to boost its stats",
            "  Loot ............ every room holds loot; open chests (X) by stepping on",
            "  Difficulty ...... type 'difficulty easy|normal|hard|nightmare'",
            "                   or just say 'too hard' / 'too easy'",
            "  Press c any time for the full list of commands.",
            "  Help ? ..........  Quit q",
            "",
            "The game master (LM Studio) narrates and grows the world as you go.",
            "If it is offline, the dungeon builds itself locally — still playable.",
            "",
            "Press any key to return.",
        ]
        top = max(0, (h - len(lines)) // 2)
        for i, ln in enumerate(lines):
            attr = self._attr(10, True) if i == 0 else self._attr(1)
            self._put(top + i, max(0, (w - 68) // 2), ln, attr)

    def _draw_win(self, h, w):
        art = [
            "  __   __  ______  __   __    ___    __    __  ____  ",
            " / /  / / / __ \\ / /  / /  / _ \\  /  |  /  |/ __/ ",
            "/ /__/ / / /_/ // /__/ /__/ , _/ / / | / / / _/   ",
            "\\____/  \\____//____/____/_/|_| /_/|_|/_/ /___/   ",
            "",
            "Art steps through the portal — and into the warm light of home.",
            "",
            f"Clues found: {self.clues}    Rooms explored: {len(self.b.rooms)}",
            "",
            "THE END.   Press any key to leave the dungeon behind.",
        ]
        top = max(0, (h - len(art)) // 2)
        for i, ln in enumerate(art):
            self._put(top + i, max(0, (w - len(ln)) // 2), ln,
                      self._attr(7, True) if i < 4 else self._attr(10, True))

    def _put(self, y, x, s, attr=0):
        h, w = self.scr.getmaxyx()
        if y < 0 or y >= h or x < 0 or x >= w:
            return
        try:
            self.scr.addnstr(y, x, s, w - x - 1, attr)
        except curses.error:
            pass


# -- helpers -------------------------------------------------------------
def _as_list(v):
    return v if isinstance(v, list) else []


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))

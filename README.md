# ARTHACK — ASCII Dungeon Escape with Cyberpunk Hacking

**ARTHACK** is a terminal ASCII roguelike where medieval dungeon-crawling meets real-world penetration testing techniques. Fight guards, loot treasure, socket gems into weapons and backpacks, and hack castle computer terminals using actual MITRE ATT&CK TTPs.

```
########################################
#  @ . . . . . ! . . . . . . . . . .  #
#  # # # # . . # . . % . . . . . . .  #
#  . . . G . . + . . . . . . . * . .  #
#  . . . . . . . . . . . . . k . = .  #
########################################
  @=Art  G=Guard  !=Terminal  %=Shop  *=Clue  k=Key
```

---

## Table of Contents

1. [Story & Win Condition](#story--win-condition)
2. [Quick Start](#quick-start)
3. [Web Frontend](#web-frontend)
4. [Controls](#controls)
5. [Tiles & Symbols](#tiles--symbols)
6. [Combat](#combat)
7. [Stealth](#stealth)
8. [Alert Level (Heat)](#alert-level-heat)
9. [Weapons & Armor](#weapons--armor)
10. [Backpack System](#backpack-system)
11. [Gem Socketing](#gem-socketing)
12. [Ranged Weapons](#ranged-weapons)
13. [Skills](#skills)
14. [Inventory & Equipment](#inventory--equipment)
15. [Crafting](#crafting)
16. [Shops](#shops)
17. [Terminal Hacking — Overview](#terminal-hacking--overview)
18. [Port Scanning & Vuln Scanning](#port-scanning--vuln-scanning)
19. [Hack Modes](#hack-modes)
20. [Hacking Skills](#hacking-skills)
21. [Modules & Tools](#modules--tools)
22. [Resources & Botnet Nodes](#resources--botnet-nodes)
23. [Terminal Control Types](#terminal-control-types)
24. [Crafting Hack Modules](#crafting-hack-modules)
25. [Architecture](#architecture)
26. [CLI Flags & Environment](#cli-flags--environment)
27. [Requirements](#requirements)

---

## Story & Win Condition

Art wakes in the dungeon of a medieval castle. Three acts:

**Act 1 — Escape:** Find a castle gate (`>`) and leave. Survive guards and locked doors.

**Act 2 — Return:** Go back inside and collect three clues (`*`). These are encrypted notes scattered through the dungeon.

**Act 3 — Portal:** The clues reveal a hidden portal room (`O`). Step through to go home.

Hacked terminals open doors, expose loot, reveal the map, and escalate your access across the dungeon. The deeper you go, the harder the terminals — and the better the rewards.

---

## Quick Start

```bash
cd /mnt/DATA/PycharmProjects/ArtHack

# Terminal (curses) — play directly in your shell
./play.sh
# or:
.venv/bin/python main.py

# Browser — serve the game at http://localhost:5000
./play_web.sh
# or:
.venv/bin/python web.py

# Repeatable seed for testing
.venv/bin/python main.py --seed 42

# Debug kit + triple XP
.venv/bin/python main.py --start-bonus
```

---

## Web Frontend

ART includes a browser-based frontend (`web.py`) powered by **Flask + xterm.js**. It runs the curses game unchanged inside a PTY subprocess and streams terminal I/O to your browser over HTTP long-polling.

### Starting the Web Server

```bash
# Default port 5000
./play_web.sh

# Custom port
PORT=8080 ./play_web.sh

# With start-bonus debug kit
./play_web.sh --start-bonus

# Bind to all interfaces (e.g. for LAN access)
.venv/bin/python web.py --host 0.0.0.0 --port 5000
```

Then open **http://localhost:5000** in any modern browser.

### Web UI Features

- **Full-screen xterm.js terminal** — Catppuccin Mocha theme, auto-resizes with your browser window.
- **New Game button** — restarts the game session without refreshing the page.
- **Help panel** (`?` button) — keyboard shortcut reference overlay.
- **Keyboard passthrough** — all game keys work as normal; browser shortcuts (Ctrl+W, Ctrl+R, F5, etc.) are blocked while the terminal is focused.
- **Auto-resize** — the PTY dimensions sync to the browser window on connect and on every resize, so the game always fills the screen correctly.

### Web CLI Options

```
web.py [--host HOST] [--port PORT] [--start-bonus]

--host HOST      Interface to bind (default: 0.0.0.0)
--port PORT      Port to listen on (default: 5000, or $PORT env var)
--start-bonus    Start every new game session with the debug kit
```

### One Game Session, Multiple Tabs

The server runs a **single shared PTY process**. Multiple browser tabs connect to the same live game. Closing a tab does not end the session — use the **New Game** button to restart.

### Dependencies for Web Mode

```bash
pip install flask flask-socketio
# or with the bundled venv:
.venv/bin/pip install flask flask-socketio
```

---

## Controls

### Movement

| Key | Action |
|-----|--------|
| Arrow keys / `W` `A` `S` `D` / `h` `j` `k` `l` (vim) | Move (`@`) |
| Walk into a `+` door | Open it / generate connected area |
| Walk into an enemy | Melee attack |

### Actions

| Key | Action |
|-----|--------|
| `e` / `Space` | Search the current area for hidden items |
| `f` | Confront nearby enemy or NPC (talk, distract, slip past) |
| `x` | Hack the nearest `!` terminal (balanced mode) |
| `r` | Rest one turn |
| `v` | Toggle stealth / sneak mode |
| `z` | Toggle shoot mode (ranged weapon must be equipped) |

### Panels

| Key | Panel |
|-----|-------|
| `i` | Inventory (Gear / Jewelry / Modules tabs) |
| `g` | Crafting bench (Recipes / Socket Gems tabs) |
| `p` | Shop (when standing on a `%` merchant tile) |
| `t` or `/` | ArtHackToolKit (modules, tools, resources) |
| `u` | Skills panel (weapon + hacking sub-skills) |
| `m` | Minimap of explored areas |
| `n` | Journal — collected clues |
| `c` | Command list |
| `?` | Help & story |
| `q` | Quit |

### Free-text Commands

Press Enter to open the command prompt:

| Command | Effect |
|---------|--------|
| `hack <mode>` | Hack nearest terminal in the specified mode |
| `scan` | Passive wifi scan — list nearby terminals |
| `portscan` / `ps` | Reveal open ports on adjacent terminal |
| `vulnscan` / `vs` | Full CVE + tool/skill/resource gap report |
| `practice <skill>` | Safe skill drill on a rooted terminal |
| `botnet` | Install C2 implant on rooted terminal → resource online |
| `equip <name>` | Equip item from inventory |
| `unequip <slot>` | Unequip a slot (weapon, head, chest, legs, shield, back, amulet, ringN) |
| `drink <name>` | Use a potion or consumable |
| `buy <name>` | Buy from adjacent shop |
| `sell <name>` | Sell item to adjacent shop |
| `shop` | Open shop panel |
| `difficulty easy\|normal\|hard\|nightmare` | Change difficulty |
| `too hard` / `too easy` | Nudge difficulty one step |

---

## Tiles & Symbols

```
@   Art (you)           #   Wall
.   Floor               +   Door (open)
=   Locked door         >   Castle gate (exit)
O   Portal (win)        k   Key
*   Clue note           $   Treasure / item
!   Hackable terminal   %   Shop (green)
~   Electronics (loot)  T   Tree / pillar
V   Chest (loot)        &   Anvil
[   Backpack (loot)     =   Crafting table
^   Gem (loot)          <   Stairs / passage

Uppercase letters = enemies and NPCs
```

---

## Combat

Melee combat triggers automatically when you walk into an enemy. Each exchange:

1. You deal `weapon_attack + melee_skill_bonus` damage, reduced by enemy armour.
2. Enemy deals `enemy_attack` damage, reduced by your equipped armour.
3. HP reaches 0 → enemy dies, drops coin and sometimes a module.

**Enemy types and base stats (normal difficulty):**

| Category | Examples | HP | ATK | ARM |
|----------|----------|----|-----|-----|
| Weak creatures | rat, bat, wolf, hound | 16 | 7 | 1 |
| Guards | guard, jailer, bandit, mercenary | 26 | 8 | 3 |
| Elites | captain, ogre, wraith, necromancer | 34 | 10 | 4 |
| Tech enemies | hacker, operative, engineer, drone | 18 | 6 | 1 |

Difficulty multipliers: easy ×0.85, normal ×1.0, hard ×1.20, nightmare ×1.35.

Enemies have a **sight radius** (typically 6–8 tiles). Once they see you they become *alerted* and chase. Alerted enemies can be calmed by hacking certain terminals (cameras, alarms, pivot mode, lolbin mode).

**Confrontation (`f` key):** Talk your way past an NPC, distract a guard, or attempt a social engineering play without entering full combat.

---

## Stealth

Press `v` to toggle sneak mode. The sidebar shows `[SNEAK −N detect]` while active.

### How Detection Works

Every guard has a `sight_radius` (normally 6–8 tiles). Each turn the engine checks whether you are within that radius **and** in the guard's line of sight. While sneaking, your effective detection range is reduced by the **stealth bonus**:

```
stealth_bonus = 3 + evasion_skill ÷ 4
```

At base (evasion Lv0) you shave 3 tiles off every guard's detection range. At evasion Lv12 you shave 6 tiles — most patrols won't see you until they're practically adjacent.

### Ambush / First Strike

If you attack an enemy (`f` confront, or walk into them) while in sneak mode **before they have spotted you**, you land an ambush:

- **+50% damage** on the first round.
- **No heat generated** from the engagement (the scuffle stays quiet).
- Stealth breaks immediately after the strike — you cannot remain hidden after hitting.

### Stealth Breaks When

- You attack or shoot.
- A guard spots you (their sight radius overcomes your bonus).
- You step out of stealth manually with `v`.

### Guard Patrol Routes

Unalerted guards walk a two-point patrol route generated around their spawn position rather than standing still. They move at **half speed** (one step every 2 turns). Watch their pattern, time your approach, and slip past — or wait for them to turn away before you strike.

Once alerted, guards switch to direct pursuit. De-alerting them (via camera/alarm terminal hacks, or the `pivot`/`lolbin` hack modes) returns them to patrol.

### Stealth Tips

- Enable stealth **before** entering a room with guards, not after you're spotted.
- The `evasion` hacking skill increases your stealth bonus as a side effect — grinding evasion mode hacks makes you physically harder to detect.
- Pairing stealth with the `lolbin` hack mode is particularly powerful: lolbin success de-alerts nearby guards, and the mode itself generates negative heat.

---

## Alert Level (Heat)

Every noisy action raises a global **heat meter** displayed in the sidebar:

```
HEAT [▓▓▓░░] ALERT
```

Heat is a continuous value from 0.0 to 5.0. The integer level gates escalating consequences.

### What Raises Heat

| Action | Heat raised |
|--------|------------|
| Guard spots you | +1.0 |
| You take a hit in combat | +0.3 per round |
| Enemy killed in open combat | +0.5 bonus |
| Ranged shot (hit or miss) | +0.5 |
| Failed bruteforce hack | +0.4 |
| Failed exploit/balanced hack | +0.25 |
| Any failed loud hack attempt | +partial of mode's value |

### What Lowers Heat

| Action | Heat lowered |
|--------|-------------|
| Hack `alarms` terminal | −2.0 |
| Hack `cameras` terminal | −1.5 |
| Hack `security` terminal | −1.0 |
| Hack `registry` terminal | −1.0 |
| Successful `evasion` mode hack | −0.5 |
| Successful `lolbin` mode hack | −0.3 |
| Passive decay | −0.1 per 20 turns |

### Heat Levels and Effects

| Level | Label | Guard sight | Hack penalty | Reinforcements |
|-------|-------|-------------|--------------|----------------|
| 0 | clear | normal | none | none |
| 1 | edgy | +1 tile | none | none |
| 2 | tense | +2 tiles | −5% | none |
| 3 | ALERT | +3 tiles | −8% | every 15 turns |
| 4 | HEAVY ALERT | +4 tiles | −12% | every 10 turns |
| 5 | LOCKDOWN | +5 tiles | −20% | every 5 turns |

At **heat 3+**, the castle commander dispatches reinforcement guards to your last known position. These spawn 10–20 tiles away and arrive already alerted. At heat 4 they are veteran enforcers; at heat 5 elite operatives.

### Managing Heat

The core tension loop: aggressive play raises heat fast, which makes guards harder to avoid and hacking harder to succeed. Backing off to hack a camera or alarm terminal can reset the situation — but that itself requires tools and skill.

**Key strategies:**

- **Quiet hacks first.** Hack `cameras` or `alarms` terminals before doing anything loud — they give you a clean −1.5/−2.0 heat head start.
- **Stay in stealth.** Ambush kills generate zero heat. Open brawls generate heat every round.
- **Use evasion/lolbin modes.** These are the only hack modes that actively lower heat on success, making them worth taking even at lower success rates.
- **Watch the sidebar bar.** Once you see `ALERT` (level 3), prioritise heat reduction before reinforcements arrive — you have ~15 turns.
- **Hacking under LOCKDOWN (level 5)** has a −20% success penalty stacked on top of normal difficulty. Getting here means things went badly; hack a cameras/alarms terminal immediately.

---

## Weapons & Armor

### Weapon Quality

| Quality | Rarity | Typical ATK |
|---------|--------|-------------|
| crude | common | 1–2 |
| sturdy | common / uncommon | 3–5 |
| fine | uncommon / rare | 6–9 |
| masterwork | epic / legendary | 10+ |

### Equipment Slots

| Slot | Key in equip/unequip command |
|------|------------------------------|
| Weapon | `weapon` |
| Head | `armor_head` |
| Chest | `armor_chest` |
| Legs | `armor_legs` |
| Shield | `shield` |
| **Back** | `back` / `backpack` / `pack` |
| Amulet | `amulet` |
| Rings | `ring_1` … `ring_10` |

Rings and amulets are **jewelry** — they appear on the Jewelry tab in the inventory panel (`i` then Tab to switch tabs).

---

## Backpack System

Backpacks occupy the **back** slot and provide two bonuses: extra **carry weight capacity** and a **sub-inventory** that overflows when your main bag is full.

### Main Inventory vs Backpack Sub-Inventory

- Your main inventory holds up to **20 item slots**.
- When the main inventory is full and you walk over an item, it **auto-loots into your worn backpack** (up to the backpack's slot capacity).
- If both are full you get a message telling you what to drop.

### Backpack Tiers

| Tier | Name | Bag slots | +Carry | Weight | Price |
|------|------|-----------|--------|--------|-------|
| 1 | small satchel | 12 | +16.0 | 0.8 | 1gp 80cp |
| 2 | canvas pack | 24 | +32.0 | 1.5 | 3gp 80cp |
| 3 | leather haversack | 40 | +56.0 | 2.5 | 7gp 20cp |
| 4 | iron-frame rucksack | 60 | +88.0 | 4.0 | 14gp |

A **small satchel** spawns on the floor of the starting room every run. Tiers 1–2 are always stocked at shops; tier 3 has a 40% chance.

### Equipping & Swapping Backpacks

- `equip <name>` — equips the backpack; transfers contents from the old one automatically.
- The game refuses to equip a smaller backpack if its capacity is insufficient for the current backpack's contents.
- `unequip back` — moves backpack contents to main inventory if space allows, then removes it.

### Socketing into Backpacks

At an **anvil**, you can socket gems into a backpack (equipped or in bag):

| Gem | Effect |
|-----|--------|
| citrine | +N bag slots (2/4/6 per tier) |
| amethyst | +N carry weight |
| jade / obsidian | +N hacking skill bonus |

---

## Gem Socketing

Gems (`^`) are found as floor loot or bought at shops. At an **anvil** (`&`) you can socket a gem into almost any equipped or inventory item via the crafting panel (`g` → Socket tab).

### Gem Types

| Gem | Bonus | Works best in |
|-----|-------|---------------|
| ruby / garnet | +ATK | armor, ranged weapons |
| sapphire / onyx | +DEF | armor |
| emerald / topaz | +sight | armor |
| diamond | +ATK / +DEF / +sight (mixed) | armor |
| amethyst | +carry weight | armor, backpacks |
| citrine | +bag slots | backpacks |
| jade / obsidian | +hack (all hacking sub-skills) | armor, backpacks |

Gem bonuses scale with dungeon level: `mag = rand(1–3) + level ÷ 3`.

### Socketing Flow

1. Open crafting panel (`g`) → **Socket** tab.
2. Navigate to the item you want to socket into (armor, ranged weapon, or backpack).
3. Press **Enter** — a **PICK GEM** sub-modal opens listing all gems in your inventory.
4. Navigate to the gem and press **Enter** — a **CONFIRM SOCKET** sub-modal shows:
   - The selected gem and its effect
   - Before → after stats for every relevant stat
   - Socket count before → after
5. Press **Enter / Y** to confirm or **Esc / N** to cancel.

Multiple gems can be socketed into one item — each adds its bonus on top.

---

## Ranged Weapons

Equip a bow, crossbow, hand crossbow, shortbow, or slingshot. Press `z` to enter **shoot mode**, then move in a direction to fire in that direction.

- **Base range** is set per weapon type.
- **Sight gems** add range; **attack gems** add damage.
- **Ranged skill** adds further range as you level up.
- **Swift Quiver enchant** (legendary): fire and move in the same turn.

Ranged weapons also appear in dungeon loot and shop stock.

---

## Skills

Open the Skills panel with `u`. Three categories:

### Weapon Skills

| Skill | Gains XP when | Benefit |
|-------|---------------|---------|
| Melee | Killing enemies (2 XP) or hitting (1 XP) | +1 ATK per 2 levels |
| Ranged | Hitting enemies with ranged attacks | +1 range per 3 levels |

3 XP = 1 level for weapon skills.

### Hacking Sub-Skills

Seven independent tracks, each levelled by a specific hack mode or action. 1 successful use = 1 level.

| Skill | How to level | Used for |
|-------|-------------|----------|
| `recon` | recon mode, portscan, vulnscan | entry gate on all terminals |
| `exploit` | exploit mode, balanced mode | binary vulns, web shells, CVE chains |
| `creds` | bruteforce, kerberos, ntlm modes | cracking, PtH, Kerberoast, relay |
| `lateral` | pivot mode, wmi mode | tunnels, WMI exec, RDP, PsExec |
| `persist` | botnet installs, evasion mode | C2 implants, cron jobs, rootkits |
| `evasion` | stealth, spoof, lolbin modes | log wipe, obfuscation, LOLBins — **also increases stealth detection bonus (+1 per 4 levels)** |
| `social` | social mode (even on failure) | phishing, pretexting |

**Jade / obsidian gems** socketed into any equipped item add a flat bonus to all seven hacking sub-skills simultaneously.

Each terminal stores per-skill requirements based on its **control type**, **tier**, and the **dungeon level** it appears on. When you attempt a hack mode and your skill is too low, practice triggers automatically (+1 XP, no penalty). Use `hack recon` to preview all requirements before committing.

---

## Inventory & Equipment

Press `i` to open the inventory panel. It has three tabs (cycle with **Tab**):

### Gear Tab

Shows equipped items (all slots including back/backpack), then items in your main bag grouped by category:

```
── EQUIPPED ──
  weapon:  war axe  (ATK 25)
  back:    leather haversack  (40/40 slots, +56 carry)
── WEAPONS ──
  > iron dagger  (ATK 4)
── BACKPACKS ──
    canvas pack  (24 slots, +32 carry)
── Inventory (3/20): ──
── BACKPACK (0/40 slots) ──
```

- Main bag is capped at **20 item slots**; overflow goes to the worn backpack.
- Base carry weight: **108.0** units. Backpacks and amethyst gems raise this further.
- Navigate with arrow keys / `j` / `k`. Press **Enter** or **E** to equip/use; **X** to inspect.

### Jewelry Tab

Shows equipped rings and amulet, then unequipped jewelry in bag.

### Modules Tab

Lists all **installed hacking modules** and their unlocked tools, followed by any **module items** in your bag (press **U** to install directly from here).

**Item rarities:** common → uncommon → rare → epic → legendary.

---

## Crafting

Open the crafting bench with `g`. Two tabs (cycle with **Tab**):

### Recipes Tab

Recipes are **grouped by category** (MISC, WEAPONS, ARMOR, POTIONS, JEWELRY, MODULES) with scrolling support.

- Navigate with arrow keys / `j` / `k`. Press **Enter** or **C** to craft; **X** to inspect.
- Press **F** to toggle **available-only filter** — hides recipes you can't currently craft.
- A scroll indicator (`^` / `v`) appears when the list exceeds screen height.

You need:
- The correct **materials** in your inventory (wood, clay, metal, gem, electronics).
- A nearby crafting **station** (anvil `&` or table `=`) if the recipe requires one. Some simple recipes can be crafted anywhere.

### Socket Tab

Shows all socketable items: equipped armor / ranged weapon / backpack, plus any armor or backpacks in your bag.

- Navigate to an item and press **Enter** to open the gem picker sub-modal.
- Pick a gem, then confirm in the preview panel — see [Gem Socketing](#gem-socketing) for the full flow.

### Material Categories

| Symbol | Category | Found as |
|--------|----------|----------|
| (plain item) | wood | branches, timber, planks |
| (plain item) | clay | clay shards, fired brick |
| (plain item) | metal | iron scraps, steel ingot |
| `^` | gem | ruby, sapphire, emerald, diamond, amethyst, citrine, jade, obsidian, … |
| `~` | electronics | circuit board, relay chip, signal module, old PCB, logic array |

Electronics are cyan `~` items found as floor loot or in chests. They are the primary ingredient for all hacking modules.

### Craftable Gear (sample)

| Item | Inputs | Station |
|------|--------|---------|
| Torch Bundle | 1 wood | anywhere |
| Iron Dagger | 1 metal | table |
| Wooden Buckler | 2 wood | table |
| Iron Helm | 2 metal | anvil |
| Iron Cuirass | 3 metal | anvil |
| Gemmed Sight Ring | 1 gem + 1 metal | anvil |
| Healing Draught | 2 clay | table |

Hack modules are also craftable — see [Crafting Hack Modules](#crafting-hack-modules).

---

## Shops

Green `%` tiles are merchants. Walk onto one and type `shop` or press `p`.

The shop panel has two tabs (cycle with **Tab**):

### BUY Tab

Stock is grouped by category (WEAPONS, ARMOR, BACKPACKS, JEWELRY, POTIONS, MODULES) with scrolling. Each shop generates **20 items** on spawn.

- Navigate with arrow keys / `j` / `k`. Press **Enter** or **B** to buy; **X** to inspect.
- Items you buy are added to your inventory (or backpack if the main bag is full).

### SELL Tab

Lists everything in your main inventory, also grouped by category.

- Navigate and press **Enter** or **B** to sell. Payout is **60% of item value**.
- Sold items reappear in the shop's buy stock at 85% value.

**General:**
- Shops **restock every 30–90 turns** with 2–5 fresh items (up to a cap of 20).
- Quest-critical items (keys, clues) cannot be sold.
- A scroll range indicator (`1-8/20`) appears at the bottom when the list is long.

---

## Terminal Hacking — Overview

Hackable terminals (`!`) are connected to the castle's internal wifi network. Each terminal controls something physical — doors, cameras, vault locks, SCADA systems, cloud infrastructure, and more.

**Terminals are everywhere** — roughly every other room contains one, each tied to a different network and control system. Many doors and chests are hack-locked to a specific terminal's SSID and can only be opened by hacking that terminal.

### The Full Workflow

```
scan          →  list all terminals within 18 tiles
portscan      →  reveal open ports/services on an adjacent terminal
vulnscan      →  map each port to its CVE, required tool, skill gap, resource gap
hack recon    →  preview requirements without spending a hack attempt
hack <mode>   →  attempt the breach (or press x for balanced mode)
botnet        →  install C2 implant after gaining root → resource comes online
practice <sk> →  drill a specific skill on a terminal you own
```

### Terminal Anatomy

Every terminal has:

| Property | Description |
|----------|-------------|
| SSID | Its network name (e.g., `CastleNet-0-1`, `KERBDC-02`) |
| Control | What it controls (`cameras`, `auth`, `vault`, …) |
| Tier | Difficulty 1–3 (scales skill requirements) |
| Services | Hidden ports revealed by portscan (smb/445, rtsp/554, etc.) |
| Skill reqs | Per-skill level requirements, set by control × tier × dungeon level |
| Hacked | Whether you have root |
| Botnet | Whether a C2 node is installed (resource active) |

### Hack-Locked Doors & Chests

Each terminal `wires` 2–4 nearby locked doors (`=`) and 2–3 cache chests (`V`) to its SSID. These remain sealed until you hack the controlling terminal. Look for `[hack-locked: CastleNet-0-N]` in the door/chest description.

---

## Port Scanning & Vuln Scanning

### `portscan` (always available, no tools needed)

Stand adjacent to a `!` terminal and type `portscan` (or `ps`).

Reveals the open ports/protocols running on that terminal — drawn from real-world service lists matched to the terminal's control type:

| Control | Typical services |
|---------|-----------------|
| doors / locks | smb/445, ldap/389, msrpc/135 |
| cameras | rtsp/554, onvif/2020, http/80 |
| auth | kerberos/88, ldap/389, ntlm/445 |
| db | mysql/3306, mssql/1433, postgresql/5432 |
| scada | modbus/502, dnp3/20000, s7comm/102 |
| container | docker/2375, k8s/6443, https/443 |
| vpn | openvpn/1194, ipsec/500, l2tp/1701 |

### `vulnscan` (requires `port_scan` tool)

Maps every open port to a real CVE or finding, shows the exploit tool needed, your current skill vs the requirement, and any missing infrastructure resources:

```
vulnscan KERBDC-02 — vulnerability assessment:
     88/kerberos    ✗ AS-REP roasting — TGT without pre-auth flag
                  → tool:kerberoast  mode:kerberos  ✗ need creds Lv9
    389/ldap       ✓ Null bind — unauthenticated LDAP enumeration
                  → tool:credential_dump  mode:exploit  ✓
    445/ntlm       ✗ NTLM relay via UNC path coercion
                  → tool:force_auth  mode:ntlm  ✗ need creds Lv7
  [cloud] MISSING — hack a cloud/backup/auth terminal first
```

---

## Hack Modes

Type `hack <mode>` or use the default balanced mode (`x` key). Each mode maps to a different MITRE ATT&CK technique chain, requires different tools and skill levels, and yields different rewards on success.

| Mode | TTP | Primary skill | Success bonus | Heat change | Effect on success |
|------|-----|--------------|--------------|-------------|-------------------|
| `balanced` | T1040+T1110 | exploit | ±0% | +0.30 | Standard — applies terminal effect |
| `stealth` | T1583 | evasion | −8% | **0** | Low footprint; no noise generated |
| `spoof` | T1557+T1583 | evasion | +3% | +0.10 | AiTM signal spoof |
| `bruteforce` | T1110 | creds | +8% | **+0.80** | Reliable but very loud |
| `exploit` | T1203+T1068 | exploit | +4% | +0.50 | Binary exploit chain |
| `pivot` | T1572 | lateral | −5% | +0.10 | De-alerts nearby patrol on success |
| `evasion` | T1070+T1036 | persist | −12% | **−0.50** | Terminal stays re-hackable; logs purged; heat drops |
| `recon` | T1046 | recon | — | **0** | Shows all requirements; no hack effect |
| `social` | T1566 | social | 4–15% fixed | +0.05 | No tools needed; chance scales with social skill |
| `kerberos` | T1558 | creds | +15% | +0.30 | Sets `valid_credentials` session-wide |
| `wmi` | T1047 | lateral | +10% | +0.20 | De-tiers adjacent terminals on success |
| `ntlm` | T1187 | creds | +7% | +0.30 | Replaces `crack_password` with `force_auth`; sets `valid_credentials` |
| `lolbin` | T1218 | evasion | +12% vs security/cameras/alarms | **−0.30** | Silences nearby guards; heat drops on success |

### Session-Wide States

**`valid_credentials`** (set by kerberos or ntlm mode success, or by hacking an `auth` terminal): the credential tools `credential_dump`, `pass_the_hash`, `forge_token`, `pass_the_ticket`, `kerberoast` are automatically satisfied — you don't need to carry those modules.

**`firmware_bonus`** (set by hacking `firmware` terminals): each hack adds +5% to all future hack success chances, capped at +20%.

---

## Hacking Skills

### Skill Requirements

When you type `hack <mode>`, the engine checks the terminal's per-skill requirement for that mode. If your skill is too low:

1. A single XP point is added to that skill (practice triggered automatically).
2. The 1-in-20 bonus fires: either reduces the terminal's skill requirement by 1, or grants you a missing module from the practice session.

### Practice on Rooted Terminals

On a terminal you already own (`hacked: true`), type `practice <skill>`:

- **Always** grants +1 XP in that skill (no RNG gate).
- **1-in-10** chance of discovering a missing module for that terminal.
- Use partial names: `practice cred`, `practice lat`, `practice ev`.

Available skills for practice: `recon`, `exploit`, `creds`, `lateral`, `persist`, `evasion`, `social`.

### Skill Requirement Scaling

```
requirement = (base_for_control_type + dungeon_level ÷ 3) × (1 + (tier − 1) × 0.5)
```

A Tier 2 `auth` terminal on dungeon level 3 needs `creds` Lv9 for kerberos mode. Plan ahead by running `vulnscan` or `hack recon` early.

---

## Modules & Tools

Modules are `$` items found as enemy drops or crafted from electronics. Each module unlocks exactly one tool. You can see all your unlocked modules and tools in the **ArtHackToolKit panel** (`t` key), or on the **Modules tab** of the inventory panel (`i` → Tab → Tab).

44 modules across 7 tiers (MITRE ATT&CK references):

### Tier 1 — Initial Access & Handshake
| Module | Tool | TTP |
|--------|------|-----|
| sniffer_patch | capture_handshake | T1040 |
| cipher_kernel | crack_password | T1110 |
| radio_firmware | signal_spoof | T1583 |
| logic_probe | circuit_bypass | T1574 |

### Tier 2 — Escalation & Persistence
| Module | Tool | TTP |
|--------|------|-----|
| kernel_implant | privilege_escalation | T1068 |
| override_bus | door_override | T1098 |
| daemon_rootkit | root_shell | T1014 |
| chest_decoder | loot_decrypt | T1560 |

### Tier 3 — Credential & Lateral Movement
| Module | Tool | TTP |
|--------|------|-----|
| mimikatz_stub | credential_dump | T1003 |
| keylog_implant | keylogger | T1056 |
| hash_extractor | pass_the_hash | T1550.002 |
| ssh_tunneler | pivot_relay | T1572 |

### Tier 4 — Evasion & Discovery
| Module | Tool | TTP |
|--------|------|-----|
| log_wiper | erase_logs | T1070 |
| process_mask | process_spoof | T1036 |
| port_scanner | port_scan | T1046 |
| arp_sweep_kit | host_discovery | T1018 |

### Tier 5 — Exploitation & Impact
| Module | Tool | TTP |
|--------|------|-----|
| buffer_exploit | exploit_vuln | T1203 |
| sql_injector | sql_inject | T1190 |
| cam_jammer | camera_blind | T1562 |
| arp_spoofer | arp_poison | T1557 |

### Tier 6 — Credential Forgery, Execution & Exfil
| Module | Tool | TTP |
|--------|------|-----|
| kerberoast_kit | kerberoast | T1558.003 |
| golden_ticket | forge_token | T1558.001 |
| pass_ticket | pass_the_ticket | T1550.003 |
| shellcode_loader | shellcode_exec | T1055.001 |
| uac_bypass | uac_escape | T1548.002 |
| wmi_implant | wmi_exec | T1047 |
| rdp_hijack | remote_desktop | T1021.001 |
| psexec_kit | remote_exec | T1021.002 |
| cron_backdoor | persist_cron | T1053.003 |
| startup_hook | persist_boot | T1547.001 |
| dns_tunnel | dns_exfil | T1071.004 |
| firmware_patch | flash_firmware | T1601 |

### Tier 7 — Relay, LOLBins, Collection & Covert Channels
| Module | Tool | TTP |
|--------|------|-----|
| ntlm_relay | force_auth | T1187 |
| lolbin_wrapper | lolbin_exec | T1218 |
| token_stealer | token_impersonate | T1134 |
| bits_scheduler | bits_job | T1197 |
| obfuscator_kit | obfuscate | T1027 |
| dcom_exploit | dcom_exec | T1021.003 |
| screen_cap | screenshot | T1113 |
| cookie_stealer | steal_cookie | T1539 |
| browser_dump | browser_creds | T1555 |
| icmp_tunnel | icmp_covert | T1095 |
| share_scanner | share_harvest | T1039 |
| env_harvester | env_creds | T1552 |

### Where to Get Modules

- **Enemy drops:** every enemy kill has a chance to drop a module appropriate to that enemy type.
- **Shops (`%`):** stock rotates every 30–90 turns. Always carries at least 3 module items.
- **Crafting:** all 44 modules can be crafted from electronics (`~`) at tables or anvils.
- **Inventory Modules tab:** press `U` on a module item in bag to install it immediately.

---

## Resources & Botnet Nodes

Some tools require **infrastructure resources** to function — hardware that can't run on your handheld device alone. Resources come online when you **hack a terminal that provides them** and then **install a botnet node**.

### Resource Types

| Resource | Required by tools | Provided by hacking |
|----------|------------------|---------------------|
| `[gpu]` | crack_password | security, cameras, scada terminals |
| `[cloud]` | kerberoast, forge_token | cloud, backup, auth terminals |
| `[relay]` | force_auth, wmi_exec, remote_exec | comm, vpn, webshell terminals |
| `[compute]` | exploit_vuln, shellcode_exec | power, firmware, dungeon terminals |

### Botnet Install Workflow

1. **Hack** a resource-providing terminal (e.g., a `cameras` terminal for GPU).
2. Stand adjacent to the rooted terminal and type `botnet`.
3. Requires:
   - A **persistence tool**: `persist_cron` (from `cron_backdoor` module) **or** `persist_boot` (from `startup_hook` module).
   - A **C2 channel**: `dns_exfil` (from `dns_tunnel` module) **or** `icmp_covert` (from `icmp_tunnel` module).
4. The implant is installed (T1053 + T1071), the terminal state becomes `botnet`, and the resource goes **ONLINE** for the rest of the session.
5. Grants +1 `persist` skill XP.

Once a resource is online, all future hacks that require it are automatically satisfied — the hacked terminal hosts that capability remotely.

### When Hitting a Resource Gate

If you try to hack a terminal and a required resource is offline, the engine tells you exactly which terminal types to hack first:

```
Missing infrastructure resources:
  crack_password needs [gpu] — hack a security/cameras/scada terminal first
```

Check current resource status anytime in the **ArtHackToolKit panel** (`t`).

---

## Terminal Control Types

Control types are tiered by dungeon depth. Deeper = more powerful effects and higher skill requirements.

### Tier by Depth

| Depth | Control types available |
|-------|------------------------|
| Levels 0–1 | doors, locks, loot, gates, dungeon, security |
| Levels 2–4 | + cameras, alarms, comm, vault, power, db |
| Levels 5–6 | + auth, scada, radio, firmware, backup, cloud |
| Levels 7+ | + registry, webshell, vpn, container |

### Effects on Successful Hack

| Control | Effect |
|---------|--------|
| `doors` | Unlocks all standard locked doors on the level |
| `locks` | Same as doors + unlocks key-locked doors |
| `loot` | Spawns 2–4 items near you |
| `gates` | Opens castle gates (exit doors) |
| `security` | De-alerts guards within 10 tiles, shrinks sight radius — **heat −1.0** |
| `cameras` | De-alerts all guards, shrinks sight radius, blinds alarms — **heat −1.5** |
| `alarms` | De-alerts all guards on level, opens alarm-linked gates — **heat −2.0** |
| `comm` | De-alerts nearby guards; opens communication-locked passages |
| `power` | Opens power-locked doors; may blind some guards temporarily |
| `db` | Spawns rare loot (database exfil) |
| `vault` | Opens vault doors; spawns 3 high-value items |
| `auth` | Sets `valid_credentials = True` session-wide |
| `scada` | De-alerts guards; opens SCADA-controlled gates |
| `radio` | Spawns a free random module from radio intercept |
| `firmware` | Adds +5% to `firmware_bonus` (max 20%) |
| `backup` | Full HP restore + full map reveal |
| `cloud` | Spawns 4 rare/epic/legendary items |
| `registry` | Reduces all enemy sight radii by 3; unlocks registry-linked doors — **heat −1.0** |
| `webshell` | Resets all previously hacked terminals to re-hackable at lower tier; drops access token |
| `vpn` | Reveals 65% of map; forces all locked doors open |
| `container` | Teleports you to a random floor tile; spawns 2 legendary artefacts |
| `dungeon` | Full map reveal; may spawn clues or keys in late-game phases |

---

## Crafting Hack Modules

55 total recipes (11 gear + 44 modules). All module recipes require **electronics (`~`)** and sometimes metal, clay, or gem. Crafted at an **anvil** (`&`) or **table** (`=`), or anywhere for the simplest ones.

The recipe list is **grouped by category** and **scrollable**. Press **F** in the Recipes tab to show only recipes you can currently craft.

Sample module recipes:

| Recipe | Inputs | Station | Unlocks |
|--------|--------|---------|---------|
| Sniffer Patch | 1 electronics | anywhere | capture_handshake |
| Port Scanner | 1 electronics | anywhere | port_scan |
| Cipher Kernel | 2 electronics | table | crack_password |
| Mimikatz Stub | 2 electronics + 1 metal | table | credential_dump |
| Kerberoast Kit | 3 electronics + 1 gem | anvil | kerberoast |
| NTLM Relay | 2 electronics + 1 metal | table | force_auth |
| LOLBin Wrapper | 2 electronics | table | lolbin_exec |
| Firmware Patch | 3 electronics + 2 metal | anvil | flash_firmware |
| DNS Tunnel | 2 electronics + 1 metal | table | dns_exfil |
| ICMP Tunnel | 2 electronics + 1 metal | anvil | icmp_covert |
| Cron Backdoor | 1 electronics + 1 clay | table | persist_cron |

Crafting a module automatically installs it — it goes straight into your toolkit without taking inventory space.

---

## Architecture

```
main.py        CLI entry point — launches the curses game
game.py        curses UI + full game loop + all gameplay mechanics
board.py       authoritative world state (grid, items, entities, rooms)
               + procedural dungeon generation
web.py         Flask web frontend — runs main.py inside a PTY,
               streams I/O to browser via xterm.js + Socket.IO
templates/     index.html — xterm.js browser terminal UI
static/        CSS / JS assets for the web frontend
play.sh        terminal launcher (runs main.py)
play_web.sh    browser launcher (runs web.py)
```

### Key Design Points

- **Procedural dungeon master.** `board.py` generates rooms, corridors, enemies, loot, terminals, keys, and clues — no network connection required.
- **Board is authoritative.** The world lives in `board.py`. `game.py` reads it for rendering and writes back mutations; `web.py` never touches it.
- **World size:** 450 × 150 tiles with a scrolling camera centred on the player.
- **Scrolling minimap** (`m`) renders the full explored area at ~1/6 scale.
- **Terminal density:** ~50% of rooms contain a hackable terminal. Many locked doors and chests are wired to a specific terminal's SSID.
- **Web PTY bridge:** `web.py` opens a PTY, forks `main.py` into it, and relays bytes between the PTY and xterm.js over Socket.IO long-polling. Terminal resize is handled with `TIOCSWINSZ` + `SIGWINCH`.

---

## CLI Flags & Environment

### Terminal game (`main.py`)

```
main.py [--seed N] [--start-bonus]

--seed N         Seed the RNG for a repeatable dungeon layout
--start-bonus    Spawn a debug kit and triple XP gain (see below)
```

### Web frontend (`web.py`)

```
web.py [--host HOST] [--port PORT] [--start-bonus]

--host HOST      Interface to bind (default: 0.0.0.0)
--port PORT      Port number (default: 5000, or $PORT env var)
--start-bonus    Start every game session with the debug kit
```

### --start-bonus

Intended for testing and exploration. On game start you receive:

- **leather haversack** (40 slots, +56 carry) — equip with `equip leather haversack`
- **war axe** (25 ATK, fine/rare)
- **2× citrine** gems (+4 bag slots each)
- **2× amethyst** gems (+16 carry each)
- **10× random gems** (mixed types)
- **10 modules** (tiers 1–3 unlocked immediately)
- **XP ×3** on all melee kills, ranged hits, and social engineering attempts

---

## Requirements

### Terminal game

- **Python 3.10+** (uses `match`, union types, `str | None`)
- **Linux terminal**, at least **80 × 24** characters
- `curses` — ships with CPython on all Linux distributions
- **No pip dependencies** required

### Web frontend

- All terminal requirements above
- `flask` and `flask-socketio` (install via pip)
- Any modern browser (Chrome, Firefox, Edge, Safari)

```bash
# Install web dependencies
.venv/bin/pip install flask flask-socketio

# Verify everything works
.venv/bin/python -c "import game; import board; import web; print('OK')"

# Play in terminal
./play.sh

# Play in browser
./play_web.sh
# then open http://localhost:5000
```

---

*ART is a personal project. The hacking mechanics are modelled after MITRE ATT&CK for educational purposes. All exploitation happens inside a fictional ASCII dungeon.*

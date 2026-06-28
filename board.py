"""Authoritative gameboard model.

The Python engine remembers the entire world. The LLM only ever supplies the
opening board and, after that, deltas (new rooms / items / characters / removals)
which are merged here. A procedural fallback keeps the game fully playable when
the model is offline or returns something unusable.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

WORLD_W = 450
WORLD_H = 150
VOID = " "

# Movement is blocked by walls, locked doors, the void, and characters.
BLOCKING = {"#", "=", VOID}

DIRS = {
    "north": (0, -1),
    "south": (0, 1),
    "east": (1, 0),
    "west": (-1, 0),
}
OPPOSITE = {"north": "south", "south": "north", "east": "west", "west": "east"}

# Glyphs the engine recognises for items so model grids can seed pickups.
ITEM_CHARS = {"k": "key", "*": "clue", "$": "treasure"}

# Vision / fog of war ----------------------------------------------------------
_VISION_RADIUS = 16
# Precomputed ray directions (720 angles) so compute_visible skips trig each call.
_RAYS: list[tuple[float, float]] = [
    (math.cos(2 * math.pi * i / 720), math.sin(2 * math.pi * i / 720))
    for i in range(720)
]
_OPAQUE = {"#", "="}  # cells that block line-of-sight (VOID implicitly stops rays)

NUM_LEVELS = random.randint(8, 12)
ZONE_COLS = 7
ZONE_ROWS = 4   # 7×4 = 28 zones per level — smaller zones → shorter corridors

_LEVEL_THEMES = [
    ["Torture Chamber", "Cell Block", "Guard Barracks", "Storage Pit", "Rat Warren",
     "Dark Passage", "Prison Row", "Cave Vault", "Underground Hall",
     "Flooded Tunnel", "Coal Store", "Oubliette", "Sewer Junction", "Bone Pit", "The Pit"],
    ["Dungeon Hall", "Lower Barracks", "Water Cistern", "Weapons Store",
     "Guard Room", "Service Tunnel", "Servant Quarters", "Root Cellar",
     "Barrel Room", "Stone Passage", "Laundry", "Supply Cache",
     "Watch Post", "Side Chamber", "Guardroom"],
    ["Castle Cellar", "Wine Vault", "Armory", "Stable", "Blacksmith",
     "Chapel Crypt", "Archive Basement", "Gatehouse Tunnel",
     "Trophy Room", "Grain Store", "Secret Passage", "Storeroom",
     "Guard Post", "Scullery", "Pantry"],
    ["Great Hall", "Throne Antechamber", "Guard Tower", "Courtyard",
     "Barracks", "Captain's Quarters", "Watchtower", "Meeting Chamber",
     "Feasting Hall", "Chapel", "Royal Guard Post", "Gate House",
     "Parapet Room", "Sword Hall", "Armoury"],
]

_LEVEL_NAMES = [
    "Deep Dungeon" if i == 0 else
    "Castle" if i == NUM_LEVELS - 1 else
    f"Dungeon Stratum {i + 1}"
    for i in range(NUM_LEVELS)
]


@dataclass
class Item:
    id: str
    x: int
    y: int
    char: str
    name: str
    desc: str = ""
    kind: str = "item"
    slot: str = "none"        # none|weapon|armor_head|armor_chest|armor_legs|shield|ring|amulet|back
    attack: int = 0
    defense: int = 0
    quality: str = "common"
    rarity: str = "common"
    enchantment: str = ""
    sight_bonus: int = 0
    weight: float = 1.0
    value_cp: int = 0
    material: str = ""        # wood|clay|gem|metal for crafting stock, else ""
    sockets: list = field(default_factory=list)  # gems socketed into armor/ranged weapon
    range: int = 0            # shoot range in tiles (0 = melee)
    range_bonus: int = 0      # extra range from socketed sight gems
    carry_bonus: float = 0.0  # extra carry-weight capacity (backpacks, strength gems)
    bag_capacity: int = 0     # item slots provided when worn in "back" slot (backpacks only)
    bag_slots: int = 0        # bonus bag slots granted by a gem (citrine) when socketed
    hack_bonus: int = 0       # bonus to hacking sub-skills from a socketed gem (obsidian/jade)


@dataclass
class Entity:
    id: str
    x: int
    y: int
    char: str
    name: str
    desc: str = ""
    hostile: bool = False
    sight_radius: int = 8
    alerted: bool = False
    hp: int = -1              # -1 = not yet initialised (set on first damage/combat)
    max_hp: int = -1


@dataclass
class Room:
    id: str
    name: str
    x0: int
    y0: int
    w: int
    h: int
    narration: str = ""

    def contains(self, x: int, y: int) -> bool:
        return self.x0 <= x < self.x0 + self.w and self.y0 <= y < self.y0 + self.h


@dataclass
class Board:
    grid: list[list[str]] = field(default_factory=list)
    rooms: dict[str, Room] = field(default_factory=dict)
    items: dict[str, Item] = field(default_factory=dict)
    entities: dict[str, Entity] = field(default_factory=dict)
    doors: dict[tuple[int, int], dict] = field(default_factory=dict)
    specials: dict[tuple[int, int], dict] = field(default_factory=dict)
    inventory: list[Item] = field(default_factory=list)
    px: int = 0
    py: int = 0
    phase: str = "escape"
    _seq: int = 0
    seen: set = field(default_factory=set)      # all positions Art has ever seen
    visible: set = field(default_factory=set)    # positions visible right now
    level: int = 0
    width: int = WORLD_W
    height: int = WORLD_H
    dungeon_generated: bool = False
    _level_store: list = field(default_factory=list)
    stair_links: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.grid:
            self.grid = [[VOID] * self.width for _ in range(self.height)]

    # -- visibility ------------------------------------------------------
    def compute_visible(self, radius: int = _VISION_RADIUS) -> None:
        """Ray-cast LOS from the player. Updates self.visible and self.seen.

        Casts 720 rays outward. VOID stops the ray without being added (it is
        unexplored space). Opaque cells (#, =) are added (you see the wall)
        then stop the ray. Transparent cells are added and the ray continues.
        """
        px, py = self.px, self.py
        vis: set = {(px, py)}
        grid = self.grid
        for cos_a, sin_a in _RAYS:
            for r in range(1, radius + 1):
                cx = int(px + cos_a * r + 0.5)
                cy = int(py + sin_a * r + 0.5)
                if not (0 <= cx < WORLD_W and 0 <= cy < WORLD_H):
                    break
                cell = grid[cy][cx]
                if cell == VOID:
                    break                    # unexplored space blocks sight
                vis.add((cx, cy))
                if cell in _OPAQUE:
                    break                    # wall/locked-door is visible but blocks
        self.visible = vis
        self.seen.update(vis)

    # -- ids -------------------------------------------------------------
    def _id(self, prefix: str) -> str:
        self._seq += 1
        return f"{prefix}{self._seq}"

    # -- grid access -----------------------------------------------------
    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def get(self, x: int, y: int) -> str:
        if not self.in_bounds(x, y):
            return VOID
        return self.grid[y][x]

    def setc(self, x: int, y: int, ch: str) -> None:
        if self.in_bounds(x, y):
            self.grid[y][x] = ch

    def occupied(self, x: int, y: int) -> bool:
        return self.get(x, y) != VOID

    def is_blocked(self, x: int, y: int) -> bool:
        if not self.in_bounds(x, y):
            return True
        if self.get(x, y) in BLOCKING:
            return True
        return self.entity_at(x, y) is not None

    # -- lookups ---------------------------------------------------------
    def item_at(self, x: int, y: int) -> Item | None:
        for it in reversed(list(self.items.values())):
            if it.x == x and it.y == y:
                return it
        return None

    def _items_at(self, x: int, y: int) -> list[Item]:
        return [it for it in self.items.values() if it.x == x and it.y == y]

    def _refresh_item_glyph(self, x: int, y: int) -> None:
        if self._items_at(x, y):
            self.setc(x, y, self._items_at(x, y)[-1].char)
        elif self.get(x, y) in ITEM_CHARS:
            self.setc(x, y, ".")

    def entity_at(self, x: int, y: int) -> Entity | None:
        for e in self.entities.values():
            if e.x == x and e.y == y:
                return e
        return None

    def room_at(self, x: int, y: int) -> Room | None:
        for r in self.rooms.values():
            if r.contains(x, y):
                return r
        return None

    # -- mutation --------------------------------------------------------
    def remove_id(self, ident: str) -> str | None:
        if ident in self.items:
            it = self.items.pop(ident)
            self._refresh_item_glyph(it.x, it.y)
            return f"the {it.name}"
        if ident in self.entities:
            e = self.entities.pop(ident)
            return e.name
        return None

    def add_item(self, x: int, y: int, char: str, name: str, desc: str = "",
                 kind: str = "item", slot: str = "none", attack: int = 0,
                 defense: int = 0, quality: str = "common",
                 rarity: str = "common", enchantment: str = "",
                 sight_bonus: int = 0, weight: float = 1.0,
                 value_cp: int = 0, material: str = "",
                 range: int = 0, carry_bonus: float = 0.0,
                 bag_capacity: int = 0, bag_slots: int = 0,
                 hack_bonus: int = 0) -> Item:
        it = Item(self._id("it"), x, y, char or "*", name, desc, kind)
        it.slot = slot
        it.attack = max(0, int(attack))
        it.defense = max(0, int(defense))
        it.quality = quality or "common"
        it.rarity = rarity or "common"
        it.enchantment = enchantment or ""
        it.sight_bonus = max(0, int(sight_bonus))
        it.weight = max(0.1, float(weight))
        it.value_cp = max(0, int(value_cp))
        it.material = material or ""
        it.range = max(0, int(range))
        it.carry_bonus = float(carry_bonus)
        it.bag_capacity = max(0, int(bag_capacity))
        it.bag_slots = max(0, int(bag_slots))
        it.hack_bonus = max(0, int(hack_bonus))
        self.items[it.id] = it
        if self.get(x, y) not in BLOCKING:
            self._refresh_item_glyph(x, y)
        return it

    def add_entity(self, x: int, y: int, char: str, name: str, desc: str = "",
                   hostile: bool = False) -> Entity:
        e = Entity(self._id("en"), x, y, (char or "?")[0], name, desc, hostile)
        self.entities[e.id] = e
        return e

    def add_terminal(self, x: int, y: int, ssid: str, control: str,
                     tier: int = 1) -> None:
        """Place a hackable terminal tile tied to a wifi network."""
        if self.get(x, y) != ".":
            return
        self.setc(x, y, "!")
        self.specials[(x, y)] = {
            "kind": "terminal",
            "ssid": ssid,
            "control": control,
            "tier": max(1, min(3, int(tier))),
            "hacked": False,
        }

    def add_shop(self, x: int, y: int, name: str, stock: list[dict]) -> None:
        """Place a shop tile with per-level stock."""
        if self.get(x, y) != ".":
            return
        self.setc(x, y, "%")
        self.specials[(x, y)] = {
            "kind": "shop",
            "name": name,
            "stock": list(stock),
        }

    def add_hack_chest(self, x: int, y: int, ssid: str,
                       loot_name: str, loot_desc: str,
                       loot_char: str = "$", loot_kind: str = "item") -> None:
        """Place a locked cache chest that can only be opened by terminal hacks."""
        if self.get(x, y) != ".":
            return
        self.setc(x, y, "&")
        self.specials[(x, y)] = {
            "kind": "hack_chest",
            "ssid": ssid,
            "locked": True,
            "loot": {
                "char": loot_char,
                "name": loot_name,
                "desc": loot_desc,
                "kind": loot_kind,
            },
        }

    def add_station(self, x: int, y: int, station: str) -> None:
        """Place a crafting station tile (anvil 'A' or crafting table 'F')."""
        if self.get(x, y) != ".":
            return
        glyph = "A" if station == "anvil" else "F"
        self.setc(x, y, glyph)
        self.specials[(x, y)] = {"kind": "station", "station": station}

    def add_loot_chest(self, x: int, y: int, loot: list[dict]) -> None:
        """Place a freely-openable loot chest 'X' holding item specs."""
        if self.get(x, y) != ".":
            return
        self.setc(x, y, "X")
        self.specials[(x, y)] = {"kind": "loot_chest", "loot": list(loot),
                                 "opened": False}

    # -- room stamping ---------------------------------------------------
    def _rect_free(self, x0: int, y0: int, w: int, h: int) -> bool:
        if x0 < 1 or y0 < 1 or x0 + w > self.width - 1 or y0 + h > self.height - 1:
            return False
        for y in range(y0, y0 + h):
            for x in range(x0, x0 + w):
                if self.occupied(x, y):
                    return False
        return True

    def _stamp_box(self, x0: int, y0: int, w: int, h: int,
                   grid: list[str] | None) -> None:
        """Stamp a sealed room. Borders are walls (doors may pierce them);
        interiors are always open floor so small-model 'maze' walls can never
        trap the player away from an exit. Items/stairs/portal are honoured."""
        for j in range(h):
            for i in range(w):
                edge = i == 0 or j == 0 or i == w - 1 or j == h - 1
                g = grid[j][i] if grid and j < len(grid) and i < len(grid[j]) else ""
                if edge:
                    ch = g if (g and g in "+=") else "#"
                elif g and g in ".+=<>kO*$!":
                    ch = g
                else:  # model walls, letters, '@', junk -> walkable floor
                    ch = "."
                self.setc(x0 + i, y0 + j, ch)

    def place_start_room(self, spec: dict) -> None:
        """Stamp the opening room near the left-centre of the world."""
        grid = _clean_grid(spec.get("grid"))
        w, h = _grid_dims(grid, default=(11, 7))
        x0, y0 = 6, WORLD_H // 2 - h // 2
        self._stamp_box(x0, y0, w, h, grid)
        room = Room(spec.get("id", "cell"), spec.get("name", "Dungeon Cell"),
                    x0, y0, w, h, spec.get("narration", ""))
        self.rooms[room.id] = room
        self._register_room_contents(room, spec, grid)
        sx, sy = spec.get("start", [w // 2, h // 2])
        self.px, self.py = x0 + _clampi(sx, 1, w - 2), y0 + _clampi(sy, 1, h - 2)
        # If start landed on a wall, nudge to first floor cell.
        if self.get(self.px, self.py) != ".":
            self.px, self.py = self._first_floor(room)
        # Guarantee Art can actually leave the opening room.
        self._ensure_frontier_door(room, exclude=(self.px, self.py))

    def _first_floor(self, room: Room) -> tuple[int, int]:
        for y in range(room.y0 + 1, room.y0 + room.h - 1):
            for x in range(room.x0 + 1, room.x0 + room.w - 1):
                if self.get(x, y) == ".":
                    return x, y
        return room.x0 + 1, room.y0 + 1

    def _register_room_contents(self, room: Room, spec: dict,
                                grid: list[str] | None) -> None:
        # Doors declared in the spec (room-relative coords).
        for d in spec.get("doors", []) or []:
            dx, dy = _coord(d, room.w, room.h)
            if dx is None:
                continue
            ax, ay = room.x0 + dx, room.y0 + dy
            locked = bool(d.get("locked"))
            self.setc(ax, ay, "=" if locked else "+")
            self.doors[(ax, ay)] = {
                "locked": locked, "desc": d.get("desc", "door"),
                "explored": False, "room": room.id,
            }
        # Any '+'/'=' already in the grid become doors too.
        for y in range(room.y0, room.y0 + room.h):
            for x in range(room.x0, room.x0 + room.w):
                c = self.get(x, y)
                if c in "+=" and (x, y) not in self.doors:
                    self.doors[(x, y)] = {
                        "locked": c == "=", "desc": "door",
                        "explored": False, "room": room.id,
                    }
        # Items / entities (room-relative, clamped to the interior so they
        # never spawn embedded in a wall).
        for it in spec.get("items", []) or []:
            ix, iy = _coord_in(it, room.w, room.h)
            if ix is None:
                continue
            self.add_item(room.x0 + ix, room.y0 + iy, it.get("char", "*"),
                          it.get("name", "something"), it.get("desc", ""),
                          it.get("kind", "item"))
        for en in spec.get("entities", []) or []:
            ex, ey = _coord_in(en, room.w, room.h)
            if ex is None:
                continue
            self.add_entity(room.x0 + ex, room.y0 + ey, en.get("char", "?"),
                            en.get("name", "a figure"), en.get("desc", ""),
                            bool(en.get("hostile")))
        # Seed items from grid glyphs (k/*/$) the model may have drawn.
        if grid:
            self._seed_grid_items(room, grid)
            self._seed_grid_terminals(room, grid)
        # Small local models often drop doors mid-room; snap them to a wall
        # that actually opens onto the void so they can be used to explore.
        self._normalize_room_doors(room)

    def _on_perimeter(self, room: Room, x: int, y: int) -> bool:
        return (x in (room.x0, room.x0 + room.w - 1)
                or y in (room.y0, room.y0 + room.h - 1))

    def _nearest_void_wall(self, room: Room, x: int, y: int):
        cands = [(room.x0, y), (room.x0 + room.w - 1, y),
                 (x, room.y0), (x, room.y0 + room.h - 1)]
        best, bestd = None, 1e9
        for cx, cy in cands:
            if self.get(cx, cy) == "#" and self._faces_void(cx, cy):
                d = abs(cx - x) + abs(cy - y)
                if d < bestd:
                    best, bestd = (cx, cy), d
        return best

    def _normalize_room_doors(self, room: Room) -> None:
        for (x, y), info in list(self.doors.items()):
            if info["room"] != room.id or info["explored"]:
                continue
            if self._faces_void(x, y):
                continue  # already a usable exit
            target = self._nearest_void_wall(room, x, y)
            if not target:
                continue  # nowhere useful to move it; leave as decoration
            tx, ty = target
            self.setc(tx, ty, "=" if info["locked"] else "+")
            self.doors[(tx, ty)] = dict(info, room=room.id)
            if not self._on_perimeter(room, x, y):
                self.setc(x, y, ".")
                del self.doors[(x, y)]

    def _seed_grid_items(self, room: Room, grid: list[str]) -> None:
        for j, row in enumerate(grid):
            for i, g in enumerate(row):
                if g in ITEM_CHARS:
                    ax, ay = room.x0 + i, room.y0 + j
                    if self.get(ax, ay) == g and not self.item_at(ax, ay):
                        self.add_item(ax, ay, g, ITEM_CHARS[g].title(),
                                      "", ITEM_CHARS[g])

    def _seed_grid_terminals(self, room: Room, grid: list[str]) -> None:
        for j, row in enumerate(grid):
            for i, g in enumerate(row):
                if g != "!":
                    continue
                ax, ay = room.x0 + i, room.y0 + j
                if self.get(ax, ay) != "!":
                    continue
                if self.specials.get((ax, ay), {}).get("kind") == "terminal":
                    continue
                ssid = f"CastleNet-{self.level}-{len(self.specials) % 9 + 1}"
                self.specials[(ax, ay)] = {
                    "kind": "terminal",
                    "ssid": ssid,
                    "control": random.choice(["doors", "gates", "dungeon"]),
                    "tier": 1 + (self.level // 2),
                    "hacked": False,
                }

    # -- exploration: grow a room beyond a frontier door -----------------
    def connect_room(self, door: tuple[int, int], direction: str,
                     spec: dict | None) -> Room | None:
        """Carve a corridor + room beyond `door` in `direction`. Returns the
        new Room, or None if the area is blocked (door becomes a dead end)."""
        px, py = door
        ddx, ddy = DIRS[direction]
        grid = _clean_grid((spec or {}).get("grid"))
        w, h = _grid_dims(grid, default=(random.randint(9, 15),
                                         random.randint(6, 9)))

        x0, y0, opening = self._find_placement(px, py, direction, w, h)
        if x0 is None:
            self.doors[door]["explored"] = True
            return None

        self._stamp_box(x0, y0, w, h, grid)
        self._carve_corridor(door, direction, x0, y0, w, h, opening)

        room = Room(_safe_id(spec, "room") if spec else self._id("room"),
                    (spec or {}).get("name") or _room_name(self.phase),
                    x0, y0, w, h, (spec or {}).get("narration", ""))
        # Guarantee a unique id.
        if room.id in self.rooms:
            room.id = self._id("room")
        self.rooms[room.id] = room
        self.doors[door]["explored"] = True
        # Mark the opening as a door back the way we came.
        self.setc(*opening, "+")
        self.doors[opening] = {"locked": False, "desc": "doorway",
                               "explored": True, "room": room.id}
        self._register_room_contents(room, spec or {}, grid)
        if not spec:
            self._procedural_fill(room)
        self._ensure_frontier_door(room, exclude=opening)
        return room

    def _add_extra_frontiers(self, room: Room, count: int) -> None:
        """Carve up to `count` additional void-facing '+' doors onto room's walls
        (for procedural branching; skips positions already used as doors)."""
        added = 0
        candidates: list = []
        for x in range(room.x0 + 1, room.x0 + room.w - 1):
            candidates += [(x, room.y0, 0, -1), (x, room.y0 + room.h - 1, 0, 1)]
        for y in range(room.y0 + 1, room.y0 + room.h - 1):
            candidates += [(room.x0, y, -1, 0), (room.x0 + room.w - 1, y, 1, 0)]
        random.shuffle(candidates)
        for x, y, ox, oy in candidates:
            if added >= count:
                break
            if (x, y) in self.doors:
                continue
            if self.get(x + ox, y + oy) == VOID:
                self.setc(x, y, "+")
                self.doors[(x, y)] = {"locked": False, "desc": "passage",
                                      "explored": False, "room": room.id}
                added += 1

    def _all_frontiers_of(self, room: Room) -> list:
        """Return all (door_pos, direction) pairs for unexplored void-facing
        doors in `room`.  At most one entry per door position."""
        result = []
        seen: set = set()
        for (x, y), info in self.doors.items():
            if info["room"] != room.id or info["explored"] or (x, y) in seen:
                continue
            for name, (dx, dy) in DIRS.items():
                if self.get(x + dx, y + dy) == VOID:
                    result.append(((x, y), name))
                    seen.add((x, y))
                    break
        return result

    def connect_cluster(self, entry_door: tuple[int, int], direction: str,
                        specs: list) -> list:
        """BFS placement of up to len(specs) rooms starting at `entry_door`.

        Each placed room may have 1-4 frontier doors (drawn by the model or
        guaranteed by _ensure_frontier_door).  Subsequent specs are distributed
        across those doors BFS-wise, naturally creating a branching layout.
        Returns the list of Room objects successfully placed (3-12 for a live
        call, 3-8 offline depending on available world space).
        """
        if not specs:
            return []
        placed: list[Room] = []
        queue: list = [(entry_door, direction, specs[0])]
        spec_idx = 1

        while queue:
            cur_door, cur_dir, cur_spec = queue.pop(0)
            room = self.connect_room(cur_door, cur_dir,
                                     cur_spec if cur_spec else None)
            if room is None:
                continue  # blocked — skip, keep going with remaining queue
            placed.append(room)

            # For procedural slots, add extra frontier doors so the BFS fans
            # out into a tree rather than a linear chain.
            if cur_spec is None:
                self._add_extra_frontiers(room, random.randint(1, 2))

            # Spread remaining specs across this room's frontier doors (BFS).
            for fdoor, fdir in self._all_frontiers_of(room):
                if spec_idx >= len(specs):
                    break
                queue.append((fdoor, fdir, specs[spec_idx]))
                spec_idx += 1

        return placed

    def _find_placement(self, px: int, py: int, direction: str, w: int, h: int):
        """Pick a free origin for a room of size w×h beyond door (px,py)."""
        ddx, ddy = DIRS[direction]
        gap = 2
        for shift in _spread(12):
            if direction in ("east", "west"):
                if direction == "east":
                    x0 = px + gap
                else:
                    x0 = px - gap - (w - 1)
                y0 = py - h // 2 + shift
                face_perp = _clampi(py, y0 + 1, y0 + h - 2)
                opening = (x0 if direction == "east" else x0 + w - 1, face_perp)
            else:
                if direction == "south":
                    y0 = py + gap
                else:
                    y0 = py - gap - (h - 1)
                x0 = px - w // 2 + shift
                face_perp = _clampi(px, x0 + 1, x0 + w - 2)
                opening = (face_perp, y0 if direction == "south" else y0 + h - 1)
            if self._rect_free(x0, y0, w, h):
                return x0, y0, opening
        return None, None, None

    def _carve_corridor(self, door, direction, x0, y0, w, h, opening) -> None:
        px, py = door
        ddx, ddy = DIRS[direction]
        ox, oy = opening
        if direction in ("east", "west"):
            just_outside = x0 - 1 if direction == "east" else x0 + w
            x = px
            while x != just_outside:
                x += ddx
                if (x, py) != opening:
                    self._floor_if_void(x, py)
            y = py
            while y != oy:
                y += 1 if oy > y else -1
                self._floor_if_void(just_outside, y)
        else:
            just_outside = y0 - 1 if direction == "south" else y0 + h
            y = py
            while y != just_outside:
                y += ddy
                if (px, y) != opening:
                    self._floor_if_void(px, y)
            x = px
            while x != ox:
                x += 1 if ox > x else -1
                self._floor_if_void(x, just_outside)

    def _floor_if_void(self, x: int, y: int) -> None:
        if self.get(x, y) == VOID:
            self.setc(x, y, ".")

    def _faces_void(self, x: int, y: int) -> bool:
        return any(self.get(x + dx, y + dy) == VOID
                   for dx, dy in DIRS.values())

    def _ensure_frontier_door(self, room: Room, exclude: tuple[int, int]) -> None:
        """Make sure the room has at least one onward door into the void."""
        for (dx, dy), info in self.doors.items():
            if (info["room"] == room.id and (dx, dy) != exclude
                    and self._faces_void(dx, dy)):
                return  # already has an onward exit
        # Carve a new '+' on a wall whose outside is void.
        candidates = []
        for x in range(room.x0 + 1, room.x0 + room.w - 1):
            candidates.append((x, room.y0, 0, -1))
            candidates.append((x, room.y0 + room.h - 1, 0, 1))
        for y in range(room.y0 + 1, room.y0 + room.h - 1):
            candidates.append((room.x0, y, -1, 0))
            candidates.append((room.x0 + room.w - 1, y, 1, 0))
        random.shuffle(candidates)
        for x, y, ox, oy in candidates:
            if (x, y) == exclude:
                continue
            if self.get(x + ox, y + oy) == VOID:
                self.setc(x, y, "+")
                self.doors[(x, y)] = {"locked": False, "desc": "passage",
                                      "explored": False, "room": room.id}
                return

    # -- procedural fill (offline / model gave nothing) ------------------
    def _procedural_fill(self, room: Room) -> None:
        floor = [(x, y)
                 for y in range(room.y0 + 1, room.y0 + room.h - 1)
                 for x in range(room.x0 + 1, room.x0 + room.w - 1)
                 if self.get(x, y) == "." and (x, y) != (self.px, self.py)]
        random.shuffle(floor)
        roll = random.random()
        if self.phase in ("escape", "flee"):
            if roll < 0.35 and floor:
                x, y = floor.pop()
                self.add_entity(x, y, "G", "Castle Guard",
                                "patrolling with a torch", hostile=False)
            if roll < 0.25 and floor:
                x, y = floor.pop()
                self.add_item(x, y, "k", "iron key", "fits a heavy lock", "key")
        elif self.phase == "return":
            if floor and random.random() < 0.6:
                x, y = floor.pop()
                clue = random.choice(_CLUES)
                self.add_item(x, y, "*", "scrap of parchment", clue, "clue")

    # -- multi-level dungeon generation ----------------------------------

    def generate_dungeon(self) -> None:
        """Generate NUM_LEVELS complete dungeon levels and activate level 0."""
        self._level_store.clear()
        self.stair_links.clear()
        for lvl in range(NUM_LEVELS):
            self._reset_for_level()
            self._gen_level(lvl)
            self._populate_level_offline(lvl)
            self._level_store.append(self._snapshot())
        self._place_all_stairs()
        self._restore(self._level_store[0])
        self.level = 0
        start_room = self.rooms.get("l0r0_0")
        if start_room:
            self.px = start_room.x0 + start_room.w // 2
            self.py = start_room.y0 + start_room.h // 2
            if self.get(self.px, self.py) != ".":
                cells = self._floor_cells_of(start_room)
                if cells:
                    self.px, self.py = cells[0]
            self._place_tutorial_terminal(start_room)
        self.dungeon_generated = True

    def _place_tutorial_terminal(self, room) -> None:
        """A guaranteed, un-failable terminal in the start room to teach hacking."""
        cells = [c for c in self._floor_cells_of(room)
                 if c != (self.px, self.py) and not self.specials.get(c)]
        if not cells:
            return
        # Prefer a cell adjacent to the player so it's seen immediately.
        adj = [c for c in cells
               if abs(c[0] - self.px) + abs(c[1] - self.py) <= 2]
        x, y = (adj or cells)[0]
        self.add_terminal(x, y, "CastleNet-TUTORIAL", "doors", tier=1)
        spec = self.specials.get((x, y))
        if spec:
            spec["tutorial"] = True
            spec["honeypot"] = False

    def _reset_for_level(self) -> None:
        self.grid = [[VOID] * self.width for _ in range(self.height)]
        self.rooms = {}
        self.items = {}
        self.entities = {}
        self.doors = {}
        self.specials = {}
        self.seen = set()
        self.visible = set()

    def _gen_level(self, level_num: int) -> None:
        growth = 1.3 ** level_num
        # Keep zone growth moderate; over-fragmentation creates sparse maps.
        zone_growth = 1.16 ** level_num
        zone_cols = max(ZONE_COLS, int(round(ZONE_COLS * zone_growth)))
        zone_rows = max(ZONE_ROWS, int(round(ZONE_ROWS * zone_growth)))
        # Keep zones at least large enough to host useful rooms.
        zone_cols = min(zone_cols, max(6, self.width // 10))
        zone_rows = min(zone_rows, max(4, self.height // 8))

        zone_w = self.width // zone_cols
        zone_h = self.height // zone_rows
        themes = list(_LEVEL_THEMES[level_num % len(_LEVEL_THEMES)])
        random.shuffle(themes)
        room_grid: list[list] = [[None] * zone_cols for _ in range(zone_rows)]

        # Stamp rooms
        ti = 0
        room_scale = min(3.8, growth)
        for row in range(zone_rows):
            for col in range(zone_cols):
                x_min = col * zone_w + 2
                x_max = min(self.width - 2, (col + 1) * zone_w - 2)
                y_min = row * zone_h + 2
                y_max = min(self.height - 2, (row + 1) * zone_h - 2)
                if x_max - x_min < 6 or y_max - y_min < 5:
                    continue

                # Cap room size lower so corridors are broken up by more chambers.
                rw = random.randint(max(6, int(zone_w * 0.44)),
                                    max(7, int(zone_w * 0.72)))
                rh = random.randint(max(5, int(zone_h * 0.42)),
                                    max(6, int(zone_h * 0.70)))
                rw = int(rw * min(1.2, 0.9 + 0.06 * room_scale))
                rh = int(rh * min(1.2, 0.9 + 0.06 * room_scale))
                rw = min(rw, 26)
                rh = min(rh, 16)
                rw = min(rw, x_max - x_min - 1)
                rh = min(rh, y_max - y_min - 1)
                if rw < 5 or rh < 4:
                    continue
                x0 = random.randint(x_min, max(x_min, x_max - rw))
                y0 = random.randint(y_min, max(y_min, y_max - rh))
                rid = f"l{level_num}r{col}_{row}"
                name = themes[ti % len(themes)]
                ti += 1
                self._stamp_box(x0, y0, rw, rh, None)
                room = Room(rid, name, x0, y0, rw, rh)
                self.rooms[rid] = room
                room_grid[row][col] = room

        flat = [room_grid[row][col]
                for row in range(zone_rows)
                for col in range(zone_cols)
                if room_grid[row][col] is not None]

        if not flat:
            rw = max(8, min(self.width - 4, int(12 * min(3.8, growth))))
            rh = max(6, min(self.height - 4, int(7 * min(3.8, growth))))
            x0 = max(2, self.width // 2 - rw // 2)
            y0 = max(2, self.height // 2 - rh // 2)
            self._stamp_box(x0, y0, rw, rh, None)
            rid = f"l{level_num}r0_0"
            room = Room(rid, random.choice(themes), x0, y0, rw, rh)
            self.rooms[rid] = room
            flat = [room]

        # Connect grid neighbours with L-shaped corridors
        for row in range(zone_rows):
            for col in range(zone_cols):
                r1 = room_grid[row][col]
                if r1 is None:
                    continue
                if col + 1 < zone_cols and room_grid[row][col + 1]:
                    self._corridor_between(r1, room_grid[row][col + 1])
                if row + 1 < zone_rows and room_grid[row + 1][col]:
                    self._corridor_between(r1, room_grid[row + 1][col])

        # Extra random connections for loops
        for _ in range(3):
            if len(flat) >= 2:
                a, b = random.sample(flat, 2)
                self._corridor_between(a, b)

        # Fill big gaps with extra small rooms and connect them in.
        self._infill_small_rooms(level_num)
        flat = list(self.rooms.values())

        # Castle level: place exit gate in top-right zone room
        if level_num == NUM_LEVELS - 1:
            gate_room = room_grid[0][zone_cols - 1] or (flat[-1] if flat else None)
            if gate_room:
                gx = gate_room.x0 + gate_room.w // 2
                gy = gate_room.y0 + 1
                self.setc(gx, gy, ">")
                self.specials[(gx, gy)] = {"kind": "gate"}

    def _sample_room_dims(self) -> tuple[int, int]:
        roll = random.random()
        if roll < 0.15:  # compact cells
            return random.randint(8, 13), random.randint(6, 9)
        if roll < 0.7:  # medium rooms
            return random.randint(14, 24), random.randint(8, 14)
        return random.randint(22, 34), random.randint(12, 20)

    def _infill_small_rooms(self, level_num: int) -> None:
        """Add extra small chambers into large void regions and connect them."""
        growth = 1.3 ** level_num
        target = random.randint(28, 48) + int(18 * growth)
        added = 0
        tries = 0
        while added < target and tries < 1800:
            tries += 1
            # Favor compact/medium infill to keep hallway spans short.
            if random.random() < 0.2:
                w = random.randint(9, 14)
                h = random.randint(6, 10)
            else:
                w = random.randint(6, 11)
                h = random.randint(4, 8)
            x0 = random.randint(2, self.width - w - 3)
            y0 = random.randint(2, self.height - h - 3)
            if not self._rect_free(x0, y0, w, h):
                continue
            cx, cy = x0 + w // 2, y0 + h // 2
            nearest = self._nearest_room_center(cx, cy)
            if nearest is None:
                continue
            ncx, ncy, near_room = nearest
            if abs(ncx - cx) + abs(ncy - cy) > 52:
                continue
            rid = f"l{level_num}s{added}_{tries}"
            name = random.choice(["Closet", "Cache", "Antechamber", "Hideout",
                                  "Niche", "Store Nook", "Watch Nook"])
            self._stamp_box(x0, y0, w, h, None)
            room = Room(rid, name, x0, y0, w, h)
            self.rooms[rid] = room
            self._corridor_between(room, near_room)
            added += 1

    def _nearest_room_center(self, x: int, y: int):
        best = None
        best_d = 10**9
        for room in self.rooms.values():
            cx = room.x0 + room.w // 2
            cy = room.y0 + room.h // 2
            d = abs(cx - x) + abs(cy - y)
            if d < best_d:
                best_d = d
                best = (cx, cy, room)
        return best

    def _corridor_cell(self, x: int, y: int) -> None:
        if not self.in_bounds(x, y):
            return
        c = self.get(x, y)
        if c == VOID:
            self.setc(x, y, ".")
        elif c == "#":
            room = self.room_at(x, y)
            self.setc(x, y, "+")
            if room and (x, y) not in self.doors:
                self.doors[(x, y)] = {
                    "locked": False, "desc": "doorway",
                    "explored": True, "room": room.id,
                }

    def _hcorridor(self, x1: int, x2: int, y: int) -> None:
        for x in range(min(x1, x2), max(x1, x2) + 1):
            self._corridor_cell(x, y)
            # Occasional side nib for organic feel
            if random.random() < 0.07:
                self._corridor_cell(x, y + random.choice([-1, 1]))

    def _vcorridor(self, x: int, y1: int, y2: int) -> None:
        for y in range(min(y1, y2), max(y1, y2) + 1):
            self._corridor_cell(x, y)
            if random.random() < 0.07:
                self._corridor_cell(x + random.choice([-1, 1]), y)

    def _try_stamp_junction(self, bx: int, by: int) -> None:
        """Stamp a small chamber at the corridor bend point to break up long hallways."""
        w = random.randint(4, 7)
        h = random.randint(4, 6)
        x0 = bx - w // 2
        y0 = by - h // 2
        if not self._rect_free(x0, y0, w, h):
            return
        self._stamp_box(x0, y0, w, h, None)
        rid = self._id("junc")
        name = random.choice(["Junction", "Crossing", "Alcove", "Side Chamber",
                               "Nook", "Guard Post", "Anteroom", "Passage Room"])
        self.rooms[rid] = Room(rid, name, x0, y0, w, h)

    def _corridor_between(self, r1: Room, r2: Room) -> None:
        cx1, cy1 = r1.x0 + r1.w // 2, r1.y0 + r1.h // 2
        cx2, cy2 = r2.x0 + r2.w // 2, r2.y0 + r2.h // 2

        # Connect room edges instead of centers when rooms don't overlap —
        # this cuts corridor length roughly in half for adjacent zones.
        if r1.x0 + r1.w <= r2.x0:        # r1 fully left of r2
            cx1 = r1.x0 + r1.w - 1
            cx2 = r2.x0
        elif r2.x0 + r2.w <= r1.x0:      # r2 fully left of r1
            cx2 = r2.x0 + r2.w - 1
            cx1 = r1.x0

        if r1.y0 + r1.h <= r2.y0:        # r1 fully above r2
            cy1 = r1.y0 + r1.h - 1
            cy2 = r2.y0
        elif r2.y0 + r2.h <= r1.y0:      # r2 fully above r1
            cy2 = r2.y0 + r2.h - 1
            cy1 = r1.y0

        # Place a small junction room at the L-bend for long corridors
        h_len = abs(cx2 - cx1)
        v_len = abs(cy2 - cy1)
        if h_len + v_len > 16 and random.random() < 0.65:
            if random.random() < 0.5:
                self._try_stamp_junction(cx2, cy1)
            else:
                self._try_stamp_junction(cx1, cy2)

        if random.random() < 0.5:
            self._hcorridor(cx1, cx2, cy1)
            self._vcorridor(cx2, cy1, cy2)
        else:
            self._vcorridor(cx1, cy1, cy2)
            self._hcorridor(cx1, cx2, cy2)

    def _floor_cells_of(self, room: Room) -> list:
        return [(x, y)
                for y in range(room.y0 + 1, room.y0 + room.h - 1)
                for x in range(room.x0 + 1, room.x0 + room.w - 1)
                if self.get(x, y) == "."]

    def _floor_cells_in_snap(self, grid: list, room: Room) -> list:
        return [(x, y)
                for y in range(room.y0 + 1, room.y0 + room.h - 1)
                for x in range(room.x0 + 1, room.x0 + room.w - 1)
                if grid[y][x] == "."]

    def _populate_level_offline(self, level_num: int) -> None:
        flat = list(self.rooms.values())
        if not flat:
            return
        random.shuffle(flat)

        def make_gear(is_weapon: bool) -> dict:
            base_name, slot, lo, hi, weight = random.choice(
                WEAPON_BASES if is_weapon else ARMOR_BASES)
            rarity = _rarity_for_level(level_num)
            quality = _quality_for_level(level_num)
            ench = _maybe_enchantment(rarity)
            tier = _tier_value(rarity, quality)
            material = _material_for_tier(tier)
            base_range = RANGED_WEAPON_RANGE.get(base_name, 0) if is_weapon else 0

            # Rare+ ranged weapons get a chance at the swift-quiver enchantment.
            if base_range > 0 and rarity in ("rare", "epic", "legendary"):
                swift_chance = {"rare": 0.18, "epic": 0.38, "legendary": 0.60}.get(rarity, 0)
                if random.random() < swift_chance:
                    ench = RANGED_ENCHANTMENT_SWIFT

            primary = int(random.randint(lo, hi) * tier) + (1 if ench else 0)
            atk = primary if is_weapon else 0
            dfn = 0 if is_weapon else primary
            sight = 0

            # Secondary affix: a rarity-scaled chance of a bonus stat, which
            # may grant attack, defense, or extra sight range on the piece.
            affix_suffix = ""
            if random.random() < _affix_chance(rarity):
                aff_name, aff_stat, alo, ahi = random.choice(
                    WEAPON_AFFIXES if is_weapon else ARMOR_AFFIXES)
                bonus = max(1, int(random.randint(alo, ahi) * (tier ** 0.5)))
                if aff_stat == "attack":
                    atk += bonus
                elif aff_stat == "defense":
                    dfn += bonus
                else:
                    sight += bonus
                affix_suffix = f" {aff_name}"

            name = _named_loot(base_name, rarity, is_weapon)
            if material and rarity in ("common", "uncommon"):
                name = f"{material} {name}"
            name = f"{name}{affix_suffix}"

            desc = f"{quality} {rarity}"
            if material:
                desc += f" {material}"
            desc += f" {base_name}"
            if base_range:
                desc += f", range {base_range}"
            if ench:
                desc += f", enchanted ({ench})"
            if sight:
                desc += f", sharpens sight (+{sight})"

            value = (_coin_value_cp(220 if is_weapon else 260, rarity, quality)
                     + (atk + dfn) * 12 + sight * 40 + base_range * 8)
            return {
                "char": "$",
                "name": name,
                "desc": desc,
                "kind": "weapon" if is_weapon else "armor",
                "slot": slot,
                "attack": atk,
                "defense": dfn,
                "quality": quality,
                "rarity": rarity,
                "enchantment": ench,
                "sight_bonus": sight,
                "weight": round(weight * (0.9 if quality == "masterwork" else 1.0), 2),
                "value_cp": int(value),
                "range": base_range,
            }

        def make_jewelry() -> dict:
            base_name, slot, stat, lo, hi, weight = random.choice(JEWELRY_BASES)
            rarity = _rarity_for_level(level_num)
            quality = _quality_for_level(level_num)
            ench = _maybe_enchantment(rarity) or "warded"
            tier = _tier_value(rarity, quality)

            atk = dfn = sight = 0
            primary = max(1, int(random.randint(lo, hi) * tier))
            if stat == "attack":
                atk = primary
            elif stat == "defense":
                dfn = primary
            elif stat == "mixed":
                sight = max(1, primary // 2)
                if random.random() < 0.5:
                    atk = max(1, primary // 2)
                else:
                    dfn = max(1, primary // 2)
            else:
                sight = primary

            # Finer jewelry gains a secondary enchanted bonus on top.
            name = _named_jewelry(base_name, rarity)
            if random.random() < _affix_chance(rarity) * 0.85:
                aff_name, aff_stat, alo, ahi = random.choice(JEWELRY_AFFIXES)
                bonus = max(1, int(random.randint(alo, ahi) * (tier ** 0.5)))
                if aff_stat == "attack":
                    atk += bonus
                elif aff_stat == "defense":
                    dfn += bonus
                else:
                    sight += bonus
                name = f"{name} {aff_name}"

            bonus_words = []
            if sight:
                bonus_words.append(f"+{sight} sight")
            if atk:
                bonus_words.append(f"+{atk} attack")
            if dfn:
                bonus_words.append(f"+{dfn} defense")
            desc = f"{quality} {rarity} {base_name}, enchanted ({ench})"
            if bonus_words:
                desc += " — " + ", ".join(bonus_words)

            value = (_coin_value_cp(150, rarity, quality)
                     + sight * 40 + (atk + dfn) * 14)
            return {
                "char": "$",
                "name": name,
                "desc": desc,
                "kind": "jewelry",
                "slot": slot,
                "attack": atk,
                "defense": dfn,
                "quality": quality,
                "rarity": rarity,
                "enchantment": ench,
                "sight_bonus": sight,
                "weight": round(weight, 2),
                "value_cp": int(value),
            }

        def make_material() -> dict:
            cat = random.choice(["wood", "wood", "clay", "metal", "metal", "gem",
                                 "electronics"])
            if cat == "wood":
                name = random.choice(["oak log", "birch log", "ash branch", "pine timber"])
                return {"char": "/", "name": name, "desc": "raw wood for crafting",
                        "kind": "material", "material": "wood", "weight": 0.6,
                        "value_cp": 25}
            if cat == "clay":
                name = random.choice(["river clay", "clay lump", "kiln clay"])
                return {"char": ":", "name": name, "desc": "mouldable clay for crafting",
                        "kind": "material", "material": "clay", "weight": 0.5,
                        "value_cp": 30}
            if cat == "metal":
                name = random.choice(["iron ingot", "copper ingot", "steel billet", "bronze bar"])
                return {"char": "-", "name": name, "desc": "smelted metal stock",
                        "kind": "material", "material": "metal", "weight": 1.0,
                        "value_cp": 60}
            if cat == "electronics":
                name = random.choice(["circuit board", "relay chip", "signal module",
                                      "old PCB", "logic array"])
                return {"char": "~", "name": name, "desc": "salvaged electronics for crafting",
                        "kind": "material", "material": "electronics", "weight": 0.4,
                        "value_cp": 90}
            # gem: carries a socketable attack/defense/sight/carry/slots/hack bonus
            gname, gstat = random.choice([
                ("ruby", "attack"),   ("garnet", "attack"),
                ("sapphire", "defense"), ("onyx", "defense"),
                ("emerald", "sight"), ("topaz", "sight"),
                ("diamond", "mixed"),
                ("amethyst", "carry"), ("amethyst", "carry"),
                ("citrine", "slots"), ("citrine", "slots"),
                ("jade", "hack"),     ("obsidian", "hack"),
            ])
            mag = random.randint(1, 3) + (level_num // 3)
            atk = dfn = sight = carry = slots = hack = 0
            if gstat == "attack":
                atk = mag
            elif gstat == "defense":
                dfn = mag
            elif gstat == "sight":
                sight = mag
            elif gstat == "carry":
                carry = mag * 4
            elif gstat == "slots":
                slots = mag * 2
            elif gstat == "hack":
                hack = mag
            else:  # mixed
                atk = max(1, mag // 2)
                dfn = max(1, mag // 2)
                sight = max(1, mag // 2)
            bits = []
            if atk:   bits.append(f"+{atk} atk")
            if dfn:   bits.append(f"+{dfn} def")
            if sight: bits.append(f"+{sight} sight")
            if carry: bits.append(f"+{carry} carry")
            if slots: bits.append(f"+{slots} slots")
            if hack:  bits.append(f"+{hack} hack")
            return {"char": "^", "name": gname,
                    "desc": "a cut gem (socket into armor/backpack: " + ", ".join(bits) + ")",
                    "kind": "material", "material": "gem", "attack": atk,
                    "defense": dfn, "sight_bonus": sight, "carry_bonus": float(carry),
                    "bag_slots": slots, "hack_bonus": hack,
                    "weight": 0.2, "value_cp": 80 + mag * 30}

        def random_loot() -> dict:
            roll = random.random()
            if roll < 0.30:
                return make_material()
            if roll < 0.50:
                return make_gear(is_weapon=True)
            if roll < 0.68:
                return make_gear(is_weapon=False)
            if roll < 0.80:
                return make_jewelry()
            if roll < 0.90:
                return {"char": "*",
                        "name": random.choice(["healing draught", "night-sight tonic", "potion of vigor"]),
                        "desc": "alchemical tonic", "kind": "potion", "weight": 0.4,
                        "value_cp": random.randint(110, 200)}
            return {"char": "$", "name": "coin purse", "desc": "mixed coin",
                    "kind": "currency", "value_cp": random.randint(80, 360), "weight": 0.2}

        _BACKPACK_SPECS = [
            {"char": "[", "name": "small satchel",       "desc": "a modest cloth satchel",
             "kind": "backpack", "slot": "back", "rarity": "common",
             "carry_bonus": 16.0,  "bag_capacity": 12,  "weight": 0.8,  "value_cp": 180},
            {"char": "[", "name": "canvas pack",          "desc": "a sturdy canvas traveller's pack",
             "kind": "backpack", "slot": "back", "rarity": "uncommon",
             "carry_bonus": 32.0, "bag_capacity": 24, "weight": 1.5,  "value_cp": 380},
            {"char": "[", "name": "leather haversack",    "desc": "a well-stitched leather haversack",
             "kind": "backpack", "slot": "back", "rarity": "rare",
             "carry_bonus": 56.0, "bag_capacity": 40, "weight": 2.5,  "value_cp": 720},
            {"char": "[", "name": "iron-frame rucksack",  "desc": "an expedition pack with iron stays",
             "kind": "backpack", "slot": "back", "rarity": "epic",
             "carry_bonus": 88.0, "bag_capacity": 60, "weight": 4.0,  "value_cp": 1400},
        ]

        def shop_stock() -> list[dict]:
            stock = []
            for _ in range(random.randint(4, 6)):
                stock.append(make_gear(is_weapon=True))
            for _ in range(random.randint(4, 6)):
                stock.append(make_gear(is_weapon=False))
            for _ in range(random.randint(3, 5)):
                stock.append(make_jewelry())
            # Every shop always carries the two smallest backpack tiers
            stock += [dict(s) for s in _BACKPACK_SPECS[:2]]
            if random.random() < 0.4:
                stock.append(dict(_BACKPACK_SPECS[2]))
            stock += [
                {
                    "char": "*", "name": "healing draught", "desc": "restorative potion",
                    "kind": "potion", "slot": "none", "attack": 0, "defense": 0,
                    "quality": "fine", "rarity": "uncommon", "enchantment": "",
                    "sight_bonus": 0, "weight": 0.4, "value_cp": 140,
                },
                {
                    "char": "*", "name": "night-sight tonic", "desc": "sharpens vision in dark halls",
                    "kind": "potion", "slot": "none", "attack": 0, "defense": 0,
                    "quality": "fine", "rarity": "uncommon", "enchantment": "",
                    "sight_bonus": 0, "weight": 0.4, "value_cp": 160,
                },
                {
                    "char": "*", "name": "potion of vigor", "desc": "restores stamina and clears fatigue",
                    "kind": "potion", "slot": "none", "attack": 0, "defense": 0,
                    "quality": "fine", "rarity": "uncommon", "enchantment": "",
                    "sight_bonus": 0, "weight": 0.4, "value_cp": 180,
                },
                {
                    "char": "$", "name": "sniffer_patch module", "desc": "unlocks capture_handshake",
                    "kind": "module", "module": "sniffer_patch", "slot": "none", "attack": 0,
                    "defense": 0, "quality": "fine", "rarity": "rare", "enchantment": "",
                    "sight_bonus": 0, "weight": 0.2, "value_cp": 320,
                },
                {
                    "char": "$", "name": "logic_probe module", "desc": "unlocks circuit_bypass",
                    "kind": "module", "module": "logic_probe", "slot": "none", "attack": 0,
                    "defense": 0, "quality": "fine", "rarity": "rare", "enchantment": "",
                    "sight_bonus": 0, "weight": 0.2, "value_cp": 360,
                },
                {
                    "char": "$", "name": "chest_decoder module", "desc": "unlocks loot_decrypt",
                    "kind": "module", "module": "chest_decoder", "slot": "none", "attack": 0,
                    "defense": 0, "quality": "fine", "rarity": "epic", "enchantment": "",
                    "sight_bonus": 0, "weight": 0.2, "value_cp": 520,
                },
            ]
            random.shuffle(stock)
            return stock[:20]

        item_specs: list[dict] = []
        item_specs += [{"char": "k", "name": "iron key", "desc": "cold and heavy", "kind": "key", "value_cp": 40}] * random.randint(1, 2)
        item_specs += [{"char": "*", "name": "scrap of parchment", "desc": random.choice(_CLUES), "kind": "clue", "value_cp": 20}] * random.randint(1, 2)
        item_specs += [{"char": "$", "name": "coin purse", "desc": "a handful of mixed coin", "kind": "currency", "value_cp": random.randint(120, 420), "weight": 0.2}] * random.randint(1, 3)
        for _ in range(random.randint(2, 5)):
            item_specs.append(make_gear(is_weapon=True))
        for _ in range(random.randint(2, 5)):
            item_specs.append(make_gear(is_weapon=False))
        for _ in range(random.randint(2, 6)):
            item_specs.append(make_jewelry())
        for _ in range(random.randint(5, 10)):
            item_specs.append(make_material())
        item_specs += [
            {"char": "*", "name": "healing draught", "desc": "a red potion that mends cuts", "kind": "potion", "sight_bonus": 0, "weight": 0.4, "value_cp": 120},
            {"char": "*", "name": "night-sight tonic", "desc": "an alchemical potion for dim halls", "kind": "potion", "sight_bonus": 0, "weight": 0.4, "value_cp": 140},
            {"char": "$", "name": "signal lens", "desc": "tech scavenged from old terminal relays", "kind": "item", "sight_bonus": 0, "weight": 0.8, "value_cp": 180},
            {"char": "*", "name": "rune shard", "desc": "faint magic hums beneath the dust", "kind": "item", "sight_bonus": 0, "weight": 0.5, "value_cp": 160},
        ]
        random.shuffle(item_specs)
        for i, spec in enumerate(item_specs):
            room = flat[i % len(flat)]
            floor = self._floor_cells_of(room)
            if floor:
                x, y = random.choice(floor)
                self.add_item(
                    x, y,
                    spec.get("char", "$"),
                    spec.get("name", "loot"),
                    spec.get("desc", ""),
                    spec.get("kind", "item"),
                    slot=spec.get("slot", "none"),
                    attack=spec.get("attack", 0),
                    defense=spec.get("defense", 0),
                    quality=spec.get("quality", "common"),
                    rarity=spec.get("rarity", "common"),
                    enchantment=spec.get("enchantment", ""),
                    sight_bonus=spec.get("sight_bonus", 0),
                    weight=spec.get("weight", 1.0),
                    value_cp=spec.get("value_cp", 0),
                    material=spec.get("material", ""),
                    range=spec.get("range", 0),
                    carry_bonus=spec.get("carry_bonus", 0.0),
                    bag_capacity=spec.get("bag_capacity", 0),
                    bag_slots=spec.get("bag_slots", 0),
                    hack_bonus=spec.get("hack_bonus", 0),
                )

        # (char, name, desc, hostile, sight_radius)
        ent_pool = [
            ("G", "guard", "pacing with a torch", True, 10),
            ("R", "giant rat", "hungry and aggressive", True, 5),
            ("S", "skeleton", "animated by dark magic", True, 7),
            ("B", "bat", "screeches if disturbed", True, 6),
            ("J", "jailer", "carries a ring of keys", True, 9),
            ("W", "wild wolf", "lean and territorial", True, 11),
            ("H", "hunting hound", "trained to track escapees", True, 13),
            ("Q", "orc raider", "a brutal villain from the outer hills", True, 8),
            ("M", "mercenary", "armoured villain with a cruel grin", True, 9),
            ("N", "necromancer", "villain whispering to dead bones", True, 12),
        ]
        if level_num >= 2:
            ent_pool.append(("C", "castle captain", "armoured and alert", True, 14))
        n_ents = max(4, NUM_LEVELS + 3 - level_num)
        for i in range(n_ents):
            room = flat[i % len(flat)]
            floor = self._floor_cells_of(room)
            if floor:
                x, y = random.choice(floor)
                char, name, desc, hostile, sight = random.choice(ent_pool)
                ent = self.add_entity(x, y, char, name, desc, hostile)
                ent.sight_radius = sight

        # Lock 35-50% of non-explored doors; place a matching key in a different room.
        door_list = [(pos, info) for pos, info in self.doors.items()
                     if not info["locked"] and not info.get("explored", False)]
        random.shuffle(door_list)
        n_lock = max(2, int(len(door_list) * random.uniform(0.35, 0.50)))
        for i in range(min(n_lock, len(door_list))):
            (dx, dy), info = door_list[i]
            info["locked"] = True
            self.setc(dx, dy, "=")
            locked_rid = info.get("room", "")
            key_rooms = [r for r in flat if r.id != locked_rid] or flat
            kroom = random.choice(key_rooms)
            floor = self._floor_cells_of(kroom)
            if floor:
                x, y = random.choice(floor)
                self.add_item(x, y, "k", "iron key", "opens a heavy lock", "key")

        # Trapdoors on levels 1+ (fall to level below)
        if level_num > 0:
            for _ in range(random.randint(1, 2)):
                room = random.choice(flat)
                floor = self._floor_cells_of(room)
                if floor:
                    x, y = random.choice(floor)
                    self.setc(x, y, "T")
                    self.specials[(x, y)] = {"kind": "trapdoor",
                                              "target_level": level_num - 1}

        # Hackable terminals on hostile local wifi networks.
        # Control types tiered by dungeon depth
        _ctrl_basic = ["doors", "locks", "loot", "gates", "dungeon", "security"]
        _ctrl_mid   = ["cameras", "alarms", "comm", "vault", "power", "db"]
        _ctrl_adv   = ["auth", "scada", "radio", "firmware", "backup", "cloud"]
        _ctrl_apex  = ["registry", "webshell", "vpn", "container"]
        if level_num < 2:
            _ctrl_pool = _ctrl_basic
        elif level_num < 5:
            _ctrl_pool = _ctrl_basic + _ctrl_mid
        elif level_num < 7:
            _ctrl_pool = _ctrl_basic + _ctrl_mid + _ctrl_adv
        else:
            _ctrl_pool = _ctrl_basic + _ctrl_mid + _ctrl_adv + _ctrl_apex
        # Every other room gets a terminal (minimum 3).
        term_candidate_rooms = flat.copy()
        random.shuffle(term_candidate_rooms)
        n_terms = max(3, (len(flat) + 1) // 2)
        terminal_specs: list[tuple[int, int, str, int]] = []
        term_idx = 0
        for i in range(n_terms):
            # cycle through rooms so terminals are spread out, not clustered
            room = term_candidate_rooms[term_idx % len(term_candidate_rooms)]
            term_idx += 1
            floor = [c for c in self._floor_cells_of(room)
                     if not self.specials.get(c)]
            if not floor:
                continue
            x, y = random.choice(floor)
            control = random.choice(_ctrl_pool)
            ssid = f"CastleNet-{level_num}-{i + 1}"
            tier = 1 + (level_num // 2)
            self.add_terminal(x, y, ssid, control, tier=tier)
            # ~12% of terminals are honeypots: hacking them burns you instead of
            # granting control. A vulnscan reveals the trap before you commit.
            if random.random() < 0.12:
                spec = self.specials.get((x, y))
                if spec:
                    spec["honeypot"] = True
            terminal_specs.append((x, y, ssid, tier))

        for tx, ty, ssid, tier in terminal_specs:
            self._wire_terminal_security(tx, ty, ssid, tier, level_num)

        # One shop per level with level-appropriate stock.
        if level_num == 0:
            shop_room = self.rooms.get("l0r0_0") or random.choice(flat)
        else:
            shop_room = random.choice(flat)
        floor = self._floor_cells_of(shop_room)
        if floor:
            sx, sy = random.choice(floor)
            self.add_shop(sx, sy, f"{_LEVEL_NAMES[level_num]} Quartermaster", shop_stock())

        # Crafting stations: an anvil and a crafting table. On level 0 both go
        # in the starting room so the player can craft from the outset.
        if level_num == 0:
            host = self.rooms.get("l0r0_0") or (flat[0] if flat else None)
            station_hosts = [host, host]
        else:
            station_hosts = random.sample(flat, min(2, len(flat))) if flat else []
        used_cells: set = set()
        for st_kind, st_room in zip(("anvil", "table"), station_hosts):
            if not st_room:
                continue
            cells = [c for c in self._floor_cells_of(st_room)
                     if self.get(*c) == "." and not self.item_at(*c) and c not in used_cells]
            if cells:
                cx, cy = random.choice(cells)
                used_cells.add((cx, cy))
                self.add_station(cx, cy, st_kind)

        # Drop a small satchel in the starting room on level 0.
        if level_num == 0:
            start = self.rooms.get("l0r0_0")
            if start:
                sp = _BACKPACK_SPECS[0]
                free = [c for c in self._floor_cells_of(start)
                        if self.get(*c) == "." and not self.item_at(*c)]
                if free:
                    sx2, sy2 = random.choice(free)
                    self.add_item(
                        sx2, sy2,
                        sp["char"], sp["name"], sp.get("desc", ""),
                        kind=sp["kind"], slot=sp["slot"],
                        weight=sp["weight"], value_cp=sp["value_cp"],
                        rarity=sp.get("rarity", "common"),
                        carry_bonus=sp["carry_bonus"],
                        bag_capacity=sp["bag_capacity"],
                    )

        # Guarantee loot in every room and scatter frequent loot chests.
        for room in list(self.rooms.values()):
            free = [c for c in self._floor_cells_of(room)
                    if self.get(*c) == "." and not self.item_at(*c)]
            random.shuffle(free)
            for _ in range(random.randint(2, 4)):
                if not free:
                    break
                cx, cy = free.pop()
                spec = random_loot()
                self.add_item(cx, cy, spec.get("char", "$"), spec.get("name", "loot"),
                              spec.get("desc", ""), spec.get("kind", "item"),
                              slot=spec.get("slot", "none"),
                              attack=spec.get("attack", 0),
                              defense=spec.get("defense", 0),
                              quality=spec.get("quality", "common"),
                              rarity=spec.get("rarity", "common"),
                              enchantment=spec.get("enchantment", ""),
                              sight_bonus=spec.get("sight_bonus", 0),
                              weight=spec.get("weight", 1.0),
                              value_cp=spec.get("value_cp", 0),
                              material=spec.get("material", ""),
                              range=spec.get("range", 0))
            # ~85% chance of a loot chest per room
            if free and random.random() < 0.85:
                cx, cy = free.pop()
                chest_loot = [random_loot() for _ in range(random.randint(3, 5))]
                self.add_loot_chest(cx, cy, chest_loot)

    def _wire_terminal_security(self, tx: int, ty: int, ssid: str, tier: int,
                                level_num: int) -> None:
        """Bind nearby locked doors and chest caches to a specific terminal ssid."""
        room = self.room_at(tx, ty)
        if not room:
            return

        start_room = self.rooms.get(f"l{level_num}r0_0")

        def room_distance(src: Room | None, dst: Room | None) -> int:
            if not src or not dst:
                return -1
            sx = src.x0 + src.w // 2
            sy = src.y0 + src.h // 2
            dx = dst.x0 + dst.w // 2
            dy = dst.y0 + dst.h // 2
            return abs(sx - dx) + abs(sy - dy)

        terminal_distance = room_distance(start_room, room)

        # Never lock-link doors in the same room as the terminal.
        # This keeps the terminal accessible before using it.
        if start_room:
            candidate_doors = [((dx, dy), info)
                               for (dx, dy), info in self.doors.items()
                               if info.get("room") != room.id
                               and abs(dx - tx) + abs(dy - ty) <= 20
                               and not info.get("explored", False)
                               and room_distance(start_room,
                                                 self.rooms.get(info.get("room", "")))
                                   > terminal_distance]
        else:
            candidate_doors = [((dx, dy), info)
                               for (dx, dy), info in self.doors.items()
                               if info.get("room") != room.id
                               and abs(dx - tx) + abs(dy - ty) <= 24]
        random.shuffle(candidate_doors)
        for (dx, dy), info in candidate_doors[:random.randint(2, 4)]:
            info["locked"] = True
            info["hack_locked"] = True
            info["hack_ssid"] = ssid
            self.setc(dx, dy, "=")

        floor = self._floor_cells_of(room)
        random.shuffle(floor)
        chest_count = 0
        for x, y in floor:
            if (x, y) == (tx, ty):
                continue
            if self.specials.get((x, y)):
                continue
            loot = random.choice([
                ("$", "knight's longsword", "a balanced medieval blade", "item"),
                ("$", "plate cuirass", "thick armor with riveted joints", "item"),
                ("*", "potion of vigor", "a tonic that burns like firewine", "item"),
                ("$", "encrypted relay core", "tech module housing old exploit code", "item"),
                ("*", "sigil charm", "a magic ward etched in silver", "item"),
            ])
            self.add_hack_chest(x, y, ssid, loot[1], loot[2], loot[0], loot[3])
            chest_count += 1
            if chest_count >= random.randint(2, 3):
                break

    def _snapshot(self) -> dict:
        return {
            "grid": [row[:] for row in self.grid],
            "rooms": dict(self.rooms),
            "items": dict(self.items),
            "entities": dict(self.entities),
            "doors": {k: dict(v) for k, v in self.doors.items()},
            "specials": dict(self.specials),
            "seen": set(self.seen),
        }

    def _restore(self, snap: dict) -> None:
        self.grid = [row[:] for row in snap["grid"]]
        self.rooms = dict(snap["rooms"])
        self.items = dict(snap["items"])
        self.entities = dict(snap["entities"])
        self.doors = {k: dict(v) for k, v in snap["doors"].items()}
        self.specials = dict(snap["specials"])
        self.seen = set(snap["seen"])
        self.visible = set()

    def _place_all_stairs(self) -> None:
        for lvl in range(NUM_LEVELS - 1):
            snap_lo = self._level_store[lvl]
            snap_hi = self._level_store[lvl + 1]
            rooms_lo = list(snap_lo["rooms"].values())
            rooms_hi = list(snap_hi["rooms"].values())
            if not rooms_lo or not rooms_hi:
                continue
            # Keep level 0 start room clear of stairs
            start_id = "l0r0_0"
            rooms_lo_f = [r for r in rooms_lo if r.id != start_id] or rooms_lo

            room_lo = random.choice(rooms_lo_f)
            floor_lo = self._floor_cells_in_snap(snap_lo["grid"], room_lo)
            if not floor_lo:
                continue
            lx, ly = random.choice(floor_lo)
            snap_lo["grid"][ly][lx] = "<"
            snap_lo["specials"][(lx, ly)] = {"kind": "stairs_up", "target_level": lvl + 1}

            room_hi = random.choice(rooms_hi)
            floor_hi = self._floor_cells_in_snap(snap_hi["grid"], room_hi)
            if not floor_hi:
                continue
            ux, uy = random.choice(floor_hi)
            snap_hi["grid"][uy][ux] = "V"
            snap_hi["specials"][(ux, uy)] = {"kind": "stairs_down", "target_level": lvl}

            self.stair_links[(lx, ly, lvl)] = (ux, uy, lvl + 1)
            self.stair_links[(ux, uy, lvl + 1)] = (lx, ly, lvl)

        # Wire up trapdoors to landing spots on the level below
        for lvl in range(1, NUM_LEVELS):
            snap = self._level_store[lvl]
            snap_below = self._level_store[lvl - 1]
            rooms_below = list(snap_below["rooms"].values())
            for (tx, ty), info in snap["specials"].items():
                if info.get("kind") != "trapdoor":
                    continue
                if not rooms_below:
                    continue
                target_room = random.choice(rooms_below)
                landing = self._floor_cells_in_snap(snap_below["grid"], target_room)
                if landing:
                    lx, ly = random.choice(landing)
                    self.stair_links[(tx, ty, lvl)] = (lx, ly, lvl - 1)

    def save_current_level(self) -> None:
        if 0 <= self.level < len(self._level_store):
            self._level_store[self.level] = self._snapshot()

    def transition_to_level(self, tx: int, ty: int, target_level: int) -> None:
        self.save_current_level()
        self._restore(self._level_store[target_level])
        self.level = target_level
        self.px, self.py = tx, ty

    # -- summary for the model -------------------------------------------
    def summary(self) -> str:
        room = self.room_at(self.px, self.py)
        rn = room.name if room else "a passage"
        inv = ", ".join(i.name for i in self.inventory) or "nothing"
        here_items = [i.name for i in self.items.values()
                      if room and room.contains(i.x, i.y)]
        here_chars = [e.name for e in self.entities.values()
                      if room and room.contains(e.x, e.y)]
        exits = sum(1 for (dx, dy), info in self.doors.items()
                    if room and room.contains(dx, dy) and not info["explored"])
        terms = [s for (x, y), s in self.specials.items()
                 if s.get("kind") == "terminal"
                 and room and room.contains(x, y)
                 and not s.get("hacked")]
        level_info = (f" Level {self.level}/{NUM_LEVELS-1}: {_LEVEL_NAMES[self.level]}."
                      if self.dungeon_generated else "")
        return (
            f"[STATE] phase={self.phase}; Art is in '{rn}'.{level_info} "
            f"Carrying: {inv}. "
            f"Here: items=[{', '.join(here_items) or 'none'}], "
            f"characters=[{', '.join(here_chars) or 'none'}], "
            f"terminals={[t.get('ssid', 'unknown') for t in terms] or ['none']}, "
            f"unexplored exits={exits}. Rooms on level: {len(self.rooms)}."
        )


# -- module helpers ------------------------------------------------------
_CLUES = [
    "the throne hides what the king feared",
    "behind the tapestry, a draft from nowhere",
    "count the candles; the hidden door wants light",
    "the well remembers the way home",
    "where the portrait's eyes follow, press the stone",
]
_NAMES = {
    "escape": ["Damp Corridor", "Guard Room", "Torture Cell", "Rat Warren",
               "Stone Stair", "Storeroom"],
    "flee": ["Bailey", "Gatehouse", "Moonlit Courtyard", "Stable Yard"],
    "return": ["Great Hall", "Kitchen", "Library", "Chapel", "Solar",
               "Servant Passage", "Wine Cellar"],
    "portal": ["Forgotten Vault", "Sealed Sanctum"],
    "win": ["Sealed Sanctum"],
}

RARITY_ORDER = ["common", "uncommon", "rare", "epic", "legendary"]
QUALITY_ORDER = ["worn", "sturdy", "fine", "masterwork"]

WEAPON_BASES = [
    ("dagger", "weapon", 2, 5, 1.1),
    ("rondel dagger", "weapon", 2, 5, 1.0),
    ("short sword", "weapon", 3, 6, 1.8),
    ("arming sword", "weapon", 4, 8, 2.8),
    ("longsword", "weapon", 5, 9, 3.0),
    ("rapier", "weapon", 4, 7, 2.0),
    ("falchion", "weapon", 4, 8, 2.6),
    ("scimitar", "weapon", 4, 8, 2.4),
    ("hand axe", "weapon", 3, 6, 2.0),
    ("war axe", "weapon", 5, 9, 3.6),
    ("battle axe", "weapon", 6, 10, 4.2),
    ("mace", "weapon", 4, 7, 3.4),
    ("morningstar", "weapon", 5, 9, 3.8),
    ("flail", "weapon", 5, 9, 3.6),
    ("warhammer", "weapon", 6, 11, 4.6),
    ("spear", "weapon", 3, 7, 2.6),
    ("trident", "weapon", 4, 8, 3.0),
    ("glaive", "weapon", 5, 9, 4.4),
    ("halberd", "weapon", 6, 10, 5.0),
    ("pike", "weapon", 5, 9, 4.8),
    ("war scythe", "weapon", 5, 10, 4.5),
    ("greatsword", "weapon", 7, 12, 5.5),
    ("greataxe", "weapon", 8, 13, 6.0),
    ("maul", "weapon", 8, 14, 6.8),
    ("slingshot", "weapon", 2, 4, 0.6),
    ("shortbow", "weapon", 3, 6, 1.6),
    ("longbow", "weapon", 4, 8, 2.3),
    ("crossbow", "weapon", 5, 9, 3.2),
    ("hand crossbow", "weapon", 3, 6, 1.8),
]

# Base shoot range for every ranged weapon (0 = not ranged / melee)
RANGED_WEAPON_RANGE = {
    "slingshot": 5,
    "hand crossbow": 7,
    "shortbow": 9,
    "crossbow": 11,
    "longbow": 14,
}

ARMOR_BASES = [
    # head
    ("padded coif", "armor_head", 1, 2, 0.6),
    ("leather hood", "armor_head", 1, 2, 0.8),
    ("iron cap", "armor_head", 2, 3, 1.2),
    ("iron helm", "armor_head", 2, 4, 1.6),
    ("bascinet", "armor_head", 3, 6, 2.0),
    ("great helm", "armor_head", 3, 5, 2.4),
    ("horned helm", "armor_head", 3, 6, 2.6),
    # chest
    ("cloth tunic", "armor_chest", 1, 3, 1.5),
    ("gambeson", "armor_chest", 3, 5, 3.5),
    ("leather cuirass", "armor_chest", 3, 6, 4.0),
    ("ring mail", "armor_chest", 4, 7, 5.0),
    ("brigandine", "armor_chest", 5, 8, 5.5),
    ("chain hauberk", "armor_chest", 5, 8, 6.2),
    ("scale mail", "armor_chest", 6, 9, 6.8),
    ("plate cuirass", "armor_chest", 7, 11, 8.4),
    ("full plate", "armor_chest", 9, 14, 10.5),
    # legs
    ("cloth leggings", "armor_legs", 1, 2, 1.2),
    ("padded chausses", "armor_legs", 2, 4, 2.8),
    ("leather greaves", "armor_legs", 3, 5, 3.4),
    ("mail chausses", "armor_legs", 4, 6, 4.8),
    ("plate greaves", "armor_legs", 5, 8, 5.6),
    # shield
    ("buckler", "shield", 2, 4, 2.0),
    ("round shield", "shield", 3, 5, 3.5),
    ("heater shield", "shield", 3, 6, 5.0),
    ("kite shield", "shield", 4, 7, 5.8),
    ("tower shield", "shield", 5, 9, 7.5),
]

# Jewelry tuples: (name, slot, primary_stat, lo, hi, weight)
# primary_stat: sight | attack | defense | mixed
JEWELRY_BASES = [
    # sight rings
    ("moon ring", "ring", "sight", 1, 3, 0.2),
    ("sunstone ring", "ring", "sight", 1, 3, 0.2),
    ("obsidian ring", "ring", "sight", 2, 4, 0.2),
    ("owl-eye ring", "ring", "sight", 2, 5, 0.2),
    ("lantern band", "ring", "sight", 2, 5, 0.2),
    ("starglass ring", "ring", "sight", 3, 6, 0.2),
    # offensive rings
    ("ring of fury", "ring", "attack", 1, 3, 0.2),
    ("bloodstone ring", "ring", "attack", 2, 4, 0.2),
    ("ember signet", "ring", "attack", 2, 5, 0.2),
    # defensive rings
    ("ironward ring", "ring", "defense", 1, 3, 0.2),
    ("turtle signet", "ring", "defense", 2, 4, 0.2),
    ("aegis band", "ring", "defense", 2, 5, 0.2),
    # mixed ring
    ("twin-soul ring", "ring", "mixed", 2, 5, 0.2),
    # sight amulets
    ("amulet of dawn", "amulet", "sight", 2, 4, 0.3),
    ("pendant of watchfires", "amulet", "sight", 2, 5, 0.3),
    ("seer's torque", "amulet", "sight", 3, 6, 0.3),
    ("astral locket", "amulet", "sight", 3, 7, 0.3),
    # offensive / defensive amulets
    ("amulet of wrath", "amulet", "attack", 2, 4, 0.3),
    ("warding pendant", "amulet", "defense", 2, 4, 0.3),
    ("talisman of vigil", "amulet", "mixed", 2, 5, 0.3),
]

# Material flavour prefixes unlocked by an item's tier value.
GEAR_MATERIALS = [
    ("rusted", 0.0),
    ("worn iron", 0.0),
    ("iron", 0.9),
    ("hardened", 1.1),
    ("steel", 1.3),
    ("silvered", 1.6),
    ("blacksteel", 1.9),
    ("elven", 2.2),
    ("mithril", 2.6),
    ("adamant", 3.0),
    ("dragonforged", 3.4),
]

# Secondary affixes: (suffix, stat, lo, hi). stat: attack | defense | sight
WEAPON_AFFIXES = [
    ("of warding", "defense", 1, 3),
    ("of the bulwark", "defense", 2, 4),
    ("of farsight", "sight", 1, 3),
    ("of the watch", "sight", 2, 4),
    ("of ruin", "attack", 1, 3),
    ("of slaughter", "attack", 2, 4),
    ("of the vanguard", "attack", 1, 2),
]
ARMOR_AFFIXES = [
    ("of the brute", "attack", 1, 3),
    ("of retort", "attack", 1, 2),
    ("of farsight", "sight", 1, 3),
    ("of the owl", "sight", 2, 4),
    ("of the sentinel", "defense", 1, 3),
    ("of the mountain", "defense", 2, 3),
]
JEWELRY_AFFIXES = [
    ("of keen eyes", "sight", 1, 3),
    ("of the hawk", "sight", 2, 4),
    ("of malice", "attack", 1, 3),
    ("of the bulwark", "defense", 1, 3),
]

WEAPON_NAME_PREFIXES = [
    "Iron", "Hollow", "Storm", "Blood", "Ash", "Lion", "Grim", "King's",
    "Raven", "Frost", "Ember", "Warden's", "Wolf", "Dread", "Sun", "Night",
    "Thorn", "Bone", "Gale", "Doom", "Wyrm", "Saint's",
]
WEAPON_NAME_SUFFIXES = [
    "of the Bastion", "of Iron Oaths", "of Crows", "of Dawn", "of Dusk",
    "the Oathbreaker", "the Gatecleaver", "the Quiet Fang", "of Emberlight",
    "of the Black March", "of Sundered Kings", "of the Last Stand",
    "the Widowmaker", "of Hollow Hymns", "of the Red Hour",
]
ARMOR_NAME_PREFIXES = [
    "Ward", "Knight", "Runed", "Bastion", "Sentinel", "Aegis", "Saint's",
    "Blackwall", "Frostbound", "Lionguard", "Ironheart", "Dawnward",
    "Gravewatch", "Oakenmail", "Stormhide",
]
ARMOR_NAME_SUFFIXES = [
    "of the Keep", "of Winter Stone", "of Holy Iron", "the Unyielding",
    "of Moonsteel", "of Ashen Dawn", "of the Last Watch", "of the Deep Vault",
    "of Standing Stones", "of the Warden's Oath", "of Quiet Vigil",
]

JEWELRY_NAME_PREFIXES = [
    "Seer's", "Warden's", "Astral", "Silver", "Sunforged", "Moonbound",
    "Starlit", "Hallowed", "Twilight", "Gilded", "Whispering",
]
JEWELRY_NAME_SUFFIXES = [
    "of Lanternlight", "of Long Sight", "of the Night Watch", "of Far Stars",
    "of the Open Eye", "of Pale Fire", "of the Sleepless",
]

ENCHANTMENTS = [
    "flame-touched", "frostbound", "storm-etched", "warded", "saint-marked",
    "shadow-kissed", "oakbound", "iron-sigil", "moon-blessed", "venom-laced",
    "rune-scored", "soul-tethered", "sun-forged", "grave-bound", "wind-singing",
]

# Ranged-weapon-only enchantment: allows shooting and moving in the same turn.
RANGED_ENCHANTMENT_SWIFT = "swift quiver"


def _room_name(phase: str) -> str:
    return random.choice(_NAMES.get(phase, _NAMES["escape"]))


def _rarity_for_level(level_num: int) -> str:
    roll = random.random() + level_num * 0.05
    if roll > 1.28:
        return "legendary"
    if roll > 1.05:
        return "epic"
    if roll > 0.78:
        return "rare"
    if roll > 0.5:
        return "uncommon"
    return "common"


def _quality_for_level(level_num: int) -> str:
    roll = random.random() + level_num * 0.08
    if roll > 1.1:
        return "masterwork"
    if roll > 0.75:
        return "fine"
    if roll > 0.4:
        return "sturdy"
    return "worn"


def _tier_value(rarity: str, quality: str) -> float:
    r = {"common": 1.0, "uncommon": 1.35, "rare": 1.8, "epic": 2.4, "legendary": 3.2}
    q = {"worn": 0.8, "sturdy": 1.0, "fine": 1.25, "masterwork": 1.5}
    return r.get(rarity, 1.0) * q.get(quality, 1.0)


def _coin_value_cp(base: int, rarity: str, quality: str) -> int:
    return int(base * _tier_value(rarity, quality))


def _maybe_enchantment(rarity: str) -> str:
    odds = {"common": 0.0, "uncommon": 0.18, "rare": 0.45, "epic": 0.75, "legendary": 1.0}
    if random.random() < odds.get(rarity, 0.0):
        return random.choice(ENCHANTMENTS)
    return ""


def _named_loot(base_name: str, rarity: str, is_weapon: bool) -> str:
    if rarity in ("epic", "legendary"):
        p = random.choice(WEAPON_NAME_PREFIXES if is_weapon else ARMOR_NAME_PREFIXES)
        s = random.choice(WEAPON_NAME_SUFFIXES if is_weapon else ARMOR_NAME_SUFFIXES)
        return f"{p} {base_name.title()} {s}"
    if rarity == "rare":
        p = random.choice(WEAPON_NAME_PREFIXES if is_weapon else ARMOR_NAME_PREFIXES)
        return f"{p} {base_name}"
    return base_name


def _named_jewelry(base_name: str, rarity: str) -> str:
    if rarity in ("epic", "legendary"):
        p = random.choice(JEWELRY_NAME_PREFIXES)
        s = random.choice(JEWELRY_NAME_SUFFIXES)
        return f"{p} {base_name.title()} {s}"
    if rarity == "rare":
        p = random.choice(JEWELRY_NAME_PREFIXES)
        return f"{p} {base_name}"
    return base_name


def _material_for_tier(tier: float) -> str:
    """Pick a flavour material prefix appropriate to an item's tier value."""
    eligible = [name for name, min_tier in GEAR_MATERIALS if min_tier <= tier + 0.35]
    if not eligible:
        return ""
    # Favour the better materials the item's tier has unlocked.
    pool = eligible[-3:] if len(eligible) >= 3 else eligible
    return random.choice(pool)


def _affix_chance(rarity: str) -> float:
    """Probability that a generated item rolls a secondary affix bonus."""
    return {"common": 0.08, "uncommon": 0.28, "rare": 0.58,
            "epic": 0.82, "legendary": 1.0}.get(rarity, 0.25)


def _spread(n: int):
    yield 0
    for k in range(1, n):
        yield k
        yield -k


def _clampi(v, lo, hi):
    try:
        v = int(v)
    except (TypeError, ValueError):
        v = lo
    return max(lo, min(hi, v))


def _coord(d: dict, w: int, h: int):
    if "x" not in d or "y" not in d:
        return None, None
    return _clampi(d["x"], 0, w - 1), _clampi(d["y"], 0, h - 1)


def _coord_in(d: dict, w: int, h: int):
    """Like _coord but clamped to the room interior (off the walls)."""
    if "x" not in d or "y" not in d:
        return None, None
    return _clampi(d["x"], 1, w - 2), _clampi(d["y"], 1, h - 2)


def _clean_grid(grid):
    if not isinstance(grid, list) or not grid:
        return None
    rows = [str(r) for r in grid if isinstance(r, str)]
    rows = [r for r in rows if r.strip()] or rows  # drop only blank rows
    if not rows:
        return None
    width = max(len(r) for r in rows)
    return [r.ljust(width, "#") for r in rows]


def _grid_dims(grid, default):
    if not grid:
        return default
    h = max(3, min(len(grid), 14))
    w = max(5, min(max(len(r) for r in grid), 24))
    return w, h


def _safe_id(spec: dict, prefix: str) -> str:
    rid = str(spec.get("id", "")).strip().replace(" ", "_")
    return rid or prefix

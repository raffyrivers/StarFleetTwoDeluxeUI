"""Gameplay domain models and manual-inspired constants.

The drawing layer should not own game truth. These small dataclasses describe
the ship, contacts, stores, weapons, shields, probes, and mission clock in a
form that can be updated by the simulation and read by every console.
"""

from dataclasses import dataclass, field
import math


def clamp(value, low, high):
    return max(low, min(high, value))


def percent(value, capacity):
    if capacity <= 0:
        return 0
    return round(clamp(value / capacity * 100, 0, 100))


def bearing_from_delta(dx, dy):
    """0 is up/north, 90 is right/east, matching the tactical display."""
    return (math.degrees(math.atan2(dx, -dy)) + 360) % 360


def rotate_delta(dx, dy, degrees):
    rad = math.radians(degrees)
    return (dx * math.cos(rad) - dy * math.sin(rad),
            dx * math.sin(rad) + dy * math.cos(rad))


@dataclass
class MissionClock:
    elapsed_days: float = 15.24
    time_left_days: float = 5.26

    def advance(self, dt, rest_mode=False, hyper_velocity=0):
        rate = 0.0025 if rest_mode else 0.001
        if hyper_velocity:
            rate += hyper_velocity * 0.0004
        self.elapsed_days += dt * rate
        self.time_left_days = max(0.0, self.time_left_days - dt * rate)


@dataclass
class NavigationState:
    region_x: float = 4.0
    region_y: float = 6.0
    system_x: float = 40.0
    system_y: float = 23.0
    set_course: float = 135.0
    actual_heading: float = 135.0
    sideslip: int = 0
    evasive: bool = False
    evasive_phase: float = 0.0
    docked: bool = False
    in_orbit: bool = True
    mode: str = "In Orbit"

    @property
    def galactic_position(self):
        """Continuous map position, including progress through the current region."""
        return (self.region_x + self.system_x / 50.0,
                self.region_y + self.system_y / 50.0)

    def move(self, dt, hyper_velocity, space_velocity, rest_mode=False):
        if rest_mode:
            return
        speed = space_velocity * 0.55 + hyper_velocity * 0.22
        if speed <= 0:
            return
        angle = math.radians(self.actual_heading - 90)
        self.system_x += math.cos(angle) * speed * dt
        self.system_y += math.sin(angle) * speed * dt
        while self.system_x < 0:
            self.system_x += 50
            self.region_x -= 1
        while self.system_x >= 50:
            self.system_x -= 50
            self.region_x += 1
        while self.system_y < 0:
            self.system_y += 50
            self.region_y -= 1
        while self.system_y >= 50:
            self.system_y -= 50
            self.region_y += 1


@dataclass
class Inventory:
    energy_capacity: int = 4000
    energy_units: float = 4000.0
    backup_energy_pct: int = 100
    supplies: int = 1000
    torpedoes: int = 24
    probe_loaded: int = 5
    probe_storage: int = 5
    pods: int = 2
    escorts: int = 4

    @property
    def energy_pct(self):
        return percent(self.energy_units, self.energy_capacity)


@dataclass
class CrewManifest:
    officers: int = 35
    regulars: int = 240
    shock_troops: int = 150
    prisoners: int = 0
    marines: int = 1
    medical_cases: int = 0

    @property
    def crew(self):
        return self.officers + self.regulars


@dataclass
class DamageModel:
    level: int = 1
    hull_pct: int = 100
    system_health: dict = field(default_factory=lambda: {
        "CMPTR": 100, "S/L ENG": 100, "HYP ENG": 100, "SRS": 100,
        "LRS": 100, "SHD CTL": 100, "TRP CTL": 100, "PHS CTL": 100,
        "TELEPRT": 100, "COM CTL": 100, "TRAC BM": 100, "PLS": 100,
    })

    def set_level(self, level):
        self.level = int(clamp(level, 1, 4))
        self.hull_pct = {1: 100, 2: 72, 3: 38, 4: 0}[self.level]
        health = {1: 100, 2: 65, 3: 30, 4: 0}[self.level]
        for key in self.system_health:
            self.system_health[key] = health


@dataclass
class WeaponBank:
    label: str
    cooldown: float
    ammo: str = "energy"
    reload: float = 0.0
    operational: bool = True

    @property
    def ready(self):
        return self.operational and self.reload <= 0


@dataclass
class ShieldSystem:
    policy: str = "Manual"
    aas_enabled: bool = False
    up: bool = True
    facings: list = field(default_factory=lambda: [500, 2000, 1000, 0])

    @property
    def pct(self):
        return percent(sum(self.facings), 3500)

    def set_policy(self, mode):
        self.policy = mode
        self.aas_enabled = mode == "Auto"
        if mode == "Manual":
            self.up = True
        elif mode == "Battle Entry":
            self.up = True
            self.facings = [750, 750, 750, 750]
        elif mode == "Maximum":
            self.up = True
            self.facings = [1000, 1000, 1000, 1000]


@dataclass
class Contact:
    id: str
    name: str
    kind: str
    x: float
    y: float
    region: tuple = (4, 6)
    threat: bool = False
    shields_up: bool = False
    prisoners: int = 0
    velocity: float = 0.0
    course: float = 0.0
    weapon: str = ""
    status: str = "READY"
    hull_pct: int = 100
    shield_strength: int = 100
    reload: float = 0.0
    deck_class: str = "Unknown"
    defenders: int = 0
    compartments: list = field(default_factory=list)
    boarding_status: str = "Not engaged"

    def __getitem__(self, key):
        return getattr(self, key)

    def __setitem__(self, key, value):
        setattr(self, key, value)

    def get(self, key, default=None):
        return getattr(self, key, default)

    def move(self, dt):
        if self.velocity <= 0:
            return
        angle = math.radians(self.course - 90)
        self.x += math.cos(angle) * self.velocity * dt
        self.y += math.sin(angle) * self.velocity * dt
        self.x = clamp(self.x, 0, 49)
        self.y = clamp(self.y, 0, 49)

    def reading(self, distance):
        return {
            "id": self.id, "name": self.name, "kind": self.kind,
            "x": self.x, "y": self.y, "region": self.region,
            "threat": self.threat, "shields_up": self.shields_up,
            "prisoners": self.prisoners, "velocity": self.velocity,
            "course": self.course, "weapon": self.weapon,
            "status": self.status, "hull_pct": self.hull_pct,
            "shield_strength": self.shield_strength,
            "reload": self.reload, "deck_class": self.deck_class,
            "defenders": self.defenders, "compartments": self.compartments,
            "boarding_status": self.boarding_status, "distance": distance,
        }


@dataclass
class ProbeTrack:
    id: int
    mode: str
    target: str
    x: float
    y: float
    power: float = 100.0
    detect: str = "None"
    status: str = "Outbound"

    def __getitem__(self, key):
        return getattr(self, key)

    def __setitem__(self, key, value):
        setattr(self, key, value)


INITIAL_MESSAGES = [
    ("Executive Off.", "Klagar-class battlecruiser ready"),
    ("Starfort SF-1", "24 torps / 4000 power loaded"),
    ("Fleet Command", "training patrol assigned"),
    ("Damage Control", "shields and tractor beam nominal"),
    ("Probe Control", "L:5 S:5 sensor probes loaded"),
    ("Landing Party", "150 shock troops aboard"),
    ("Strategic Cmd", "4 destroyer escorts standing by"),
]

INITIAL_REPORTS = [
    ("NAV-006", "docked at region 6,0"),
    ("ENG-4000", "power reserve 4000 units"),
    ("CMB-024", "torpedo stores full"),
    ("DATA-1000", "supplies 1000 tons"),
    ("TRP-150", "shock troops ready"),
    ("SCI-L5S5", "sensor probes loaded"),
    ("STG-004", "destroyer escort screen"),
]

INITIAL_CONTACTS = [
    Contact("SF-1", "Starfort", "base", 42.0, 20.0,
            threat=False, shields_up=False, prisoners=0, weapon="",
            hull_pct=100, shield_strength=0,
            deck_class="Starfort Docking Core", defenders=120,
            compartments=["Dock", "Control", "Stores", "Barracks", "Power", "Brig"]),
    Contact("TRUTH", "Truth", "planet", 47.0, 17.0,
            threat=False, shields_up=False, prisoners=0, weapon="",
            hull_pct=100, shield_strength=0),
    Contact("EN-1", "Krell Raider", "ship", 37.0, 27.0,
            threat=True, shields_up=True, prisoners=2,
            velocity=0.35, course=315.0, weapon="P1",
            hull_pct=100, shield_strength=80, reload=1.2,
            deck_class="Destroyer Deck Plan", defenders=38,
            compartments=["Bridge", "Forward Gun", "Port Berth", "Starboard Berth",
                          "Engineering", "Magazine", "Cargo", "Brig"]),
    Contact("MN-1", "Minefield", "mine", 43.0, 31.0,
            threat=True, shields_up=False, prisoners=0, weapon="",
            hull_pct=100, shield_strength=0),
]


def weapon_loadout():
    return [
        WeaponBank("Phaser", 2.0, "energy"),
        WeaponBank("Trp1", 5.0, "torpedo"),
        WeaponBank("Trp2", 5.0, "torpedo"),
        WeaponBank("ObltrPd", 8.0, "torpedo"),
    ]

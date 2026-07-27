"""Mutable runtime state and gameplay simulation for the cockpit."""

import math
import random

from gameplay import (
    Contact,
    CrewManifest,
    DamageModel,
    INITIAL_CONTACTS,
    INITIAL_MESSAGES,
    INITIAL_REPORTS,
    Inventory,
    MissionClock,
    NavigationState,
    ProbeTrack,
    ShieldSystem,
    bearing_from_delta,
    clamp,
    weapon_loadout,
)


class ShipState:
    """Game-owned truth that every console reads and the input layer mutates."""

    TOP_ALERT_LABELS = ["LowPwr", "LowSup", "LowTime", "Medical",
                        "SecAlt", "Mines", "Distress", "HullPn"]
    WEAPON_PROFILES = {
        "Phaser": {"damage": 18, "range": 8.0, "energy": 16, "accuracy": 0.94, "falloff": 0.055},
        "Trp1": {"damage": 42, "range": 16.0, "energy": 0, "accuracy": 0.86, "falloff": 0.035},
        "Trp2": {"damage": 42, "range": 16.0, "energy": 0, "accuracy": 0.86, "falloff": 0.035},
        "ObltrPd": {"damage": 70, "range": 20.0, "energy": 0, "accuracy": 0.78, "falloff": 0.030},
    }

    def __init__(self):
        self.rng = random.Random(74216)
        self.mission = MissionClock()
        self.nav = NavigationState()
        self.inventory = Inventory()
        self.crew_manifest = CrewManifest()
        self.damage = DamageModel()
        self.shields = ShieldSystem()
        self.weapon_banks = weapon_loadout()
        self.weapon_index = 0

        self.rest_mode = False
        self.sim_frozen = False
        self.alert_status = "Green"
        self.hyper_velocity = 0
        self.space_velocity = 0
        self.weapon_setting = "Destroy"
        self.weapon_condition = "Auto"
        self.weapon_auto = True
        self.weapon_destroy = True
        self.combat_alignment = "BCS"
        self.combat_overlays = {
            "Menu": False,
            "Grid": True,
            "Head": True,
            "Target": True,
            "Line": False,
        }
        self.ecm_enabled = False
        self.cmf_enabled = False
        self.tractor_enabled = False
        self.science_scope = "LRS"
        self.science_page = "Dept Q"
        self.computer_page = "Star Systems"
        self.self_destruct_armed = False
        self.self_destructed = False
        self.ship_destroyed = False
        self.notepad_text = ""

        self.feed_index = 1
        self.feed_clock = 0
        self.messages = list(INITIAL_MESSAGES)
        self.reports = list(INITIAL_REPORTS)
        self.contacts = [Contact(**vars(contact)) for contact in INITIAL_CONTACTS]
        self.target_index = 1
        self.active_probes = []
        self.status_flags = {}
        self.energy_usage = 20
        self._sync_systems()
        self._sync_navigation()

    # --- compatibility readouts ---------------------------------------

    @property
    def mission_elapsed_days(self):
        return self.mission.elapsed_days

    @property
    def time_left_days(self):
        return self.mission.time_left_days

    @property
    def region_x(self):
        return self.nav.region_x

    @region_x.setter
    def region_x(self, value):
        self.nav.region_x = value

    @property
    def region_y(self):
        return self.nav.region_y

    @region_y.setter
    def region_y(self, value):
        self.nav.region_y = value

    @property
    def galactic_position(self):
        return self.nav.galactic_position

    @property
    def system_x(self):
        return self.nav.system_x

    @system_x.setter
    def system_x(self, value):
        self.nav.system_x = value

    @property
    def system_y(self):
        return self.nav.system_y

    @system_y.setter
    def system_y(self, value):
        self.nav.system_y = value

    @property
    def set_course(self):
        return self.nav.set_course

    @property
    def actual_heading(self):
        return self.nav.actual_heading

    @property
    def nav_evasive(self):
        return self.nav.evasive

    @property
    def nav_sideslip(self):
        return self.nav.sideslip

    @property
    def docked(self):
        return self.nav.docked

    @docked.setter
    def docked(self, value):
        self.nav.docked = bool(value)

    @property
    def in_orbit(self):
        return self.nav.in_orbit

    @in_orbit.setter
    def in_orbit(self, value):
        self.nav.in_orbit = bool(value)

    @property
    def energy_capacity(self):
        return self.inventory.energy_capacity

    @property
    def energy_units(self):
        return self.inventory.energy_units

    @energy_units.setter
    def energy_units(self, value):
        self.inventory.energy_units = value

    @property
    def backup_energy_pct(self):
        return self.inventory.backup_energy_pct

    @property
    def supplies(self):
        return round(self.inventory.supplies)

    @property
    def torpedoes(self):
        return self.inventory.torpedoes

    @torpedoes.setter
    def torpedoes(self, value):
        self.inventory.torpedoes = max(0, int(value))

    @property
    def probe_loaded(self):
        return self.inventory.probe_loaded

    @probe_loaded.setter
    def probe_loaded(self, value):
        self.inventory.probe_loaded = max(0, int(value))

    @property
    def probe_storage(self):
        return self.inventory.probe_storage

    @probe_storage.setter
    def probe_storage(self, value):
        self.inventory.probe_storage = max(0, int(value))

    @property
    def pods(self):
        return self.inventory.pods

    @property
    def escorts(self):
        return self.inventory.escorts

    @property
    def crew(self):
        return self.crew_manifest.crew

    @property
    def shock_troops(self):
        return self.crew_manifest.shock_troops

    @shock_troops.setter
    def shock_troops(self, value):
        self.crew_manifest.shock_troops = max(0, int(value))

    @property
    def prisoners(self):
        return self.crew_manifest.prisoners

    @prisoners.setter
    def prisoners(self, value):
        self.crew_manifest.prisoners = max(0, int(value))

    @property
    def marines(self):
        return self.crew_manifest.marines

    @property
    def medical_cases(self):
        return self.crew_manifest.medical_cases

    @property
    def damage_level(self):
        return self.damage.level

    @property
    def hull_pct(self):
        return self.damage.hull_pct

    @property
    def weapons(self):
        return [bank.label for bank in self.weapon_banks]

    @property
    def weapon_reload(self):
        return [bank.reload for bank in self.weapon_banks]

    @property
    def selected_weapon(self):
        return self.weapon_banks[self.weapon_index].label

    @property
    def selected_target(self):
        return self.contacts[self.target_index % len(self.contacts)]

    @property
    def aas_enabled(self):
        return self.shields.aas_enabled

    @property
    def shield_policy(self):
        return self.shields.policy

    @property
    def shields_up(self):
        return self.shields.up

    @shields_up.setter
    def shields_up(self, value):
        self.shields.up = bool(value)

    @property
    def shield_strength(self):
        return self.shields.facings

    @property
    def energy_pct(self):
        return self.inventory.energy_pct

    @property
    def shield_pct(self):
        return self.shields.pct if self.shields.up else 0

    @property
    def energy_color(self):
        if self.energy_usage > 70 or self.energy_pct < 25:
            return "red"
        if self.energy_usage > 35 or self.energy_pct < 45:
            return "yellow"
        return "green"

    # --- simulation tick ------------------------------------------------

    def tick(self, dt):
        if self.sim_frozen:
            return
        dt = max(0.0, min(float(dt), 0.25))
        if self.self_destructed or self.ship_destroyed:
            self._sync_systems()
            self._sync_navigation()
            return
        self.nav.evasive_phase += dt
        self._sync_systems()
        self.nav.move(dt, self.hyper_velocity, self.space_velocity, self.rest_mode)
        self._advance_contacts(dt)
        self._drain_energy(dt)
        self._drain_supplies(dt)
        self._reload_weapons(dt)
        self._enemy_combat(dt)
        self.mission.advance(dt, self.rest_mode, self.hyper_velocity)
        self._update_probe_tracks(dt)
        self._sync_nav_proximity()
        self._sync_systems()
        self._sync_navigation()

    # --- command methods ------------------------------------------------

    def toggle_rest(self, active=None):
        self.rest_mode = (not self.rest_mode) if active is None else bool(active)
        self.add_message("Executive Off.", "rest cycle engaged" if self.rest_mode else "rest cycle cancelled")

    def toggle_sim_freeze(self, active=None):
        self.sim_frozen = (not self.sim_frozen) if active is None else bool(active)
        self.add_message("Computer", "simulation frozen" if self.sim_frozen else "simulation resumed")

    def set_damage_level(self, level):
        self.damage.set_level(level)
        self.add_message("Damage Control", f"hull condition level {self.damage.level}")

    def cycle_damage_system(self, name):
        levels = [100, 65, 30, 0]
        if name.startswith("HULL"):
            current = self.damage.hull_pct
            if current not in levels:
                current = 100
        else:
            current = self.damage.system_health.get(name, 100)
            if current not in levels:
                current = 100
        next_level = levels[(levels.index(current) + 1) % len(levels)]
        if name.startswith("HULL"):
            self._set_ship_hull_pct(next_level)
        else:
            self.damage.system_health[name] = next_level
        self.add_message("Damage Control", f"{name} damage set to {next_level}%")

    def change_hyper_velocity(self, delta):
        if self.damage.system_health["HYP ENG"] <= 0:
            self.add_message("Engineering", "hyperdrive inoperative")
            return
        old = self.hyper_velocity
        self.hyper_velocity = int(clamp(self.hyper_velocity + int(delta), 0, 10))
        if self.hyper_velocity != old:
            self.nav.in_orbit = False
            self.nav.docked = False
            self.add_message("Helm", f"hyper velocity {self.hyper_velocity}")

    def change_space_velocity(self, delta):
        if self.damage.system_health["S/L ENG"] <= 30 and delta > 0 and self.space_velocity >= 5:
            self.add_message("Engineering", "sublight engines degraded")
            return
        old = self.space_velocity
        self.space_velocity = int(clamp(self.space_velocity + int(delta), 0, 10))
        if self.space_velocity != old:
            self.nav.in_orbit = False
            self.nav.docked = False
            self.add_message("Helm", f"sublight velocity {self.space_velocity}")

    def set_nav_course(self, degrees):
        self.nav.set_course = float(degrees) % 360
        self.nav.sideslip = 0
        self.add_message("Navigation", f"course set {round(self.nav.set_course) % 360}")
        self._sync_navigation()

    def plot_course_to_target(self):
        target = self.selected_target
        dx = target.x - self.nav.system_x
        dy = target.y - self.nav.system_y
        if abs(dx) < 0.01 and abs(dy) < 0.01:
            self.add_message("Navigation", "target already at current position")
            return False
        self.set_nav_course(bearing_from_delta(dx, dy))
        self.add_message("Navigation", f"plotted course to {target.name}")
        return True

    def select_nav_contact(self, index, plot=True):
        if not self.contacts:
            return False
        self.target_index = int(index) % len(self.contacts)
        target = self.selected_target
        self.add_message("Navigation", f"target set {target.name}")
        if plot:
            self.plot_course_to_target()
        else:
            self._sync_navigation()
        return True

    def set_nav_waypoint(self, x, y, plot=True):
        waypoint = next((c for c in self.contacts if c.id == "NAV-WP"), None)
        x = clamp(float(x), 0, 49)
        y = clamp(float(y), 0, 49)
        if waypoint is None:
            waypoint = Contact("NAV-WP", "Waypoint", "waypoint", x, y,
                               region=(round(self.nav.region_x), round(self.nav.region_y)),
                               threat=False, shields_up=False, prisoners=0, weapon="",
                               hull_pct=100, shield_strength=0, status="PLOTTED")
            self.contacts.append(waypoint)
        else:
            waypoint.x = x
            waypoint.y = y
            waypoint.region = (round(self.nav.region_x), round(self.nav.region_y))
            waypoint.status = "PLOTTED"
        self.target_index = self.contacts.index(waypoint)
        self.add_message("Navigation", f"waypoint {round(x)}, {round(y)}")
        if plot:
            self.plot_course_to_target()
        else:
            self._sync_navigation()
        return True

    def select_nav_point(self, x, y, threshold=3.0):
        x = clamp(float(x), 0, 49)
        y = clamp(float(y), 0, 49)
        candidates = [
            (math.hypot(c.x - x, c.y - y), idx)
            for idx, c in enumerate(self.contacts)
            if c.kind != "waypoint" and c.status != "DESTROYED"
        ]
        if candidates:
            distance, index = min(candidates)
            if distance <= threshold:
                return self.select_nav_contact(index, plot=True)
        return self.set_nav_waypoint(x, y, plot=True)

    def set_nav_evasive(self, active):
        self.nav.evasive = bool(active)
        self.add_message("Navigation", "evasive course enabled" if active else "evasive course cancelled")
        self._sync_navigation()

    def adjust_nav_sideslip(self, amount):
        amount = int(amount)
        self.nav.sideslip = int(clamp(self.nav.sideslip + amount, -9, 9))
        if amount:
            side = "port" if amount < 0 else "starboard"
            self.add_message("Navigation", f"sideslip {side} vector set")
        self._sync_navigation()

    def cycle_weapon(self, delta):
        self.weapon_index = (self.weapon_index + int(delta)) % len(self.weapon_banks)
        self.add_message("Weapons", f"{self.selected_weapon} selected")

    def select_weapon(self, name):
        if name in self.weapons:
            self.weapon_index = self.weapons.index(name)
            self.add_message("Weapons", f"{self.selected_weapon} selected")

    def set_combat_alignment(self, alignment):
        self.combat_alignment = "SCS" if alignment == "SCS" else "BCS"
        self.add_message("Combat", f"{self.combat_alignment} alignment selected")

    def set_combat_overlay(self, overlay, active):
        if overlay not in self.combat_overlays:
            return False
        self.combat_overlays[overlay] = bool(active)
        state = "shown" if active else "hidden"
        self.add_message("Combat", f"{overlay.lower()} overlay {state}")
        return True

    def combat_overlay(self, overlay):
        return bool(self.combat_overlays.get(overlay, False))

    def set_weapon_condition(self, condition):
        self.weapon_condition = "Cont" if condition == "Cont" else "Auto"
        self.weapon_auto = self.weapon_condition == "Auto"
        self.add_message("Weapons", f"{self.weapon_condition} fire mode")

    def set_weapon_setting(self, setting):
        valid = {"Destroy", "Disable", "Standby", "Conditional"}
        self.weapon_setting = setting if setting in valid else "Destroy"
        self.weapon_destroy = self.weapon_setting == "Destroy"
        self.add_message("Weapons", f"{self.weapon_setting.lower()} setting")

    def toggle_ecm(self, active=None):
        self.ecm_enabled = (not self.ecm_enabled) if active is None else bool(active)
        self.add_message("Weapons", "ECM enabled" if self.ecm_enabled else "ECM disabled")
        self._sync_systems()

    def fire_selected_weapon(self):
        bank = self.weapon_banks[self.weapon_index]
        if not bank.ready:
            self.add_message("Weapons", f"{bank.label} not ready")
            return False
        target = self.selected_target
        if self.weapon_setting == "Standby":
            self.add_message("Weapons", "fire held: weapons on standby")
            return False
        if self.weapon_setting == "Conditional" and not target.threat and not target.shields_up:
            self.add_message("Weapons", "conditional fire hold")
            return False
        if target.kind not in ("ship", "base", "mine"):
            self.add_message("Weapons", "target lock refused")
            return False
        if target.status in ("DESTROYED", "CAPTURED"):
            self.add_message("Weapons", f"{target.name} already neutralized")
            return False
        if self.ecm_enabled:
            self.add_message("Weapons", "ECM blocks target lock")
            return False
        profile = self.WEAPON_PROFILES.get(bank.label, self.WEAPON_PROFILES["Phaser"])
        distance = self._distance_to(target)
        if distance > profile["range"]:
            self.add_message("Weapons", f"{target.name} beyond {bank.label} range")
            return False
        if bank.ammo == "torpedo" and self.inventory.torpedoes <= 0:
            self.add_message("Weapons", "torpedo stores empty")
            return False
        if bank.label == "ObltrPd" and self.inventory.pods <= 0:
            self.add_message("Weapons", "obliterator pod stores empty")
            return False
        if bank.ammo == "energy" and self.inventory.energy_units < profile["energy"]:
            self.add_message("Weapons", "insufficient weapon power")
            return False
        if bank.ammo == "torpedo":
            if bank.label == "ObltrPd":
                self.inventory.pods = max(0, self.inventory.pods - 1)
            else:
                self.inventory.torpedoes -= 1
        else:
            self.inventory.energy_units = max(0, self.inventory.energy_units - profile["energy"])
        bank.reload = bank.cooldown
        accuracy = clamp(profile["accuracy"] - distance * profile["falloff"], 0.22, 0.98)
        if self.combat_alignment == "SCS":
            accuracy = min(0.98, accuracy + 0.08)
        if target.kind == "mine":
            accuracy = min(0.98, accuracy + 0.12)
        if self.rng.random() > accuracy:
            self.add_message("Weapons", f"{bank.label} missed {target.name}")
            return True

        outcome = self._apply_target_damage(target, profile["damage"], bank.label)
        self.add_message("Weapons", outcome)
        return True

    def set_shield_mode(self, mode):
        self.shields.set_policy(mode)
        if mode == "Auto":
            self.add_message("Shield Control", "AAS enabled")
        elif mode == "Manual":
            self.add_message("Shield Control", "manual shield control")
        elif mode == "Battle Entry":
            self.add_message("Shield Control", "battle entry shields")
        elif mode == "Maximum":
            self.add_message("Shield Control", "maximum shields raised")
        self._sync_systems()

    def set_science_scope(self, scope):
        self.science_scope = "SRS" if scope == "SRS" else "LRS"
        if self.damage.system_health.get(self.science_scope, 100) <= 0:
            self.add_message("Science", f"{self.science_scope} inoperative")
        else:
            self.add_message("Science", f"{self.science_scope} selected")

    def toggle_science_scope(self):
        self.set_science_scope("SRS" if self.science_scope == "LRS" else "LRS")

    def set_science_page(self, page):
        self.science_page = "Planet Data" if page == "Planet Data" else "Dept Q"
        self.add_message("Science", f"{self.science_page} display selected")

    def set_computer_page(self, page):
        valid = {None,"Combat Status", "Information", "Landing Party", "Planets",
                 "Star Systems", "Bases", "Intelligence", "Reference Lib",
                 "Self-Destruct", "Special Services"}


        self.computer_page = page if page in valid else "Star Systems"
        if self.computer_page != "Self-Destruct" and self.self_destruct_armed:
            self.self_destruct_armed = False
            self.add_message("Computer", "self-destruct authorization cancelled")
        elif self.computer_page != "Self-Destruct":
            self.add_message("Computer", f"{self.computer_page} selected")

        # if primary_mode == None:


    def activate_self_destruct(self):
        self.computer_page = "Self-Destruct"
        if self.self_destructed:
            self.add_message("Computer", "self-destruct already completed")
            return True
        if not self.self_destruct_armed:
            self.self_destruct_armed = True
            self.add_message("Computer", "self-destruct authorization armed")
            self.add_message("Computer", "select self-destruct again to confirm")
            return False

        self.self_destruct_armed = False
        self.self_destructed = True
        self.ship_destroyed = True
        self.hyper_velocity = 0
        self.space_velocity = 0
        self.shields.up = False
        self.inventory.energy_units = 0
        self.damage.set_level(4)
        self.status_flags["Distress"] = True
        self.alert_status = "Red"
        self.add_message("Computer", "SELF-DESTRUCT SEQUENCE COMPLETE")
        self.add_message("Damage Control", "battlecruiser destroyed")
        self._sync_systems()
        self._sync_navigation()
        return True

    def launch_probe(self):
        if self.inventory.probe_loaded <= 0:
            if self.inventory.probe_storage > 0:
                self.inventory.probe_storage -= 1
                self.inventory.probe_loaded += 1
                self.add_message("Probe Control", "probe loaded from storage")
            else:
                self.add_message("Probe Control", "no probes available")
                return False
        self.inventory.probe_loaded -= 1
        probe_no = len(self.active_probes) + 1
        target = self.selected_target
        self.active_probes.append(ProbeTrack(
            id=probe_no,
            mode="Survey" if target.kind == "planet" else "Track",
            target=target.id,
            x=self.nav.system_x,
            y=self.nav.system_y,
            detect=target.kind.title(),
        ))
        self.add_message("Probe Control", f"probe {probe_no} launched toward {target.name}")
        return True

    def attempt_boarding(self):
        target = self.selected_target
        if target.kind not in ("ship", "base"):
            target.boarding_status = "No boarding target"
            self.add_message("Security", "boarding target invalid")
            return False
        if target.status == "DESTROYED":
            target.boarding_status = "Target destroyed"
            self.add_message("Security", "boarding impossible: target destroyed")
            return False
        if target.shields_up:
            target.boarding_status = "Blocked by shields"
            self.add_message("Security", "boarding blocked: target shields up")
            return False
        if self.crew_manifest.shock_troops < 10:
            target.boarding_status = "Troops unavailable"
            self.add_message("Security", "boarding blocked: troops unavailable")
            return False
        self.crew_manifest.shock_troops -= 10
        captured = max(1, target.prisoners)
        self.crew_manifest.prisoners += captured
        target.prisoners = 0
        target.defenders = max(0, target.defenders - 18)
        target.boarding_status = "Secured" if target.defenders == 0 else "Boarding action underway"
        self.add_message("Security", f"boarding complete: {captured} prisoners held")
        return True

    def boarding_context(self):
        target = self.selected_target
        valid = target.kind in ("ship", "base")
        if not valid:
            status = "NO BOARDING TARGET"
        elif target.shields_up:
            status = "BLOCKED: TARGET SHIELDS UP"
        elif self.crew_manifest.shock_troops < 10:
            status = "BLOCKED: TROOPS UNAVAILABLE"
        else:
            status = target.boarding_status
            if status == "Not engaged":
                status = "READY TO BOARD"
        return {
            "valid": valid,
            "target": target.name,
            "target_type": target.kind.title(),
            "deck_class": target.deck_class if valid else "No deck plan",
            "shields_up": target.shields_up if valid else False,
            "shock_troops": self.crew_manifest.shock_troops,
            "space_marines": self.crew_manifest.marines,
            "defenders": target.defenders if valid else 0,
            "prisoners": target.prisoners if valid else 0,
            "compartments": list(target.compartments) if valid else [],
            "status": status,
            "secured": valid and target.boarding_status == "Secured",
        }

    def target_solution(self):
        target = self.selected_target
        dx = target.x - self.nav.system_x
        dy = target.y - self.nav.system_y
        bearing = round(bearing_from_delta(dx, dy))
        if self.combat_alignment == "BCS":
            bearing = round((bearing - self.nav.actual_heading) % 360)
        velocity = target.velocity if target.threat else 0.0
        return {
            "rpos": f"{round(dx)}, {round(dy)}",
            "bearing": f"{bearing} deg",
            "velocity": f"{velocity:.1f}*",
            "weapon": self.selected_weapon,
            "status": target.status,
            "hull": target.hull_pct,
            "shields": target.shield_strength if target.shields_up else 0,
        }

    def target_next_contact(self):
        if not self.contacts:
            return
        for step in range(1, len(self.contacts) + 1):
            index = (self.target_index + step) % len(self.contacts)
            if self.contacts[index].status != "DESTROYED":
                self.select_nav_contact(index, plot=False)
                self.add_message("Targeting", f"target {self.selected_target.name}")
                return

    def select_combat_point(self, x, y, threshold=2.75):
        candidates = [
            (math.hypot(contact.x - x, contact.y - y), index)
            for index, contact in enumerate(self.contacts)
            if contact.status != "DESTROYED"
        ]
        if not candidates:
            self.add_message("Targeting", "no tactical contacts")
            return False
        distance, index = min(candidates)
        if distance > threshold:
            self.add_message("Targeting", "no contact under cursor")
            return False
        self.target_index = index
        self.add_message("Targeting", f"target {self.selected_target.name}")
        self._sync_navigation()
        return True

    # --- messages and reports -----------------------------------------

    def add_message(self, source, body):
        item = (str(source)[:16], str(body)[:42])
        if not self.messages or self.messages[-1] != item:
            self.messages.append(item)
            self.messages = self.messages[-9:]

    def report_rows(self):
        dynamic = [
            ("NAV", f"reg {self.nav_region[0]},{self.nav_region[1]} orb {self.nav_orbit[0]}{self.nav_orbit[1]}"),
            ("ENG", f"power {self.energy_pct}% usage {self.energy_usage}%"),
            ("CMB", f"{self.selected_weapon} torps {self.inventory.torpedoes}"),
            ("SCI", f"L:{self.probe_loaded} S:{self.probe_storage} contacts {len(self.scanner_contacts())}"),
            ("SEC", f"troops {self.shock_troops} prisoners {self.prisoners}"),
        ]
        return (self.reports + dynamic)[-9:]

    # --- contacts and indicators --------------------------------------

    def scanner_contacts(self):
        if self.ecm_enabled:
            return []
        contacts = []
        for contact in self.contacts:
            d = self._distance_to(contact)
            if d <= 18:
                contacts.append(contact.reading(d))
        return contacts

    def science_range(self):
        base_range = 6 if self.science_scope == "SRS" else 18
        health = self.damage.system_health.get(self.science_scope, 100)
        if health <= 0:
            return 0
        if health < 50:
            return max(1, base_range // 2)
        return base_range

    def science_contacts(self):
        if self.ecm_enabled:
            return []
        contacts = []
        range_limit = self.science_range()
        if range_limit <= 0:
            return []
        for contact in self.contacts:
            if contact.status == "DESTROYED":
                continue
            d = self._distance_to(contact)
            if d <= range_limit:
                contacts.append(contact.reading(d))
        contacts.sort(key=lambda item: item["distance"])
        return contacts

    def tactical_contacts(self):
        rows = []
        for contact in self.contacts:
            d = self._distance_to(contact)
            if d <= 25 or contact is self.selected_target:
                rows.append(contact.reading(d))
        return rows

    def status_indicator_goods(self):
        return [
            self.energy_pct >= 25,
            self.inventory.supplies >= 250,
            self.mission.time_left_days >= 1,
            self.crew_manifest.medical_cases == 0,
            self.alert_status != "Red",
            not self.status_flags.get("Mines", False),
            not self.status_flags.get("Distress", False),
            self.damage.hull_pct >= 40,
            not self.ecm_enabled,
            self.shield_pct >= 25,
        ]

    # --- private simulation helpers -----------------------------------

    def _advance_contacts(self, dt):
        for contact in self.contacts:
            if contact.status not in ("DESTROYED", "DISABLED", "CAPTURED"):
                contact.move(dt)

    def _drain_energy(self, dt):
        drain = self.energy_usage * dt * (0.08 if not self.rest_mode else 0.03)
        self.inventory.energy_units = max(0.0, self.inventory.energy_units - drain)
        if self.inventory.energy_units <= 0:
            self.hyper_velocity = 0
            self.space_velocity = 0
            self.shields.up = False

    def _drain_supplies(self, dt):
        if self.rest_mode:
            return
        burn = dt * (0.0008 + (0.0004 if self.space_velocity or self.hyper_velocity else 0))
        self.inventory.supplies = max(0, self.inventory.supplies - burn)

    def _reload_weapons(self, dt):
        rate = 1.4 if self.rest_mode else 1.0
        for bank in self.weapon_banks:
            bank.reload = max(0.0, bank.reload - dt * rate)

    def _enemy_combat(self, dt):
        for contact in self.contacts:
            if contact.kind not in ("ship", "base") or not contact.threat:
                continue
            if contact.status in ("DESTROYED", "DISABLED", "CAPTURED"):
                continue
            contact.reload = max(0.0, contact.reload - dt)
            distance = self._distance_to(contact)
            if distance > 12 or contact.reload > 0:
                continue
            contact.reload = 5.0 + self.rng.random() * 2.0
            accuracy = clamp(0.80 - distance * 0.035 - (0.16 if self.nav.evasive else 0), 0.25, 0.90)
            if self.rng.random() > accuracy:
                self.add_message("Combat", f"{contact.name} attack missed")
                continue
            damage = 12 if contact.weapon.startswith("P") else 18
            report = self._apply_ship_damage(damage, contact)
            self.add_message("Combat", report)

    def _update_probe_tracks(self, dt):
        for probe in self.active_probes:
            contact = next((c for c in self.contacts if c.id == probe.target), None)
            if contact:
                dx = contact.x - probe.x
                dy = contact.y - probe.y
                dist = max(0.01, math.hypot(dx, dy))
                step = min(dist, dt * 3.0)
                probe.x += dx / dist * step
                probe.y += dy / dist * step
                probe.status = "Mapping" if dist < 0.8 else "Outbound"
            probe.power = max(0, probe.power - dt * 0.35)

    def _sync_nav_proximity(self):
        if self.hyper_velocity or self.space_velocity:
            self.nav.in_orbit = False
            self.nav.docked = False
            return
        target = self.selected_target
        if target.status == "DESTROYED":
            self.nav.in_orbit = False
            self.nav.docked = False
            return
        distance = self._distance_to(target)
        if target.kind == "base" and distance <= 0.9:
            self.nav.docked = True
            self.nav.in_orbit = False
        elif target.kind == "planet" and distance <= 1.5:
            self.nav.in_orbit = True
            self.nav.docked = False
        else:
            self.nav.in_orbit = False
            self.nav.docked = False

    def _apply_target_damage(self, target, damage, weapon_name):
        remaining = int(damage)
        shield_hit = 0
        if target.shields_up and target.shield_strength > 0:
            shield_hit = min(target.shield_strength, remaining)
            target.shield_strength -= shield_hit
            remaining -= shield_hit
            if target.shield_strength <= 0:
                target.shields_up = False
                target.shield_strength = 0
                target.status = "SHIELDS DOWN"

        if remaining <= 0:
            return f"{weapon_name} hit {target.name} shields -{shield_hit}"

        if target.kind == "mine":
            target.hull_pct = 0
            target.threat = False
            target.status = "DESTROYED"
            target.velocity = 0
            return f"{target.name} destroyed"

        if self.weapon_setting == "Disable":
            target.hull_pct = max(15, target.hull_pct - remaining)
            if target.hull_pct <= 35:
                target.status = "DISABLED"
                target.threat = False
                target.velocity = 0
                target.weapon = ""
                target.boarding_status = "Ready for boarding"
                return f"{target.name} disabled"
            target.status = "DAMAGED"
            return f"{target.name} hull damaged to {target.hull_pct}%"

        target.hull_pct = max(0, target.hull_pct - remaining)
        if target.hull_pct <= 0:
            target.status = "DESTROYED"
            target.threat = False
            target.shields_up = False
            target.shield_strength = 0
            target.velocity = 0
            target.weapon = ""
            target.defenders = 0
            target.boarding_status = "Target destroyed"
            return f"{target.name} destroyed"
        if target.hull_pct <= 35:
            target.status = "CRIPPLED"
            target.threat = False
            target.velocity *= 0.35
            return f"{target.name} crippled"
        target.status = "DAMAGED"
        return f"{target.name} hull damaged to {target.hull_pct}%"

    def _apply_ship_damage(self, damage, attacker):
        remaining = int(damage)
        if self.shields.up and sum(self.shields.facings) > 0:
            dx = attacker.x - self.nav.system_x
            dy = attacker.y - self.nav.system_y
            bearing = bearing_from_delta(dx, dy)
            facing = int(((bearing + 45) % 360) // 90) % 4
            absorbed = min(self.shields.facings[facing], remaining)
            self.shields.facings[facing] -= absorbed
            remaining -= absorbed
            if remaining <= 0:
                return f"{attacker.name} hit shield {facing + 1}"
            if sum(self.shields.facings) <= 0:
                self.shields.up = False

        self._set_ship_hull_pct(self.damage.hull_pct - remaining)
        system = self.rng.choice(list(self.damage.system_health))
        self.damage.system_health[system] = max(0, self.damage.system_health[system] - remaining * 2)
        if self.damage.hull_pct <= 0:
            self.ship_destroyed = True
            self.hyper_velocity = 0
            self.space_velocity = 0
            self.shields.up = False
            self.inventory.energy_units = 0
            return f"{attacker.name} destroyed the battlecruiser"
        return f"{attacker.name} scored hull hit -{remaining}%"

    def _set_ship_hull_pct(self, pct):
        self.damage.hull_pct = round(clamp(pct, 0, 100))
        if self.damage.hull_pct <= 0:
            self.damage.level = 4
        elif self.damage.hull_pct < 40:
            self.damage.level = 3
        elif self.damage.hull_pct < 75:
            self.damage.level = 2
        else:
            self.damage.level = 1

    def _sync_systems(self):
        if self.self_destructed or self.ship_destroyed:
            self.energy_usage = 0
            self.alert_status = "Red"
            self.status_flags = {
                "LowPwr": True,
                "LowSup": self.inventory.supplies < 250,
                "LowTime": self.mission.time_left_days < 1.0,
                "Medical": self.crew_manifest.medical_cases > 0,
                "SecAlt": True,
                "Mines": False,
                "Distress": True,
                "HullPn": True,
            }
            return
        threat_contacts = [c for c in self.scanner_contacts() if c.get("threat")]
        mines = any(c["kind"] == "mine" for c in threat_contacts)
        if self.shields.aas_enabled:
            if threat_contacts:
                self.shields.up = True
                if self.shields.policy == "Auto":
                    self.shields.facings = [850, 850, 850, 850]
            elif self.shields.policy == "Auto":
                self.shields.up = False

        shield_load = 18 if self.shields.up else 0
        if self.shields.policy == "Maximum":
            shield_load = 30
        elif self.shields.policy == "Battle Entry":
            shield_load = 24
        self.energy_usage = int(clamp(
            20 + self.hyper_velocity * 5 + self.space_velocity * 3 + shield_load +
            (8 if self.tractor_enabled else 0) + (5 if self.ecm_enabled else 0) +
            (4 if self.cmf_enabled else 0),
            0, 100,
        ))
        self.alert_status = "Red" if threat_contacts and self.shields.up else (
            "Yellow" if threat_contacts or self.energy_pct < 25 or self.damage.hull_pct < 40 else "Green")
        self.status_flags = {
            "LowPwr": self.energy_pct < 25,
            "LowSup": self.inventory.supplies < 250,
            "LowTime": self.mission.time_left_days < 1.0,
            "Medical": self.crew_manifest.medical_cases > 0,
            "SecAlt": self.alert_status == "Red",
            "Mines": mines,
            "Distress": self.damage.hull_pct < 25 or self.energy_pct < 10,
            "HullPn": self.damage.hull_pct < 40,
        }

    def _sync_navigation(self):
        evasive_offset = math.sin(self.nav.evasive_phase * 5.0) * 45.0 if self.nav.evasive else 0.0
        slip_offset = 45.0 if self.nav.sideslip > 0 else (-45.0 if self.nav.sideslip < 0 else 0.0)
        self.nav.actual_heading = (self.nav.set_course + slip_offset + evasive_offset) % 360

        target = self.selected_target
        self.nav_region = (round(self.nav.region_x), round(self.nav.region_y))
        orbit_code = chr(ord("A") + int(clamp(self.nav.system_x // 2, 0, 25)))
        self.nav_orbit = (orbit_code, int(clamp(round(self.nav.system_y), 0, 99)))
        self.nav_course = round(self.nav.set_course) % 360
        self.nav_target = (round(target.x), round(target.y))
        self.nav_distance = round(self._distance_to(target) / 5.0, 1)
        self.nav_object = target.name if target.kind != "ship" else "Ship"
        if self.nav.docked:
            self.nav_mode = "Docked"
        elif self.nav.in_orbit:
            self.nav_mode = "In Orbit"
        elif self.nav.evasive:
            self.nav_mode = "Evasive"
        elif self.nav.sideslip:
            self.nav_mode = "Sideslip"
        elif self.hyper_velocity:
            self.nav_mode = "Hyperspace"
        else:
            self.nav_mode = "Norm Spc"
        self.nav.mode = self.nav_mode

    def _distance_to(self, contact):
        return math.hypot(self.nav.system_x - contact.x, self.nav.system_y - contact.y)

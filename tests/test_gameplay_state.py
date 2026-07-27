import unittest

from state import ShipState


class GameplayStateTests(unittest.TestCase):
    def test_engine_tick_moves_ship_and_drains_energy(self):
        state = ShipState()
        start = (state.system_x, state.system_y, state.energy_units)
        state.change_space_velocity(3)
        state.tick(1.0)
        self.assertNotEqual((state.system_x, state.system_y), start[:2])
        self.assertLess(state.energy_units, start[2])
        self.assertGreater(state.energy_usage, 20)

    def test_galactic_position_moves_continuously_across_region_boundary(self):
        state = ShipState()
        state.region_x = 4
        state.system_x = 49.9
        state.nav.actual_heading = 90
        before = state.galactic_position

        state.nav.move(0.1, hyper_velocity=0, space_velocity=2)

        self.assertEqual(state.region_x, 5)
        self.assertGreater(state.galactic_position[0], before[0])
        self.assertAlmostEqual(state.galactic_position[0] - before[0], 0.11 / 50)
        self.assertAlmostEqual(state.galactic_position[1], before[1])

    def test_sideslip_changes_actual_heading_not_set_course(self):
        state = ShipState()
        course = state.nav_course
        state.adjust_nav_sideslip(1)
        state.tick(0.1)
        self.assertEqual(state.nav_course, course)
        self.assertEqual(round((state.actual_heading - course) % 360), 45)

    def test_plot_course_to_target_moves_ship_toward_target(self):
        state = ShipState()
        enemy = next(i for i, c in enumerate(state.contacts) if c.kind == "ship")
        state.target_index = enemy
        state.contacts[enemy].velocity = 0
        before = state._distance_to(state.selected_target)
        self.assertTrue(state.plot_course_to_target())
        state.change_space_velocity(2)
        state.tick(1.0)
        after = state._distance_to(state.selected_target)
        self.assertLess(after, before)

    def test_nav_waypoint_sets_target_and_course(self):
        state = ShipState()
        self.assertTrue(state.set_nav_waypoint(45, 23))
        self.assertEqual(state.selected_target.id, "NAV-WP")
        self.assertEqual(state.nav_target, (45, 23))
        self.assertEqual(state.nav_course, 90)

    def test_stopped_ship_docks_or_orbits_when_close(self):
        state = ShipState()
        base = next(i for i, c in enumerate(state.contacts) if c.kind == "base")
        state.target_index = base
        state.system_x = state.contacts[base].x
        state.system_y = state.contacts[base].y
        state.tick(0.1)
        self.assertEqual(state.nav_mode, "Docked")

        planet = next(i for i, c in enumerate(state.contacts) if c.kind == "planet")
        state.target_index = planet
        state.system_x = state.contacts[planet].x
        state.system_y = state.contacts[planet].y
        state.nav.docked = False
        state.tick(0.1)
        self.assertEqual(state.nav_mode, "In Orbit")

    def test_science_lrs_and_srs_have_distinct_ranges(self):
        state = ShipState()
        state.ecm_enabled = False
        state.set_science_scope("LRS")
        lrs_ids = {contact["id"] for contact in state.science_contacts()}
        state.set_science_scope("SRS")
        srs_ids = {contact["id"] for contact in state.science_contacts()}
        self.assertGreaterEqual(len(lrs_ids), len(srs_ids))
        self.assertNotEqual(state.science_range(), 18)
        self.assertEqual(state.science_range(), 6)

    def test_damaged_selected_science_sensor_limits_contacts(self):
        state = ShipState()
        state.set_science_scope("LRS")
        self.assertGreater(len(state.science_contacts()), 0)
        state.damage.system_health["LRS"] = 0
        self.assertEqual(state.science_range(), 0)
        self.assertEqual(state.science_contacts(), [])

    def test_aas_and_ecm_follow_manual_sensor_rules(self):
        state = ShipState()
        self.assertTrue(any(c["threat"] for c in state.scanner_contacts()))
        state.set_shield_mode("Auto")
        state.tick(0.1)
        self.assertTrue(state.aas_enabled)
        self.assertTrue(state.shields_up)
        self.assertEqual(state.alert_status, "Red")
        state.toggle_ecm(True)
        self.assertEqual(state.scanner_contacts(), [])
        self.assertGreaterEqual(len(state.tactical_contacts()), 1)

    def test_weapon_fire_consumes_torpedo_and_reloads(self):
        state = ShipState()
        enemy = next(i for i, c in enumerate(state.contacts) if c.kind == "ship")
        state.target_index = enemy
        state.contacts[enemy].x = state.system_x
        state.contacts[enemy].y = state.system_y
        state.select_weapon("Trp1")
        torps = state.torpedoes
        self.assertTrue(state.fire_selected_weapon())
        self.assertEqual(state.torpedoes, torps - 1)
        self.assertGreater(state.weapon_reload[state.weapon_index], 0)

    def test_combat_fire_strips_shields_and_damages_hull(self):
        state = ShipState()
        enemy = next(i for i, c in enumerate(state.contacts) if c.kind == "ship")
        target = state.contacts[enemy]
        state.target_index = enemy
        target.x = state.system_x
        target.y = state.system_y
        target.shields_up = True
        target.shield_strength = 20
        target.hull_pct = 100
        state.select_weapon("Trp1")

        self.assertTrue(state.fire_selected_weapon())
        self.assertFalse(target.shields_up)
        self.assertEqual(target.shield_strength, 0)
        self.assertLess(target.hull_pct, 100)
        self.assertIn(target.status, ("DAMAGED", "CRIPPLED", "DESTROYED"))

    def test_disable_setting_neutralizes_target_without_destroying_it(self):
        state = ShipState()
        enemy = next(i for i, c in enumerate(state.contacts) if c.kind == "ship")
        target = state.contacts[enemy]
        state.target_index = enemy
        target.x = state.system_x
        target.y = state.system_y
        target.shields_up = False
        target.shield_strength = 0
        target.hull_pct = 40
        state.set_weapon_setting("Disable")
        state.select_weapon("Trp1")

        self.assertTrue(state.fire_selected_weapon())
        self.assertEqual(target.status, "DISABLED")
        self.assertFalse(target.threat)
        self.assertEqual(target.hull_pct, 15)

    def test_combat_overlay_toggles_are_state_backed(self):
        state = ShipState()
        self.assertTrue(state.combat_overlay("Grid"))
        self.assertTrue(state.set_combat_overlay("Grid", False))
        self.assertFalse(state.combat_overlay("Grid"))
        self.assertTrue(state.set_combat_overlay("Line", True))
        self.assertTrue(state.combat_overlay("Line"))
        self.assertFalse(state.set_combat_overlay("Bogus", True))

    def test_combat_point_selects_nearest_tactical_contact(self):
        state = ShipState()
        enemy = next(i for i, c in enumerate(state.contacts) if c.kind == "ship")
        target = state.contacts[enemy]
        self.assertTrue(state.select_combat_point(target.x + 0.25, target.y + 0.25))
        self.assertEqual(state.target_index, enemy)
        self.assertFalse(state.select_combat_point(0, 0, threshold=0.01))
        self.assertEqual(state.target_index, enemy)

    def test_enemy_return_fire_damages_ship_systems(self):
        state = ShipState()
        state.rng.seed(0)
        enemy = next(i for i, c in enumerate(state.contacts) if c.kind == "ship")
        target = state.contacts[enemy]
        target.x = state.system_x
        target.y = state.system_y
        target.reload = 0
        state.shields.facings = [0, 0, 0, 0]
        state.shields.up = False
        hull = state.hull_pct

        state.tick(0.25)
        self.assertLess(state.hull_pct, hull)
        self.assertTrue(any(v < 100 for v in state.damage.system_health.values()))

    def test_ship_damage_button_cycle_changes_system_health_levels(self):
        state = ShipState()
        state.cycle_damage_system("CMPTR")
        self.assertEqual(state.damage.system_health["CMPTR"], 65)
        state.cycle_damage_system("CMPTR")
        self.assertEqual(state.damage.system_health["CMPTR"], 30)
        state.cycle_damage_system("CMPTR")
        self.assertEqual(state.damage.system_health["CMPTR"], 0)
        state.cycle_damage_system("CMPTR")
        self.assertEqual(state.damage.system_health["CMPTR"], 100)

    def test_probe_launch_and_boarding_gate(self):
        state = ShipState()
        loaded = state.probe_loaded
        self.assertTrue(state.launch_probe())
        self.assertEqual(state.probe_loaded, loaded - 1)
        self.assertEqual(len(state.active_probes), 1)

        enemy = next(i for i, c in enumerate(state.contacts) if c.kind == "ship")
        state.target_index = enemy
        state.contacts[enemy].shields_up = True
        self.assertFalse(state.attempt_boarding())
        state.contacts[enemy].shields_up = False
        prisoners = state.prisoners
        self.assertTrue(state.attempt_boarding())
        self.assertGreater(state.prisoners, prisoners)

    def test_boarding_context_for_valid_blocked_and_invalid_targets(self):
        state = ShipState()
        enemy = next(i for i, c in enumerate(state.contacts) if c.kind == "ship")
        state.target_index = enemy
        state.contacts[enemy].shields_up = True
        ctx = state.boarding_context()
        self.assertTrue(ctx["valid"])
        self.assertTrue(ctx["shields_up"])
        self.assertIn("SHIELDS", ctx["status"])
        self.assertGreater(ctx["defenders"], 0)
        self.assertGreater(len(ctx["compartments"]), 0)

        state.contacts[enemy].shields_up = False
        ctx = state.boarding_context()
        self.assertTrue(ctx["valid"])
        self.assertFalse(ctx["shields_up"])
        self.assertEqual(ctx["status"], "READY TO BOARD")

        planet = next(i for i, c in enumerate(state.contacts) if c.kind == "planet")
        state.target_index = planet
        ctx = state.boarding_context()
        self.assertFalse(ctx["valid"])
        self.assertEqual(ctx["status"], "NO BOARDING TARGET")

    def test_successful_boarding_updates_context(self):
        state = ShipState()
        enemy = next(i for i, c in enumerate(state.contacts) if c.kind == "ship")
        state.target_index = enemy
        state.contacts[enemy].shields_up = False
        troops = state.shock_troops
        defenders = state.contacts[enemy].defenders
        self.assertTrue(state.attempt_boarding())
        ctx = state.boarding_context()
        self.assertLess(state.shock_troops, troops)
        self.assertLess(ctx["defenders"], defenders)
        self.assertIn(ctx["status"], ("Boarding action underway", "Secured"))

    def test_self_destruct_requires_confirmation_and_destroys_ship(self):
        state = ShipState()
        self.assertFalse(state.activate_self_destruct())
        self.assertEqual(state.computer_page, "Self-Destruct")
        self.assertTrue(state.self_destruct_armed)
        self.assertGreater(state.energy_pct, 0)
        self.assertGreater(state.hull_pct, 0)

        self.assertTrue(state.activate_self_destruct())
        self.assertTrue(state.self_destructed)
        self.assertFalse(state.self_destruct_armed)
        self.assertEqual(state.energy_pct, 0)
        self.assertEqual(state.hull_pct, 0)
        self.assertFalse(state.shields_up)
        self.assertEqual(state.hyper_velocity, 0)
        self.assertEqual(state.space_velocity, 0)
        self.assertEqual(state.alert_status, "Red")


if __name__ == "__main__":
    unittest.main()

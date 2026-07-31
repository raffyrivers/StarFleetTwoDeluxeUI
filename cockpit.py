"""Builds every console panel and draws its per-frame content.

Layout coordinates match the Star Fleet II Deluxe command screen. Static
readouts are expressed as data and rendered through shared helpers so text
always fits its box and the code stays compact.
"""

import math
import random
import pygame
from threeDEngine import wireframe_display as wfd
from threeDEngine import wireframe as wf
from core import (BLACK, PANEL_BG, FRAME, FRAME_DIM, BUTTON_FACE, CYAN, GREEN,
                  RED, YELLOW, GREY, MAGENTA, WHITE, color, font, fit_text,
                  text_line, asset)
from widgets import Panel, Button, Text, Display, CircleDisplay, StatusBar
from video import VideoDisplay

P = {}            # panels keyed by tab/name
WARN_WORDS = {"CAUTION", "LOW", "HOLD", "QUEUED", "LOCK"}
SPHERE_FRAME_COUNT = 120
SPHERE_ROTATION_FPS = 10

# Communication feed content (authentic Krellan briefing data).
MESSAGES = [
    ("Executive Off.", "Klagar-class battlecruiser ready"),
    ("Starfort SF-1", "24 torps / 4000 power loaded"),
    ("Fleet Command", "training patrol assigned"),
    ("Damage Control", "shields and tractor beam nominal"),
    ("Probe Control", "L:5 S:5 sensor probes loaded"),
    ("Landing Party", "150 shock troops aboard"),
    ("Strategic Cmd", "4 destroyer escorts standing by"),
]
REPORTS = [
    ("NAV-006", "docked at region 6,0"),
    ("ENG-4000", "power reserve 4000 units"),
    ("CMB-024", "torpedo stores full"),
    ("DATA-1000", "supplies 1000 tons"),
    ("TRP-150", "shock troops ready"),
    ("SCI-L5S5", "sensor probes loaded"),
    ("STG-004", "destroyer escort screen"),
]


# --- shared display helpers -------------------------------------------------

def text_rows(surface, rows, x=6, y=6, line_h=14, size=10):
    for text, fg in rows:
        fit_text(surface, text, [x, y, surface.get_width() - x - 4, line_h],
                 fg, size, align="left")
        y += line_h


def readout(surface, rows, x=6, y=6, line_h=15, size=11, label_w=82):
    for label, value, fg in rows:
        fit_text(surface, label, [x, y, label_w, line_h], CYAN, size, align="left")
        if value != "":
            fit_text(surface, value, [x + label_w + 6, y,
                     surface.get_width() - x - label_w - 10, line_h],
                     fg, size, align="left")
        y += line_h


def table(surface, headers, rows, x, y, widths, line_h=14, size=10, column_lines=False):
    surf_rect = surface.get_rect()
    cx = x
    for i, head in enumerate(headers):
        fit_text(surface, head, [cx, y, widths[i] - 2, line_h], CYAN, size, align="center")
        cx += widths[i]
        if column_lines:
            pygame.draw.line(surface, GREY, (cx, 0), (cx, surf_rect.h))
    pygame.draw.line(surface, FRAME, (0, y + line_h), (surf_rect.w + sum(widths), y + line_h), 1)
    for r, row in enumerate(rows):
        cx = x
        ry = y + line_h + 3 + r * line_h
       
        for i, cell in enumerate(row):
            fg = YELLOW if cell in WARN_WORDS else GREEN
            fit_text(surface, cell, [cx, ry, widths[i] - 2, line_h], fg, size, align="left")
            
            cx += widths[i]


def _project_sphere_texture(texture, diameter, longitude_offset=0.0):
    """Project an equirectangular texture onto a shaded orthographic sphere."""
    sphere = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
    center = (diameter - 1) / 2
    radius = center - 1
    texture_width, texture_height = texture.get_size()
    latitude_map = pygame.Surface((texture_width, diameter), pygame.SRCALPHA)

    for y in range(diameter):
        normal_y = max(-1, min(1, (center - y) / radius))
        latitude = math.asin(normal_y)
        texture_y = int((0.5 - latitude / math.pi) * texture_height)
        texture_y = max(0, min(texture_height - 1, texture_y))
        latitude_map.blit(
            texture.subsurface((0, texture_y, texture_width, 1)), (0, y)
        )

    for x in range(diameter):
        normal_x = (x - center) / radius
        if abs(normal_x) > 1:
            continue
        normal_z = math.sqrt(1 - normal_x * normal_x)
        longitude = math.asin(normal_x)
        texture_x = int(
            (0.5 + longitude / (2 * math.pi) + longitude_offset) * texture_width
        ) % texture_width
        half_height = radius * normal_z
        top = max(0, round(center - half_height))
        bottom = min(diameter, round(center + half_height) + 1)
        column = latitude_map.subsurface((texture_x, 0, 1, diameter))
        sphere.blit(
            pygame.transform.smoothscale(column, (1, bottom - top)), (x, top)
        )

    mask_size = 32
    mask = pygame.Surface((mask_size, mask_size), pygame.SRCALPHA)
    mask_center = (mask_size - 1) / 2
    mask_radius = mask_center
    light_x, light_y, light_z = -0.38, 0.46, 0.80
    for y in range(mask_size):
        normal_y = (mask_center - y) / mask_radius
        for x in range(mask_size):
            normal_x = (x - mask_center) / mask_radius
            distance = normal_x * normal_x + normal_y * normal_y
            if distance > 1:
                continue
            normal_z = math.sqrt(1 - distance)
            diffuse = max(
                0, normal_x * light_x + normal_y * light_y + normal_z * light_z
            )
            brightness = 0.42 + 0.58 * diffuse
            rim = min(0.22, (1 - normal_z) ** 2 * 0.3)
            shade = round(255 * brightness * (1 - rim))
            mask.set_at((x, y), (shade, shade, min(255, shade + 8), 255))

    mask = pygame.transform.smoothscale(mask, (diameter, diameter))
    sphere.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

    pygame.draw.circle(
        sphere, (90, 185, 235), (round(center), round(center)), round(radius), 1
    )
    return sphere


# --- panel construction -----------------------------------------------------

def build():
    P.clear()
    layout = [
       (10, 30, 440, 330, "Navigation Console", 168, True),
        (455, 30, 192, 225, "Science Console", 130, True),
        (656, 50, 655, 385, "Primary Display", 130, True),
        (1330, 30, 440, 60, "Status Indicators", 140, True),
        (451, 265, 197, 170, "Navigation", 0, True),
        (10, 361, 440, 225, "Star Map", 0, False),
        (1330, 110, 580, 260, "Computer Display", 140, True),
        (451, 451, 197, 135, "Data", 60, True),
        (660, 455, 655, 550, "Combat Console", 130, True),
        (1330, 390, 580, 350, "Strategic Command Console", 200, True),
        (10, 605, 640, 240, "Engineering Console", 160, True),
        (10, 865, 640, 205, "Communication Console", 180, True),
        (1330, 760, 330, 310, "Security Console", 130, True),
        (1670, 760, 240, 310, "Commanders Log", 150, True),
    ]
    for x, y, w, h, label, tab, has_tab in layout:
        P[label] = Panel(x, y, w, h, label, tab, has_tab)

    _build_primary()
    _build_science()
    _build_navigation()
    _build_navigation_data()
    _build_star_map()
    _build_status_indicators()
    _build_computer()
    _build_data()
    _build_engineering()
    _build_communication()
    _build_combat()
    _build_strategic()
    _build_security()
    _build_log()
    return list(P.values())


def _build_primary():
    panel = P["Primary Display"]
    video = VideoDisplay(panel, "primary", (panel.width - 10, 320), (5, 5))
    video.set_videos(["DeepSpace.mp4", "EarthOrbit.mp4"])
    video.fallback.label = "EARTH ORBIT"
    if len(video.sources) > 1:
        video.index = 1
    Text(panel, (5, 350), "Msn Elapsed", "cyan", 11)
    panel.lbl_elapsed = pygame.Rect(95, 344, 84, 18)
    Text(panel, (190, 350), "Time Left", "cyan", 11)
    panel.lbl_left = pygame.Rect(255, 344, 84, 18)
    right_x = panel.width - 295
    Button(panel, (right_x, 333, 64, 18), "REST", text_size=11)
    Button(panel, (right_x, 356, 64, 18), "Sim Freeze", text_size=11)
    Button(panel, (right_x + 70, 356, 105, 18), "Help F1/Ctrl+H", text_size=10)


def _build_science():
    panel = P["Science Console"]
    panel.tab_label = "Target Data"
    Button(panel, (132, 26, 50, 18), "Board", key=pygame.K_RSHIFT, text_size=10)


def _build_navigation():
    panel = P["Navigation Console"]
    Display(panel, "system", (210, 210), (225, 24))
    Display(panel, "orbital display", (210, 80), (5, 245))
    Display(panel, "planets display", (210, 80), (225, 245))
    objectDisplay = wfd.ProjectionViewer(panel, "object display", (210, 210), (5, 24))
    shape = wf.Sphere((105, 105, 0), 90)
    sphere = wf.Wireframe()
    sphere.addNodes(shape.buildVertices())
    objectDisplay.addWireframe("sphere", sphere)
    wfd.ProjectionViewer.rotateFrame(sphere, 'X', math.pi/2)
    wfd.ProjectionViewer.initTexture(sphere, "assets/notEarth.png")

    Text(panel, (5, 8), "Orbital Displays", "cyan", 11)
    Text(panel, (228, 8), "System Map", "cyan", 11)
    Text(panel, (305, 233), "Planets", BLACK, 11)
    Button(panel, (7, 26, 67, 13), "Show Orbit", key=pygame.K_3, group="orbit", text_size=11, momentary=True) # TODO: Show satellites around planet 
    Button(panel, (7, 233, 67, 13), "Objects", key=pygame.K_i, group="nav",
           active=True, text_size=11)
    Button(panel, (77, 233, 67, 13), "Orbit Zones", key=pygame.K_o, group="nav", text_size=11)
    Button(panel, (147, 233, 67, 13), "Mercator Map", key=pygame.K_p, group="nav", text_size=11)


def _build_navigation_data():
    panel = P["Navigation"]
    Display(panel, "nav readout", (192, 145), (2, 22), double_border=False)
    #had to unbind 'e' because it's being used for the combat view in computer display
    Button(panel, (122, 62, 66, 18), "Evasive", text_size=12)
    Button(panel, (126, 94, 28, 22), "<<", text_size=16)
    Button(panel, (160, 94, 28, 22), ">>", text_size=16)
    


def _build_star_map():
    panel = P["Star Map"]
    Display(panel, "map", (430, 196), (5, 24))
    Button(panel, (206, 4, 90, 16), "Mercator Map", key=pygame.K_l, group="map", text_size=11)
    Button(panel, (300, 4, 62, 16), "Nav Map", key=pygame.K_SEMICOLON, group="map", text_size=11)
    Button(panel, (366, 4, 66, 16), "War Map", key=pygame.K_QUOTE, group="map", text_size=11)


def _build_status_indicators():
    panel = P["Status Indicators"]
    for i in range(10):
        col = i % 5
        row = i // 5
        x = 10 + col * 60
        y = 4 + row * 28
        Text(panel, (x + 18, y), str(i + 1), "cyan", 11)
        panel.add(_Indicator(panel, (x, y + 12, 40, 12), good=True))
    Button(panel, (312, 22, 30, 18), "\u2640", text_size=12)
    Button(panel, (312, 42, 50, 16), "SNAP", text_size=11)
    Text(panel, (352, 8), "Distance", "cyan", 11)
    panel.lbl_distance = pygame.Rect(352, 22, 62, 16)


class _Indicator:
    """Small green/red status lamp."""

    def __init__(self, panel, rect, good=True):
        self.panel = panel
        self.rect = pygame.Rect(rect)
        self.good = good
        self.label = None
        self.z = 2

    def prepare(self):
        pass

    def draw(self):
        pygame.draw.rect(self.panel.surf, GREEN if self.good else RED, self.rect)
        pygame.draw.rect(self.panel.surf, FRAME_DIM, self.rect, 1)


def _build_computer():
    panel = P["Computer Display"]
    panel.computer_mode = "default"
    panel.computer_combat_view = "e"

    menu = ["Combat Stats", "Information", "Landing Party", "Planets", "Star Systems",
            "Bases", "Intelligence", "Reference Lib", "Self-Destruct", "Special Services"]
    Display(panel, "options", (90, 250), (5, 5))
    Display(panel, "screen", (475, 250), (100, 5))

    #footer buttons
    #combat
    # panel.combat_view_buttons = []



    menu_x, menu_y, menu_w, menu_h, menu_gap = 8, 7, 84, 22, 3
    for i, label in enumerate(menu):

        if label == "Combat Stats":
            Button(panel,(menu_x, menu_y + i * (menu_h + menu_gap), menu_w, menu_h), label,group="computer_menu",
                   on_toggle=lambda b, mode=label.lower(): setattr(panel,"computer_mode","combat_enemy" if b.active else "default"))


        if label == "Information":
            Button(panel,(menu_x, menu_y + i * (menu_h + menu_gap), menu_w, menu_h),label,group="computer_menu",
                   on_toggle=lambda b, mode=label.lower(): setattr(panel,"computer_mode",mode if b.active else "default"))

        if label == "Landing Party":
            Button(panel, (menu_x, menu_y + i * (menu_h + menu_gap), menu_w, menu_h), label, group="computer_menu",
                   on_toggle=lambda b, mode=label.lower(): setattr(panel, "computer_mode", mode if b.active else "default"))

        if label == "Planets":
            Button(panel, (menu_x, menu_y + i * (menu_h + menu_gap), menu_w, menu_h), label, group="computer_menu",
                   on_toggle=lambda b, mode=label.lower(): setattr(panel, "computer_mode", mode if b.active else "default"))

        if label == "Star Systems":
            Button(panel,(menu_x, menu_y + i * (menu_h + menu_gap), menu_w, menu_h),label,group="computer_menu",
                   on_toggle=lambda b, mode=label.lower(): setattr(panel,"computer_mode",mode if b.active else "default"))

        if label == "Bases":
            Button(panel,(menu_x, menu_y + i * (menu_h + menu_gap), menu_w, menu_h),label,group="computer_menu",
                   on_toggle=lambda b, mode=label.lower(): setattr(panel,"computer_mode",mode if b.active else "default"))

        if label == "Intelligence":
            Button(panel,(menu_x, menu_y + i * (menu_h + menu_gap), menu_w, menu_h),label,group="computer_menu",
                   on_toggle=lambda b, mode=label.lower(): setattr(panel,"computer_mode",mode if b.active else "default"))

        if label == "Reference Lib":
            Button(panel,(menu_x, menu_y + i * (menu_h + menu_gap), menu_w, menu_h),label,group="computer_menu",
                   on_toggle=lambda b, mode=label.lower(): setattr(panel,"computer_mode",mode if b.active else "default"))

        if label == "Self-Destruct":
            Button(panel,(menu_x, menu_y + i * (menu_h + menu_gap), menu_w, menu_h),label,group="computer_menu",
                   on_toggle=lambda b, mode=label.lower(): setattr(panel,"computer_mode",mode if b.active else "default"))

        if label == "Special Services":
            Button(panel,(menu_x, menu_y + i * (menu_h + menu_gap), menu_w, menu_h),label,group="computer_menu",
                   on_toggle=lambda b, mode=label.lower(): setattr(panel,"computer_mode",mode if b.active else "default"))

def _build_data():
    panel = P["Data"]
    Display(panel, "stores", (192, 112), (2, 20), double_border=False)


def _build_engineering():
    panel = P["Engineering Console"]
    Display(panel, "probes", (380, 98), (5, 25))
    Display(panel, "energy", (380, 90), (5, 145))
    Display(panel, "velocity", (250, 210), (386, 25))
    Text(panel, (5, 8), "Probes Control", "cyan", 12)
    Text(panel, (400, 8), "Damage - Ship", "cyan", 12)
    Text(panel, (560, 8), "Velocity", "cyan", 12)
    Text(panel, (5, 128), "Energy", "cyan", 12)
    Button(panel, (214, 6, 88, 17), "Operations", key=pygame.K_q, group="probe", text_size=12)
    Button(panel, (306, 6, 78, 17), "Launch", key=pygame.K_w, group="probe", text_size=12)

    disp = panel.get("velocity")
    base_x = 386 + 6
    top = 25 + 122
    row_h = 13
    row_gap = 1
    left_w = 76
    right_x = base_x + 148
    right_w = 60
    for i, name in enumerate(("CMPTR", "S/L ENG", "HYP ENG", "SRS", "LRS", "SHD CTL")):
        Button(panel, (base_x + 4, top + i * (row_h + row_gap), left_w, row_h),
               name, group="ship_damage", text_size=9)
    for i, name in enumerate(("TRP CTL", "PHS CTL", "TELEPRT", "COM CTL", "TRAC BM", "PLS")):
        Button(panel, (right_x, top + i * (row_h + row_gap), right_w, row_h),
               name, group="ship_damage", text_size=9)
    Button(panel, (base_x + 80, top, 66, 6 * row_h + 5 * row_gap),
           "HULL", group="ship_damage", text_size=10)


def _build_communication():
    panel = P["Communication Console"]
    Display(panel, "feed left", (315, 175), (5, 25))
    Display(panel, "feed right", (310, 175), (325, 25))
    Text(panel, (5, 9), "Status", "cyan", 12)
    Button(panel, (325, 7, 70, 16), "Messages", key=pygame.K_9, group="comm",
           active=True, text_size=12)
    Button(panel, (399, 7, 62, 16), "Reports", key=pygame.K_0, group="comm", text_size=12)
    Button(panel, (465, 7, 74, 16), "Combined", key=pygame.K_MINUS, group="comm", text_size=12)
    Button(panel, (543, 7, 92, 16), "Send Message", text_size=12)


def _build_combat():
    panel = P["Combat Console"]
    Display(panel, "grid", (470, 470), (5, 25))
    CircleDisplay(panel, "combat science scope", (493, 414), 45)
    Text(panel, (5, 6), "Combat Information Display", "cyan", 11)
    Text(panel, (515, 6), "Alignment:", BLACK, 11)
    Button(panel, (586, 3, 38, 20), "BCS", group="combat_align", active=True, text_size=11)
    Button(panel, (628, 3, 38, 20), "SCS", group="combat_align", text_size=11)
    Button(panel, (40, 510, 44, 20), "Menu", key=pygame.K_d, group="cmb_menu", text_size=11)
    Button(panel, (90, 510, 44, 20), "Grid", key=pygame.K_f, group="cmb_grid", text_size=11)
    Button(panel, (140, 510, 44, 20), "Head", key=pygame.K_g, group="cmb_head", text_size=11)
    Button(panel, (190, 510, 44, 20), "Target", key=pygame.K_h, group="cmb_tgt", text_size=11)
    Button(panel, (240, 510, 44, 20), "Line", key=pygame.K_j, group="cmb_line", text_size=11)
    # Make these momentary toggles so a click flips them independently.
    for b in panel.elements:
        if isinstance(b, Button) and b.group and b.group.startswith("cmb_"):
            b.group = None
    # Shield mode radio buttons sit on the shields sub-panel.
    Button(panel, (493, 304, 74, 16), "Auto", key=pygame.K_m, group="shield", text_size=10)
    Button(panel, (573, 304, 74, 16), "Manual", key=pygame.K_COMMA, group="shield",
           active=True, text_size=10)
    Button(panel, (493, 322, 74, 16), "Battle Entry", key=pygame.K_PERIOD,
           group="shield", text_size=10)
    Button(panel, (573, 322, 74, 16), "Maximum", key=pygame.K_SLASH,
           group="shield", text_size=10)
    for i, name in enumerate(("Phaser", "Trp1", "Trp2", "ObltrPd")):
        Button(panel, (493 + i * 39, 55, 37, 18), name, group="combat_weapon",
               active=i == 0, text_size=10)
    Button(panel, (610, 92, 34, 18), "ECM", text_size=10)
    for i, name in enumerate(("Ph", "T1", "T2", "Cont")):
        Button(panel, (493 + i * 39, 352, 37, 22), name, group="weapon_condition",
               active=i == 0, text_size=10)
    Button(panel, (612, 402, 34, 18), "SRS", text_size=10)
    Button(panel, (586, 430, 58, 16), "Dept Q", group="science_page",
           active=True, text_size=9)
    Button(panel, (586, 450, 58, 16), "Planet Data", group="science_page", text_size=8)


def _build_strategic():
    panel = P["Strategic Command Console"]
    Display(panel, "escort", (150, 120), (5, 12))
    Display(panel, "formation", (80, 120), (165, 12))
    Display(panel, "fleet pos", (200, 120), (255, 12))
    Display(panel, "fleet cmd", (570, 195), (5, 150))
    cmd_x, cmd_w, cmd_h = 455, 120, 20
    for y, label in ((10, "Escort Commands"), (39, "Fleet Commands"),
                     (68, "Strategic Commands"), (97, "Menu")):
        Button(panel, (cmd_x, y, cmd_w, cmd_h), label, text_size=10)
    Button(panel, (cmd_x, 126, 58, cmd_h), "Editor", text_size=10)
    Button(panel, (cmd_x + 62, 126, 58, cmd_h), "View", text_size=10)

def _toggle_security_board(panel, state):
    if panel.security_mode == "boarding":
        _draw_boarding_panel(panel, state)
    else:
        _draw_security_panel(panel, state)

def _draw_security_panel(panel, state):
    internal = panel.get("internal")
    interrogations = panel.get("interrogations")
    internal.surf.fill(BLACK)
    interrogations.surf.fill(BLACK)

    fit_text(internal.surf, f"Shock Troops: {state.shock_troops}", [6, 20, 200, 16], GREEN, 12)
    fit_text(internal.surf, f"Prisoners: {state.prisoners}", [6, 40, 200, 16], GREEN, 12)
    fit_text(internal.surf, f"Target: {state.selected_target['name'][:18]}",
             [6, 66, 260, 16], CYAN, 12, align="left")
    fit_text(interrogations.surf, "QUEUE", [8, 8, 80, 14], CYAN, 10, align="left")
    fit_text(interrogations.surf, "No active interviews" if state.prisoners == 0 else "KR-17 00:12 hold",
             [8, 27, 190, 14], YELLOW if state.prisoners else GREEN, 10, align="left")

def _draw_boarding_panel(panel, state):
    internal = panel.get("internal")
    interrogations = panel.get("interrogations")
    internal.surf.fill(BLACK)
    interrogations.surf.fill(BLACK)
    ctx = state.boarding_context()

    img_h = internal.size[1] - 40
    img_w = internal.size[0]
    img = pygame.transform.smoothscale(panel.boarding_img, (img_w, img_h))
    internal.surf.blit(img, (0,0))

    # --- table under the image ---
    list_y = img_h - 12  # adjust vertical position
    label_x = 12  # red label position
    value_x = 90  # green value position

    enemType = "battlecruiser"
    enemClass = "klagar"


    rows = [
        ("TYPE", enemType.upper()),
        ("CLASS", enemClass.upper()),
        ("CREW", f"{ctx['defenders']}   SHK: {ctx['shock_troops']}"),
    ]

    for i, (label, value) in enumerate(rows):
        line_y = list_y + i * 18  # spacing between lines

        # red label
        fit_text(internal.surf,
                 f"{label}:",
                 [label_x, line_y, 80, 14],
                 RED, 11, align="left")

        # green value on same line
        fit_text(internal.surf,
                 value,
                 [value_x, line_y, 200, 14],
                 GREEN, 11, align="left")

    _draw_boarding_notes(interrogations.surf, ctx)


def _draw_boarding_notes(surface, ctx):
    fit_text(surface, "BOARDING DATA", [8, 6, 130, 14], CYAN, 11, align="left")
    notes = [
        ("Target shields must be down.", RED if ctx["shields_up"] else GREEN),
        (f"Enemy prisoners aboard: {ctx['prisoners']}", YELLOW if ctx["prisoners"] else GREEN),
        (f"Defenders remaining: {ctx['defenders']}", RED if ctx["defenders"] else GREEN),
        (ctx["status"], RED if "BLOCKED" in ctx["status"] or not ctx["valid"] else GREEN),
    ]
    for i, (text, fg) in enumerate(notes):
        fit_text(surface, text, [8, 28 + i * 17, 300, 14], fg, 10, align="left")


def _build_security():
    panel = P["Security Console"]
    panel.security_mode = "security"
    panel.boarding_img = asset("SFD_Enemy_Ship.png")

    # boarding button
    Button(panel, (5,22,90,18), "Boarding", text_size=12,
   on_toggle=lambda b: setattr(panel, "security_mode",
   "boarding" if b.active else "security"))

    Display(panel, "internal", (320, 160), (5, 18))
    Display(panel, "interrogations", (320, 100), (5, 205))
    Text(panel, (5, 190), "Interrogations", "cyan", 12)


def _build_log():
    panel = P["Commanders Log"]
    Display(panel, "log", (228, 298), (5, 6))


# --- per-frame drawing ------------------------------------------------------

def draw(state, current_time):
    _draw_primary(state)
    _draw_science(state)
    _draw_navigation(state, current_time)
    _draw_navigation_console_data(state)
    _draw_navigation_data(state)
    _draw_star_map(state)
    _draw_status_indicators(state)
    _draw_computer(state)
    _draw_data(state)
    _draw_engineering(state)
    _draw_communication(state, current_time)
    _draw_combat(state)
    _draw_strategic(state)
    _toggle_security_board(P["Security Console"], state)
    _draw_log(state)

def _draw_primary(state):
    panel = P["Primary Display"]
    pygame.draw.rect(panel.surf, BLACK, panel.lbl_elapsed)
    pygame.draw.rect(panel.surf, FRAME_DIM, panel.lbl_elapsed, 1)
    fit_text(panel.surf, f"{state.mission_elapsed_days:.2f} Days", panel.lbl_elapsed, GREEN, 13)
    pygame.draw.rect(panel.surf, BLACK, panel.lbl_left)
    pygame.draw.rect(panel.surf, FRAME_DIM, panel.lbl_left, 1)
    fit_text(panel.surf, f"{state.time_left_days:.2f} Days", panel.lbl_left, GREEN, 13)
    status = pygame.Rect(panel.width - 115, 333, 100, 40)
    status_col = {"Green": GREEN, "Yellow": YELLOW, "Red": RED}.get(state.alert_status, GREEN)
    pygame.draw.rect(panel.surf, status_col, status)
    fit_text(panel.surf, f"Status: {state.alert_status}", status, BLACK, 13)


def _draw_science(state):
    panel = P["Science Console"]
    _draw_target_data(panel, state, pygame.Rect(5, 20, 182, 198))


def _draw_science_scope(panel, state, scope_label="scope", compact=False):
    scope = panel.get(scope_label)
    scope.surf.fill(PANEL_BG)
    cx, cy = scope.rect.center
    radius = scope.radius - 1
    pygame.draw.circle(scope.surf, BLACK, (cx, cy), radius)

    def clipped_line_horizontal(y, col=WHITE, width=2):
        half = int(math.sqrt(max(0, radius * radius - (y - cy) ** 2)))
        pygame.draw.line(scope.surf, col, (cx - half, y), (cx + half, y), width)

    def clipped_line_vertical(x, col=WHITE, width=2):
        half = int(math.sqrt(max(0, radius * radius - (x - cx) ** 2)))
        pygame.draw.line(scope.surf, col, (x, cy - half), (x, cy + half), width)

    clipped_line_horizontal(cy)
    clipped_line_vertical(cx)
    tick_step = 12 if compact else 24
    for tick in range(-3, 4):
        if tick == 0:
            continue
        tx = cx + tick * tick_step
        ty = cy + tick * tick_step
        if abs(tx - cx) < radius:
            pygame.draw.line(scope.surf, WHITE, (tx, cy - 9), (tx, cy + 9), 2)
        if abs(ty - cy) < radius:
            pygame.draw.line(scope.surf, WHITE, (cx - 9, ty), (cx + 9, ty), 2)

    range_units = state.science_range()
    if range_units <= 0:
        fit_text(scope.surf, "OFFLINE", [cx - radius + 8, cy - 8, radius * 2 - 16, 16],
                 RED, 10, align="center")
    else:
        scale = (radius - 8) / range_units
        contacts = state.science_contacts()
        if state.science_page == "Planet Data":
            contacts = [contact for contact in contacts if contact["kind"] == "planet"]
        for contact in contacts:
            dx = int((contact["x"] - state.system_x) * 5)
            dy = int((contact["y"] - state.system_y) * 5)
            if math.hypot(dx / 5, dy / 5) > range_units:
                continue
            px = int(cx + (contact["x"] - state.system_x) * scale)
            py = int(cy + (contact["y"] - state.system_y) * scale)
            if math.hypot(px - cx, py - cy) > radius - 5:
                continue
            dot = RED if contact.get("threat") else GREEN
            pygame.draw.circle(scope.surf, dot, (px, py), 3 if not compact else 2)
        heading = math.radians(state.actual_heading - 90)
        ship_tip = 8 if compact else 10
        ship_wing = 6 if compact else 8
        ship = [
            (cx + int(math.cos(heading) * ship_tip), cy + int(math.sin(heading) * ship_tip)),
            (cx + int(math.cos(heading + 2.45) * ship_wing), cy + int(math.sin(heading + 2.45) * ship_wing)),
            (cx + int(math.cos(heading - 2.45) * ship_wing), cy + int(math.sin(heading - 2.45) * ship_wing)),
        ]
        pygame.draw.polygon(scope.surf, RED, ship)
    pygame.draw.circle(scope.surf, WHITE, (cx, cy), radius, 2)

    if compact:
        fit_text(panel.surf, state.science_scope, [492, 400, 40, 12], BLACK, 9, align="left")
        return
    else:
        fit_text(panel.surf, state.science_scope, [10, 20, 52, 16], BLACK, 16, align="left")
        page_rect = pygame.Rect(68, 20, 76, 16)
    fg = CYAN if state.science_page == "Dept Q" else GREEN
    fit_text(panel.surf, state.science_page, page_rect, fg, 9, align="right")


def _draw_navigation(state, current_time):
    panel = P["Navigation Console"]
    objectDisplay = panel.get("object display")
    system = panel.get("system")
    wfd.ProjectionViewer.rotateFrame(objectDisplay.wireframes['sphere'], 'Y', 0.005)
    system.surf.fill(BLACK)
    objectDisplay.surf.fill(BLACK)
    grid = pygame.Surface(system.size, pygame.SRCALPHA)
    for gx in range(0, system.rect.width, 21):
        pygame.draw.line(grid, (255, 255, 255, 40), (gx, 0), (gx, system.rect.height))
    for gy in range(0, system.rect.height, 21):
        pygame.draw.line(grid, (255, 255, 255, 40), (0, gy), (system.rect.width, gy))
    system.surf.blit(grid, (0, 0))
    objectDisplay.surf.blit(grid, (0, 0))
    cx, cy = system.rect.center
    pygame.draw.circle(system.surf, RED, (cx, cy), 90, 1)
    pygame.draw.circle(system.surf, (60, 120, 220), (cx, cy), 55, 1)
    pygame.draw.circle(system.surf, YELLOW, (cx, cy), 8)
    for contact in state.tactical_contacts():
        sx = int(cx + (contact["x"] - state.system_x) * 5)
        sy = int(cy + (contact["y"] - state.system_y) * 5)
        if 3 <= sx <= system.rect.width - 3 and 3 <= sy <= system.rect.height - 3:
            dot = RED if contact.get("threat") else ((255, 150, 60) if contact["kind"] == "planet" else CYAN)
            pygame.draw.circle(system.surf, dot, (sx, sy),
                               5 if contact["id"] == state.selected_target["id"] else 4)
            text_line(system.surf, contact["name"][:8], (sx - 20, sy - 16), dot, 8)
    ship_x = max(4, min(system.rect.width - 4, int(cx + (state.system_x - 40) * 2)))
    ship_y = max(4, min(system.rect.height - 4, int(cy + (state.system_y - 23) * 2)))
    pygame.draw.circle(system.surf, GREEN, (ship_x, ship_y), 4)
    

def _draw_navigation_console_data(state):
    panel = P["Navigation Console"] 
    orbit = panel.get("orbital display")
    planet = panel.get("planets display")
    orbit.surf.fill(BLACK)
    object_columns = ["ID#", "Name", "Rel-Pos", "Status"]
    zone_columns = ["ID#", "Zone", "Rel-Pos", "Status"]
    planets_columns = ["ID", "Cls", "Inh", "Tch", "LP", "BS", "Status"]
    obj_rows = []
    zone_rows = []
    planet_rows = []
    obj_col_widths = [35, 45, 40, 80]
    planets_col_widths = [25, 25, 25, 25, 25, 25, 50]
    
    contacts = state.scanner_contacts()
    for contact in contacts[:4]:
        rel = f"{round(contact['x'] - state.system_x)},{round(contact['y'] - state.system_y)}"
        status = "THREAT" if contact.get("threat") else "CLEAR"
        obj_rows.append([contact["id"], contact["name"][:8], rel, status])
        zone = "Mine" if contact["kind"] == "mine" else ("Orbit" if contact["kind"] == "planet" else "Track")
        zone_rows.append([contact["id"], zone, rel, status])
        if contact["kind"] == "planet":
            planet_rows.append([contact["id"][:2], "M", "Y", "4", "1", "0", "Survey"])

    active = next((b for b in panel.elements
                   if isinstance(b, Button) and b.active), None)
    if active and active.label == "Objects":
        table(orbit.surf, object_columns, obj_rows, 6, 5, obj_col_widths, column_lines=True)
    elif active and active.label == "Orbit Zones":
        table(orbit.surf, zone_columns, zone_rows, 6, 5, obj_col_widths, column_lines=True)

    table(planet.surf, planets_columns, planet_rows, 6, 5, planets_col_widths, column_lines=True) 


def _draw_navigation_data(state):
    disp = P["Navigation"].get("nav readout")
    disp.surf.fill((34, 34, 34))
    pygame.draw.rect(disp.surf, FRAME, disp.rect, 2)

    def field(rect, value, size=13, align="right"):
        rect = pygame.Rect(rect)
        pygame.draw.rect(disp.surf, BLACK, rect)
        pygame.draw.rect(disp.surf, WHITE, rect, 2)
        fit_text(disp.surf, value, rect.inflate(-4, -2), GREEN, size, align=align)

    fit_text(disp.surf, "X", [65, 4, 24, 14], CYAN, 11, align="center")
    fit_text(disp.surf, "Y", [94, 4, 24, 14], CYAN, 11, align="center")

    fit_text(disp.surf, "Reg. Loc:", [6, 20, 60, 15], CYAN, 10, align="left")
    field([62, 17, 28, 18], state.nav_region[0], 13)
    field([94, 17, 28, 18], state.nav_region[1], 13)
    fit_text(disp.surf, "Dist:", [128, 20, 28, 15], CYAN, 9, align="left")
    field([160, 17, 28, 18], f"{state.nav_distance:.1f}", 10)

    fit_text(disp.surf, "Orb Pos:", [6, 41, 60, 15], CYAN, 10, align="left")
    field([62, 38, 28, 18], state.nav_orbit[0], 13)
    field([94, 38, 28, 18], state.nav_orbit[1], 13)

    fit_text(disp.surf, "Course:", [6, 64, 58, 15], CYAN, 10, align="left")
    field([70, 61, 50, 18], state.nav_course, 13)
    fit_text(disp.surf, "Sideslip", [128, 58, 60, 12], CYAN, 8, align="center")

    fit_text(disp.surf, "Target 1:", [6, 86, 65, 15], CYAN, 10, align="left")
    field([70, 83, 50, 18], f"{state.nav_target[0]}, {state.nav_target[1]}", 11)
    fit_text(disp.surf, str(state.nav_sideslip), [144, 118, 28, 12], GREEN, 8, align="center")

    fit_text(disp.surf, "Object:", [6, 108, 52, 15], CYAN, 10, align="left")
    field([58, 105, 130, 18], state.nav_object, 11, align="center")

    fit_text(disp.surf, "Mode:", [6, 129, 52, 14], CYAN, 10, align="left")
    mode_rect = pygame.Rect(58, 125, 130, 18)
    pygame.draw.rect(disp.surf, BLACK, mode_rect)
    pygame.draw.rect(disp.surf, GREEN, mode_rect, 2)
    fit_text(disp.surf, state.nav_mode, mode_rect.inflate(-4, -2), GREEN, 12, align="center")

def _draw_star_map(state):
    panel = P["Star Map"]
    disp = panel.get("map")
    active = next((b for b in panel.elements
                   if isinstance(b, Button) and b.active), None)
    if active and active.label == "Nav Map":
        img = pygame.transform.smoothscale(asset("NavMap.png"), disp.size)
        disp.surf.blit(img, (0, 0))
    elif active and active.label == "War Map":
        img = pygame.transform.smoothscale(asset("WarMap.png"), disp.size)
        disp.surf.blit(img, (0, 0))
    else:
        rng = random.Random(74216)
        for _ in range(260):
            x = rng.randrange(8, disp.rect.width - 8)
            y = rng.randrange(14, disp.rect.height - 8)
            shade = rng.randrange(40, 150)
            disp.surf.set_at((x, y), (shade, shade, shade))
        star_colors = [GREEN, CYAN, YELLOW, RED, MAGENTA, (120, 160, 255), WHITE]
        for _ in range(55):
            x = rng.randrange(12, disp.rect.width - 12)
            y = rng.randrange(22, disp.rect.height - 12)
            radius = 1 if rng.random() < 0.82 else 2
            pygame.draw.circle(disp.surf, star_colors[rng.randrange(len(star_colors))],
                               (x, y), radius)
        pygame.draw.rect(disp.surf, (26, 26, 26), (0, 0, disp.rect.width, 14))
        for i, label in enumerate(("0", "5", "10", "15", "20", "25", "30", "35")):
            fit_text(disp.surf, label, [8 + i * 53, 0, 26, 13], CYAN, 9)
        ship_x = max(6, min(disp.rect.width - 8, int(state.region_x / 35 * disp.rect.width)))
        ship_y = max(18, min(disp.rect.height - 8, int(state.region_y / 20 * disp.rect.height)))
        pygame.draw.rect(disp.surf, MAGENTA, (ship_x - 6, ship_y - 6, 12, 12), 2)


def _draw_status_indicators(state):
    panel = P["Status Indicators"]
    goods = state.status_indicator_goods()
    for element in panel.elements:
        if isinstance(element, _Indicator):
            element.good = goods.pop(0) if goods else True
    pygame.draw.rect(panel.surf, BLACK, panel.lbl_distance)
    pygame.draw.rect(panel.surf, FRAME_DIM, panel.lbl_distance, 1)
    fit_text(panel.surf, f"{state.nav_distance:.1f} Ly", panel.lbl_distance, GREEN, 12)


def _draw_computer(state):
    panel = P["Computer Display"]
    options = panel.get("options")
    options.surf.fill(PANEL_BG)
    mode = panel.computer_mode
    state.computer_panel = panel

    screen = panel.get("screen")
    screen.surf.fill(BLACK)

    if mode == "default":
        _draw_computer_landing(screen, state)
    elif mode == "combat_enemy" or mode == "combat_krellan":
        _draw_computer_combat_stats(screen, state, getattr(panel, "computer_combat_view", "e"))
    elif mode == "star systems":
        _draw_star_systems(screen,state)
    elif mode == "self-destruct":
        _draw_self_destruct_screen(screen,state)
    else:
        _draw_computer_database_page(screen, state, mode)


def _draw_computer_landing(screen, state):
    surf = screen.surf
    rect = screen.rect
    pygame.draw.rect(surf, FRAME_DIM, (4, 4, rect.width - 8, rect.height - 8), 1)
    fit_text(surf, "SHIP INFORMATION SYSTEM", [10, 8, rect.width - 20, 20],
             WHITE, 14, align="center")
    fit_text(surf, "KRELLAN BATTLECRUISER COMPUTER", [10, 29, rect.width - 20, 14],
             CYAN, 10, align="center")

    status_rows = [
        ("Alert", state.alert_status, RED if state.alert_status == "Red" else GREEN),
        ("Mission", f"{state.mission_elapsed_days:.2f} / {state.time_left_days:.2f} days", GREEN),
        ("Region", f"{state.nav_region[0]}, {state.nav_region[1]}", GREEN),
        ("System", f"{state.system_x:.0f}, {state.system_y:.0f}", GREEN),
        ("Power", f"{state.energy_pct}%", RED if state.energy_pct < 25 else GREEN),
        ("Hull", f"{state.hull_pct}%", RED if state.hull_pct < 40 else GREEN),
    ]
    for col, (title, rows) in enumerate((("SHIP", status_rows[:3]), ("READINESS", status_rows[3:]))):
        box = pygame.Rect(18 + col * 224, 56, 204, 82)
        pygame.draw.rect(surf, (8, 8, 8), box)
        pygame.draw.rect(surf, FRAME_DIM, box, 1)
        fit_text(surf, title, [box.x + 8, box.y + 6, box.w - 16, 14], CYAN, 10, align="left")
        for i, (label, value, fg) in enumerate(rows):
            y = box.y + 26 + i * 17
            fit_text(surf, label, [box.x + 10, y, 70, 14], CYAN, 10, align="left")
            fit_text(surf, value, [box.x + 82, y, box.w - 92, 14], fg, 10, align="left")

    modules = [
        ("Combat Stats", "enemy and Krellan reports"),
        ("Information", "ship records"),
        ("Landing Party", "troop status"),
        ("Planets", "survey files"),
        ("Star Systems", "regional database"),
        ("Bases", "installation records"),
        ("Intelligence", "enemy data"),
        ("Reference Lib", "manual index"),
    ]
    fit_text(surf, "DATABASE CATALOG", [18, 150, rect.width - 36, 15], WHITE, 11, align="left")
    for i, (name, detail) in enumerate(modules):
        col = i % 2
        row = i // 2
        x = 18 + col * 224
        y = 171 + row * 16
        fit_text(surf, name, [x, y, 94, 13], GREEN, 9, align="left")
        fit_text(surf, detail, [x + 100, y, 112, 13], CYAN, 8, align="left")

    footer = f"Contacts {len(state.scanner_contacts())}   Torpedoes {state.torpedoes}   Prisoners {state.prisoners}"
    fit_text(surf, footer, [18, rect.height - 19, rect.width - 36, 13], YELLOW, 9, align="center")


def _draw_computer_database_page(screen, state, mode):
    surf = screen.surf
    rect = screen.rect
    title = mode.replace("-", " ").title()
    pygame.draw.rect(surf, FRAME_DIM, (4, 4, rect.width - 8, rect.height - 8), 1)
    fit_text(surf, title.upper(), [10, 10, rect.width - 20, 18], WHITE, 13, align="center")
    rows = {
        "information": [("Ship", "Klagar-class battlecruiser"), ("Crew", str(state.crew)),
                        ("Power", f"{state.energy_pct}%"), ("Hull", f"{state.hull_pct}%")],
        "landing party": [("Shock Troops", str(state.shock_troops)), ("Space Marines", str(state.marines)),
                          ("Prisoners", str(state.prisoners)), ("Boarding", state.boarding_context()["status"])],
        "planets": [("Selected", state.selected_target["name"]), ("Object", state.selected_target["kind"].title()),
                    ("Region", f"{state.nav_region[0]}, {state.nav_region[1]}"), ("System", f"{state.system_x:.0f}, {state.system_y:.0f}")],
        "bases": [("Known Contacts", str(len([c for c in state.contacts if c.kind == "base"]))),
                  ("Target", state.selected_target["name"]), ("Shields", "UP" if state.selected_target.get("shields_up") else "DOWN")],
        "intelligence": [("Threat Contacts", str(len([c for c in state.scanner_contacts() if c.get("threat")]))),
                         ("Alert", state.alert_status), ("ECM", "ACTIVE" if state.ecm_enabled else "OFF")],
        "reference lib": [("Navigation", "course, maps, movement"), ("Sensors", "LRS, SRS, ECM limits"),
                          ("Combat", "weapons and target data"), ("Controls", "keyboard and panel toggles")],
        "special services": [("Self-Destruct", "computer menu authorization"), ("Rest", "primary display control"),
                             ("Snapshot", "status indicator control")],
    }.get(mode, [("Status", "No database records loaded")])
    y = 54
    for label, value in rows:
        fit_text(surf, label, [40, y, 120, 18], CYAN, 12, align="left")
        box = pygame.Rect(170, y - 1, rect.width - 210, 20)
        pygame.draw.rect(surf, BLACK, box)
        pygame.draw.rect(surf, FRAME_DIM, box, 1)
        fit_text(surf, value, box.inflate(-8, -2), GREEN, 11, align="left")
        y += 30


def _draw_computer_combat_stats(screen, state, view):
    surf = screen.surf
    rect = screen.rect
    panel = P["Computer Display"]
    mode = panel.computer_mode

    if mode == "combat_enemy":
        fit_text(surf, "COMBAT STATUS REPORT - Enemy", [4, 4, rect.width - 8, 20], WHITE, 14)

        headers = [
            ("OBJECT", 70),
            ("REL POS", 50),
            ("BNG", 35),
            ("VEL", 35),
            ("HDG", 35),
            ("L", 20),
            ("T", 20),
            ("POWER", 70),
            ("AX.E", 30),
            ("MN.E", 30),
            ("DAM", 30),
            ("STATUS", 38),
        ]

        # Format:
        # [object, relpos, bng, vel, hdg, L_flag, T_flag, power, ax.e, mn.e, dam, status]

        base_rows = [
            ["unknown", "26, -3", "95", "0.9", "211", 0, 1, "unknown", "unk", "unk", "unk", "HOSTILE"],
            ["heavy cruiser", "-2, 1", "225", "0.9", "45", 0, 0, "3636 (72%)", "ok", "unk", "lgt", "HOSTILE"],
            ["light cruiser", "9, -1", "225", "0.9", "90", 1, 0, "2724 (90%)", "ok", "unk", "med", "HOSTILE"],
            ["unknown", "29, -31", "91", "0.9", "210", 1, 0, "unknown", "ok", "unk", "unk", "HOSTILE"],
            ["destroyer", "29, -31", "91", "0.9", "210", 1, 0, "1757 (87%)", "ok", "unk", "unk", "HOSTILE"],
            ["unknown", "31, 31", "91", "0.9", "210", 0, 1, "unknown", "ok", "unk", "unk", "HOSTILE"],
        ]

        rows = []
        for r in base_rows:
            L_flag = "x" if r[5] == 1 else ""
            T_flag = "x" if r[6] == 1 else ""

            row = [
                r[0], r[1], r[2], r[3], r[4],
                L_flag, T_flag,
                r[7], r[8], r[9], r[10], r[11]
            ]
            rows.append(row)

        start_x = 8
        start_y = 32
        x = start_x
        for label, width in headers:
            fit_text(surf, label, [x, start_y, width, 18], CYAN, 12)
            x += width

        pygame.draw.line(surf, FRAME_DIM, (start_x, start_y + 20), (rect.width - 8, start_y + 20), 1)

        row_y = start_y + 24
        for i, row in enumerate(rows):
            x = start_x
            bg = (25, 25, 25) if i % 2 else (0, 0, 0)
            pygame.draw.rect(surf, bg, (start_x, row_y, rect.width - 16, 20))

            for (label, width), cell in zip(headers, row):
                fg = GREEN

                if label == "DAM":
                    if "med" in cell:
                        fg = YELLOW
                    elif "lgt" in cell:
                        fg = CYAN

                elif label == "STATUS" and "HOSTILE" in cell:
                    fg = RED

                elif label in ("L", "T") and cell == "x":
                    fg = CYAN

                fit_text(surf, cell, [x, row_y, width, 20], fg, 12)
                x += width

            row_y += 20

        pygame.draw.rect(surf, FRAME_DIM, (4, 24, rect.width - 8, rect.height - 32), 1)

    elif mode == "combat_krellan":
        fit_text(surf, "COMBAT STATUS REPORT - Krellan Forces",
                 [4, 4, rect.width - 8, 20], WHITE, 14)

        headers = [
            ("OBJECT", 70),
            ("REL POS", 50),
            ("BNG", 35),
            ("VEL", 35),
            ("HDG", 35),
            ("L", 20),
            ("T", 20),
            ("POWER", 70),
            ("AX.E", 30),
            ("MN.E", 30),
            ("DAM", 30),
            ("STATUS", 38),
        ]

        base_rows = [
            ["Krellan BC", "12, -4", "045", "1.2", "090", 1, 0, "88%", "12", "8", "0", "READY"],
            ["Krellan DD", "18, 10", "120", "1.4", "270", 0, 1, "72%", "10", "6", "5", "ESCORT"],
            ["Krellan FF", "5, -22", "200", "1.8", "315", 1, 0, "55%", "8", "4", "12", "PATROL"],
            ["Krellan Scout", "30, 5", "010", "0.8", "040", 0, 1, "40%", "4", "2", "20", "SCOUT"],
            ["Mine Layer", "2, 2", "180", "0.0", "000", 1, 0, "100%", "0", "0", "0", "READY"],
            ["Drone", "7, -1", "270", "0.4", "180", 0, 1, "20%", "1", "1", "80", "READY"],
        ]

        rows = []
        for r in base_rows:
            L_flag = "x" if r[5] == 1 else ""
            T_flag = "x" if r[6] == 1 else ""

            row = [
                r[0], r[1], r[2], r[3], r[4],
                L_flag, T_flag,
                r[7], r[8], r[9], r[10], r[11]
            ]
            rows.append(row)

        start_x = 8
        start_y = 32
        x = start_x
        for label, width in headers:
            fit_text(surf, label, [x, start_y, width, 18], CYAN, 12)
            x += width

        pygame.draw.line(surf, FRAME_DIM,
                         (start_x, start_y + 20), (rect.width - 8, start_y + 20), 1)

        row_y = start_y + 24
        for i, row in enumerate(rows):
            x = start_x
            bg = (25, 25, 25) if i % 2 else (0, 0, 0)
            pygame.draw.rect(surf, bg, (start_x, row_y, rect.width - 16, 20))

            for (label, width), cell in zip(headers, row):
                fg = GREEN

                # Damage color logic
                if label == "DAM":
                    dmg = int(cell) if cell.isdigit() else 0
                    if dmg >= 50:
                        fg = RED
                    elif dmg >= 20:
                        fg = YELLOW
                    elif dmg >= 1:
                        fg = CYAN

                # Hostile status
                elif label == "STATUS" and "HOSTILE" in cell:
                    fg = RED

                # L/T flags
                elif label in ("L", "T") and cell == "x":
                    fg = CYAN

                fit_text(surf, cell, [x, row_y, width, 20], fg, 12)
                x += width

            row_y += 20
        pygame.draw.rect(surf, FRAME_DIM, (4, 24, rect.width - 8, rect.height - 32), 1)

    btn_width = rect.width // 6
    btn_height = 24
    y = panel.rect.height - 36

    enemy_box = pygame.Rect(0, y, btn_width, btn_height)
    krellan_box = pygame.Rect(btn_width, y, btn_width, btn_height)

    color = WHITE if mode == "combat_enemy" else GREY
    pygame.draw.rect(surf, color, enemy_box)
    pygame.draw.rect(surf, FRAME_DIM, enemy_box, 1)
    fit_text(surf, "Enemy [e]", [enemy_box.x + 5, enemy_box.y, enemy_box.width - 10, enemy_box.height],
             BLACK, 12)
    color = WHITE if mode == "combat_krellan" else GREY
    pygame.draw.rect(surf, color, krellan_box)
    pygame.draw.rect(surf, FRAME_DIM, krellan_box, 1)
    fit_text(surf, "Krellan [k]",
             [krellan_box.x + 5, krellan_box.y, krellan_box.width - 10, krellan_box.height],
             BLACK, 12)


def _computer_combat_tab_rects(screen):
    y = screen.rect.height - 30
    return pygame.Rect(20, y, 120, 24), pygame.Rect(160, y, 140, 24)


def computer_combat_tab_click(point):
    panel = P["Computer Display"]
    if panel.computer_mode != "combat stats":
        return False
    screen = panel.get("screen")
    screen_rect = pygame.Rect(panel.x + screen.pos[0], panel.y + screen.pos[1],
                              screen.size[0], screen.size[1])
    if not screen_rect.collidepoint(point):
        return False
    local = (point[0] - screen_rect.x, point[1] - screen_rect.y)
    enemy_box, krellan_box = _computer_combat_tab_rects(screen)
    if enemy_box.collidepoint(local):
        panel.computer_combat_view = "e"
        return True
    if krellan_box.collidepoint(local):
        panel.computer_combat_view = "k"
        return True
    return False



def _draw_self_destruct_screen(screen, state):
    surf = screen.surf
    rect = screen.rect
    pygame.draw.rect(surf, FRAME_DIM, (4, 4, rect.width - 8, rect.height - 8), 1)
    fit_text(surf, "SELF-DESTRUCT CONTROL", [8, 10, rect.width - 16, 22],
             RED, 16, align="center")
    pygame.draw.line(surf, FRAME_DIM, (16, 42), (rect.width - 16, 42), 1)

    if state.self_destructed:
        status = "SEQUENCE COMPLETE"
        instruction = "BATTLECRUISER DESTROYED"
        status_fg = RED
    elif state.self_destruct_armed:
        status = "AUTHORIZATION ARMED"
        instruction = "SELECT SELF-DESTRUCT AGAIN TO CONFIRM"
        status_fg = YELLOW
    else:
        status = "AUTHORIZATION REQUIRED"
        instruction = "SELECT SELF-DESTRUCT TO ARM"
        status_fg = CYAN

    rows = [
        ("Status", status, status_fg),
        ("Hull", f"{state.hull_pct}%", RED if state.hull_pct < 40 else GREEN),
        ("Power", f"{state.energy_pct}%", RED if state.energy_pct < 25 else GREEN),
        ("Shields", "UP" if state.shields_up else "DOWN", GREEN if state.shields_up else RED),
        ("Velocity", f"H{state.hyper_velocity} / S{state.space_velocity}", CYAN),
        ("Alert", state.alert_status, RED if state.alert_status == "Red" else YELLOW),
    ]
    for i, (label, value, fg) in enumerate(rows):
        y = 62 + i * 22
        fit_text(surf, label + ":", [34, y, 100, 16], CYAN, 12, align="left")
        fit_text(surf, value, [142, y, 260, 16], fg, 12, align="left")

    box = pygame.Rect(36, 204, rect.width - 72, 28)
    pygame.draw.rect(surf, BLACK, box)
    pygame.draw.rect(surf, RED if state.self_destruct_armed or state.self_destructed else FRAME_DIM, box, 1)
    fit_text(surf, instruction, box.inflate(-8, 0),
             RED if state.self_destructed else (YELLOW if state.self_destruct_armed else CYAN),
             12, align="center")

def _draw_star_systems(screen, state):
    fit_text(screen.surf, "TACTICAL SYSTEM DATABASE", [4, 4, screen.rect.width - 8, 16],
             WHITE, 10)
    headers = ["ID", "Rx", "Ry", "Cls", "S", "Plt"]
    classes = ["G", "M", "B", "K", "F", "A", "D", "O"]
    contact_rows = []
    for contact in state.tactical_contacts():
        cls = {"planet": "M", "ship": "K", "base": "B", "mine": "N"}.get(contact["kind"], "G")
        stat = "H" if contact.get("threat") else "N"
        contact_rows.append([
            contact["id"][:2], str(round(contact["x"])), str(round(contact["y"])),
            cls, stat, "1" if contact["kind"] == "planet" else "0",
        ])
    for block in range(4):
        x = 8 + block * 114
        for i, head in enumerate(headers):
            fit_text(screen.surf, head, [x + i * 18, 22, 17, 11], CYAN, 8)
        pygame.draw.line(screen.surf, FRAME_DIM, (x, 35), (x + 104, 35), 1)
        for row in range(15):
            system_id = block * 15 + row + 1
            y = 38 + row * 13
            if block == 0 and row < len(contact_rows):
                cells = contact_rows[row]
            else:
                cells = [
                    f"{system_id:02d}", f"{(system_id * 7) % 50}",
                    f"{(system_id * 11) % 50}", classes[system_id % len(classes)],
                    "N" if system_id % 5 else "H", str((system_id * 3) % 4),
                ]
            for i, cell in enumerate(cells):
                fg = RED if cell == "H" else GREEN
                if i == 3:
                    fg = MAGENTA if cell in ("B", "O") else YELLOW
                fit_text(screen.surf, cell, [x + i * 18, y, 17, 11], fg, 8)
    pygame.draw.rect(screen.surf, FRAME_DIM, (4, 18, screen.rect.width - 8, 222), 1)
    fit_text(screen.surf,
             f"Status: {state.alert_status}  RG {state.nav_region[0]},{state.nav_region[1]}  "
             f"Energy {state.energy_pct}%  Contacts {len(state.tactical_contacts())}",
             [8, 230, screen.rect.width - 16, 14], CYAN, 9, align="left")

def _draw_data(state):
    disp = P["Data"].get("stores")
    disp.surf.fill(BLACK)
    items = [("Torps", str(state.torpedoes)), ("Crew", str(state.crew)),
             ("Shk Troops", str(state.shock_troops)),
             ("Supplies", f"{state.supplies}t"),
             ("Probes", f"L:{state.probe_loaded} S:{state.probe_storage}"),
             ("Pods", str(state.pods)), ("Escorts", str(state.escorts))]
    for i, (label, value) in enumerate(items):
        y = 8 + i * 15
        box = pygame.Rect(disp.rect.width - 78, y, 64, 14)
        fit_text(disp.surf, label, [8, y, box.x - 16, 14], CYAN, 10, align="left")
        pygame.draw.rect(disp.surf, BLACK, box)
        pygame.draw.rect(disp.surf, FRAME_DIM, box, 1)
        fit_text(disp.surf, value, box, GREEN, 10)
    pygame.draw.rect(disp.surf, FRAME_DIM, (6, 6, disp.rect.width - 12, disp.rect.height - 12), 1)


def _draw_engineering(state):
    panel = P["Engineering Console"]
    _sync_damage_buttons(panel, state)
    _draw_probes(panel, state)
    _draw_damage(panel, state)
    _draw_energy(panel, state)
    _draw_velocity(panel, state)


def _draw_probes(panel, state):
    disp = panel.get("probes")
    disp.surf.fill(BLACK)
    active = next((b.label for b in panel.elements
                   if isinstance(b, Button) and b.active and b.group == "probe"), "Launch")
    if active == "Operations":
        headers = ["#", "Mode", "TG", "SS#", "R.LOC", "S.LOC", "Pw%", "Status"]
        widths = [16, 52, 44, 40, 50, 56, 36, 60]
        rows = []
        for probe in state.active_probes[:5]:
            rows.append([
                str(probe["id"]), probe["mode"], probe["target"], "039",
                f"({state.nav_region[0]},{state.nav_region[1]})",
                f"({round(probe['x'])},{round(probe['y'])})",
                str(round(probe["power"])), probe["status"],
            ])
        while len(rows) < 5:
            n = len(rows) + 1
            status = "Loaded" if n <= state.probe_loaded else ("Stored" if n <= state.probe_loaded + state.probe_storage else "Empty")
            rows.append([str(n), "Reserve", "--", "--", "--", "--", "100", status])
    else:
        headers = ["#", "Status", "TG", "RAD", "SS", "REG.L", "SYS.L", "DETECT"]
        widths = [16, 56, 36, 36, 36, 56, 60, 48]
        rows = []
        contacts = state.scanner_contacts()
        for i in range(5):
            if i < len(contacts):
                contact = contacts[i]
                rows.append([
                    str(i + 1), "Detect", contact["id"][-2:], str(round(contact["distance"])),
                    "39", f"({state.nav_region[0]},{state.nav_region[1]})",
                    f"({round(contact['x'])},{round(contact['y'])})",
                    contact["kind"].title(),
                ])
            else:
                status = "Standby" if i < state.probe_loaded else "Empty"
                rows.append([str(i + 1), status, "--", "00", "39",
                             f"({state.nav_region[0]},{state.nav_region[1]})",
                             f"({round(state.system_x)},{round(state.system_y)})", "None"])
    table(disp.surf, headers, rows, 6, 6, widths, 14, 10)


def _draw_damage(panel, state):
    disp = panel.get("velocity")  # rightmost display hosts the dynamic ship
    disp.surf.fill(BLACK)
    base_x = 6
    ship_box = pygame.Rect(base_x + 2, 24, 142, 108)
    ship_img = asset("shipdmg.png")
    ship_mask = pygame.mask.from_surface(ship_img)
    ship_rects = ship_mask.get_bounding_rects()
    if ship_rects:
        ship_rect = ship_rects[0]
        ship_crop = pygame.Surface((ship_rect.width, ship_rect.height), pygame.SRCALPHA)
        ship_crop.blit(ship_img, (0, 0), ship_rect)
        scale = min(ship_box.width / ship_rect.width, ship_box.height / ship_rect.height)
        ship_size = (max(1, int(ship_rect.width * scale)), max(1, int(ship_rect.height * scale)))
        ship_scaled = pygame.transform.scale(ship_crop, ship_size)
        ship_pos = ship_box.move((ship_box.width - ship_size[0]) // 2, (ship_box.height - ship_size[1]) // 2)
        disp.surf.blit(ship_scaled, ship_pos)


def _sync_damage_buttons(panel, state):
    phase_by_health = {100: 0, 65: 1, 30: 2, 0: 3}
    for button in panel.elements:
        if not isinstance(button, Button) or button.group != "ship_damage":
            continue
        if button.label.startswith("HULL"):
            button.label = f"HULL {state.hull_pct}%"
            button.active = phase_by_health.get(state.hull_pct, 0)
        else:
            button.active = phase_by_health.get(state.damage.system_health.get(button.label, 100), 0)


def _draw_energy(panel, state):
    disp = panel.get("energy")
    disp.surf.fill(BLACK)
    rows = [("Usage", state.energy_usage, state.energy_color),
            ("Quantity", state.energy_pct, "green" if state.energy_pct >= 45 else "yellow"),
            ("Backup", state.backup_energy_pct, "green"),
            ("Shields", state.shield_pct, "yellow" if state.shields_up else "red")]
    for i, (label, pct, fg) in enumerate(rows):
        y = 10 + i * 20
        fit_text(disp.surf, label, [4, y, 60, 16], CYAN, 11, align="left")
        fit_text(disp.surf, f"{pct}%", [66, y, 36, 16], fg, 11, align="left")
        bar = pygame.Rect(106, y + 1, 268, 14)
        pygame.draw.rect(disp.surf, FRAME_DIM, bar, 1)
        fill = pygame.Rect(bar.x + 1, bar.y + 1, int((bar.width - 2) * pct / 100), bar.height - 2)
        pygame.draw.rect(disp.surf, color(fg), fill)


def _draw_velocity(panel, state):
    disp = panel.get("velocity")
    w, h = disp.size
    rail = pygame.Rect(w - 32, 18, 28, h - 36)
    pygame.draw.rect(disp.surf, BLACK, rail)
    pygame.draw.line(disp.surf, FRAME, (rail.x, rail.y), (rail.x, rail.bottom), 1)
    text_line(disp.surf, "H", (rail.x + 8, 124), MAGENTA, 9, align="center")
    text_line(disp.surf, "S", (rail.x + 21, 124), GREEN, 9, align="center")
    track_top, track_bot = 26, h - 26
    track_h = track_bot - track_top
    for bx, vel, col in [(rail.x + 8, state.hyper_velocity, MAGENTA),
                         (rail.x + 21, state.space_velocity, GREEN)]:
        pygame.draw.line(disp.surf, FRAME_DIM, (bx, track_top), (bx, track_bot), 1)
        for step in range(11):
            ty = track_bot - int(track_h * step / 10)
            pygame.draw.line(disp.surf, FRAME_DIM, (bx - 3, ty), (bx + 3, ty), 1)
        fill_h = int(track_h * vel / 10)
        pygame.draw.rect(disp.surf, col, (bx - 3, track_bot - fill_h, 6, fill_h))
        text_line(disp.surf, str(vel), (bx, track_bot + 12), col, 9, align="center")


def _draw_communication(state, current_time):
    panel = P["Communication Console"]
    left = panel.get("feed left")
    right = panel.get("feed right")
    left.surf.fill(BLACK)
    right.surf.fill(BLACK)
    mode = next((b.label for b in panel.elements
                 if isinstance(b, Button) and b.active and b.group == "comm"), "Messages")
    if mode == "Reports":
        source = [(a, b) for a, b in state.report_rows()]
    elif mode == "Combined":
        reports = state.report_rows()
        messages = state.messages
        source = [(messages[i % len(messages)][0], reports[i % len(reports)][1])
                  for i in range(max(len(messages), len(reports)))]
    else:
        source = [(a, b) for a, b in state.messages]
    if not source:
        source = [("Comms", "no traffic")]

    if current_time > state.feed_clock + 900:
        state.feed_index = (state.feed_index % len(source)) + 1
        state.feed_clock = current_time
    y = 4
    for i in range(state.feed_index):
        head, body = source[i]
        text_line(left.surf, head, (4, y), GREEN, 10)
        text_line(right.surf, body, (4, y), WHITE, 10)
        y += 14


def _draw_combat(state):
    panel = P["Combat Console"]
    _sync_combat_buttons(panel, state)
    grid = panel.get("grid")
    grid.surf.fill(BLACK)
    pygame.draw.rect(grid.surf, FRAME, grid.rect, 1)
    cx, cy = grid.rect.center
    pygame.draw.line(grid.surf, WHITE, (10, cy), (grid.rect.width - 10, cy), 2)
    pygame.draw.line(grid.surf, WHITE, (cx, 10), (cx, grid.rect.height - 10), 2)

    if state.combat_overlay("Grid"):
        for step in range(-8, 9):
            gx = cx + step * 25
            gy = cy + step * 25
            if 0 < gx < grid.rect.width:
                pygame.draw.line(grid.surf, WHITE, (gx, cy - 8), (gx, cy + 8), 1)
            if 0 < gy < grid.rect.height:
                pygame.draw.line(grid.surf, WHITE, (cx - 8, gy), (cx + 8, gy), 1)

        overlay = pygame.Surface(grid.size, pygame.SRCALPHA)
        for gx in range(18, grid.rect.width, 22):
            for gy in range(18, grid.rect.height, 22):
                dot = (95, 120, 235, 100) if abs(gx - cx) + abs(gy - cy) > 130 else (210, 120, 55, 120)
                pygame.draw.circle(overlay, dot, (gx, gy), 2)
        pygame.draw.circle(overlay, (90, 110, 230, 150), (cx, cy), 165, 2)
        pygame.draw.circle(overlay, (255, 140, 80, 150), (cx, cy), 105, 2)
        grid.surf.blit(overlay, (0, 0))

    if state.combat_overlay("Head"):
        for deg in range(0, 360, 15):
            if deg % 30 == 0:
                rad = math.radians(deg - 90)
                tx = cx + int(178 * math.cos(rad))
                ty = cy + int(178 * math.sin(rad))
                text_line(grid.surf, str(deg), (tx, ty), WHITE, 10, align="center")
        heading_rad = math.radians(state.actual_heading - 90)
        pygame.draw.line(grid.surf, YELLOW, (cx, cy),
                         (cx + int(48 * math.cos(heading_rad)),
                          cy + int(48 * math.sin(heading_rad))), 1)

    target_point = None
    for contact in state.tactical_contacts():
        px, py = _combat_contact_point(grid, state, contact)
        selected = contact["id"] == state.selected_target["id"]
        col = RED if contact.get("threat") else (GREEN if contact["kind"] == "base" else CYAN)
        shape = [(px, py - 9), (px + 9, py + 7), (px - 9, py + 7)]
        if contact["kind"] == "mine":
            pygame.draw.circle(grid.surf, RED, (px, py), 6, 2)
        else:
            pygame.draw.polygon(grid.surf, col, shape)
        if selected:
            target_point = (px, py)

        if selected and state.combat_overlay("Target"):
            pygame.draw.rect(grid.surf, MAGENTA, (px - 12, py - 12, 24, 24), 1)
            fit_text(grid.surf, contact["id"], [px + 14, py - 9, 64, 14],
                     YELLOW if contact.get("threat") else GREEN, 9, align="left")

    if state.combat_overlay("Line") and target_point:
        pygame.draw.line(grid.surf, MAGENTA, (cx, cy), target_point, 1)
        solution = state.target_solution()
        label = f"{solution['bearing']}  {solution['rpos']}"
        mid = ((cx + target_point[0]) // 2 + 6, (cy + target_point[1]) // 2 - 10)
        fit_text(grid.surf, label, [mid[0], mid[1], 110, 13], MAGENTA, 9, align="left")

    if state.combat_overlay("Target"):
        _draw_combat_target_overlay(grid.surf, state)

    if state.combat_overlay("Menu"):
        _draw_combat_menu_overlay(grid.surf, state)

    grid.surf.blit(pygame.transform.smoothscale(asset("combcShip.png"), (34, 34)),
                   (cx - 17, cy - 17))

    _draw_weapons(panel, state)
    _draw_shields(panel, state)
    _draw_fire_controls(panel, state)
    _draw_combat_science(panel, state)


def _sync_combat_buttons(panel, state):
    active_by_group = {
        "combat_align": state.combat_alignment,
        "combat_weapon": state.selected_weapon,
        "shield": state.shield_policy,
        "weapon_condition": "Cont" if state.weapon_condition == "Cont"
        else {"Phaser": "Ph", "Trp1": "T1", "Trp2": "T2"}.get(state.selected_weapon, "Ph"),
    }
    for element in panel.elements:
        if isinstance(element, Button):
            if element.group in active_by_group:
                element.active = element.label == active_by_group[element.group]
            elif element.label == "ECM":
                element.active = state.ecm_enabled
            elif element.label in ("SRS", "LRS"):
                element.label = "LRS" if state.science_scope == "SRS" else "SRS"
                element.active = False
            elif element.group == "science_page":
                element.active = element.label == state.science_page
            elif element.label in state.combat_overlays:
                element.active = state.combat_overlay(element.label)


def _combat_contact_point(grid, state, contact):
    cx, cy = grid.rect.center
    dx = contact["x"] - state.system_x
    dy = contact["y"] - state.system_y
    if state.combat_alignment == "BCS":
        angle = math.radians(-state.actual_heading)
        dx, dy = (dx * math.cos(angle) - dy * math.sin(angle),
                  dx * math.sin(angle) + dy * math.cos(angle))
    px = max(18, min(grid.rect.width - 18, cx + int(dx * 15)))
    py = max(18, min(grid.rect.height - 18, cy + int(dy * 15)))
    return px, py


def _draw_combat_target_overlay(surface, state):
    solution = state.target_solution()
    box = pygame.Rect(8, 8, 128, 62)
    pygame.draw.rect(surface, BLACK, box)
    pygame.draw.rect(surface, MAGENTA, box, 1)
    fit_text(surface, "TARGET", [box.x + 6, box.y + 4, box.w - 12, 13], CYAN, 9, align="left")
    rows = [
        state.selected_target["name"][:18],
        f"BRG {solution['bearing']}  VEL {solution['velocity']}",
        f"HULL {solution['hull']}  SHD {solution['shields']}",
    ]
    for i, row in enumerate(rows):
        fit_text(surface, row, [box.x + 6, box.y + 19 + i * 13, box.w - 12, 12],
                 YELLOW if i == 0 else GREEN, 8, align="left")


def _draw_combat_menu_overlay(surface, state):
    box = pygame.Rect(surface.get_width() - 146, 8, 136, 78)
    pygame.draw.rect(surface, BLACK, box)
    pygame.draw.rect(surface, CYAN, box, 1)
    fit_text(surface, "TACTICAL MENU", [box.x + 6, box.y + 4, box.w - 12, 13], CYAN, 9, align="left")
    rows = [
        f"ALIGN {state.combat_alignment}",
        f"WEAP  {state.selected_weapon}",
        f"MODE  {state.weapon_condition}",
        f"SET   {state.weapon_setting}",
    ]
    for i, row in enumerate(rows):
        fit_text(surface, row, [box.x + 6, box.y + 20 + i * 13, box.w - 12, 12],
                 GREEN, 8, align="left")


def _draw_weapons(panel, state):
    box = pygame.Rect(485, 35, 165, 130)
    pygame.draw.rect(panel.surf, PANEL_BG, box)
    pygame.draw.rect(panel.surf, GREY, box, 2)
    fit_text(panel.surf, "Weapons", [box.x + 4, box.y + 2, 100, 14], CYAN, 11, align="left")
    for i in range(4):
        ready = state.weapon_reload[i] <= 0
        cell = pygame.Rect(box.x + 6 + i * 39, box.y + 20, 37, 18)
        pygame.draw.rect(panel.surf, GREEN if ready else RED, cell)
        pygame.draw.rect(panel.surf, BLACK, cell, 1)
    fit_text(panel.surf, "Qty:", [box.x + 88, box.y + 43, 26, 14], BLACK, 10, align="right")
    qty = pygame.Rect(box.x + 118, box.y + 42, 36, 16)
    pygame.draw.rect(panel.surf, BLACK, qty)
    pygame.draw.rect(panel.surf, WHITE, qty, 2)
    fit_text(panel.surf, str(state.torpedoes), qty.inflate(-3, -2), GREEN, 10)

    mode_box = pygame.Rect(box.x + 8, box.y + 58, 46, 18)
    setting_box = pygame.Rect(box.x + 8, box.y + 90, 56, 18)
    pygame.draw.rect(panel.surf, CYAN, mode_box)
    pygame.draw.rect(panel.surf, CYAN, setting_box)
    fit_text(panel.surf, "Mode", mode_box, BLACK, 10)
    fit_text(panel.surf, "Setting", setting_box, BLACK, 10)
    fit_text(panel.surf, "Auto", [box.x + 18, box.y + 78, 42, 12],
             RED if state.weapon_auto else BLACK, 9, align="left")
    fit_text(panel.surf, "Manual", [box.x + 76, box.y + 78, 50, 12],
             RED if not state.weapon_auto else BLACK, 9, align="left")
    settings = [("Destroy", 98), ("Disable", 98), ("Standby", 112), ("Conditional", 112)]
    for i, (label, y) in enumerate(settings):
        x = box.x + 18 if i % 2 == 0 else box.x + 76
        hot = RED if state.weapon_setting == label else BLACK
        fit_text(panel.surf, label, [x, box.y + y, 66, 12], hot, 8, align="left")

    ready_text = "READY" if state.weapon_reload[state.weapon_index] <= 0 else f"{state.weapon_reload[state.weapon_index]:.1f}s"
    fit_text(panel.surf, ready_text, [box.x + 8, box.y + 42, 72, 14],
             GREEN if ready_text == "READY" else YELLOW, 8, align="left")


def _draw_shields(panel, state):
    box = pygame.Rect(485, 172, 165, 170)
    pygame.draw.rect(panel.surf, PANEL_BG, box)
    pygame.draw.rect(panel.surf, GREY, box, 2)
    fit_text(panel.surf, "Shields", [box.x + 4, box.y + 2, 80, 14], CYAN, 11, align="left")
    center = (box.centerx, box.y + 70)
    arcs = [(225, 315), (135, 225), (45, 135), (315, 45)]
    for idx, (start, end) in enumerate(arcs):
        strength = state.shield_strength[idx] if state.shields_up else 0
        col = GREEN if strength >= 500 else (YELLOW if strength > 0 else RED)
        label = f"{idx + 1}:{strength}"
        _arc_quadrant(panel.surf, center, 38, 56, start, end, col)
        mid = math.radians((start + (end if end > start else end + 360)) / 2)
        lx = center[0] + int(47 * math.cos(mid))
        ly = center[1] + int(47 * math.sin(mid))
        text_line(panel.surf, label, (lx, ly), BLACK, 9, align="center")
    panel.surf.blit(pygame.transform.smoothscale(asset("babaaa 2.png"), (28, 40)),
                    (center[0] - 14, center[1] - 20))
    text_line(panel.surf, "Shield Mode", (box.x + 6, box.y + 118), CYAN, 10)
    fit_text(panel.surf, state.shield_policy, [box.x + 70, box.y + 111, 80, 14],
             GREEN if state.shields_up else RED, 10, align="left")
    fit_text(panel.surf, f"AAS: {'Y' if state.aas_enabled else 'N'}",
             [box.x + 6, box.y + 132, 70, 13], CYAN, 9, align="left")


def _draw_fire_controls(panel, state):
    box = pygame.Rect(485, 346, 165, 36)
    pygame.draw.rect(panel.surf, PANEL_BG, box)
    pygame.draw.rect(panel.surf, GREY, box, 2)
    for i, label in enumerate(("Ph", "T1", "T2", "Cont")):
        cell = pygame.Rect(box.x + 8 + i * 39, box.y + 6, 37, 22)
        pygame.draw.rect(panel.surf, GREEN if label != "Cont" else CYAN, cell)
        pygame.draw.rect(panel.surf, BLACK, cell, 1)
    fit_text(panel.surf, state.weapon_condition, [box.x + 8, box.y + 27, 146, 8],
             GREEN, 8, align="right")


def _draw_combat_science(panel, state):
    box = pygame.Rect(485, 384, 165, 122)
    pygame.draw.rect(panel.surf, PANEL_BG, box)
    pygame.draw.rect(panel.surf, GREY, box, 2)
    fit_text(panel.surf, "Science Console", [box.x + 6, box.y + 3, 110, 12],
             BLACK, 9, align="left")
    _draw_science_scope(panel, state, "combat science scope", compact=True)


def _draw_target_data(panel, state, box=None):
    box = pygame.Rect(box or (485, 396, 165, 100))
    pygame.draw.rect(panel.surf, BLACK, box)
    pygame.draw.rect(panel.surf, GREY, box, 2)
    fit_text(panel.surf, "Target Data", [box.x + 6, box.y + 4, 86, 15], CYAN, 10, align="left")
    solution = state.target_solution()
    headers = ["R.Pos", "Brng", "Vel", "Wpn"]
    values = [solution["rpos"], solution["bearing"], solution["velocity"], solution["weapon"][:4]]
    available = box.w - 8
    widths = [max(38, int(available * 0.31)), max(34, int(available * 0.27)),
              max(30, int(available * 0.21)), max(30, int(available * 0.21))]
    widths[-1] += available - sum(widths)
    x = box.x + 4
    y = box.y + 28
    for i, header in enumerate(headers):
        pygame.draw.line(panel.surf, FRAME_DIM, (x, y), (x, box.bottom - 3), 1)
        fit_text(panel.surf, header, [x + 2, y, widths[i] - 4, 14], CYAN, 9)
        fit_text(panel.surf, values[i], [x + 2, y + 22, widths[i] - 4, 16],
                 RED if header == "Wpn" else GREEN, 10)
        x += widths[i]
    pygame.draw.line(panel.surf, FRAME_DIM, (x, y), (x, box.bottom - 3), 1)
    target_name = state.selected_target["name"][:17]
    fit_text(panel.surf, target_name, [box.x + 6, box.bottom - 22, box.w - 12, 14],
             YELLOW if state.selected_target.get("threat") else GREEN, 9, align="left")
    fit_text(panel.surf,
             f"H:{solution['hull']} S:{solution['shields']} {solution['status'][:8]}",
             [box.x + 6, box.bottom - 38, box.w - 12, 13],
             RED if solution["hull"] <= 35 else CYAN, 8, align="left")


def _arc_quadrant(surface, center, r_in, r_out, start, end, col):
    if end <= start:
        end += 360
    pts_out = [(center[0] + r_out * math.cos(math.radians(a)),
                center[1] + r_out * math.sin(math.radians(a)))
               for a in range(start, end + 1, 4)]
    pts_in = [(center[0] + r_in * math.cos(math.radians(a)),
               center[1] + r_in * math.sin(math.radians(a)))
              for a in range(end, start - 1, -4)]
    poly = pts_out + pts_in
    if len(poly) >= 3:
        pygame.draw.polygon(surface, col, poly)
        pygame.draw.polygon(surface, BLACK, poly, 1)


def _draw_strategic(state):
    panel = P["Strategic Command Console"]
    escort_rows = [["BC", "CMD", "FLAG"]]
    for idx in range(max(0, state.escorts)):
        order = "ESCORT" if idx < 2 else "HOLD"
        escort_rows.append([f"D{idx + 1}", "DD", order])
    table(panel.get("escort").surf, ["ID", "TYPE", "ORD"], escort_rows[:7],
          5, 6, [30, 44, 70], 15, 10)
    form = panel.get("formation")
    form.surf.fill(BLACK)
    pygame.draw.circle(form.surf, GREEN, (40, 30), 5)
    pygame.draw.circle(form.surf, GREEN, (20, 74), 4)
    pygame.draw.circle(form.surf, YELLOW, (60, 74), 4)
    pygame.draw.line(form.surf, CYAN, (40, 34), (20, 74), 1)
    pygame.draw.line(form.surf, CYAN, (40, 34), (60, 74), 1)
    text_rows(form.surf, [("DELTA", "cyan"), (f"{state.nav_distance:.1f} LY", "green"),
                          (state.alert_status.upper(), "yellow")],
              16, 90, 12, 9)
    fleet_rows = [["KLG-1", "0.0", state.alert_status.upper()]]
    for idx in range(max(0, state.escorts)):
        rng = f"{1.2 + idx * 0.6:.1f}"
        stat = "READY" if idx < 2 else "HOLD"
        fleet_rows.append([f"DES-{idx + 1}", rng, stat])
    table(panel.get("fleet pos").surf, ["SHIP", "RNG", "STAT"], fleet_rows[:6],
          6, 6, [48, 42, 66], 15, 10)
    fleet = panel.get("fleet cmd")
    fleet.surf.fill(BLACK)
    groups = [
        ("Battle Fleets", ["Hotspur", "Panzer", state.selected_target["name"], "Rifle", "Sickle"]),
        ("Supply Fleets", ["Liberation", "Graviton", f"{state.supplies}t stores", "Cosmic Lance"]),
        ("Legion Fleets", ["Leviathan", "Sunblock", f"{state.shock_troops} troops", "Paramount"]),
    ]
    y = 8
    for title, names in groups:
        fit_text(fleet.surf, title, [8, y, 110, 12], MAGENTA, 9, align="left")
        y += 14
        for col, name in enumerate(names):
            x = 8 + col * 138
            fit_text(fleet.surf, f"{col + 1}", [x, y, 14, 12], CYAN, 9)
            fit_text(fleet.surf, f"KS-{col + 1}", [x + 18, y, 40, 12], WHITE, 9, align="left")
            fit_text(fleet.surf, name, [x + 58, y, 72, 12], WHITE, 9, align="left")
        y += 28
        pygame.draw.line(fleet.surf, FRAME_DIM, (4, y - 8), (fleet.rect.width - 4, y - 8), 1)


def _draw_log(state):
    disp = P["Commanders Log"].get("log")
    text_rows(disp.surf, [
        ("IMPERIAL TRIBUNE", "cyan"), ("STARDATE 7421.6", "green"),
        ("Klagar-class", "green"),
        (f"battlecruiser {state.nav_mode.lower()}", "green"),
        (f"near {state.selected_target['name'][:18]}.", "green"),
        (f"Stores: {state.torpedoes} torpedoes,", "green"),
        (f"{round(state.energy_units)} power units,", "green"),
        (f"{state.supplies} tons supplies.", "green"),
        (f"{state.shock_troops} shock troops ready.", "yellow"), ("", "green"),
        ("Standing order:", "cyan"), ("complete training", "cyan"),
        ("patrol and report.", "cyan"),
    ], 8, 8, 18, 11)

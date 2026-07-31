"""UI widgets: framed panels, clickable buttons, displays, and status bars."""
# TODO: Instead of having multiple display classes. Use a single class for all types of displays
import pygame
from core import (BLACK, SHELL_BG, PANEL_BG, FRAME, FRAME_DIM, BEVEL_LIGHT, BEVEL_DARK,
                  BUTTON_FACE, BUTTON_ACTIVE, BUTTON_HOVER, CYAN, GREEN, RED,
                  YELLOW, GREY, WHITE, color, font, fit_text, text_line)

# Every button registers here so the main loop can hit-test mouse clicks.
BUTTONS = []


def reset_buttons():
    BUTTONS.clear()


class Panel:
    """A framed region with an optional tab label that hosts child elements."""

    def __init__(self, x, y, width, height, tab_label, tab_width=0, has_tab=True):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.rect = pygame.Rect(0, 0, width, height)
        self.surf = pygame.Surface((width, height)).convert()
        self.tab_label = tab_label
        self.tab_width = tab_width
        self.elements = []
        self.has_tab = has_tab

    def add(self, element):
        self.elements.append(element)
        return element

    def get(self, label):
        for element in self.elements:
            if getattr(element, "label", None) == label:
                return element
        return None

    def draw_base(self):
        """Phase 1: paint frame and reset child display surfaces."""
        self.surf.fill(PANEL_BG)
        pygame.draw.rect(self.surf, BEVEL_LIGHT, self.rect, 2)
        pygame.draw.rect(self.surf, FRAME_DIM, self.rect.inflate(-2, -2), 1)
        if self.width > 14 and self.height > 14:
            pygame.draw.rect(self.surf, FRAME, self.rect.inflate(-8, -8), 1)
        for element in self.elements:
            element.prepare()

    def finish(self, surface):
        """Phase 3: layer displays, then buttons and text, then blit and tab."""
        order = sorted(self.elements, key=lambda e: getattr(e, "z", 0))
        for element in order:
            element.draw()
        surface.blit(self.surf, (self.x, self.y))
        if self.has_tab:
            tab_w = self.tab_width or min(self.width, len(self.tab_label) * 9 + 16)
            tab = pygame.Rect(self.x, self.y - 16, tab_w, 18)
            pygame.draw.rect(surface, PANEL_BG, tab)
            pygame.draw.line(surface, BEVEL_LIGHT, tab.topleft, tab.topright, 2)
            pygame.draw.line(surface, BEVEL_LIGHT, tab.topleft, tab.bottomleft, 2)
            pygame.draw.line(surface, FRAME_DIM, tab.bottomleft, tab.bottomright, 2)
            pygame.draw.line(surface, FRAME_DIM, tab.topright, tab.bottomright, 2)
            fit_text(surface, self.tab_label, tab.inflate(-6, 0), BLACK, 13)
        else:
            tab_w = self.tab_width or min(self.width, len(self.tab_label) * 9 + 16)
            # Inline headers (currently the Star Map) share their row with
            # controls. Keep the title inside the panel and align it to the
            # same 16px header grid instead of expanding text past the frame.
            tab = pygame.Rect(self.x + 4, self.y + 4, tab_w, 16)
            pygame.draw.rect(surface, PANEL_BG, tab)
            pygame.draw.line(surface, BEVEL_LIGHT, tab.topleft, tab.topright)
            pygame.draw.line(surface, BEVEL_LIGHT, tab.topleft, tab.bottomleft)
            pygame.draw.line(surface, BEVEL_DARK, tab.bottomleft, tab.bottomright)
            pygame.draw.line(surface, BEVEL_DARK, tab.topright, tab.bottomright)
            fit_text(surface, self.tab_label, tab.inflate(-6, -2), BLACK, 13,
                     align="left")


class Button:
    """A bevelled, clickable button. Click and key both call on_toggle."""

    DAMAGE_FACE = [GREEN, YELLOW, RED, GREY]

    def __init__(self, panel, rect, label, key=None, group=None,
                 active=False, momentary=False, text_size=11, on_toggle=None):
        self.panel = panel
        self.local = pygame.Rect(rect)
        self.label = label
        self.key = key
        self.group = group
        self.active = active
        self.momentary = momentary
        self.text_size = text_size
        self.on_toggle = on_toggle
        self.hover = False
        self.z = 2
        panel.add(self)
        BUTTONS.append(self)

    def prepare(self):
        pass

    @property
    def screen_rect(self):
        return self.local.move(self.panel.x, self.panel.y)

    def draw(self):
        rect = self.local
        if self.group == "ship_damage":
            phase = int(self.active) % len(self.DAMAGE_FACE)
            face = self.DAMAGE_FACE[phase]
            text_color = BLACK if face in (GREEN, YELLOW) else WHITE
        else:
            if self.active:
                face = BUTTON_ACTIVE
            elif self.hover:
                face = BUTTON_HOVER
            else:
                face = BUTTON_FACE
            text_color = BLACK
        pygame.draw.rect(self.panel.surf, face, rect)
        pygame.draw.line(self.panel.surf, BEVEL_LIGHT, rect.topleft, rect.topright)
        pygame.draw.line(self.panel.surf, BEVEL_LIGHT, rect.topleft, rect.bottomleft)
        pygame.draw.line(self.panel.surf, BEVEL_DARK, rect.bottomleft, rect.bottomright)
        pygame.draw.line(self.panel.surf, BEVEL_DARK, rect.topright, rect.bottomright)
        if self.label:
            fit_text(self.panel.surf, self.label, rect, text_color, self.text_size)

    def activate(self):
        """Toggle (or set, for grouped radios) and notify the handler."""
        if self.group == "ship_damage":
            self.active = (int(self.active) + 1) % len(self.DAMAGE_FACE)
        elif self.group is not None:
            for other in BUTTONS:
                if other.group == self.group and other is not self:
                    other.active = False
            self.active = True if not self.momentary else self.active
        else:
            self.active = not self.active
        if self.on_toggle:
            self.on_toggle(self)


class Text:
    """Static label drawn onto a panel."""

    def __init__(self, panel, pos, text, fg="cyan", size=11):
        self.panel = panel
        self.pos = pos
        self.label = text
        self.fg = fg
        self.size = size
        self.z = 3
        panel.add(self)

    def prepare(self):
        pass

    def draw(self):
        text_line(self.panel.surf, self.label, self.pos, self.fg, self.size)


class Display:
    """A sub-screen surface with a recessed border that elements draw onto."""

    def __init__(self, panel, label, size, pos, double_border=True):
        self.panel = panel
        self.label = label
        self.pos = pos
        self.size = size
        self.double_border = double_border
        self.surf = pygame.Surface(size).convert()
        self.rect = self.surf.get_rect()
        self.z = 1
        panel.add(self)

    def prepare(self):
        self.surf.fill(BLACK)

    def clear(self):
        self.surf.fill(BLACK)

    def draw(self):
        pygame.draw.rect(self.surf, BEVEL_LIGHT, self.rect, 2)
        if self.double_border and self.rect.width > 12 and self.rect.height > 12:
            pygame.draw.rect(self.surf, FRAME_DIM, self.rect.inflate(-6, -6), 1)
        self.panel.surf.blit(self.surf, self.pos)


class CircleDisplay(Display):
    """A round scope display, used for the sensor sweep."""

    def __init__(self, panel, label, pos, radius):
        size = (radius * 2, radius * 2)
        super().__init__(panel, label, size, pos)
        self.radius = radius

    def draw(self):
        pygame.draw.circle(self.surf, BEVEL_LIGHT, self.rect.center, self.radius, 2)
        self.panel.surf.blit(self.surf, self.pos)


class StatusBar:
    """Top alert indicators and bottom console selector tabs."""

    TOP_LABELS = ["LowPwr", "LowSup", "LowTime", "Medical",
                  "SecAlt", "Mines", "Distress", "HullPn"]
    MENU_LABELS = ["NAV", "ENG", "CMB", "CMP", "SEC", "COM", "STG", "SCI", "CTL"]
    MENU_HIGHLIGHT = [0, 0, 2, 0, 0, 2, 2, 2, 2]

    def __init__(self, label, size=(80, 18), highlight=None):
        self.label = label
        self.size = size
        self.surf = pygame.Surface(size).convert()
        self.rect = self.surf.get_rect()
        self.fill = BLACK
        self.highlight = highlight
        self.alerting = False

    def _draw_label(self):
        f = font(13, True)
        total = sum(f.size(c)[0] for c in self.label)
        x = (self.rect.width - total) // 2
        y = (self.rect.height - f.get_height()) // 2
        for i, ch in enumerate(self.label):
            if self.highlight == i:
                ch_color = RED
            else:
                ch_color = BLACK
            glyph = f.render(ch, True, ch_color)
            self.surf.blit(glyph, (x, y))
            x += glyph.get_width()

    def draw(self, surface, pos):
        self.surf.fill(SHELL_BG)
        face = BUTTON_FACE if self.fill == BLACK else self.fill
        pygame.draw.rect(self.surf, face, self.rect, 0, 3)
        pygame.draw.line(self.surf, BEVEL_LIGHT, self.rect.topleft, self.rect.topright)
        pygame.draw.line(self.surf, BEVEL_LIGHT, self.rect.topleft, self.rect.bottomleft)
        pygame.draw.line(self.surf, BEVEL_DARK, self.rect.bottomleft, self.rect.bottomright)
        pygame.draw.line(self.surf, BEVEL_DARK, self.rect.topright, self.rect.bottomright)
        self._draw_label()
        surface.blit(self.surf, pos)

    @staticmethod
    def make_top():
        return [StatusBar(label) for label in StatusBar.TOP_LABELS]

    @staticmethod
    def make_menu():
        return [StatusBar(label, (71, 18), StatusBar.MENU_HIGHLIGHT[i])
                for i, label in enumerate(StatusBar.MENU_LABELS)]

    @staticmethod
    def sequence_flash(bars):
        """Run a green sweep across the alert bars unless one is latched red."""
        slot = (pygame.time.get_ticks() % 800) // 100
        for i, bar in enumerate(bars):
            if bar.alerting:
                bar.fill = RED
            elif i == slot:
                bar.fill = GREEN
            else:
                bar.fill = BUTTON_FACE

    @staticmethod
    def draw_bars(surface, top, menu, notepad):
        x = 660
        for bar in top:
            bar.draw(surface, (x, 10))
            x += 82
        x = 660
        for bar in menu:
            bar.draw(surface, (x, 1050))
            x += 73
        notepad.draw(surface, ((surface.get_width() - notepad.size[0]) // 2, 1015))

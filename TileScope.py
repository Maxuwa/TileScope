# Copyright (C) 2025 Maxy* <mxj.janiszewski@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
import pygame
import sys
import os
import configparser # For INI file handling
import ast          # For safely evaluating tuples from strings
import subprocess   # For opening file location
import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox # Keep for file dialogs
import pygame_gui

# Configuration
TILESET_WIDTH = 2048
TILESET_HEIGHT = 512
TILE_SIZE = 16
COLS = TILESET_WIDTH // TILE_SIZE
ROWS = TILESET_HEIGHT // TILE_SIZE
TOTAL_TILES = COLS * ROWS
CONFIG_FILE_NAME = "tilescope_config.ini"
THEME_FILE = "theme.json"
MAX_SURFACE_DIM = 8192
# Name of the separate guide file (not used by code, but for user reference)
GUIDE_FILE_NAME = "CONFIGURATION_GUIDE.md"

# Defines the structure and default string values for the INI file.
DEFAULT_INI_STRUCTURE = {
    "DisplayColors": {
        "background": "(25, 30, 40)           ; Main background color of the tileset viewing area",
        "grid_color": "(60, 70, 90)           ; Color of the grid lines",
        "overlay_color": "(0, 0, 0, 70)        ; Tileset area overlay color (if enabled)"
    },
    "TextColors": {
        "tile_number_text": "(220, 220, 220)    ; Color of tile ID numbers",
        "tooltip_text": "(230, 230, 230)      ; Color of tooltip text"
    },
    "HighlightColors": {
        "tile_hover": "(255, 215, 0, 128)   ; Tile hover highlight color",
        "tile_select": "(50, 200, 50, 128)  ; Selected tile highlight color"
    },
    "TooltipAppearance": {
        "tooltip_background": "(20, 20, 30, 220)  ; Tooltip box background color",
        "tooltip_border": "(70, 130, 180)     ; Tooltip box border color"
    },
    "UIAppearance": {
        "progress_bar_border": "(70, 100, 130)   ; Export progress bar border (fallback)"
    },
    "FontSettings": {
        "tile_number_font_name": "Arial",
        "tile_number_reference_font_size": "10 ; Base size for tile numbers",
        "tile_number_font_aa": "true           ; Anti-alias tile numbers on display?"
    },
    "Toggles": {
        "show_background_overlay_default": "true ; Default: Show background overlay on startup?",
        "show_grid_default": "true             ; Default: Show grid on startup?",
        "show_numbers_default": "true           ; Default: Show tile numbers on startup?"
    },
    "Export": {
        "default_format": "png                ; Default export image format (png, jpg, bmp)",
        "default_path": ".                  ; Default export directory ('.' is current)"
    },
    "ThemeFile": {
        "theme_file_name": f"{THEME_FILE}    ; Name of the UI theme file (do not change unless you rename the file)"
    }
}


class TileScope:
    def __init__(self, input_path=None):
        pygame.init()
        pygame.display.set_caption("TileScope")

        self.screen_width = 1000
        self.screen_height = 700
        self.screen = pygame.display.set_mode((self.screen_width, self.screen_height), pygame.RESIZABLE)

        self.settings_raw = {} # Will hold raw string values from INI
        self.load_settings_from_ini()

        self.ui_manager = pygame_gui.UIManager((self.screen_width, self.screen_height), THEME_FILE)
        try:
            self.ui_manager.get_theme().load_theme(THEME_FILE)
        except Exception as e:
            print(f"Warning: Could not load theme file '{THEME_FILE}': {e}. Using default theme.")

        self.ui_font = pygame.font.SysFont("Arial", 18)

        self.base_tileset_image = self.create_base_tileset_image(input_path)
        self.scaled_tileset_image = None

        self.zoom = 1.0
        self.actual_applied_zoom = 1.0
        self.min_zoom = 0.05
        self.max_zoom = 4.0

        self.offset_x = 0.0
        self.offset_y = 0.0
        self.dragging = False
        self.last_mouse_pos = (0, 0)

        self.hover_col = None
        self.hover_row = None
        self.selected_tiles = set()

        self.show_grid = self._get_setting("Toggles", "show_grid_default", bool, True)
        self.show_numbers = self._get_setting("Toggles", "show_numbers_default", bool, True)
        self.show_background_overlay = self._get_setting("Toggles", "show_background_overlay_default", bool, True)

        self.export_requested = False
        self.show_export_progress = False
        self.export_progress = 0

        self.temp_message = None
        self.temp_message_time = 0
        self.show_ui_panel_flag = True

        self.tile_number_reference_font = None
        self.pre_rendered_tile_numbers = {}
        self.cached_fonts = {}
        self.cached_rendered_numbers = {}

        self.base_hover_surface = None
        self.base_select_surface = None
        self.cached_scaled_hover_surface = None
        self.cached_scaled_select_surface = None
        self.cached_actual_zoom_for_overlays = -1.0

        self.tileset_area_overlay_surface = None

        self.ui_panel = None
        self.ui_panel_rect = pygame.Rect(0,0,0,0)
        self.buttons = {}
        self.button_configs = {
            "row1": [
                ("open", "Open Image", self.open_image_dialog, False),
                ("grid", "Toggle Grid", self.toggle_grid, self.show_grid),
                ("numbers", "Toggle Numbers", self.toggle_numbers, self.show_numbers),
                ("bg_overlay", "Toggle BG Overlay", self.toggle_background_overlay, self.show_background_overlay),
                ("search", "Search Tile", self.activate_search_dialog, False),
                ("copy", "Copy IDs", self.copy_selected_ids_to_clipboard, False),
            ],
            "row2": [
                ("zoom_in", "Zoom In (+)", lambda: self.adjust_zoom_at_center(1.2), False),
                ("zoom_out", "Zoom Out (-)", lambda: self.adjust_zoom_at_center(1/1.2), False),
                ("reset", "Reset View (R)", self.reset_view, False),
                ("export", "Export Image", self.request_export, False),
                # ("config_info_btn", "Config Info", self.show_config_info_dialog, False), # REMOVED
                ("hide_ui", "Hide UI (F1)", self.toggle_ui_panel_visibility, False),
            ]
        }
        self._update_font_and_pre_render_numbers()
        self._update_base_overlay_surfaces()
        self.setup_ui_elements()
        self.update_scaled_tileset_and_overlays()
        self.clamp_offset()
        self.clock = pygame.time.Clock()

    def _parse_color_tuple_from_string(self, s_tuple_str, default_color=(0,0,0,0)):
        try:
            evaluated = ast.literal_eval(s_tuple_str.strip())
            if isinstance(evaluated, tuple) and (3 <= len(evaluated) <= 4) and all(isinstance(x, int) for x in evaluated):
                return evaluated
        except (ValueError, SyntaxError, TypeError):
            pass
        return default_color

    def _get_setting(self, section, key, expected_type, default_value):
        str_val = self.settings_raw.get(section, {}).get(key)

        if str_val is None:
            return default_value

        str_val = str_val.split(';')[0].strip()
        str_val = str_val.split('#')[0].strip()

        if expected_type == bool:
            return str_val.lower() == 'true'
        elif expected_type == int:
            try: return int(str_val)
            except ValueError: pass
        elif expected_type == tuple:
            return self._parse_color_tuple_from_string(str_val, default_value)
        elif expected_type == float:
            try: return float(str_val)
            except ValueError: pass
        elif expected_type == str:
            return str_val
        return default_value

    def load_settings_from_ini(self):
        self.settings_raw = {}

        config_to_write = configparser.ConfigParser(inline_comment_prefixes=(';', '#'), allow_no_value=True)
        for section_name, section_options in DEFAULT_INI_STRUCTURE.items():
            if not config_to_write.has_section(section_name):
                config_to_write.add_section(section_name)
            for key, full_default_value in section_options.items():
                config_to_write.set(section_name, key, full_default_value)

        file_existed = os.path.exists(CONFIG_FILE_NAME)
        if file_existed:
            config_from_file = configparser.ConfigParser(inline_comment_prefixes=(';', '#'), allow_no_value=True)
            try:
                if config_from_file.read(CONFIG_FILE_NAME):
                    for section in config_from_file.sections():
                        if section in DEFAULT_INI_STRUCTURE:
                            for key, value_from_file in config_from_file.items(section):
                                if key in DEFAULT_INI_STRUCTURE[section]:
                                    default_value_in_structure = DEFAULT_INI_STRUCTURE[section][key]
                                    is_default_structural = default_value_in_structure.strip().startswith(';') or \
                                                       default_value_in_structure.strip().startswith('#') or \
                                                       default_value_in_structure.strip() == ""
                                    if not is_default_structural or value_from_file.strip():
                                        config_to_write.set(section, key, value_from_file)
            except configparser.Error as e:
                print(f"Warning: Error parsing config file '{CONFIG_FILE_NAME}': {e}")

        try:
            with open(CONFIG_FILE_NAME, 'w') as configfile:
                config_to_write.write(configfile)
            if not file_existed:
                print(f"Info: Created new config file '{CONFIG_FILE_NAME}' with defaults.")
        except IOError:
            print(f"Error: Could not write config file to '{CONFIG_FILE_NAME}'.")

        runtime_config = configparser.ConfigParser(inline_comment_prefixes=(';', '#'), allow_no_value=True)
        if runtime_config.read(CONFIG_FILE_NAME):
            for section_default, options_default in DEFAULT_INI_STRUCTURE.items():
                self.settings_raw[section_default] = {}
                for key_default, default_val_str in options_default.items():
                    if runtime_config.has_option(section_default, key_default):
                        self.settings_raw[section_default][key_default] = runtime_config.get(section_default, key_default)
                    else:
                        self.settings_raw[section_default][key_default] = default_val_str
        else:
            print(f"Warning: Could not read '{CONFIG_FILE_NAME}' for runtime. Using hardcoded defaults for self.settings_raw.")
            for section_default, options_default in DEFAULT_INI_STRUCTURE.items():
                self.settings_raw[section_default] = dict(options_default)

        self.show_grid = self._get_setting("Toggles", "show_grid_default", bool, True)
        self.show_numbers = self._get_setting("Toggles", "show_numbers_default", bool, True)
        self.show_background_overlay = self._get_setting("Toggles", "show_background_overlay_default", bool, True)

        if hasattr(self, 'ui_manager'):
            self._update_base_overlay_surfaces()

    def save_settings_to_ini(self):
        config = configparser.ConfigParser(inline_comment_prefixes=(';', '#'), allow_no_value=True)

        for section, options in DEFAULT_INI_STRUCTURE.items():
            if not config.has_section(section):
                config.add_section(section)
            for key, default_str_val_with_comment in options.items():
                current_val_to_write = self.settings_raw.get(section, {}).get(key, default_str_val_with_comment)

                if section == "Toggles":
                    original_comment_part = ""
                    comment_marker = " ; "
                    if comment_marker in default_str_val_with_comment:
                        original_comment_part = default_str_val_with_comment[default_str_val_with_comment.find(comment_marker):]

                    if key == "show_background_overlay_default":
                        current_val_to_write = ("true" if self.show_background_overlay else "false") + original_comment_part
                    elif key == "show_grid_default":
                        current_val_to_write = ("true" if self.show_grid else "false") + original_comment_part
                    elif key == "show_numbers_default":
                        current_val_to_write = ("true" if self.show_numbers else "false") + original_comment_part

                config.set(section, key, current_val_to_write)
        try:
            with open(CONFIG_FILE_NAME, 'w') as configfile:
                config.write(configfile)
        except IOError:
            print(f"Error: Could not save settings to '{CONFIG_FILE_NAME}'.")

    def _update_font_and_pre_render_numbers(self):
        font_name = self._get_setting("FontSettings", "tile_number_font_name", str, "Arial")
        ref_size = self._get_setting("FontSettings", "tile_number_reference_font_size", int, 10)
        font_aa = self._get_setting("FontSettings", "tile_number_font_aa", bool, True)
        font_aa_export = True

        try:
            self.tile_number_reference_font = pygame.font.SysFont(font_name, ref_size)
        except pygame.error:
            print(f"Warning: Font '{font_name}' (ref size {ref_size}) not found. Using default Arial.")
            self.tile_number_reference_font = pygame.font.SysFont("Arial", ref_size)

        text_color_numbers = self._get_setting("TextColors", "tile_number_text", tuple, (220,220,220))
        self.pre_rendered_tile_numbers.clear()
        for i in range(100):
            label_str = f"{i:02d}"
            text_surface = self.tile_number_reference_font.render(label_str, font_aa_export, text_color_numbers)
            self.pre_rendered_tile_numbers[label_str] = text_surface

        self.cached_fonts.clear()
        self.cached_rendered_numbers.clear()

    def _update_base_overlay_surfaces(self):
        self.base_hover_surface = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
        self.base_hover_surface.fill(self._get_setting("HighlightColors", "tile_hover", tuple, (255,215,0,128)))

        self.base_select_surface = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
        self.base_select_surface.fill(self._get_setting("HighlightColors", "tile_select", tuple, (50,200,50,128)))

        self.cached_actual_zoom_for_overlays = -1.0

    def setup_ui_elements(self):
        # print("-" * 20) # Debug
        # print(f"DEBUG: setup_ui_elements called. screen_width={self.screen_width}, screen_height={self.screen_height}") # Debug
        panel_height = 85
        self.ui_panel_rect = pygame.Rect(0, self.screen_height - panel_height,
                                         self.screen_width, panel_height)
        # print(f"DEBUG: Calculated ui_panel_rect: {self.ui_panel_rect}") # Debug

        if self.ui_panel and self.ui_panel.alive():
            # print("DEBUG: Killing existing ui_panel") # Debug
            self.ui_panel.kill()
        self.ui_panel = None

        self.buttons = {}
        # print("DEBUG: Old button references cleared.") # Debug

        btn_w, btn_h = 130, 30
        spacing = 10
        panel_internal_padding_x = 15
        panel_internal_padding_y = 10
        row1_y_rel = panel_internal_padding_y
        row2_y_rel = panel_internal_padding_y + btn_h + panel_internal_padding_y // 2

        # print("DEBUG: Attempting to create UIPanel...") # Debug
        try:
            self.ui_panel = pygame_gui.elements.UIPanel(
                relative_rect=self.ui_panel_rect,
                starting_height=1,
                manager=self.ui_manager,
                object_id="#ui_panel"
            )
            # if self.ui_panel: print(f"DEBUG: New UIPanel alive: {self.ui_panel.alive()}, visible: {self.ui_panel.visible}") # Debug
            # else: print("DEBUG: self.ui_panel is None AFTER creation attempt!") # Debug
        except Exception as e:
            print(f"DEBUG: EXCEPTION during UIPanel creation: {e}")
            self.ui_panel = None

        if self.ui_panel and self.ui_panel.alive():
            current_x_rel = panel_internal_padding_x
            for key, text, _, is_selected_initially in self.button_configs["row1"]:
                btn_rect = pygame.Rect(current_x_rel, row1_y_rel, btn_w, btn_h)
                button = pygame_gui.elements.UIButton(
                    relative_rect=btn_rect, text=text, manager=self.ui_manager,
                    container=self.ui_panel, object_id=f"#{key}_button"
                )
                self.buttons[key] = button
                if is_selected_initially: button.select()
                current_x_rel += btn_w + spacing

            current_x_rel = panel_internal_padding_x
            for key, text, _, is_selected_initially in self.button_configs["row2"]:
                btn_rect = pygame.Rect(current_x_rel, row2_y_rel, btn_w, btn_h)
                button = pygame_gui.elements.UIButton(
                    relative_rect=btn_rect, text=text, manager=self.ui_manager,
                    container=self.ui_panel, object_id=f"#{key}_button"
                )
                self.buttons[key] = button
                if is_selected_initially: button.select()
                current_x_rel += btn_w + spacing
        # else: print("DEBUG: UIPanel is not valid, skipping button creation.") # Debug

        if self.ui_panel and self.ui_panel.alive():
            if self.show_ui_panel_flag:
                self.ui_panel.show()
            else:
                self.ui_panel.hide()

        # self.ui_manager.update(0.0) # Debug
        # if self.ui_panel and self.ui_panel.alive(): print(f"DEBUG: (End of method) UIPanel abs_rect: {self.ui_panel.get_abs_rect()}") # Debug
        # print(f"DEBUG: (End of method) Number of buttons in self.buttons dict: {len(self.buttons)}") # Debug
        # for key, btn in self.buttons.items(): # Debug
        #     if btn and btn.alive(): print(f"DEBUG: (End of method) Button '{key}' alive: {btn.alive()}, visible: {btn.visible}, abs_rect: {btn.get_abs_rect()}") # Debug
        #     else: print(f"DEBUG: (End of method) Button '{key}' is None or not alive.") # Debug
        # print("--- End setup_ui_elements debug ---") # Debug

    def create_base_tileset_image(self, input_path=None):
        surface = pygame.Surface((TILESET_WIDTH, TILESET_HEIGHT))
        if input_path and os.path.exists(input_path):
            try:
                img = pygame.image.load(input_path)
                if img.get_size() != (TILESET_WIDTH, TILESET_HEIGHT):
                    self.show_temp_message(f"Warning: Image resized to {TILESET_WIDTH}x{TILESET_HEIGHT}", "warning")
                    img = pygame.transform.scale(img, (TILESET_WIDTH, TILESET_HEIGHT))
                surface.blit(img, (0, 0))
            except pygame.error as e:
                print(f"Error loading image '{input_path}': {e}")
                self.show_temp_message(f"Error loading: {os.path.basename(input_path)}", "error")
                self.create_placeholder_gradient(surface)
        else:
            if input_path: self.show_temp_message(f"File not found: {os.path.basename(input_path)}", "error")
            self.create_placeholder_gradient(surface)
        return surface

    def create_placeholder_gradient(self, surface):
        for y in range(TILESET_HEIGHT):
            color_val = int(200 + 55 * y / TILESET_HEIGHT)
            pygame.draw.line(surface, (color_val, color_val, color_val), (0, y), (TILESET_WIDTH, y))

    def update_scaled_tileset_and_overlays(self):
        conceptual_w = TILESET_WIDTH * self.zoom
        conceptual_h = TILESET_HEIGHT * self.zoom
        current_aspect_ratio = TILESET_WIDTH / TILESET_HEIGHT if TILESET_HEIGHT > 0 else 1.0

        if conceptual_w > MAX_SURFACE_DIM:
            final_scaled_w = MAX_SURFACE_DIM
            final_scaled_h = MAX_SURFACE_DIM / current_aspect_ratio if current_aspect_ratio > 0 else MAX_SURFACE_DIM
        elif conceptual_h > MAX_SURFACE_DIM:
            final_scaled_h = MAX_SURFACE_DIM
            final_scaled_w = MAX_SURFACE_DIM * current_aspect_ratio
        else:
            final_scaled_w = conceptual_w
            final_scaled_h = conceptual_h

        final_scaled_w = max(1, int(final_scaled_w))
        final_scaled_h = max(1, int(final_scaled_h))

        if self.base_tileset_image.get_width() > 0 and self.base_tileset_image.get_height() > 0:
            self.scaled_tileset_image = pygame.transform.scale(self.base_tileset_image, (final_scaled_w, final_scaled_h))
        else:
            self.scaled_tileset_image = pygame.Surface((final_scaled_w, final_scaled_h))
            self.scaled_tileset_image.fill(self._get_setting("DisplayColors", "background", tuple, (25,30,40)))

        self.actual_applied_zoom = final_scaled_w / TILESET_WIDTH if TILESET_WIDTH > 0 else 1.0
        if TILESET_HEIGHT > 0 and abs(final_scaled_h / TILESET_HEIGHT - self.actual_applied_zoom) > 1e-5 :
            self.actual_applied_zoom = final_scaled_h / TILESET_HEIGHT

        if self.scaled_tileset_image:
            overlay_w = self.scaled_tileset_image.get_width()
            overlay_h = self.scaled_tileset_image.get_height()
            if overlay_w > 0 and overlay_h > 0:
                self.tileset_area_overlay_surface = pygame.Surface((overlay_w, overlay_h), pygame.SRCALPHA)
                self.tileset_area_overlay_surface.fill(self._get_setting("DisplayColors", "overlay_color", tuple, (0,0,0,70)))
            else: self.tileset_area_overlay_surface = None
        else: self.tileset_area_overlay_surface = None

        current_on_screen_tile_size = round(TILE_SIZE * self.actual_applied_zoom)
        if abs(self.actual_applied_zoom - self.cached_actual_zoom_for_overlays) > 1e-6:
            if current_on_screen_tile_size < 1:
                dummy_surf = pygame.Surface((1,1), pygame.SRCALPHA); dummy_surf.fill((0,0,0,0))
                self.cached_scaled_hover_surface = dummy_surf
                self.cached_scaled_select_surface = dummy_surf
            else:
                if self.base_hover_surface:
                    self.cached_scaled_hover_surface = pygame.transform.scale(self.base_hover_surface, (current_on_screen_tile_size, current_on_screen_tile_size))
                if self.base_select_surface:
                    self.cached_scaled_select_surface = pygame.transform.scale(self.base_select_surface, (current_on_screen_tile_size, current_on_screen_tile_size))
            self.cached_actual_zoom_for_overlays = self.actual_applied_zoom

    def clamp_offset(self):
        conceptual_scaled_width = TILESET_WIDTH * self.zoom
        conceptual_scaled_height = TILESET_HEIGHT * self.zoom
        panel_height = self.ui_panel_rect.height if self.show_ui_panel_flag and self.ui_panel and self.ui_panel.alive() else 0
        view_height = self.screen_height - panel_height

        if conceptual_scaled_width < self.screen_width:
            self.offset_x = (self.screen_width - conceptual_scaled_width) / 2.0
        else:
            self.offset_x = min(0.0, max(self.offset_x, self.screen_width - conceptual_scaled_width))
        if conceptual_scaled_height < view_height:
            self.offset_y = (view_height - conceptual_scaled_height) / 2.0
        else:
            self.offset_y = min(0.0, max(self.offset_y, view_height - conceptual_scaled_height))

    def _adjust_zoom_internal(self, factor, zoom_center_x, zoom_center_y):
        old_conceptual_zoom = self.zoom
        new_conceptual_zoom = self.zoom * factor
        new_conceptual_zoom = max(self.min_zoom, min(new_conceptual_zoom, self.max_zoom))
        if abs(new_conceptual_zoom - old_conceptual_zoom) < 1e-6: return

        self.offset_x = zoom_center_x - (zoom_center_x - self.offset_x) * (new_conceptual_zoom / old_conceptual_zoom)
        self.offset_y = zoom_center_y - (zoom_center_y - self.offset_y) * (new_conceptual_zoom / old_conceptual_zoom)
        self.zoom = new_conceptual_zoom
        self.update_scaled_tileset_and_overlays(); self.clamp_offset()

    def adjust_zoom_at_mouse(self, factor):
        mouse_x, mouse_y = pygame.mouse.get_pos()
        panel_height = self.ui_panel_rect.height if self.show_ui_panel_flag and self.ui_panel and self.ui_panel.alive() else 0
        if mouse_y < self.screen_height - panel_height : self._adjust_zoom_internal(factor, float(mouse_x), float(mouse_y))

    def adjust_zoom_at_center(self, factor):
        panel_height = self.ui_panel_rect.height if self.show_ui_panel_flag and self.ui_panel and self.ui_panel.alive() else 0
        center_x = self.screen_width / 2.0; center_y = (self.screen_height - panel_height) / 2.0
        self._adjust_zoom_internal(factor, center_x, center_y)

    def toggle_grid(self):
        self.show_grid = not self.show_grid
        button = self.buttons.get("grid")
        if button:
            if self.show_grid: button.select()
            else: button.unselect()
        self.settings_raw.setdefault("Toggles", {})["show_grid_default"] = "true" if self.show_grid else "false"

    def toggle_numbers(self):
        self.show_numbers = not self.show_numbers
        button = self.buttons.get("numbers")
        if button:
            if self.show_numbers: button.select()
            else: button.unselect()
        self.settings_raw.setdefault("Toggles", {})["show_numbers_default"] = "true" if self.show_numbers else "false"

    def toggle_background_overlay(self):
        self.show_background_overlay = not self.show_background_overlay
        self.settings_raw.setdefault("Toggles", {})["show_background_overlay_default"] = "true" if self.show_background_overlay else "false"
        button = self.buttons.get("bg_overlay")
        if button:
            if self.show_background_overlay: button.select()
            else: button.unselect()

    def toggle_ui_panel_visibility(self):
        self.show_ui_panel_flag = not self.show_ui_panel_flag
        hide_ui_button = self.buttons.get("hide_ui")
        if self.ui_panel:
            if self.show_ui_panel_flag:
                self.ui_panel.show()
                if hide_ui_button: hide_ui_button.set_text("Hide UI (F1)")
            else:
                self.ui_panel.hide()
                if hide_ui_button: hide_ui_button.set_text("Show UI (F1)")
        self.clamp_offset()

    def request_export(self): self.export_requested = True
    def compute_tile_id(self, col, row): return (col % 16) + (col // 16) * 512 + row * 16
    def get_tile_from_id(self, tile_id):
        if not (0 <= tile_id < TOTAL_TILES): return None
        for r_idx in range(ROWS):
            for c_idx in range(COLS):
                if self.compute_tile_id(c_idx, r_idx) == tile_id: return c_idx, r_idx
        return None

    def export_tileset_image(self):
        self.show_export_progress = True; self.export_progress = 0; pygame.display.flip()
        root = tk.Tk(); root.withdraw()

        default_path_str = self._get_setting("Export", "default_path", str, ".")
        if default_path_str == ".": default_path_str = os.getcwd()

        file_ext = self._get_setting("Export", "default_format", str, "png").lower()

        file_path = filedialog.asksaveasfilename(
            initialdir=default_path_str,
            initialfile=f"tileset_export.{file_ext}",
            defaultextension=f".{file_ext}",
            filetypes=[("PNG files", "*.png"), ("JPEG files", "*.jpg;*.jpeg"), ("BMP files", "*.bmp")]
        )
        if not file_path: self.show_export_progress = False; return

        self.settings_raw.setdefault("Export", {})["default_path"] = os.path.dirname(file_path)
        self.settings_raw.setdefault("Export", {})["default_format"] = os.path.splitext(file_path)[1].lstrip('.') or "png"

        export_surf = pygame.Surface((TILESET_WIDTH, TILESET_HEIGHT)); export_surf.blit(self.base_tileset_image, (0, 0))

        if self.show_background_overlay:
            export_overlay_tile_surf = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
            export_overlay_tile_surf.fill(self._get_setting("DisplayColors", "overlay_color", tuple, (0,0,0,70)))
            for r_idx in range(ROWS):
                for c_idx in range(COLS):
                    export_surf.blit(export_overlay_tile_surf, (c_idx * TILE_SIZE, r_idx * TILE_SIZE))

        if self.show_grid:
            grid_color = self._get_setting("DisplayColors", "grid_color", tuple, (60,70,90))
            for x_coord in range(0, TILESET_WIDTH + 1, TILE_SIZE): pygame.draw.line(export_surf, grid_color, (x_coord, 0), (x_coord, TILESET_HEIGHT), 1)
            for y_coord in range(0, TILESET_HEIGHT + 1, TILE_SIZE): pygame.draw.line(export_surf, grid_color, (0, y_coord), (TILESET_WIDTH, y_coord), 1)
        if self.show_numbers:
            total_export_tiles = COLS * ROWS; processed_tiles = 0
            for r_idx in range(ROWS):
                for c_idx in range(COLS):
                    tile_id_val = self.compute_tile_id(c_idx, r_idx); label_str = f"{tile_id_val % 100:02d}"
                    number_surf = self.pre_rendered_tile_numbers.get(label_str)
                    if number_surf:
                        tx = c_idx * TILE_SIZE + (TILE_SIZE - number_surf.get_width()) // 2
                        ty = r_idx * TILE_SIZE + (TILE_SIZE - number_surf.get_height()) // 2
                        export_surf.blit(number_surf, (tx, ty))
                    processed_tiles +=1
                    if processed_tiles % 100 == 0:
                        self.export_progress = processed_tiles / total_export_tiles
                        self.draw_export_progress_bar(); pygame.display.flip()
                        for evt in pygame.event.get():
                             if evt.type == pygame.QUIT: self.show_export_progress = False; return
        try:
            pygame.image.save(export_surf, file_path)
            self.show_temp_message(f"Exported to {os.path.basename(file_path)}", "success")
        except pygame.error as e: self.show_temp_message(f"Error saving: {e}", "error"); print(f"Export error: {e}")
        self.show_export_progress = False

    def reset_view(self):
        self.zoom = 1.0
        self.update_scaled_tileset_and_overlays()
        panel_height = self.ui_panel_rect.height if self.show_ui_panel_flag and self.ui_panel and self.ui_panel.alive() else 0
        view_height = self.screen_height - panel_height
        current_display_width = TILESET_WIDTH * self.actual_applied_zoom
        current_display_height = TILESET_HEIGHT * self.actual_applied_zoom
        self.offset_x = (self.screen_width - current_display_width) / 2.0
        self.offset_y = (view_height - current_display_height) / 2.0
        self.clamp_offset()

    def open_image_dialog(self):
        root = tk.Tk(); root.withdraw()
        current_path = self._get_setting("Export", "default_path", str, ".")
        if current_path == ".": current_path = os.getcwd()

        file_path = filedialog.askopenfilename(
            initialdir=current_path,
            title="Select Tileset Image",
            filetypes=[("Image files", "*.png;*.jpg;*.jpeg;*.bmp;*.tga"), ("All files", "*.*")]
        )
        if file_path:
            self.base_tileset_image = self.create_base_tileset_image(file_path)
            self.settings_raw.setdefault("Export", {})["default_path"] = os.path.dirname(file_path)
            self.reset_view()

    def activate_search_dialog(self):
        root = tk.Tk(); root.withdraw()
        tile_id_str = simpledialog.askstring("Search Tile", "Enter Tile ID (0-4095):", parent=root)
        if tile_id_str:
            try:
                tile_id = int(tile_id_str)
                if self.center_on_tile_id(tile_id): self.show_temp_message(f"Found Tile ID: {tile_id}", "info")
                else: self.show_temp_message(f"Tile ID {tile_id} not found or invalid.", "error")
            except ValueError: self.show_temp_message("Invalid Tile ID format.", "error")

    def center_on_tile_id(self, tile_id):
        coords = self.get_tile_from_id(tile_id)
        if coords:
            col, row = coords; self.selected_tiles = {(col, row)}
            if self.zoom < 2.0: self.zoom = 2.0
            self.update_scaled_tileset_and_overlays()
            tile_center_x_on_screen = (col + 0.5) * TILE_SIZE * self.actual_applied_zoom
            tile_center_y_on_screen = (row + 0.5) * TILE_SIZE * self.actual_applied_zoom
            panel_height = self.ui_panel_rect.height if self.show_ui_panel_flag and self.ui_panel and self.ui_panel.alive() else 0
            view_center_x_screen = self.screen_width / 2.0
            view_center_y_screen = (self.screen_height - panel_height) / 2.0
            self.offset_x = view_center_x_screen - tile_center_x_on_screen
            self.offset_y = view_center_y_screen - tile_center_y_on_screen
            self.clamp_offset(); return True
        return False

    def copy_selected_ids_to_clipboard(self):
        if not self.selected_tiles: self.show_temp_message("No tiles selected.", "info"); return
        ids_str = ", ".join(sorted([str(self.compute_tile_id(c, r)) for c, r in self.selected_tiles]))
        root = tk.Tk(); root.withdraw(); root.clipboard_clear(); root.clipboard_append(ids_str)
        root.update(); root.destroy()
        self.show_temp_message(f"{len(self.selected_tiles)} ID(s) copied: {ids_str[:50]}...", "success")

    def show_temp_message(self, message, level="info"):
        self.temp_message = {"text": message, "level": level, "time": pygame.time.get_ticks()}

    def _open_file_location(self, file_path_to_open): # Still used by removed dialog, but harmless to keep for now
        directory = os.path.dirname(os.path.abspath(file_path_to_open))
        if not os.path.exists(directory):
            directory = os.path.abspath(os.path.dirname(sys.argv[0]))

        try:
            if sys.platform == "win32": os.startfile(directory)
            elif sys.platform == "darwin": subprocess.Popen(["open", directory])
            else: subprocess.Popen(["xdg-open", directory])
            self.show_temp_message(f"Opened folder: {directory}", "info")
        except Exception as e:
            self.show_temp_message(f"Error opening folder: {e}", "error")
            print(f"Error opening folder {directory}: {e}")

    def get_visible_tile_range(self):
        panel_height = self.ui_panel_rect.height if self.show_ui_panel_flag and self.ui_panel and self.ui_panel.alive() else 0
        safe_actual_zoom = self.actual_applied_zoom if self.actual_applied_zoom > 1e-6 else 1.0
        base_img_x_start = -self.offset_x / safe_actual_zoom
        base_img_y_start = -self.offset_y / safe_actual_zoom
        base_img_view_width = self.screen_width / safe_actual_zoom
        base_img_view_height = (self.screen_height - panel_height) / safe_actual_zoom
        base_img_x_end = base_img_x_start + base_img_view_width
        base_img_y_end = base_img_y_start + base_img_view_height
        start_col = max(0, int(base_img_x_start // TILE_SIZE))
        end_col = min(COLS, int(base_img_x_end // TILE_SIZE) + 2)
        start_row = max(0, int(base_img_y_start // TILE_SIZE))
        end_row = min(ROWS, int(base_img_y_end // TILE_SIZE) + 2)
        return start_col, end_col, start_row, end_row

    def handle_events(self, time_delta):
        for event in pygame.event.get():
            ui_consumed_event = self.ui_manager.process_events(event)

            if event.type == pygame.QUIT:
                self.save_settings_to_ini()
                return False

            elif event.type == pygame.VIDEORESIZE:
                self.screen_width = max(600, event.w)
                self.screen_height = max(400, event.h)
                self.screen = pygame.display.set_mode((self.screen_width, self.screen_height), pygame.RESIZABLE)
                self.ui_manager.set_window_resolution((self.screen_width, self.screen_height))
                self.setup_ui_elements()
                self.clamp_offset()
                self.update_scaled_tileset_and_overlays()

            elif event.type == pygame_gui.UI_BUTTON_PRESSED:
                action_to_perform = None
                for row_key in self.button_configs:
                    for key, _, action_func, _ in self.button_configs[row_key]:
                        button_instance = self.buttons.get(key)
                        if button_instance == event.ui_element:
                            action_to_perform = action_func
                            break
                    if action_to_perform:
                        break
                if action_to_perform:
                    action_to_perform()
                ui_consumed_event = True

            if not ui_consumed_event:
                if event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        panel_height = self.ui_panel_rect.height if self.show_ui_panel_flag and self.ui_panel and self.ui_panel.alive() else 0
                        if event.pos[1] < self.screen_height - panel_height:
                            self.dragging = True
                            self.last_mouse_pos = event.pos
                            if self.hover_col is not None and self.hover_row is not None:
                                tile_coords = (self.hover_col, self.hover_row)
                                mods = pygame.key.get_mods()
                                if mods & pygame.KMOD_SHIFT or mods & pygame.KMOD_CTRL:
                                    if tile_coords in self.selected_tiles:
                                        self.selected_tiles.remove(tile_coords)
                                    else:
                                        self.selected_tiles.add(tile_coords)
                                else:
                                    self.selected_tiles = {tile_coords}
                    elif event.button == 4:
                        self.adjust_zoom_at_mouse(1.1)
                    elif event.button == 5:
                        self.adjust_zoom_at_mouse(0.9)

                elif event.type == pygame.MOUSEBUTTONUP:
                    if event.button == 1:
                        self.dragging = False

            if event.type == pygame.MOUSEMOTION:
                if self.dragging:
                    dx = event.pos[0] - self.last_mouse_pos[0]
                    dy = event.pos[1] - self.last_mouse_pos[1]
                    self.offset_x += dx
                    self.offset_y += dy
                    self.last_mouse_pos = event.pos
                    self.clamp_offset()

                panel_height = self.ui_panel_rect.height if self.show_ui_panel_flag and self.ui_panel and self.ui_panel.alive() else 0
                if event.pos[1] < self.screen_height - panel_height:
                    safe_actual_zoom = self.actual_applied_zoom if self.actual_applied_zoom > 1e-6 else 1.0
                    img_x = (event.pos[0] - self.offset_x) / safe_actual_zoom
                    img_y = (event.pos[1] - self.offset_y) / safe_actual_zoom
                    if 0 <= img_x < TILESET_WIDTH and 0 <= img_y < TILESET_HEIGHT:
                        self.hover_col = int(img_x // TILE_SIZE)
                        self.hover_row = int(img_y // TILE_SIZE)
                    else:
                        self.hover_col = None
                        self.hover_row = None
                else:
                    self.hover_col = None
                    self.hover_row = None

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_F1:
                    self.toggle_ui_panel_visibility()
                elif event.key == pygame.K_r:
                    self.reset_view()
                elif event.key == pygame.K_PLUS or event.key == pygame.K_EQUALS:
                    self.adjust_zoom_at_center(1.2)
                elif event.key == pygame.K_MINUS or event.key == pygame.K_UNDERSCORE:
                    self.adjust_zoom_at_center(1/1.2)
                elif event.key == pygame.K_g:
                    self.toggle_grid()
                elif event.key == pygame.K_n:
                    self.toggle_numbers()
                elif event.key == pygame.K_c and (pygame.key.get_mods() & pygame.KMOD_CTRL):
                    self.copy_selected_ids_to_clipboard()
                elif event.key == pygame.K_f and (pygame.key.get_mods() & pygame.KMOD_CTRL):
                    self.activate_search_dialog()
        return True

    def draw_grid_and_overlays(self):
        start_col, end_col, start_row, end_row = self.get_visible_tile_range()
        on_screen_tile_size = TILE_SIZE * self.actual_applied_zoom
        on_screen_tile_size_px = round(on_screen_tile_size)

        if self.show_grid and on_screen_tile_size_px > 1:
            grid_color = self._get_setting("DisplayColors", "grid_color", tuple, (60,70,90))
            panel_h = self.ui_panel_rect.height if self.show_ui_panel_flag and self.ui_panel and self.ui_panel.alive() else 0
            view_bottom_y = self.screen_height - panel_h
            for c_idx in range(start_col, end_col + 1):
                x = round(self.offset_x + c_idx * on_screen_tile_size)
                y_start_on_grid = self.offset_y ; y_end_on_grid = self.offset_y + TILESET_HEIGHT * self.actual_applied_zoom
                draw_y_start = round(max(y_start_on_grid, 0)); draw_y_end = round(min(y_end_on_grid, view_bottom_y))
                if draw_y_start < draw_y_end and -1 <= x <= self.screen_width + 1 :
                    pygame.draw.line(self.screen, grid_color, (x, draw_y_start), (x, draw_y_end), 1)
            for r_idx in range(start_row, end_row + 1):
                y = round(self.offset_y + r_idx * on_screen_tile_size)
                x_start_on_grid = self.offset_x; x_end_on_grid = self.offset_x + TILESET_WIDTH * self.actual_applied_zoom
                draw_x_start = round(max(x_start_on_grid, 0)); draw_x_end = round(min(x_end_on_grid, self.screen_width))
                if draw_x_start < draw_x_end and -1 <= y <= view_bottom_y + 1:
                    pygame.draw.line(self.screen, grid_color, (draw_x_start, y), (draw_x_end, y), 1)

        if self.show_numbers and on_screen_tile_size_px >= 4 :
            base_font_calc_size = int(self._get_setting("FontSettings", "tile_number_reference_font_size", int, 10) * self.zoom)
            target_num_font_size = max(4, min(base_font_calc_size, 40))
            if target_num_font_size >= 4:
                font_name = self._get_setting("FontSettings", "tile_number_font_name", str, "Arial")
                text_color = self._get_setting("TextColors", "tile_number_text", tuple, (220,220,220))
                font_aa = self._get_setting("FontSettings", "tile_number_font_aa", bool, True)
                font_cache_key = (font_name, target_num_font_size, font_aa)
                current_font = self.cached_fonts.get(font_cache_key)
                if not current_font:
                    try: current_font = pygame.font.SysFont(font_name, target_num_font_size)
                    except pygame.error: current_font = pygame.font.SysFont("Arial", target_num_font_size)
                    self.cached_fonts[font_cache_key] = current_font

                for r_idx in range(start_row, end_row):
                    for c_idx in range(start_col, end_col):
                        if not (0 <= c_idx < COLS and 0 <= r_idx < ROWS): continue
                        tile_id_val = self.compute_tile_id(c_idx, r_idx); label_str = f"{tile_id_val % 100:02d}"
                        num_surf_cache_key = (label_str, font_name, target_num_font_size, font_aa)
                        final_number_surf = self.cached_rendered_numbers.get(num_surf_cache_key)
                        if not final_number_surf:
                            final_number_surf = current_font.render(label_str, font_aa, text_color)
                            self.cached_rendered_numbers[num_surf_cache_key] = final_number_surf

                        scr_x_center = self.offset_x + (c_idx + 0.5) * on_screen_tile_size
                        scr_y_center = self.offset_y + (r_idx + 0.5) * on_screen_tile_size
                        num_rect = final_number_surf.get_rect(center=(round(scr_x_center), round(scr_y_center)))
                        self.screen.blit(final_number_surf, num_rect)

        if self.selected_tiles and self.cached_scaled_select_surface and on_screen_tile_size_px >= 1:
            for col, row in self.selected_tiles:
                if start_col <= col < end_col and start_row <= row < end_row:
                    if 0 <= col < COLS and 0 <= row < ROWS:
                        scr_x = round(self.offset_x + col * on_screen_tile_size)
                        scr_y = round(self.offset_y + row * on_screen_tile_size)
                        self.screen.blit(self.cached_scaled_select_surface, (scr_x, scr_y))

        if self.hover_col is not None and self.hover_row is not None and \
           self.cached_scaled_hover_surface and on_screen_tile_size_px >= 1:
             scr_x = round(self.offset_x + self.hover_col * on_screen_tile_size)
             scr_y = round(self.offset_y + self.hover_row * on_screen_tile_size)
             self.screen.blit(self.cached_scaled_hover_surface, (scr_x, scr_y))

    def draw_tooltip(self):
        if self.hover_col is None or self.hover_row is None: return
        tile_id_val = self.compute_tile_id(self.hover_col, self.hover_row)
        id_text_str = f"ID: {tile_id_val}"; pos_text_str = f"Pos: ({self.hover_col}, {self.hover_row})"

        text_color = self._get_setting("TextColors", "tooltip_text", tuple, (230,230,230))
        id_surf = self.ui_font.render(id_text_str, True, text_color)
        pos_surf = self.ui_font.render(pos_text_str, True, text_color)

        padding = 8; tooltip_w = max(id_surf.get_width(), pos_surf.get_width()) + 2 * padding
        tooltip_h = id_surf.get_height() + pos_surf.get_height() + 3 * padding
        mx, my = pygame.mouse.get_pos(); tt_x = mx + 15; tt_y = my - tooltip_h - 5
        tt_x = max(5, min(tt_x, self.screen_width - tooltip_w - 5))
        panel_h = self.ui_panel_rect.height if self.show_ui_panel_flag and self.ui_panel and self.ui_panel.alive() else 0
        tt_y = max(5, min(tt_y, self.screen_height - panel_h - tooltip_h - 5))

        pygame.draw.rect(self.screen, self._get_setting("TooltipAppearance", "tooltip_background", tuple, (20,20,30,220)),
                         (tt_x, tt_y, tooltip_w, tooltip_h), border_radius=3)
        pygame.draw.rect(self.screen, self._get_setting("TooltipAppearance", "tooltip_border", tuple, (70,130,180)),
                         (tt_x, tt_y, tooltip_w, tooltip_h), 1, border_radius=3)
        self.screen.blit(id_surf, (tt_x + padding, tt_y + padding))
        self.screen.blit(pos_surf, (tt_x + padding, tt_y + padding + id_surf.get_height() + padding // 2))

    def draw_export_progress_bar(self):
        if not self.show_export_progress: return
        bar_w, bar_h = 300, 30; bar_x = (self.screen_width - bar_w) // 2; bar_y = (self.screen_height - bar_h) // 2
        try:
            progress_bar_bg = pygame.Color(self.ui_manager.get_theme().get_colour('dark_bg'))
            progress_bar_fill = pygame.Color(self.ui_manager.get_theme().get_colour('selected_bg'))
            progress_text_color = pygame.Color(self.ui_manager.get_theme().get_colour('normal_text'))
            progress_bar_border_from_theme = pygame.Color(self.ui_manager.get_theme().get_colour('normal_border'))
        except:
            progress_bar_bg = pygame.Color(30,40,50)
            progress_bar_fill = pygame.Color(0,120,215)
            progress_text_color = pygame.Color(220,220,220)
            progress_bar_border_from_theme = self._get_setting("UIAppearance", "progress_bar_border", tuple, (70,100,130))

        pygame.draw.rect(self.screen, progress_bar_bg, (bar_x, bar_y, bar_w, bar_h))
        pygame.draw.rect(self.screen, progress_bar_border_from_theme, (bar_x, bar_y, bar_w, bar_h), 2)
        fill_w = int(bar_w * self.export_progress)
        pygame.draw.rect(self.screen, progress_bar_fill, (bar_x, bar_y, fill_w, bar_h))
        text_str = f"Exporting... {int(self.export_progress * 100)}%"
        text_surf = self.ui_font.render(text_str, True, progress_text_color)
        text_rect = text_surf.get_rect(center=(bar_x + bar_w // 2, bar_y + bar_h // 2)); self.screen.blit(text_surf, text_rect)

    def draw_temporary_message(self):
        if self.temp_message and (pygame.time.get_ticks() - self.temp_message["time"] < 2500):
            msg = self.temp_message["text"]; level = self.temp_message["level"]
            color_map = {"info": (100,180,255), "success": (100,220,100), "warning": (255,180,80), "error": (255,100,100)}
            text_color = color_map.get(level, (200,200,200))
            try:
                bg_col_str = self.ui_manager.get_theme().get_colour_string('dark_bg')
                bg_col_tuple = pygame.Color(bg_col_str)
                msg_bg_color = (bg_col_tuple.r, bg_col_tuple.g, bg_col_tuple.b, 220)
            except: msg_bg_color = (30,40,50,220)
            msg_surf = self.ui_font.render(msg, True, text_color)
            msg_rect = msg_surf.get_rect(center=(self.screen_width // 2, 30))
            bg_rect = msg_rect.inflate(20,10)
            bg_surf = pygame.Surface(bg_rect.size, pygame.SRCALPHA)
            bg_surf.fill(msg_bg_color)
            self.screen.blit(bg_surf, bg_rect.topleft); self.screen.blit(msg_surf, msg_rect.topleft)
        elif self.temp_message: self.temp_message = None

    def draw_main_content(self):
        self.screen.fill(self._get_setting("DisplayColors", "background", tuple, (25,30,40)))
        if self.scaled_tileset_image:
            self.screen.blit(self.scaled_tileset_image, (round(self.offset_x), round(self.offset_y)))
        if self.show_background_overlay and self.tileset_area_overlay_surface:
            self.screen.blit(self.tileset_area_overlay_surface, (round(self.offset_x), round(self.offset_y)))
        self.draw_grid_and_overlays()
        if self.hover_col is not None: self.draw_tooltip()

    def run(self):
        running = True
        while running:
            time_delta = self.clock.tick(60)/1000.0
            running = self.handle_events(time_delta)
            if not running: break

            self.ui_manager.update(time_delta)

            self.draw_main_content()
            if self.show_ui_panel_flag:
                if self.ui_panel and self.ui_panel.alive():
                    self.ui_manager.draw_ui(self.screen)

            self.draw_export_progress_bar()
            self.draw_temporary_message()

            pygame.display.flip()

            if self.export_requested: self.export_tileset_image(); self.export_requested = False

        self.save_settings_to_ini(); pygame.quit()

if __name__ == "__main__":
    app = TileScope()
    app.run()

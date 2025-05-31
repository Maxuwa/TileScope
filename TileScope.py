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

# --- Helper function to find theme file ---
def get_theme_file_path(filename="theme.json"):
    """
    Determines the path to the theme file.
    Priority:
    1. External file next to the executable (or script in dev mode).
    2. Bundled file (if running as a PyInstaller app).
    3. File in the current working directory (fallback for dev mode if not next to script).
    Returns the path to the theme file, or None if not found.
    """
    # Check for external file next to the executable or script
    if getattr(sys, 'frozen', False):  # Running as a bundled app (e.g., PyInstaller)
        application_path = os.path.dirname(sys.executable)
    else:  # Running as a script
        try:
            application_path = os.path.dirname(os.path.abspath(__file__))
        except NameError: # __file__ is not defined (e.g. in interactive interpreter)
            application_path = os.path.abspath(".")

    external_theme_path = os.path.join(application_path, filename)
    if os.path.exists(external_theme_path):
        print(f"INFO: Using external theme: {external_theme_path}")
        return external_theme_path

    # If not found externally, try to find the bundled version (PyInstaller)
    try:
        base_path = sys._MEIPASS # PyInstaller creates a temp folder and stores path in _MEIPASS
        bundled_theme_path = os.path.join(base_path, filename)
        if os.path.exists(bundled_theme_path):
            print(f"INFO: Using bundled theme: {bundled_theme_path}")
            return bundled_theme_path
    except Exception:
        # _MEIPASS not defined, not running bundled or error accessing it
        pass

    # Fallback for development if still not found (e.g. if script is run from a different CWD)
    dev_cwd_path = os.path.join(os.path.abspath("."), filename)
    if os.path.exists(dev_cwd_path) and dev_cwd_path != external_theme_path: # Avoid re-checking same path
        print(f"INFO: Using theme from CWD (dev fallback): {dev_cwd_path}")
        return dev_cwd_path

    print(f"WARNING: Theme file '{filename}' not found. Pygame_GUI will use its default theme.")
    return None
# --- End Helper function ---

# --- Configuration ---
TILESET_WIDTH = 2048
TILESET_HEIGHT = 512
TILE_SIZE = 16
COLS = TILESET_WIDTH // TILE_SIZE
ROWS = TILESET_HEIGHT // TILE_SIZE
TOTAL_TILES = COLS * ROWS
CONFIG_FILE_NAME = "tilescope_config.ini"
MAX_SURFACE_DIM = 8192
GUIDE_FILE_NAME = "CONFIGURATION_GUIDE.md" # For user reference

# Determine the theme file path using the new function
ACTUAL_THEME_FILE_PATH = get_theme_file_path("theme.json")

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
        "theme_file_name": "theme.json    ; Name of the UI theme file (user can place this next to exe to override bundled theme)"
    }
}
# --- End Configuration ---

class TileScope:
    def __init__(self, input_path=None):
        pygame.init()
        pygame.display.set_caption("TileScope")

        self.screen_width = 1000
        self.screen_height = 700
        self.screen = pygame.display.set_mode((self.screen_width, self.screen_height), pygame.RESIZABLE)

        self.settings_raw = {} # Will hold raw string values from INI
        self.load_settings_from_ini()

        # Initialize UIManager with the dynamically found theme path.
        # If ACTUAL_THEME_FILE_PATH is None, UIManager uses its default theme.
        self.ui_manager = pygame_gui.UIManager((self.screen_width, self.screen_height), theme_path=ACTUAL_THEME_FILE_PATH)

        # The UIManager constructor handles theme loading if theme_path is provided.
        # If a theme was specified but failed to load, a warning would have been printed by get_theme_file_path
        # or by Pygame GUI itself.

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

        str_val = str_val.split(';')[0].strip() # Remove comments
        str_val = str_val.split('#')[0].strip() # Remove comments

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
        self.settings_raw = {} # Holds raw string values from INI

        # Prepare a ConfigParser object with all default structure and values
        config_to_write = configparser.ConfigParser(inline_comment_prefixes=(';', '#'), allow_no_value=True)
        for section_name, section_options in DEFAULT_INI_STRUCTURE.items():
            if not config_to_write.has_section(section_name):
                config_to_write.add_section(section_name)
            for key, full_default_value in section_options.items():
                config_to_write.set(section_name, key, full_default_value)

        file_existed = os.path.exists(CONFIG_FILE_NAME)
        if file_existed:
            # If file exists, read it and update our config_to_write with values from the file
            config_from_file = configparser.ConfigParser(inline_comment_prefixes=(';', '#'), allow_no_value=True)
            try:
                if config_from_file.read(CONFIG_FILE_NAME):
                    for section in config_from_file.sections():
                        if section in DEFAULT_INI_STRUCTURE: # Only process sections we know
                            for key, value_from_file in config_from_file.items(section):
                                if key in DEFAULT_INI_STRUCTURE[section]: # Only process keys we know
                                    # Preserve user's value if it's not just a structural comment
                                    default_value_in_structure = DEFAULT_INI_STRUCTURE[section][key]
                                    is_default_structural = default_value_in_structure.strip().startswith(';') or \
                                                       default_value_in_structure.strip().startswith('#') or \
                                                       default_value_in_structure.strip() == ""
                                    if not is_default_structural or value_from_file.strip():
                                        config_to_write.set(section, key, value_from_file)
            except configparser.Error as e:
                print(f"Warning: Error parsing config file '{CONFIG_FILE_NAME}': {e}. Defaults may be re-applied.")

        # Write the (potentially updated) config back to the file.
        # This ensures new options are added and comments are preserved/updated.
        try:
            with open(CONFIG_FILE_NAME, 'w') as configfile:
                config_to_write.write(configfile)
            if not file_existed:
                print(f"Info: Created new config file '{CONFIG_FILE_NAME}' with defaults.")
        except IOError:
            print(f"Error: Could not write config file to '{CONFIG_FILE_NAME}'. Using defaults.")

        # Now, read the INI file for runtime use into self.settings_raw
        runtime_config = configparser.ConfigParser(inline_comment_prefixes=(';', '#'), allow_no_value=True)
        if runtime_config.read(CONFIG_FILE_NAME):
            for section_default, options_default in DEFAULT_INI_STRUCTURE.items():
                self.settings_raw[section_default] = {}
                for key_default, default_val_str in options_default.items():
                    if runtime_config.has_option(section_default, key_default):
                        self.settings_raw[section_default][key_default] = runtime_config.get(section_default, key_default)
                    else:
                        # This case should be rare if writing logic above is correct, but good for robustness
                        self.settings_raw[section_default][key_default] = default_val_str
        else:
            # Fallback if reading fails (e.g., permissions issue after write)
            print(f"Warning: Could not read '{CONFIG_FILE_NAME}' for runtime. Using hardcoded defaults for self.settings_raw.")
            for section_default, options_default in DEFAULT_INI_STRUCTURE.items():
                self.settings_raw[section_default] = dict(options_default) # Use a copy

        # Initialize toggle states from loaded settings
        self.show_grid = self._get_setting("Toggles", "show_grid_default", bool, True)
        self.show_numbers = self._get_setting("Toggles", "show_numbers_default", bool, True)
        self.show_background_overlay = self._get_setting("Toggles", "show_background_overlay_default", bool, True)

        # If UI Manager exists, ensure overlays are updated based on new settings
        if hasattr(self, 'ui_manager'):
            self._update_base_overlay_surfaces()


    def save_settings_to_ini(self):
        config = configparser.ConfigParser(inline_comment_prefixes=(';', '#'), allow_no_value=True)

        for section, options in DEFAULT_INI_STRUCTURE.items():
            if not config.has_section(section):
                config.add_section(section)
            for key, default_str_val_with_comment in options.items():
                # Get the current raw string value to write, falling back to default if not set
                current_val_to_write = self.settings_raw.get(section, {}).get(key, default_str_val_with_comment)

                # Special handling for toggle defaults to reflect current state
                if section == "Toggles":
                    original_comment_part = ""
                    comment_marker = " ; " # Assuming space-semicolon-space for comments
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
        font_aa_export = True # Always use AA for export for quality

        try:
            self.tile_number_reference_font = pygame.font.SysFont(font_name, ref_size)
        except pygame.error:
            print(f"Warning: Font '{font_name}' (ref size {ref_size}) not found. Using default Arial.")
            self.tile_number_reference_font = pygame.font.SysFont("Arial", ref_size)

        text_color_numbers = self._get_setting("TextColors", "tile_number_text", tuple, (220,220,220))
        self.pre_rendered_tile_numbers.clear()
        for i in range(100): # Pre-render 00-99 for tile ID display
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

        self.cached_actual_zoom_for_overlays = -1.0 # Force recache of scaled overlays

    def setup_ui_elements(self):
        panel_height = 85
        self.ui_panel_rect = pygame.Rect(0, self.screen_height - panel_height,
                                         self.screen_width, panel_height)

        if self.ui_panel and self.ui_panel.alive():
            self.ui_panel.kill()
        self.ui_panel = None
        self.buttons = {}

        btn_w, btn_h = 130, 30
        spacing = 10
        panel_internal_padding_x = 15
        panel_internal_padding_y = 10
        row1_y_rel = panel_internal_padding_y
        row2_y_rel = panel_internal_padding_y + btn_h + panel_internal_padding_y // 2

        try:
            self.ui_panel = pygame_gui.elements.UIPanel(
                relative_rect=self.ui_panel_rect,
                starting_height=1, # Pygame GUI UIPanel convention
                manager=self.ui_manager,
                object_id="#ui_panel"
            )
        except Exception as e:
            print(f"Error creating UIPanel: {e}")
            self.ui_panel = None # Ensure it's None if creation fails
            return # Cannot proceed to create buttons if panel failed

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
        
            if self.show_ui_panel_flag:
                self.ui_panel.show()
            else:
                self.ui_panel.hide()

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
            if input_path: # Only show "not found" if a path was actually given
                self.show_temp_message(f"File not found: {os.path.basename(input_path)}", "error")
            self.create_placeholder_gradient(surface)
        return surface

    def create_placeholder_gradient(self, surface):
        # Simple gradient for placeholder
        for y in range(TILESET_HEIGHT):
            color_val = int(200 + 55 * y / TILESET_HEIGHT) # Light gray gradient
            pygame.draw.line(surface, (color_val, color_val, color_val), (0, y), (TILESET_WIDTH, y))

    def update_scaled_tileset_and_overlays(self):
        # Calculate conceptual dimensions based on zoom
        conceptual_w = TILESET_WIDTH * self.zoom
        conceptual_h = TILESET_HEIGHT * self.zoom
        current_aspect_ratio = TILESET_WIDTH / TILESET_HEIGHT if TILESET_HEIGHT > 0 else 1.0

        # Clamp scaled dimensions to Pygame's max surface dimension
        if conceptual_w > MAX_SURFACE_DIM:
            final_scaled_w = MAX_SURFACE_DIM
            final_scaled_h = MAX_SURFACE_DIM / current_aspect_ratio if current_aspect_ratio > 0 else MAX_SURFACE_DIM
        elif conceptual_h > MAX_SURFACE_DIM:
            final_scaled_h = MAX_SURFACE_DIM
            final_scaled_w = MAX_SURFACE_DIM * current_aspect_ratio
        else:
            final_scaled_w = conceptual_w
            final_scaled_h = conceptual_h

        final_scaled_w = max(1, int(final_scaled_w)) # Ensure at least 1x1
        final_scaled_h = max(1, int(final_scaled_h))

        if self.base_tileset_image.get_width() > 0 and self.base_tileset_image.get_height() > 0:
            self.scaled_tileset_image = pygame.transform.scale(self.base_tileset_image, (final_scaled_w, final_scaled_h))
        else: # Handle case where base image might be invalid
            self.scaled_tileset_image = pygame.Surface((final_scaled_w, final_scaled_h))
            self.scaled_tileset_image.fill(self._get_setting("DisplayColors", "background", tuple, (25,30,40)))

        # Calculate the actual zoom applied after clamping
        self.actual_applied_zoom = final_scaled_w / TILESET_WIDTH if TILESET_WIDTH > 0 else 1.0
        if TILESET_HEIGHT > 0 and abs(final_scaled_h / TILESET_HEIGHT - self.actual_applied_zoom) > 1e-5 : # Check consistency
            self.actual_applied_zoom = final_scaled_h / TILESET_HEIGHT # Prioritize height if aspect ratio was forced by MAX_SURFACE_DIM

        # Update tileset area overlay (for background dimming)
        if self.scaled_tileset_image:
            overlay_w = self.scaled_tileset_image.get_width()
            overlay_h = self.scaled_tileset_image.get_height()
            if overlay_w > 0 and overlay_h > 0:
                self.tileset_area_overlay_surface = pygame.Surface((overlay_w, overlay_h), pygame.SRCALPHA)
                self.tileset_area_overlay_surface.fill(self._get_setting("DisplayColors", "overlay_color", tuple, (0,0,0,70)))
            else: self.tileset_area_overlay_surface = None
        else: self.tileset_area_overlay_surface = None

        # Cache scaled hover/select surfaces if zoom changed significantly
        current_on_screen_tile_size = round(TILE_SIZE * self.actual_applied_zoom)
        if abs(self.actual_applied_zoom - self.cached_actual_zoom_for_overlays) > 1e-6: # If zoom changed
            if current_on_screen_tile_size < 1: # If tiles are too small, use a tiny transparent surface
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

        # Center if image is smaller than view
        if conceptual_scaled_width < self.screen_width:
            self.offset_x = (self.screen_width - conceptual_scaled_width) / 2.0
        else: # Clamp to edges if larger
            self.offset_x = min(0.0, max(self.offset_x, self.screen_width - conceptual_scaled_width))

        if conceptual_scaled_height < view_height:
            self.offset_y = (view_height - conceptual_scaled_height) / 2.0
        else:
            self.offset_y = min(0.0, max(self.offset_y, view_height - conceptual_scaled_height))

    def _adjust_zoom_internal(self, factor, zoom_center_x, zoom_center_y):
        old_conceptual_zoom = self.zoom
        new_conceptual_zoom = self.zoom * factor
        new_conceptual_zoom = max(self.min_zoom, min(new_conceptual_zoom, self.max_zoom)) # Clamp zoom

        if abs(new_conceptual_zoom - old_conceptual_zoom) < 1e-6: return # No significant change

        # Adjust offset to keep zoom_center_x/y stationary on screen
        self.offset_x = zoom_center_x - (zoom_center_x - self.offset_x) * (new_conceptual_zoom / old_conceptual_zoom)
        self.offset_y = zoom_center_y - (zoom_center_y - self.offset_y) * (new_conceptual_zoom / old_conceptual_zoom)
        self.zoom = new_conceptual_zoom

        self.update_scaled_tileset_and_overlays()
        self.clamp_offset()

    def adjust_zoom_at_mouse(self, factor):
        mouse_x, mouse_y = pygame.mouse.get_pos()
        panel_height = self.ui_panel_rect.height if self.show_ui_panel_flag and self.ui_panel and self.ui_panel.alive() else 0
        # Only zoom if mouse is over the tileset area (not the UI panel)
        if mouse_y < self.screen_height - panel_height :
            self._adjust_zoom_internal(factor, float(mouse_x), float(mouse_y))

    def adjust_zoom_at_center(self, factor):
        panel_height = self.ui_panel_rect.height if self.show_ui_panel_flag and self.ui_panel and self.ui_panel.alive() else 0
        view_center_x = self.screen_width / 2.0
        view_center_y = (self.screen_height - panel_height) / 2.0
        self._adjust_zoom_internal(factor, view_center_x, view_center_y)

    def toggle_grid(self):
        self.show_grid = not self.show_grid
        button = self.buttons.get("grid")
        if button:
            if self.show_grid: button.select()
            else: button.unselect()
        # Update raw setting for saving
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
        button = self.buttons.get("bg_overlay")
        if button:
            if self.show_background_overlay: button.select()
            else: button.unselect()
        self.settings_raw.setdefault("Toggles", {})["show_background_overlay_default"] = "true" if self.show_background_overlay else "false"

    def toggle_ui_panel_visibility(self):
        self.show_ui_panel_flag = not self.show_ui_panel_flag
        hide_ui_button = self.buttons.get("hide_ui")
        if self.ui_panel and self.ui_panel.alive(): # Check if panel exists
            if self.show_ui_panel_flag:
                self.ui_panel.show()
                if hide_ui_button: hide_ui_button.set_text("Hide UI (F1)")
            else:
                self.ui_panel.hide()
                if hide_ui_button: hide_ui_button.set_text("Show UI (F1)")
        self.clamp_offset() # Recalculate viewable area and clamp offset

    def request_export(self):
        self.export_requested = True

    def compute_tile_id(self, col, row):
        # Custom tile ID computation logic
        return (col % 16) + (col // 16) * 512 + row * 16

    def get_tile_from_id(self, tile_id):
        if not (0 <= tile_id < TOTAL_TILES): return None
        # This could be optimized if performance becomes an issue for large tilesets
        for r_idx in range(ROWS):
            for c_idx in range(COLS):
                if self.compute_tile_id(c_idx, r_idx) == tile_id:
                    return c_idx, r_idx
        return None

    def export_tileset_image(self):
        self.show_export_progress = True
        self.export_progress = 0
        pygame.display.flip() # Show initial progress bar state

        root = tk.Tk(); root.withdraw() # Hide main Tkinter window

        default_path_str = self._get_setting("Export", "default_path", str, ".")
        if default_path_str == ".": default_path_str = os.getcwd()

        file_ext = self._get_setting("Export", "default_format", str, "png").lower()
        if file_ext not in ["png", "jpg", "jpeg", "bmp"]: file_ext = "png" # Ensure valid default

        file_path = filedialog.asksaveasfilename(
            initialdir=default_path_str,
            initialfile=f"tileset_export.{file_ext}",
            defaultextension=f".{file_ext}",
            filetypes=[("PNG files", "*.png"), ("JPEG files", "*.jpg;*.jpeg"), ("BMP files", "*.bmp")]
        )
        if not file_path: # User cancelled
            self.show_export_progress = False
            return

        # Update default path and format for next time
        self.settings_raw.setdefault("Export", {})["default_path"] = os.path.dirname(file_path)
        self.settings_raw.setdefault("Export", {})["default_format"] = os.path.splitext(file_path)[1].lstrip('.').lower() or "png"

        export_surf = pygame.Surface((TILESET_WIDTH, TILESET_HEIGHT))
        export_surf.blit(self.base_tileset_image, (0, 0))

        # Apply visual overlays if they are enabled
        if self.show_background_overlay:
            export_overlay_tile_surf = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
            export_overlay_tile_surf.fill(self._get_setting("DisplayColors", "overlay_color", tuple, (0,0,0,70)))
            for r_idx in range(ROWS):
                for c_idx in range(COLS):
                    export_surf.blit(export_overlay_tile_surf, (c_idx * TILE_SIZE, r_idx * TILE_SIZE))

        if self.show_grid:
            grid_color = self._get_setting("DisplayColors", "grid_color", tuple, (60,70,90))
            for x_coord in range(0, TILESET_WIDTH + 1, TILE_SIZE):
                pygame.draw.line(export_surf, grid_color, (x_coord, 0), (x_coord, TILESET_HEIGHT), 1)
            for y_coord in range(0, TILESET_HEIGHT + 1, TILE_SIZE):
                pygame.draw.line(export_surf, grid_color, (0, y_coord), (TILESET_WIDTH, y_coord), 1)

        if self.show_numbers:
            total_export_tiles = COLS * ROWS
            processed_tiles = 0
            for r_idx in range(ROWS):
                for c_idx in range(COLS):
                    tile_id_val = self.compute_tile_id(c_idx, r_idx)
                    label_str = f"{tile_id_val % 100:02d}" # Display last two digits of ID
                    number_surf = self.pre_rendered_tile_numbers.get(label_str)
                    if number_surf:
                        tx = c_idx * TILE_SIZE + (TILE_SIZE - number_surf.get_width()) // 2
                        ty = r_idx * TILE_SIZE + (TILE_SIZE - number_surf.get_height()) // 2
                        export_surf.blit(number_surf, (tx, ty))

                    processed_tiles +=1
                    if processed_tiles % 100 == 0: # Update progress bar periodically
                        self.export_progress = processed_tiles / total_export_tiles
                        self.draw_export_progress_bar() # Draw directly to screen
                        pygame.display.flip()
                        for evt in pygame.event.get(): # Keep UI responsive
                             if evt.type == pygame.QUIT:
                                 self.show_export_progress = False
                                 return # Abort export if user quits
        try:
            pygame.image.save(export_surf, file_path)
            self.show_temp_message(f"Exported to {os.path.basename(file_path)}", "success")
        except pygame.error as e:
            self.show_temp_message(f"Error saving: {e}", "error")
            print(f"Export error: {e}")
        finally:
            self.show_export_progress = False

    def reset_view(self):
        self.zoom = 1.0
        self.update_scaled_tileset_and_overlays() # Update scaling first
        # Then calculate offset based on new scaled size
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
            self.settings_raw.setdefault("Export", {})["default_path"] = os.path.dirname(file_path) # Update default path
            self.reset_view() # Reset zoom and pan

    def activate_search_dialog(self):
        root = tk.Tk(); root.withdraw()
        tile_id_str = simpledialog.askstring("Search Tile", "Enter Tile ID (0-4095):", parent=root)
        if tile_id_str:
            try:
                tile_id = int(tile_id_str)
                if self.center_on_tile_id(tile_id):
                    self.show_temp_message(f"Found Tile ID: {tile_id}", "info")
                else:
                    self.show_temp_message(f"Tile ID {tile_id} not found or invalid.", "error")
            except ValueError:
                self.show_temp_message("Invalid Tile ID format.", "error")

    def center_on_tile_id(self, tile_id):
        coords = self.get_tile_from_id(tile_id)
        if coords:
            col, row = coords
            self.selected_tiles = {(col, row)} # Select the found tile

            if self.zoom < 2.0: self.zoom = 2.0 # Zoom in if not already zoomed
            self.update_scaled_tileset_and_overlays()

            # Calculate offset to center this tile
            tile_center_x_on_image = (col + 0.5) * TILE_SIZE * self.actual_applied_zoom
            tile_center_y_on_image = (row + 0.5) * TILE_SIZE * self.actual_applied_zoom

            panel_height = self.ui_panel_rect.height if self.show_ui_panel_flag and self.ui_panel and self.ui_panel.alive() else 0
            view_center_x_screen = self.screen_width / 2.0
            view_center_y_screen = (self.screen_height - panel_height) / 2.0

            self.offset_x = view_center_x_screen - tile_center_x_on_image
            self.offset_y = view_center_y_screen - tile_center_y_on_image

            self.clamp_offset()
            return True
        return False

    def copy_selected_ids_to_clipboard(self):
        if not self.selected_tiles:
            self.show_temp_message("No tiles selected.", "info")
            return
        ids_str = ", ".join(sorted([str(self.compute_tile_id(c, r)) for c, r in self.selected_tiles]))
        try:
            root = tk.Tk(); root.withdraw()
            root.clipboard_clear()
            root.clipboard_append(ids_str)
            root.update() # Process clipboard events
            root.destroy()
            self.show_temp_message(f"{len(self.selected_tiles)} ID(s) copied: {ids_str[:50]}...", "success")
        except Exception as e:
            self.show_temp_message(f"Error copying to clipboard: {e}", "error")
            print(f"Clipboard error: {e}")


    def show_temp_message(self, message, level="info"):
        self.temp_message = {"text": message, "level": level, "time": pygame.time.get_ticks()}

    def _open_file_location(self, file_path_to_open): # Currently unused by active UI, but kept for potential future use
        directory = os.path.dirname(os.path.abspath(file_path_to_open))
        if not os.path.exists(directory): # Fallback if path is relative or doesn't exist
            directory = os.path.abspath(os.path.dirname(sys.argv[0])) # App's directory

        try:
            if sys.platform == "win32":
                os.startfile(directory)
            elif sys.platform == "darwin": # macOS
                subprocess.Popen(["open", directory])
            else: # Linux and other POSIX
                subprocess.Popen(["xdg-open", directory])
            self.show_temp_message(f"Opened folder: {directory}", "info")
        except Exception as e:
            self.show_temp_message(f"Error opening folder: {e}", "error")
            print(f"Error opening folder {directory}: {e}")

    def get_visible_tile_range(self):
        panel_height = self.ui_panel_rect.height if self.show_ui_panel_flag and self.ui_panel and self.ui_panel.alive() else 0
        safe_actual_zoom = self.actual_applied_zoom if self.actual_applied_zoom > 1e-6 else 1.0 # Avoid division by zero

        # Calculate visible portion of the base (unscaled) image
        base_img_x_start = -self.offset_x / safe_actual_zoom
        base_img_y_start = -self.offset_y / safe_actual_zoom
        base_img_view_width = self.screen_width / safe_actual_zoom
        base_img_view_height = (self.screen_height - panel_height) / safe_actual_zoom
        base_img_x_end = base_img_x_start + base_img_view_width
        base_img_y_end = base_img_y_start + base_img_view_height

        # Determine column and row range, with a small buffer for partial tiles
        start_col = max(0, int(base_img_x_start // TILE_SIZE))
        end_col = min(COLS, int(base_img_x_end // TILE_SIZE) + 2) # +2 for buffer
        start_row = max(0, int(base_img_y_start // TILE_SIZE))
        end_row = min(ROWS, int(base_img_y_end // TILE_SIZE) + 2) # +2 for buffer
        return start_col, end_col, start_row, end_row

    def handle_events(self, time_delta):
        for event in pygame.event.get():
            # Pass event to Pygame GUI manager first
            ui_consumed_event = self.ui_manager.process_events(event)

            if event.type == pygame.QUIT:
                self.save_settings_to_ini() # Save settings on quit
                return False # Signal to exit main loop

            elif event.type == pygame.VIDEORESIZE:
                self.screen_width = max(600, event.w) # Enforce minimum size
                self.screen_height = max(400, event.h)
                self.screen = pygame.display.set_mode((self.screen_width, self.screen_height), pygame.RESIZABLE)
                self.ui_manager.set_window_resolution((self.screen_width, self.screen_height))
                self.setup_ui_elements() # Recreate UI for new size
                self.clamp_offset()
                self.update_scaled_tileset_and_overlays()

            elif event.type == pygame_gui.UI_BUTTON_PRESSED:
                action_to_perform = None
                for row_key in self.button_configs: # Check both rows of buttons
                    for key, _, action_func, _ in self.button_configs[row_key]:
                        button_instance = self.buttons.get(key)
                        if button_instance == event.ui_element:
                            action_to_perform = action_func
                            break
                    if action_to_perform: break
                if action_to_perform:
                    action_to_perform()
                ui_consumed_event = True # Ensure GUI button presses don't trigger other actions

            if not ui_consumed_event: # Process events not handled by the UI
                if event.type == pygame.MOUSEBUTTONDOWN:
                    panel_height = self.ui_panel_rect.height if self.show_ui_panel_flag and self.ui_panel and self.ui_panel.alive() else 0
                    # Check if click is outside the UI panel area
                    if event.pos[1] < self.screen_height - panel_height:
                        if event.button == 1: # Left click
                            self.dragging = True
                            self.last_mouse_pos = event.pos
                            if self.hover_col is not None and self.hover_row is not None:
                                tile_coords = (self.hover_col, self.hover_row)
                                mods = pygame.key.get_mods()
                                if mods & pygame.KMOD_SHIFT or mods & pygame.KMOD_CTRL: # Add/remove from selection
                                    if tile_coords in self.selected_tiles:
                                        self.selected_tiles.remove(tile_coords)
                                    else:
                                        self.selected_tiles.add(tile_coords)
                                else: # New selection
                                    self.selected_tiles = {tile_coords}
                        elif event.button == 4: # Mouse wheel up
                            self.adjust_zoom_at_mouse(1.1)
                        elif event.button == 5: # Mouse wheel down
                            self.adjust_zoom_at_mouse(0.9)

                elif event.type == pygame.MOUSEBUTTONUP:
                    if event.button == 1: # Left click
                        self.dragging = False

            # Mouse motion is processed regardless of UI consumption for hover effects,
            # but dragging only if not consumed and button is down.
            if event.type == pygame.MOUSEMOTION:
                if self.dragging: # Dragging is already conditional on not being UI consumed
                    dx = event.pos[0] - self.last_mouse_pos[0]
                    dy = event.pos[1] - self.last_mouse_pos[1]
                    self.offset_x += dx
                    self.offset_y += dy
                    self.last_mouse_pos = event.pos
                    self.clamp_offset()

                # Update hover tile regardless of dragging or UI consumption
                panel_height = self.ui_panel_rect.height if self.show_ui_panel_flag and self.ui_panel and self.ui_panel.alive() else 0
                if event.pos[1] < self.screen_height - panel_height: # Mouse is over tileset area
                    safe_actual_zoom = self.actual_applied_zoom if self.actual_applied_zoom > 1e-6 else 1.0
                    img_x = (event.pos[0] - self.offset_x) / safe_actual_zoom
                    img_y = (event.pos[1] - self.offset_y) / safe_actual_zoom
                    if 0 <= img_x < TILESET_WIDTH and 0 <= img_y < TILESET_HEIGHT:
                        self.hover_col = int(img_x // TILE_SIZE)
                        self.hover_row = int(img_y // TILE_SIZE)
                    else:
                        self.hover_col = None; self.hover_row = None
                else: # Mouse is over UI panel or outside window
                    self.hover_col = None; self.hover_row = None

            if event.type == pygame.KEYDOWN: # Keyboard shortcuts
                if event.key == pygame.K_F1:
                    self.toggle_ui_panel_visibility()
                elif event.key == pygame.K_r:
                    self.reset_view()
                elif event.key == pygame.K_PLUS or event.key == pygame.K_EQUALS: # Numpad plus or regular plus
                    self.adjust_zoom_at_center(1.2)
                elif event.key == pygame.K_MINUS or event.key == pygame.K_UNDERSCORE: # Numpad minus or regular minus
                    self.adjust_zoom_at_center(1/1.2)
                elif event.key == pygame.K_g:
                    self.toggle_grid()
                elif event.key == pygame.K_n:
                    self.toggle_numbers()
                elif event.key == pygame.K_c and (pygame.key.get_mods() & pygame.KMOD_CTRL):
                    self.copy_selected_ids_to_clipboard()
                elif event.key == pygame.K_f and (pygame.key.get_mods() & pygame.KMOD_CTRL):
                    self.activate_search_dialog()
        return True # Continue running

    def draw_grid_and_overlays(self):
        start_col, end_col, start_row, end_row = self.get_visible_tile_range()
        on_screen_tile_size = TILE_SIZE * self.actual_applied_zoom
        on_screen_tile_size_px = round(on_screen_tile_size) # Pixel size for drawing

        # Draw Grid
        if self.show_grid and on_screen_tile_size_px > 1: # Only draw if visible and tiles are large enough
            grid_color = self._get_setting("DisplayColors", "grid_color", tuple, (60,70,90))
            panel_h = self.ui_panel_rect.height if self.show_ui_panel_flag and self.ui_panel and self.ui_panel.alive() else 0
            view_bottom_y = self.screen_height - panel_h

            for c_idx in range(start_col, end_col + 1):
                x = round(self.offset_x + c_idx * on_screen_tile_size)
                # Clip lines to visible area
                y_start_on_grid = self.offset_y
                y_end_on_grid = self.offset_y + TILESET_HEIGHT * self.actual_applied_zoom
                draw_y_start = round(max(y_start_on_grid, 0))
                draw_y_end = round(min(y_end_on_grid, view_bottom_y))
                if draw_y_start < draw_y_end and -1 <= x <= self.screen_width + 1 : # Check if line is on screen
                    pygame.draw.line(self.screen, grid_color, (x, draw_y_start), (x, draw_y_end), 1)

            for r_idx in range(start_row, end_row + 1):
                y = round(self.offset_y + r_idx * on_screen_tile_size)
                x_start_on_grid = self.offset_x
                x_end_on_grid = self.offset_x + TILESET_WIDTH * self.actual_applied_zoom
                draw_x_start = round(max(x_start_on_grid, 0))
                draw_x_end = round(min(x_end_on_grid, self.screen_width))
                if draw_x_start < draw_x_end and -1 <= y <= view_bottom_y + 1:
                    pygame.draw.line(self.screen, grid_color, (draw_x_start, y), (draw_x_end, y), 1)

        # Draw Tile Numbers
        if self.show_numbers and on_screen_tile_size_px >= 4 : # Only draw if visible and enough space
            base_font_calc_size = int(self._get_setting("FontSettings", "tile_number_reference_font_size", int, 10) * self.zoom)
            target_num_font_size = max(4, min(base_font_calc_size, 40)) # Clamp font size

            if target_num_font_size >= 4: # Ensure font is reasonably sized
                font_name = self._get_setting("FontSettings", "tile_number_font_name", str, "Arial")
                text_color = self._get_setting("TextColors", "tile_number_text", tuple, (220,220,220))
                font_aa = self._get_setting("FontSettings", "tile_number_font_aa", bool, True)

                font_cache_key = (font_name, target_num_font_size, font_aa)
                current_font = self.cached_fonts.get(font_cache_key)
                if not current_font:
                    try: current_font = pygame.font.SysFont(font_name, target_num_font_size)
                    except pygame.error: current_font = pygame.font.SysFont("Arial", target_num_font_size) # Fallback
                    self.cached_fonts[font_cache_key] = current_font

                for r_idx in range(start_row, end_row):
                    for c_idx in range(start_col, end_col):
                        if not (0 <= c_idx < COLS and 0 <= r_idx < ROWS): continue # Bounds check
                        tile_id_val = self.compute_tile_id(c_idx, r_idx)
                        label_str = f"{tile_id_val % 100:02d}" # Last two digits

                        num_surf_cache_key = (label_str, font_name, target_num_font_size, font_aa) # Cache key for rendered number
                        final_number_surf = self.cached_rendered_numbers.get(num_surf_cache_key)
                        if not final_number_surf:
                            final_number_surf = current_font.render(label_str, font_aa, text_color)
                            self.cached_rendered_numbers[num_surf_cache_key] = final_number_surf

                        # Center number in tile
                        scr_x_center = self.offset_x + (c_idx + 0.5) * on_screen_tile_size
                        scr_y_center = self.offset_y + (r_idx + 0.5) * on_screen_tile_size
                        num_rect = final_number_surf.get_rect(center=(round(scr_x_center), round(scr_y_center)))
                        self.screen.blit(final_number_surf, num_rect)

        # Draw Selected Tile Highlights
        if self.selected_tiles and self.cached_scaled_select_surface and on_screen_tile_size_px >= 1:
            for col, row in self.selected_tiles:
                if start_col <= col < end_col and start_row <= row < end_row: # Only draw if visible
                    if 0 <= col < COLS and 0 <= row < ROWS: # Bounds check
                        scr_x = round(self.offset_x + col * on_screen_tile_size)
                        scr_y = round(self.offset_y + row * on_screen_tile_size)
                        self.screen.blit(self.cached_scaled_select_surface, (scr_x, scr_y))

        # Draw Hovered Tile Highlight
        if self.hover_col is not None and self.hover_row is not None and \
           self.cached_scaled_hover_surface and on_screen_tile_size_px >= 1:
             scr_x = round(self.offset_x + self.hover_col * on_screen_tile_size)
             scr_y = round(self.offset_y + self.hover_row * on_screen_tile_size)
             self.screen.blit(self.cached_scaled_hover_surface, (scr_x, scr_y))

    def draw_tooltip(self):
        if self.hover_col is None or self.hover_row is None: return

        tile_id_val = self.compute_tile_id(self.hover_col, self.hover_row)
        id_text_str = f"ID: {tile_id_val}"
        pos_text_str = f"Pos: ({self.hover_col}, {self.hover_row})"

        text_color = self._get_setting("TextColors", "tooltip_text", tuple, (230,230,230))
        id_surf = self.ui_font.render(id_text_str, True, text_color)
        pos_surf = self.ui_font.render(pos_text_str, True, text_color)

        padding = 8
        tooltip_w = max(id_surf.get_width(), pos_surf.get_width()) + 2 * padding
        tooltip_h = id_surf.get_height() + pos_surf.get_height() + 3 * padding # Extra padding for line spacing

        mx, my = pygame.mouse.get_pos()
        tt_x = mx + 15 # Offset from mouse
        tt_y = my - tooltip_h - 5 # Position above mouse, or below if no space

        # Keep tooltip on screen
        tt_x = max(5, min(tt_x, self.screen_width - tooltip_w - 5))
        panel_h = self.ui_panel_rect.height if self.show_ui_panel_flag and self.ui_panel and self.ui_panel.alive() else 0
        if tt_y < 5 : tt_y = my + 15 # If too high, move below mouse
        tt_y = max(5, min(tt_y, self.screen_height - panel_h - tooltip_h - 5))


        pygame.draw.rect(self.screen, self._get_setting("TooltipAppearance", "tooltip_background", tuple, (20,20,30,220)),
                         (tt_x, tt_y, tooltip_w, tooltip_h), border_radius=3)
        pygame.draw.rect(self.screen, self._get_setting("TooltipAppearance", "tooltip_border", tuple, (70,130,180)),
                         (tt_x, tt_y, tooltip_w, tooltip_h), 1, border_radius=3) # Border

        self.screen.blit(id_surf, (tt_x + padding, tt_y + padding))
        self.screen.blit(pos_surf, (tt_x + padding, tt_y + padding + id_surf.get_height() + padding // 2))

    def draw_export_progress_bar(self):
        if not self.show_export_progress: return

        bar_w, bar_h = 300, 30
        bar_x = (self.screen_width - bar_w) // 2
        bar_y = (self.screen_height - bar_h) // 2

        # Try to use theme colors, fallback to INI or hardcoded if theme not fully loaded/available
        try:
            progress_bar_bg = pygame.Color(self.ui_manager.get_theme().get_colour('dark_bg', '#ui_panel')) # More specific
            progress_bar_fill = pygame.Color(self.ui_manager.get_theme().get_colour('selected_bg', 'button'))
            progress_text_color = pygame.Color(self.ui_manager.get_theme().get_colour('normal_text'))
            progress_bar_border_from_theme = pygame.Color(self.ui_manager.get_theme().get_colour('normal_border', '#ui_panel'))
        except : # Broad except if theme colors aren't found (e.g., theme not loaded)
            progress_bar_bg = pygame.Color(30,40,50)
            progress_bar_fill = pygame.Color(0,120,215)
            progress_text_color = pygame.Color(220,220,220)
            progress_bar_border_from_theme = self._get_setting("UIAppearance", "progress_bar_border", tuple, (70,100,130))

        pygame.draw.rect(self.screen, progress_bar_bg, (bar_x, bar_y, bar_w, bar_h))
        pygame.draw.rect(self.screen, progress_bar_border_from_theme, (bar_x, bar_y, bar_w, bar_h), 2) # Border
        fill_w = int(bar_w * self.export_progress)
        pygame.draw.rect(self.screen, progress_bar_fill, (bar_x, bar_y, fill_w, bar_h))

        text_str = f"Exporting... {int(self.export_progress * 100)}%"
        text_surf = self.ui_font.render(text_str, True, progress_text_color)
        text_rect = text_surf.get_rect(center=(bar_x + bar_w // 2, bar_y + bar_h // 2))
        self.screen.blit(text_surf, text_rect)

    def draw_temporary_message(self):
        if self.temp_message and (pygame.time.get_ticks() - self.temp_message["time"] < 2500): # Message visible for 2.5s
            msg = self.temp_message["text"]
            level = self.temp_message["level"]
            color_map = {
                "info": (100,180,255), "success": (100,220,100),
                "warning": (255,180,80), "error": (255,100,100)
            }
            text_color = color_map.get(level, (200,200,200)) # Default to light gray

            try: # Try to use theme color for background
                bg_col_str = self.ui_manager.get_theme().get_colour_string('dark_bg', '#ui_panel')
                bg_col_tuple = pygame.Color(bg_col_str)
                msg_bg_color = (bg_col_tuple.r, bg_col_tuple.g, bg_col_tuple.b, 220) # Semi-transparent
            except: # Fallback
                msg_bg_color = (30,40,50,220)

            msg_surf = self.ui_font.render(msg, True, text_color)
            msg_rect = msg_surf.get_rect(center=(self.screen_width // 2, 30)) # Position at top-center
            bg_rect = msg_rect.inflate(20,10) # Padded background

            # Draw background surface for better readability
            bg_surf = pygame.Surface(bg_rect.size, pygame.SRCALPHA)
            bg_surf.fill(msg_bg_color)
            self.screen.blit(bg_surf, bg_rect.topleft)
            self.screen.blit(msg_surf, msg_rect.topleft)
        elif self.temp_message: # Message timed out
            self.temp_message = None

    def draw_main_content(self):
        self.screen.fill(self._get_setting("DisplayColors", "background", tuple, (25,30,40)))

        if self.scaled_tileset_image:
            self.screen.blit(self.scaled_tileset_image, (round(self.offset_x), round(self.offset_y)))

        if self.show_background_overlay and self.tileset_area_overlay_surface:
            self.screen.blit(self.tileset_area_overlay_surface, (round(self.offset_x), round(self.offset_y)))

        self.draw_grid_and_overlays() # Grid, numbers, selection highlights
        if self.hover_col is not None and self.hover_row is not None: # Only draw tooltip if hovering over a valid tile
            panel_height = self.ui_panel_rect.height if self.show_ui_panel_flag and self.ui_panel and self.ui_panel.alive() else 0
            mx, my = pygame.mouse.get_pos()
            if my < self.screen_height - panel_height: # Don't draw tooltip if mouse is over UI panel
                self.draw_tooltip()


    def run(self):
        running = True
        while running:
            time_delta = self.clock.tick(60)/1000.0 # Cap at 60 FPS, get time delta

            running = self.handle_events(time_delta) # Process inputs
            if not running: break # Exit if handle_events signals quit

            self.ui_manager.update(time_delta) # Update UI elements

            self.draw_main_content() # Draw tileset, grid, overlays

            if self.show_ui_panel_flag:
                if self.ui_panel and self.ui_panel.alive(): # Ensure panel exists before drawing
                    self.ui_manager.draw_ui(self.screen) # Draw UI on top

            self.draw_export_progress_bar() # Draw if exporting
            self.draw_temporary_message()   # Draw if there's a message

            pygame.display.flip() # Update the full display

            if self.export_requested: # Handle export after drawing one frame of progress bar
                self.export_tileset_image()
                self.export_requested = False

        self.save_settings_to_ini() # Save settings on exit
        pygame.quit()

if __name__ == "__main__":
    app = TileScope()
    app.run()
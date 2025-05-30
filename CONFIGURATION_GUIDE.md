# TileScope Configuration Guide

This guide explains how to customize the TileScope application by editing its configuration files.

## 1. Core Settings (`tilescope_config.ini`)

The `tilescope_config.ini` file controls the core appearance and behavior of the application, such as **display colors, text colors, highlight colors, tooltip appearance, font settings for tile numbers, default states for toggles (grid, numbers, overlay), and export preferences.**

**Location:** This file is located in the same directory as the application. If it doesn't exist, TileScope will create it with default values when it first starts. The filename will be `tilescope_config.ini` (or similar, matching what's defined in the application code).

**How to Modify:**
1.  **Open the File:** Open `tilescope_config.ini` in a plain text editor (e.g., Notepad, VS Code, Sublime Text).
2.  **Edit Values:** Find the setting you want to change. Values are to the right of the `=` sign.
    *   **Colors:** Use `(R, G, B)` or `(R, G, B, A)` format. `R, G, B` are Red, Green, Blue values (0-255). `A` is Alpha (transparency, 0-255, where 0 is fully transparent and 255 is fully opaque).
        *Example: `background = (25, 30, 40)`*
    *   **Booleans:** Use `true` or `false`. These are not case-sensitive.
        *Example: `show_grid_default = true`*
    *   **Text/Paths:** For file paths or font names, use standard text.
        *Example: `tile_number_font_name = Arial`*
        *For `default_path` in the `[Export]` section, a single dot `.` means the application's current working directory.*
3.  **Save the File:** After making your changes.
4.  **Restart TileScope:** Close and reopen the application for your changes to take effect.

**Reset to Defaults:** To restore all settings to their original values, you can delete the `tilescope_config.ini` file. TileScope will recreate it with defaults on its next launch.

**Available Settings (Sections in `tilescope_config.ini`):**
*   **[DisplayColors]**: Colors for the main viewing area and grid.
*   **[TextColors]**: Colors for text elements like tile numbers and tooltips.
*   **[HighlightColors]**: Colors for highlighting hovered or selected tiles.
*   **[TooltipAppearance]**: Background and border colors for the tile information tooltip.
*   **[UIAppearance]**: Miscellaneous UI element colors not covered by the theme.
*   **[FontSettings]**: Font name, reference size, and anti-aliasing for tile numbers.
*   **[Toggles]**: Default states for visual aids on startup.
*   **[Export]**: Default image format and save path for exports.
*   **[ThemeFile]**: Specifies the name of the UI theme file.

## 2. UI Theme (`theme.json`)

The `theme.json` file controls the **visual style of the User Interface elements like the bottom button panel, the buttons themselves, and other `pygame_gui` managed elements. This includes their colors in different states (normal, hovered, clicked), fonts used in the UI, border styles, and shadows.**

**Location:** This file is also located in the same directory as the application.

**How to Modify:**
1.  **Open the File:** Open `theme.json` in a plain text editor.
2.  **Edit Values:** The file uses JSON (JavaScript Object Notation) format.
    *   **JSON Syntax Basics:**
        *   Keys (names of settings) and string values **MUST** be enclosed in double quotes (e.g., `"normal_bg": "#3A475B"`).
        *   Colors are often represented as hex strings (e.g., `"#FF0000"` for red).
        *   Items in a list or settings within an object are separated by commas.
        *   **IMPORTANT:** There should be **NO** trailing comma after the *last* item in a list or the *last* setting in an object. This is a common source of errors.
3.  **Save the File:** After making your changes.
4.  **Restart TileScope:** Close and reopen the application for theme changes to take effect.

**What You Can Change:**
*   Colors for UI elements (buttons in normal, hovered, clicked, selected states).
*   Font family and size for text on UI elements.
*   Border thickness and colors, shadow effects.
*   Background color of the main UI panel, and more.

*For detailed theme customization options, you may need to refer to the pygame_gui library documentation, as it powers the UI theming.*

---
If you encounter issues, try deleting `tilescope_config.ini` and/or `theme.json` (if you've modified it heavily and suspect an error) to reset to defaults. TileScope will recreate `tilescope_config.ini`. You would need to restore `theme.json` from a backup or the original distribution if you delete it.
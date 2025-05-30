# TileScope

A Python-based application for visualizing and inspecting tileset images, built with Pygame and Pygame GUI. TileScope helps you examine your tilesets, find tile IDs, and export views with helpful overlays.

## Features

*   Load and display tileset images.
*   Pan and zoom the tileset view.
*   Toggle grid overlay to see individual tile boundaries.
*   Toggle display of tile ID numbers.
*   Hover tooltip showing tile ID and coordinates.
*   Select single or multiple tiles.
*   Copy selected tile IDs to the clipboard.
*   Search for a tile by its ID and center the view on it.
*   Export the tileset with visual aids (grid, numbers) as an image (PNG, JPG, BMP).
*   Hideable UI panel for an unobstructed view.

You can customize TileScope's appearance and behavior by editing two configuration files:

*   **`tilescope_config.ini`**: Controls aspects like display colors (background, grid), text colors, highlight effects, tooltip appearance, font settings for tile numbers, default startup options for visual aids (grid, numbers, overlay), and image export preferences.
*   **`theme.json`**: Defines the visual style of the User Interface elements, such as the appearance of buttons, the bottom control panel, and fonts used within the UI.

Detailed instructions for modifying both files are in **`CONFIGURATION_GUIDE.md`**.


## Usage

*   **Open Image:** Load a tileset image.
*   **Mouse Drag:** Pan the view.
*   **Mouse Wheel / +/- Keys:** Zoom in/out.
*   **R Key:** Reset view.
*   **F1 Key:** Toggle UI panel visibility.
*   **G Key:** Toggle grid.
*   **N Key:** Toggle tile numbers.
*   **Shift/Ctrl + Click Tile:** Add/remove from selection.
*   **Ctrl+C (or Copy IDs button):** Copy selected tile IDs.
*   **Ctrl+F (or Search Tile button):** Search for a tile by ID.
*   Refer to the UI buttons for other actions.


## License

This project is licensed under the [GNU General Public License v3.0](https://www.gnu.org/licenses/gpl-3.0.html).

You are free to use, modify, and distribute this software, provided that any derivative works are also licensed under the same terms. This ensures that the software and any adaptations remain free and open-source.

For full details, see the [LICENSE](./LICENSE) file or visit the [official GPL v3 website](https://www.gnu.org/licenses/gpl-3.0.html).


import importlib.resources
from string import Template

from PySide6.QtGui import QColor, QPalette

from macro_creator.ui import templates


class ThemeManager:
    # Define palettes as Python dictionaries
    DARK_THEME = {
        # --- Core UI ---
        "bg_primary": "#1e1e1e",  # Main window background
        "bg_secondary": "#252526",  # Tables/Input fields
        "text_primary": "#e0e0e0",  # Main text
        "text_light": "#ffffff",  # Bright text (Buttons/Headers)
        "border_color": "#333333",  # Generic borders

        # --- Generic Buttons ---
        "btn_bg": "#3b3b3b",
        "btn_hover": "#454545",
        "btn_press": "#2a2a2a",
        "btn_border": "#555555",
        "btn_border_h": "#666666",  # Hover border

        # -- Generic Stuff ---
        "selection_color": "#394873",
        "selected_color": "#1158c7",
        "selected_hover": "#007FF4",

        # --- Functional Buttons (Start/Stop/Etc) ---
        "btn_start_bg": "#2ea043",  # Green
        "btn_start_border": "#298e3b",
        "btn_start_hover": "#3fb950",

        "btn_stop_bg": "#da3633",  # Red
        "btn_stop_border": "#d82a27",
        "btn_stop_hover": "#f85149",

        "btn_reset_bg": "#1f6feb",  # Blue
        "btn_reset_border": "#1158c7",

        "btn_pick_bg": "#264f78",  # Navy
        "btn_pick_hover": "#3a6ea5",

        # --- Dynamic States (Paused) ---
        "btn_paused_bg": "#d29922",  # Orange
        "btn_paused_border": "#b08800",
        "btn_paused_hover": "#eac54f",

        # --- Progress Bar ---
        "progress_border": "#bbbbbb",
        "progress_chunk": "#4CAF50",  # Green
        "progress_paused": "#FFEB3B",  # Yellow

        # --- Table Widget ---
        "table_grid": "#333333",
        "header_bg": "#333333",
        "header_border": "#1e1e1e",
        "header_text": "#cccccc",

        # --- Console ---
        "alt_bg": "#101010",  # Slightly darker than main bg
        "console_text": "#f0f0f0",
    }

    LIGHT_THEME = {
        # --- Core UI ---
        "bg_primary": "#f3f3f3",  # Light gray window background
        "bg_secondary": "#ffffff",  # Pure white for tables/inputs
        "text_primary": "#333333",  # Dark gray text
        "text_light": "#000000",  # Black text (for buttons)
        "border_color": "#d0d0d0",  # Light borders

        # --- Generic Buttons ---
        "btn_bg": "#ffffff",  # White buttons
        "btn_hover": "#e6e6e6",  # Light gray hover
        "btn_press": "#d0d0d0",
        "btn_border": "#cccccc",
        "btn_border_h": "#a0a0a0",

        # -- Generic Labels ---
        "selection_color": "#cce8ff",
        "selected_color": "#1158c7",
        "selected_hover": "#007FF4",

        # --- Functional Buttons ---
        "btn_start_bg": "#45c458",  # Brighter Green
        "btn_start_border": "#2ea043",
        "btn_start_hover": "#36b04a",

        "btn_stop_bg": "#ff5f59",  # Brighter Red
        "btn_stop_border": "#da3633",
        "btn_stop_hover": "#ff453e",

        "btn_reset_bg": "#4ca1ff",  # Brighter Blue
        "btn_reset_border": "#1f6feb",

        "btn_pick_bg": "#d0e8ff",  # Very Light Blue (so black text is readable)
        "btn_pick_hover": "#b3d7ff",

        # --- Dynamic States (Paused) ---
        "btn_paused_bg": "#ffcc4d",  # Sunflower Yellow
        "btn_paused_border": "#e6b722",
        "btn_paused_hover": "#ffdb75",

        # --- Progress Bar ---
        "progress_border": "#bbbbbb",
        "progress_chunk": "#2ea043",  # Green
        "progress_paused": "#f57c00",  # Orange (Yellow is too hard to see on white)

        # --- Table Widget ---
        "table_grid": "#e0e0e0",
        "header_bg": "#e1e1e1",
        "header_border": "#d0d0d0",
        "header_text": "#000000",

        # --- Console ---
        "alt_bg": "#fafafa",  # Almost white
        "console_text": "#24292f"
    }

    @staticmethod
    def applyTheme(app, palette_name="DARK"):
        palette_dict = ThemeManager.DARK_THEME if palette_name == "DARK" else ThemeManager.LIGHT_THEME

        try:
            template_file = importlib.resources.files(templates).joinpath("style_template.qss")
            content = template_file.read_text(encoding="utf-8")
        except AttributeError:
            content = importlib.resources.read_text(templates, "style_template.qss")

        # This looks for $key instead of {key}
        src = Template(content)
        final_style = src.safe_substitute(**palette_dict)

        app.setStyleSheet(final_style)
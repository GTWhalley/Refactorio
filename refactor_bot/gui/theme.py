"""
Theme configuration for refactor-bot GUI.

Modern dark theme inspired by VSCode/Discord.
"""

from dataclasses import dataclass
from typing import Tuple


@dataclass
class Colors:
    """Color palette for the application."""

    # Background colors
    bg_darkest: str = "#0d1117"      # Sidebar, darkest areas
    bg_dark: str = "#161b22"          # Main background
    bg_medium: str = "#21262d"        # Cards, panels
    bg_light: str = "#30363d"         # Hover states, borders
    bg_lighter: str = "#484f58"       # Active states

    # Text colors
    text_primary: str = "#e6edf3"     # Main text
    text_secondary: str = "#8b949e"   # Secondary text
    text_muted: str = "#6e7681"       # Muted text
    text_link: str = "#58a6ff"        # Links

    # Accent colors
    accent_primary: str = "#238636"   # Primary actions (green)
    accent_primary_hover: str = "#2ea043"
    accent_secondary: str = "#1f6feb" # Secondary actions (blue)
    accent_secondary_hover: str = "#388bfd"

    # Status colors
    success: str = "#238636"
    success_bg: str = "#122117"
    warning: str = "#d29922"
    warning_bg: str = "#2d2207"
    error: str = "#f85149"
    error_bg: str = "#2d1216"
    info: str = "#58a6ff"
    info_bg: str = "#0d1d30"

    # Risk colors
    risk_low: str = "#238636"
    risk_medium: str = "#d29922"
    risk_high: str = "#f85149"

    # Border
    border: str = "#30363d"
    border_light: str = "#484f58"

    # Progress bar
    progress_bg: str = "#21262d"
    progress_fill: str = "#238636"


@dataclass
class Fonts:
    """Font configuration."""

    family: str = "SF Pro Display"
    family_mono: str = "SF Mono"

    # Sizes
    size_xs: int = 10
    size_sm: int = 12
    size_md: int = 14
    size_lg: int = 16
    size_xl: int = 20
    size_xxl: int = 24
    size_title: int = 32


@dataclass
class Spacing:
    """Spacing constants."""

    xs: int = 4
    sm: int = 8
    md: int = 12
    lg: int = 16
    xl: int = 24
    xxl: int = 32


@dataclass
class Dimensions:
    """Dimension constants."""

    sidebar_width: int = 220
    sidebar_collapsed: int = 60
    button_height: int = 36
    input_height: int = 40
    card_radius: int = 8
    border_radius: int = 6


class Theme:
    """Main theme class containing all theme configuration."""

    colors = Colors()
    fonts = Fonts()
    spacing = Spacing()
    dimensions = Dimensions()

    @classmethod
    def get_button_style(cls, variant: str = "primary") -> dict:
        """Get button styling based on variant."""
        if variant == "primary":
            return {
                "fg_color": cls.colors.accent_primary,
                "hover_color": cls.colors.accent_primary_hover,
                "text_color": cls.colors.text_primary,
                "corner_radius": cls.dimensions.border_radius,
            }
        elif variant == "secondary":
            return {
                "fg_color": cls.colors.accent_secondary,
                "hover_color": cls.colors.accent_secondary_hover,
                "text_color": cls.colors.text_primary,
                "corner_radius": cls.dimensions.border_radius,
            }
        elif variant == "outline":
            return {
                "fg_color": "transparent",
                "hover_color": cls.colors.bg_light,
                "text_color": cls.colors.text_primary,
                "border_width": 1,
                "border_color": cls.colors.border,
                "corner_radius": cls.dimensions.border_radius,
            }
        elif variant == "danger":
            return {
                "fg_color": cls.colors.error,
                "hover_color": "#da3633",
                "text_color": cls.colors.text_primary,
                "corner_radius": cls.dimensions.border_radius,
            }
        else:
            return {
                "fg_color": cls.colors.bg_medium,
                "hover_color": cls.colors.bg_light,
                "text_color": cls.colors.text_primary,
                "corner_radius": cls.dimensions.border_radius,
            }

    @classmethod
    def get_input_style(cls) -> dict:
        """Get input field styling."""
        return {
            "fg_color": cls.colors.bg_medium,
            "border_color": cls.colors.border,
            "border_width": 1,
            "text_color": cls.colors.text_primary,
            "placeholder_text_color": cls.colors.text_muted,
            "corner_radius": cls.dimensions.border_radius,
        }

    @classmethod
    def get_card_style(cls) -> dict:
        """Get card/panel styling."""
        return {
            "fg_color": cls.colors.bg_medium,
            "corner_radius": cls.dimensions.card_radius,
        }


# Singleton instance
theme = Theme()

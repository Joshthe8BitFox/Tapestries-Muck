from pathlib import Path

root = Path.cwd()

format = "UDZO"
size = "80M"
files = [str(root / "dist" / "TapestriesMuck.app")]
symlinks = {"Applications": "/Applications"}

background = str(root / "packaging" / "dmg" / "dmg-background.png")
window_rect = ((120, 120), (660, 400))
icon_size = 104
text_size = 13
icon_locations = {
    "TapestriesMuck.app": (135, 215),
    "Applications": (525, 215),
}

show_status_bar = False
show_tab_view = False
show_toolbar = False
show_pathbar = False
show_sidebar = False
arrange_by = None
grid_offset = (0, 0)
grid_spacing = 100
label_pos = "bottom"

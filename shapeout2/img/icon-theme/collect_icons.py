"""Collect relevant icons to icon theme subdirectories

The icons used rely on the KDE breeze theme.

    apt install breeze-icon-theme

This script must be run on a linux machine. Please make sure
that `icon_root` is correct.
"""
import pathlib
import shutil

# The key identifies the theme; each list contains icon names
icons = {
    "breeze": [
        "application-exit",
        "code-context",
        "dialog-cancel",
        "dialog-close",
        "dialog-error",
        "dialog-information",
        "dialog-messages",
        "dialog-ok",
        "dialog-ok-apply",
        "dialog-question",
        "dialog-warning",
        "documentinfo",
        "document-open",
        "document-open-folder",
        "document-save",
        "draw-watercolor",
        "edit-clear",
        "folder",
        "folder-cloud",
        "globe",
        "gtk-preferences",
        "messagebox_warning",
        "object-columns",
        "object-rows",
        "office-chart-ring",
        "office-chart-scatter",
        "show-grid",
        "tools-wizard",
        "view-filter",
        "view-statistics",
        "visibility",
        "path-mode-polyline",
        "preferences-activities",
    ],
}

# theme index file
index = """[Icon Theme]
Name=ShapeOutMix
Comment=Mix of themes for Shape-Out 2

Directories={directories}
"""

# theme file folder item
index_item = """
[{directory}]
Size={res}
Type=Fixed
"""

icon_root = pathlib.Path("/usr/share/icons")


def find_icons(name, theme):
    cands = sorted((icon_root / theme).rglob("{}.svg".format(name)))
    cands += sorted((icon_root / theme).rglob("{}.png".format(name)))
    return cands


if __name__ == "__main__":
    directories = []
    here = pathlib.Path(__file__).parent
    for theme in icons:
        for name in icons[theme]:
            ipaths = find_icons(name, theme)
            if not ipaths:
                print("Could not find {} {}".format(theme, name))
                continue
            for ipath in ipaths:
                relp = ipath.parent.relative_to(icon_root)
                dest = here / relp
                directories.append(str(relp))
                dest.mkdir(exist_ok=True, parents=True)
                shutil.copy(ipath, dest)

    with (here / "index.theme").open("w") as fd:
        directories = sorted(set(directories))
        fd.write(index.format(directories=",".join(
            ["shapeout2"] + directories)))
        # Shape-Out icons
        fd.write(index_item.format(directory="shapeout2", res="16"))
        # theme icons
        for dd in directories:
            for res in ["16", "22", "24", "32", "64", "128"]:
                if res in str(dd):
                    break
            else:
                raise ValueError("No resolution for {}!".format(dd))
            fd.write(index_item.format(directory=dd, res=res))

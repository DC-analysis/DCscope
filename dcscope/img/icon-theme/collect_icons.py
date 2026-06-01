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
        "edit-clear-all",
        "edit-paste",
        "folder",
        "folder-cloud",
        "globe",
        "gtk-preferences",
        "list-add",
        "messagebox_warning",
        "object-columns",
        "object-order-lower",
        "object-rows",
        "office-chart-line-stacked",
        "office-chart-ring",
        "office-chart-scatter",
        "remove",
        "search",
        "show-grid",
        "special_paste",
        "tools-wizard",
        "view-calendar-list",
        "view-filter",
        "view-list-tree",
        "view-statistics",
        "visibility",
        "path-mode-polyline",
        "preferences-activities",
    ],
}

# theme index file
index = """[Icon Theme]
Name=DCscopeMix
Comment=Mix of themes for DCscope

Directories={directories}
"""

# theme file folder item
index_item = """
[{directory}]
Size={res}
Type=Fixed
"""

icon_root = pathlib.Path("/usr/share/icons")


def find_icons(name, theme, resolutions_used):
    cands = sorted((icon_root / theme).rglob("{}.svg".format(name)))
    cands += sorted((icon_root / theme).rglob("{}.png".format(name)))
    # Only allow directories with the resolutions used
    cands = [c for c in cands
             if (set(resolutions_used) & set([cp.name for cp in c.parents]))]
    return cands


def create_theme(shade="light", source_append=""):
    resolutions_used = ["16", "22", "24", "32", "64", "128"]
    directories = []
    here = pathlib.Path(__file__).parent
    for theme in icons:
        for name in icons[theme]:
            ipaths = find_icons(name, theme+source_append, resolutions_used)
            if not ipaths:
                print(f"Could not find {theme+source_append} {name}")
                continue
            for ipath in ipaths:
                relp = ipath.parent.relative_to(icon_root)
                dest = here / shade / relp
                directories.append(str(relp))
                dest.mkdir(exist_ok=True, parents=True)
                shutil.copy(ipath, dest)

    with (here / shade / "index.theme").open("w") as fd:
        directories = sorted(set(directories))
        fd.write(index.format(directories=",".join(
            ["dcscope"] + directories)))
        # DCscope icons
        fd.write(index_item.format(directory="dcscope", res="16"))
        fd.write(index_item.format(directory="dcscope", res="22"))
        fd.write(index_item.format(directory="dcscope", res="24"))
        fd.write(index_item.format(directory="dcscope", res="32"))
        fd.write(index_item.format(directory="dcscope", res="64"))
        fd.write(index_item.format(directory="dcscope", res="128"))
        # theme icons
        for dd in directories:
            for res in resolutions_used:
                if res in str(dd):
                    break
            else:
                raise ValueError(f"No resolution found for {dd}!")
            fd.write(index_item.format(directory=dd, res=res))


if __name__ == "__main__":
    create_theme(shade="light")
    create_theme(shade="dark", source_append="-dark")

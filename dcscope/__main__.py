def main(splash=True):
    import importlib.resources
    import sys
    import warnings

    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import QEventLoop, Qt
    from PyQt6 import QtGui
    # import before creating application
    import pyqtgraph  # noqa: F401

    app = QApplication(sys.argv)

    style_hints = QApplication.styleHints()
    if style_hints.colorScheme() == Qt.ColorScheme.Dark:
        theme_shade = "dark"
    else:
        theme_shade = "light"

    # set Qt icon theme search path
    ref = importlib.resources.files("dcscope.img") / "icon.png"
    with importlib.resources.as_file(ref) as icon_path:
        theme_dir = icon_path.with_name("icon-theme")
        theme_path = theme_dir / theme_shade
    if theme_path.exists():
        QtGui.QIcon.setThemeSearchPaths([str(theme_path)])
        QtGui.QIcon.setThemeName(".")
    else:
        warnings.warn("DCscope theme path not available")

    if splash:
        from PyQt6.QtWidgets import QSplashScreen
        from PyQt6.QtGui import QPixmap
        ref = importlib.resources.files("dcscope.img") / "splash.png"
        with importlib.resources.as_file(ref) as splash_path:
            splash_pix = QPixmap(str(splash_path))
        splash = QSplashScreen(splash_pix)
        splash.setMask(splash_pix.mask())
        splash.show()
        # make sure Qt really displays the splash screen
        app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 300)

    from PyQt6 import QtCore, QtGui
    from .gui import DCscope

    # Set Application Icon
    ref = importlib.resources.files("dcscope.img") / "icon.png"
    with importlib.resources.as_file(ref) as icon_path:
        app.setWindowIcon(QtGui.QIcon(str(icon_path)))

    # Use dots as decimal separators
    QtCore.QLocale.setDefault(QtCore.QLocale(QtCore.QLocale.Language.C))

    window = DCscope(*app.arguments()[1:])

    if splash:
        splash.finish(window)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

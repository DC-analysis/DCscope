def main(splash=True):
    import os
    import pkg_resources
    import sys

    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import QEventLoop
    # import before creating application
    import pyqtgraph  # noqa: F401

    app = QApplication(sys.argv)
    imdir = pkg_resources.resource_filename("shapeout2", "img")

    if splash:
        from PyQt6.QtWidgets import QSplashScreen
        from PyQt6.QtGui import QPixmap
        splash_path = os.path.join(imdir, "splash.png")
        splash_pix = QPixmap(splash_path)
        splash = QSplashScreen(splash_pix)
        splash.setMask(splash_pix.mask())
        splash.show()
        # make sure Qt really displays the splash screen
        app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 300)

    from PyQt6 import QtCore, QtGui
    from .gui import ShapeOut2

    # Set Application Icon
    icon_path = os.path.join(imdir, "icon.png")
    app.setWindowIcon(QtGui.QIcon(icon_path))

    # Use dots as decimal separators
    QtCore.QLocale.setDefault(QtCore.QLocale(QtCore.QLocale.Language.C))

    window = ShapeOut2(*app.arguments()[1:])

    if splash:
        splash.finish(window)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

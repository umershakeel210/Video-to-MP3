from __future__ import annotations

import sys
from PySide6.QtWidgets import QApplication, QMessageBox

from videotomp3.services.logging_service import configure_logging
from videotomp3.services.settings_service import SettingsService
from videotomp3.ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Video to MP3 Converter")
    app.setOrganizationName("UtilityWorks")
    settings = SettingsService()
    logger = configure_logging(settings.logging_enabled)
    try:
        window = MainWindow(settings, logger)
        window.show()
        return app.exec()
    except Exception:
        logger.exception("Fatal application error")
        QMessageBox.critical(None, "Application error", "The application encountered an unexpected error. Details were saved to the troubleshooting log.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

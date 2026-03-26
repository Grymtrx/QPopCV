import logging
import logging.handlers
from qpopcv import QPopApp
from qpopcv.config import APP_DIR

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format=_LOG_FORMAT,
    )

    file_handler = logging.handlers.RotatingFileHandler(
        APP_DIR / "qpopcv.log",
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    logging.getLogger().addHandler(file_handler)

    app = QPopApp()
    app.run()


if __name__ == "__main__":
    main()

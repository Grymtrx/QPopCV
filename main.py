import logging
from qpopcv import QPopApp


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    app = QPopApp()
    app.run()


if __name__ == "__main__":
    main()

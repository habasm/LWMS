from . import models  # noqa: F401 - load model metadata before resetting tables
from .core.database import Base, engine
from .seed import seed


def reset_dev_data() -> None:
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    seed()


if __name__ == '__main__':
    reset_dev_data()

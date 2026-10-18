from enum import IntEnum


class RiskLevel(IntEnum):
    """Ordered so comparison and max() mean "worse"."""

    LOW = 0
    MODERATE = 1
    HIGH = 2
    SEVERE = 3
    NO_TRAVEL = 4

    @property
    def label(self) -> str:
        return self.name.replace("_", " ").title()

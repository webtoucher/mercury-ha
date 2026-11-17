"""Заводское обозначение счётчика: номер модели с буквами оснащения.

Прокси отдаёт только номер модели, а обозначение Инкотекс несёт после него
буквы оснащения: Меркурий 206 [P] [R|C|L] [S] [N] [O] [Fx]. Часть букв видна
в паспорте прокси, остальные дочитываются командами счётчика.
"""

from typing import Any, Final

from .api import MercuryProxyApi, MercuryProxyError, Meter
from .const import FEATURE_RELAY

# Признаки, которых в паспорте прокси нет.
FEATURE_PROFILE: Final = "profile"
FEATURE_SEAL: Final = "seal"

COMMAND_ARCHIVE_TYPE: Final = "get_archive_type"
COMMAND_LAST_COVER_OPEN: Final = "get_last_cover_open_datetime"

# Глубина архивов 2 — счётчик хранит получасовки, значит у него есть профиль мощности.
ARCHIVE_TYPE_PROFILE: Final = 2

# Буквы в том порядке, в каком их печатают в обозначении прибора.
FEATURE_LETTERS: Final[tuple[tuple[str, str], ...]] = (
    (FEATURE_PROFILE, "P"),
    ("RS485", "R"),
    ("CAN", "C"),
    ("PLC", "L"),
    ("internal power", "S"),
    (FEATURE_SEAL, "N"),
    (FEATURE_RELAY, "O"),
)


async def async_designation(api: MercuryProxyApi, meter: Meter) -> str:
    """Собирает обозначение прибора, например «206 PRNO».

    Недостающие признаки не считаются ошибкой: без них обозначение просто
    короче, а интеграция работает как обычно.
    """
    features = set(meter.features) | await _async_extra_features(api, meter)
    letters = "".join(
        letter for feature, letter in FEATURE_LETTERS if feature in features
    )
    return f"{meter.model} {letters}".strip()


async def _async_extra_features(api: MercuryProxyApi, meter: Meter) -> set[str]:
    """Дочитывает признаки, которых нет в паспорте прокси."""
    features: set[str] = set()
    serial_number = meter.serial_number

    if FEATURE_PROFILE not in meter.features:
        archive_type = await _async_read(api, serial_number, COMMAND_ARCHIVE_TYPE)
        if archive_type == ARCHIVE_TYPE_PROFILE:
            features.add(FEATURE_PROFILE)

    if FEATURE_SEAL not in meter.features:
        # Без электронной пломбы счётчику нечего сказать о вскрытии крышки,
        # и команда отвечает ошибкой.
        cover = await _async_read(api, serial_number, COMMAND_LAST_COVER_OPEN)
        if cover is not None:
            features.add(FEATURE_SEAL)

    return features


async def _async_read(
    api: MercuryProxyApi, serial_number: int, command: str
) -> Any | None:
    """Выполняет необязательную команду: None, если она не удалась."""
    try:
        return await api.command(serial_number, command)
    except MercuryProxyError:
        return None

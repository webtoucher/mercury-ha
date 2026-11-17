"""Тесты сборки заводского обозначения счётчика."""

from typing import Any

import pytest

from custom_components.mercury_proxy.api import MercuryProxyError, Meter
from custom_components.mercury_proxy.model import async_designation

SERIAL_NUMBER = 37793503


class FakeApi:
    """Прокси, отвечающий на команды из словаря, и помнящий их порядок."""

    def __init__(self, responses: dict[str, Any]) -> None:
        """Запоминает ответы: исключение в словаре будет возбуждено."""
        self.responses = responses
        self.calls: list[str] = []

    async def command(self, serial_number: int, name: str) -> Any:
        """Отдаёт заранее заданный ответ на команду."""
        self.calls.append(name)
        response = self.responses[name]
        if isinstance(response, Exception):
            raise response
        return response


def meter(*features: str) -> Meter:
    """Паспорт счётчика с заданным оснащением."""
    return Meter(serial_number=SERIAL_NUMBER, model="206", features=features)


@pytest.mark.parametrize(
    ("features", "responses", "expected"),
    [
        pytest.param(
            ("RS485", "relay"),
            {"get_archive_type": 2, "get_last_cover_open_datetime": "2022-11-27"},
            "206 PRNO",
            id="full_set",
        ),
        pytest.param(
            ("RS485", "relay"),
            {"get_archive_type": 0, "get_last_cover_open_datetime": "2022-11-27"},
            "206 RNO",
            id="without_profile",
        ),
        pytest.param(
            ("RS485", "relay"),
            {
                "get_archive_type": 2,
                "get_last_cover_open_datetime": MercuryProxyError(),
            },
            "206 PRO",
            id="without_seal",
        ),
        pytest.param(
            ("RS485", "relay"),
            {
                "get_archive_type": MercuryProxyError(),
                "get_last_cover_open_datetime": MercuryProxyError(),
            },
            "206 RO",
            id="commands_failed",
        ),
        pytest.param((), {}, "206", id="bare_model"),
        pytest.param(
            ("PLC", "relay"),
            {"get_archive_type": 2, "get_last_cover_open_datetime": "2022-11-27"},
            "206 PLNO",
            id="plc_instead_of_rs485",
        ),
    ],
)
async def test_designation(
    features: tuple[str, ...],
    responses: dict[str, Any],
    expected: str,
) -> None:
    """Обозначение собирается из оснащения в заводском порядке букв."""
    api = FakeApi(
        {
            "get_archive_type": 0,
            "get_last_cover_open_datetime": MercuryProxyError(),
            **responses,
        }
    )

    assert await async_designation(api, meter(*features)) == expected


async def test_known_features_are_not_queried() -> None:
    """Признаки из паспорта прокси повторно у счётчика не спрашиваются."""
    api = FakeApi({})

    designation = await async_designation(
        api, meter("profile", "RS485", "seal", "relay")
    )

    assert designation == "206 PRNO"
    assert api.calls == []

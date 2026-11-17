"""Тесты клиента mercury-proxy.

Клиент не зависит от Home Assistant, поэтому тесты поднимают поддельный
прокси на aiohttp и проверяют обмен с ним.
"""

from collections.abc import AsyncIterator
from typing import Any

import pytest
from aiohttp import ClientSession, web
from aiohttp.test_utils import TestServer

from custom_components.mercury_proxy.api import (
    MercuryProxyApi,
    MercuryProxyAuthError,
    MercuryProxyError,
    Meter,
    normalize_url,
)

TOKEN = "test-token"

METER_PAYLOAD = {
    "serial_number": 37793503,
    "model": "206",
    "firmware_version": "1.0",
    "date_of_manufacture": "2021-12-07",
    "meter_version": None,
    "features": ["RS485", "relay"],
    "port": "/dev/ttyACM0",
}


class FakeProxy:
    """Поддельный прокси: отдаёт заданные ответы по путям и помнит запросы."""

    def __init__(self) -> None:
        """Готовит сервер с обработчиком на любой путь."""
        self.responses: dict[str, tuple[int, Any]] = {}
        self.headers: dict[str, dict[str, str]] = {}
        app = web.Application()
        app.router.add_route("GET", "/{tail:.*}", self._handle)
        self.server = TestServer(app)

    def respond(self, path: str, payload: Any, status: int = 200) -> None:
        """Задаёт ответ на путь; строка уходит сырым телом, объект — JSON."""
        self.responses[path] = (status, payload)

    async def _handle(self, request: web.Request) -> web.StreamResponse:
        """Отвечает по заранее заданному сценарию."""
        self.headers[request.path] = dict(request.headers)
        status, payload = self.responses.get(
            request.path, (404, {"error": f"unknown path: {request.path}"})
        )
        if isinstance(payload, str):
            return web.Response(status=status, text=payload)
        return web.json_response(payload, status=status)


@pytest.fixture
async def proxy() -> AsyncIterator[FakeProxy]:
    """Поднимает поддельный прокси на свободном порту."""
    fake = FakeProxy()
    await fake.server.start_server()
    yield fake
    await fake.server.close()


@pytest.fixture
async def api(proxy: FakeProxy) -> AsyncIterator[MercuryProxyApi]:
    """Отдаёт клиент, направленный на поддельный прокси."""
    session = ClientSession()
    yield MercuryProxyApi(session, f"http://127.0.0.1:{proxy.server.port}", TOKEN)
    await session.close()


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("http://hm.webtoucher.ru:5054", "http://hm.webtoucher.ru:5054"),
        ("http://hm.webtoucher.ru:5054/", "http://hm.webtoucher.ru:5054"),
        ("hm.webtoucher.ru:5054", "http://hm.webtoucher.ru:5054"),
        ("https://example.com/prefix/", "https://example.com/prefix"),
    ],
)
def test_normalize_url(url: str, expected: str) -> None:
    """Адрес приводится к схеме и виду без хвостового слэша."""
    assert normalize_url(url) == expected


@pytest.mark.parametrize("url", ["", "ftp://host", "http://"])
def test_normalize_url_rejects_garbage(url: str) -> None:
    """Неподходящий адрес не превращается в рабочий."""
    with pytest.raises(ValueError, match="Некорректный адрес"):
        normalize_url(url)


def test_meter_from_dict() -> None:
    """Паспорт счётчика разбирается, а необязательные поля не ломают разбор."""
    meter = Meter.from_dict(METER_PAYLOAD)
    assert meter.serial_number == 37793503
    assert meter.model == "206"
    assert meter.features == ("RS485", "relay")

    sparse = Meter.from_dict({"serial_number": 1, "model": "200"})
    assert sparse.features == ()
    assert sparse.firmware_version is None


async def test_meters_and_meter(api: MercuryProxyApi, proxy: FakeProxy) -> None:
    """Список счётчиков и паспорт одного счётчика читаются из ответов прокси."""
    proxy.respond("/v1.0/meters", {"meters": [METER_PAYLOAD]})
    proxy.respond("/v1.0/meters/37793503", METER_PAYLOAD)

    assert [meter.serial_number for meter in await api.meters()] == [37793503]
    assert (await api.meter(37793503)).features == ("RS485", "relay")
    assert proxy.headers["/v1.0/meters"]["Authorization"] == f"Bearer {TOKEN}"


async def test_command_returns_result(api: MercuryProxyApi, proxy: FakeProxy) -> None:
    """Команда отдаёт только поле result."""
    proxy.respond("/v1.0/meters/37793503/get_vcp", {"result": {"voltage": 233.5}})
    assert await api.command(37793503, "get_vcp") == {"voltage": 233.5}


@pytest.mark.parametrize(
    ("status", "payload", "expected", "match"),
    [
        (401, {"error": "unauthorized"}, MercuryProxyAuthError, "отклонил токен"),
        (
            404,
            {"error": "meter 1 is not connected"},
            MercuryProxyError,
            "is not connected",
        ),
        (500, {"error": "internal error"}, MercuryProxyError, "internal error"),
    ],
)
async def test_errors(
    api: MercuryProxyApi,
    proxy: FakeProxy,
    status: int,
    payload: dict[str, str],
    expected: type[MercuryProxyError],
    match: str,
) -> None:
    """Коды ошибок прокси превращаются в исключения клиента."""
    proxy.respond("/v1.0/meters", payload, status)
    with pytest.raises(expected, match=match):
        await api.meters()


async def test_non_json_response(api: MercuryProxyApi, proxy: FakeProxy) -> None:
    """Ответ не в JSON (например, HTML от чужого сервера) не роняет клиент."""
    proxy.respond("/v1.0/meters", "<html>oops</html>", 501)
    with pytest.raises(MercuryProxyError, match="не JSON"):
        await api.meters()


async def test_unreachable_proxy() -> None:
    """Недоступный порт даёт ошибку связи, а не висящий запрос."""
    session = ClientSession()
    try:
        api = MercuryProxyApi(session, "http://127.0.0.1:1", TOKEN)
        with pytest.raises(MercuryProxyError, match="Нет связи"):
            await api.meters()
    finally:
        await session.close()

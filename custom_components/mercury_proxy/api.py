"""Клиент HTTP API mercury-proxy."""

import json
from dataclasses import dataclass
from typing import Any, Self
from urllib.parse import urlsplit

from aiohttp import ClientError, ClientSession, ClientTimeout

from .const import REQUEST_TIMEOUT


class MercuryProxyError(Exception):
    """Обращение к mercury-proxy не удалось."""


class MercuryProxyAuthError(MercuryProxyError):
    """Прокси отклонил токен."""


@dataclass(frozen=True, slots=True)
class Meter:
    """Счётчик, подключённый к прокси."""

    serial_number: int
    model: str
    firmware_version: str | None = None
    date_of_manufacture: str | None = None
    features: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Self:
        """Разбирает описание счётчика из ответа /v1.0/meters."""
        return cls(
            serial_number=payload["serial_number"],
            model=payload["model"],
            firmware_version=payload.get("firmware_version"),
            date_of_manufacture=payload.get("date_of_manufacture"),
            features=tuple(payload.get("features") or ()),
        )


def normalize_url(url: str) -> str:
    """Приводит адрес прокси к виду http://хост:порт без хвостового слэша.

    Схему можно не писать: прокси по умолчанию слушает обычный HTTP.
    """
    url = url.strip()
    if "://" not in url:
        url = f"http://{url}"
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError(f"Некорректный адрес mercury-proxy: {url}")
    return url.rstrip("/")


class MercuryProxyApi:
    """Обёртка над REST API mercury-proxy.

    Прокси отдаёт данные командами mercury-base: путь
    /v1.0/meters/<серийный номер>/<команда> возвращает {"result": ...},
    а ошибку — {"error": "..."} вместе с кодом HTTP.
    """

    def __init__(self, session: ClientSession, url: str, token: str) -> None:
        """Запоминает сессию, адрес прокси и токен доступа."""
        self._session = session
        self._url = normalize_url(url)
        self._headers = {"Authorization": f"Bearer {token}"}

    @property
    def url(self) -> str:
        """Адрес прокси без хвостового слэша."""
        return self._url

    async def meters(self) -> list[Meter]:
        """Перечисляет счётчики, подключённые к прокси."""
        payload = await self._request("/v1.0/meters")
        return [Meter.from_dict(item) for item in payload["meters"]]

    async def meter(self, serial_number: int) -> Meter:
        """Читает паспорт одного счётчика."""
        return Meter.from_dict(await self._request(f"/v1.0/meters/{serial_number}"))

    async def command(self, serial_number: int, name: str) -> Any:
        """Выполняет команду mercury-base на счётчике."""
        payload = await self._request(f"/v1.0/meters/{serial_number}/{name}")
        return payload["result"]

    async def _request(self, path: str) -> dict[str, Any]:
        """Выполняет GET-запрос и разбирает ответ прокси."""
        try:
            async with self._session.get(
                f"{self._url}{path}",
                headers=self._headers,
                timeout=ClientTimeout(total=REQUEST_TIMEOUT),
            ) as response:
                status = response.status
                body = await response.text()
        except (ClientError, TimeoutError) as err:
            raise MercuryProxyError(f"Нет связи с mercury-proxy: {err}") from err

        try:
            payload = json.loads(body)
        except ValueError as err:
            raise MercuryProxyError(
                f"mercury-proxy ответил не JSON (HTTP {status})"
            ) from err

        if status == 401:
            raise MercuryProxyAuthError("mercury-proxy отклонил токен")
        if status != 200:
            raise MercuryProxyError(payload.get("error") or f"HTTP {status}")
        return payload

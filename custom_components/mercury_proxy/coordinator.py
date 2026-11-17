"""Опрос счётчика через mercury-proxy."""

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import MercuryProxyApi, MercuryProxyAuthError, MercuryProxyError, Meter
from .const import (
    COMMAND_ENERGY_ACCUMULATORS,
    COMMAND_IS_RELAY_ON,
    COMMAND_MAINS_PARAMETERS,
    COMMAND_TARIFFS_COUNT,
    COMMAND_VCP,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    FEATURE_RELAY,
    MAX_TARIFFS,
)

_LOGGER = logging.getLogger(__name__)

type MercuryProxyConfigEntry = ConfigEntry[MercuryProxyCoordinator]


@dataclass(frozen=True, slots=True)
class MercuryProxyData:
    """Показания счётчика, полученные за один круг опроса."""

    # Сумма тарифных аккумуляторов активной энергии, кВт·ч.
    energy: float
    # Накопленная активная энергия по каждому тарифу, кВт·ч.
    tariffs: tuple[float, ...]
    voltage: float
    current: float
    # Мощность в нагрузке, кВт.
    power: float
    frequency: float
    # Состояние реле; None, если реле у счётчика нет.
    relay_on: bool | None


class MercuryProxyCoordinator(DataUpdateCoordinator[MercuryProxyData]):
    """Опрашивает один счётчик через mercury-proxy."""

    config_entry: MercuryProxyConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: MercuryProxyConfigEntry,
        api: MercuryProxyApi,
        meter: Meter,
        designation: str,
    ) -> None:
        """Берёт период опроса из настроек записи."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {meter.serial_number}",
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )
        self.api = api
        self.meter = meter
        # Обозначение вида «206 PRNO» — модель с буквами оснащения.
        self.designation = designation
        # Ноль означает, что счётчик ещё не спрашивали о числе тарифов.
        self.tariffs_count = 0

    async def _command(self, name: str) -> Any:
        """Выполняет команду на своём счётчике."""
        return await self.api.command(self.meter.serial_number, name)

    async def _async_tariffs_count(self) -> int:
        """Спрашивает число тарифов один раз за всё время работы записи."""
        if not self.tariffs_count:
            count = await self._command(COMMAND_TARIFFS_COUNT)
            self.tariffs_count = min(max(int(count), 1), MAX_TARIFFS)
        return self.tariffs_count

    async def _async_update_data(self) -> MercuryProxyData:
        """Читает энергию, мгновенные значения и состояние реле.

        Команды идут строго по одной: прокси работает с шиной счётчика
        последовательно, и параллельные запросы только встают в очередь.
        """
        try:
            await self._async_tariffs_count()
            accumulators = await self._command(COMMAND_ENERGY_ACCUMULATORS)
            vcp = await self._command(COMMAND_VCP)
            mains = await self._command(COMMAND_MAINS_PARAMETERS)
            relay_on = (
                await self._command(COMMAND_IS_RELAY_ON)
                if FEATURE_RELAY in self.meter.features
                else None
            )
        except MercuryProxyAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except MercuryProxyError as err:
            raise UpdateFailed(str(err)) from err

        return MercuryProxyData(
            energy=round(sum(accumulators), 2),
            tariffs=tuple(accumulators),
            voltage=vcp["voltage"],
            current=vcp["current"],
            power=vcp["power"],
            frequency=mains["frequency"],
            relay_on=relay_on,
        )

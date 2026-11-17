"""Интеграция со счётчиками Меркурий через mercury-proxy."""

import logging

from homeassistant.const import CONF_TOKEN, CONF_URL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import MercuryProxyApi, MercuryProxyAuthError, MercuryProxyError
from .const import CONF_SERIAL_NUMBER
from .coordinator import MercuryProxyConfigEntry, MercuryProxyCoordinator
from .model import async_designation

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: MercuryProxyConfigEntry
) -> bool:
    """Подключается к счётчику и запускает опрос."""
    api = MercuryProxyApi(
        async_get_clientsession(hass), entry.data[CONF_URL], entry.data[CONF_TOKEN]
    )
    try:
        meter = await api.meter(entry.data[CONF_SERIAL_NUMBER])
        designation = await async_designation(api, meter)
        _LOGGER.debug("Счётчик %s: обозначение %s", meter.serial_number, designation)
    except MercuryProxyAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except MercuryProxyError as err:
        raise ConfigEntryNotReady(str(err)) from err

    coordinator = MercuryProxyCoordinator(hass, entry, api, meter, designation)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: MercuryProxyConfigEntry
) -> bool:
    """Останавливает опрос и выгружает платформы."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

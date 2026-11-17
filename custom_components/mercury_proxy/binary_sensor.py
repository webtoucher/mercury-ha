"""Двоичный сенсор состояния реле счётчика."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import FEATURE_RELAY
from .coordinator import MercuryProxyConfigEntry, MercuryProxyCoordinator
from .entity import MercuryProxyEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MercuryProxyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Создаёт сенсор реле, если счётчик им оснащён."""
    coordinator = entry.runtime_data
    if FEATURE_RELAY not in coordinator.meter.features:
        return
    async_add_entities([MercuryProxyRelay(coordinator)])


class MercuryProxyRelay(MercuryProxyEntity, BinarySensorEntity):
    """Включено ли реле счётчика."""

    _attr_device_class = BinarySensorDeviceClass.POWER
    _attr_translation_key = "relay"

    def __init__(self, coordinator: MercuryProxyCoordinator) -> None:
        """Привязывает сенсор к счётчику."""
        super().__init__(coordinator, "relay")

    @property
    def is_on(self) -> bool | None:
        """Возвращает состояние реле из последнего опроса."""
        return self.coordinator.data.relay_on

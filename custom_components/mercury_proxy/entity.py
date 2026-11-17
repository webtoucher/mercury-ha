"""Общая часть сущностей счётчика."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import MercuryProxyCoordinator


class MercuryProxyEntity(CoordinatorEntity[MercuryProxyCoordinator]):
    """Сущность одного счётчика и его устройства в реестре."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: MercuryProxyCoordinator, key: str) -> None:
        """Строит описание устройства по паспорту счётчика."""
        super().__init__(coordinator)
        meter = coordinator.meter
        self._attr_unique_id = f"{meter.serial_number}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(meter.serial_number))},
            manufacturer=MANUFACTURER,
            model=f"Mercury {coordinator.designation}",
            # Имя устройства латиницей — префикс entity_id: mercury_<номер>_<ключ>.
            name=f"Mercury {meter.serial_number}",
            serial_number=str(meter.serial_number),
            sw_version=meter.firmware_version,
            configuration_url=coordinator.api.url,
        )

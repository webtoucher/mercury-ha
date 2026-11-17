"""Сенсоры счётчика: энергия, мощность, напряжение, ток и частота сети."""

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import MercuryProxyConfigEntry, MercuryProxyCoordinator
from .entity import MercuryProxyEntity

# Ключ описания совпадает с полем MercuryProxyData, из которого берётся значение,
# а translation_key ведёт к подписи в translations/<язык>.json.
SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="energy",
        translation_key="energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="power",
        translation_key="power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
    ),
    SensorEntityDescription(
        key="voltage",
        translation_key="voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="current",
        translation_key="current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="frequency",
        translation_key="frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MercuryProxyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Создаёт сенсоры счётчика и по сенсору на каждый тариф."""
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = [
        MercuryProxySensor(coordinator, description) for description in SENSORS
    ]
    # При единственном тарифе сумма и есть тариф, отдельный сенсор был бы дублем.
    if coordinator.tariffs_count > 1:
        entities.extend(
            MercuryProxyTariff(coordinator, number)
            for number in range(1, coordinator.tariffs_count + 1)
        )
    async_add_entities(entities)


class MercuryProxySensor(MercuryProxyEntity, SensorEntity):
    """Сенсор одного показателя счётчика."""

    entity_description: SensorEntityDescription

    def __init__(
        self,
        coordinator: MercuryProxyCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Привязывает сенсор к описанию и счётчику."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float:
        """Берёт значение из поля данных опроса с именем ключа описания."""
        return getattr(self.coordinator.data, self.entity_description.key)


class MercuryProxyTariff(MercuryProxyEntity, SensorEntity):
    """Накопленная активная энергия одного тарифа."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_suggested_display_precision = 2
    _attr_translation_key = "tariff"

    def __init__(self, coordinator: MercuryProxyCoordinator, number: int) -> None:
        """Привязывает сенсор к номеру тарифа."""
        super().__init__(coordinator, f"tariff_{number}")
        self._attr_translation_placeholders = {"number": str(number)}
        self._number = number

    @property
    def native_value(self) -> float:
        """Берёт накопленную энергию тарифа из последнего опроса."""
        return self.coordinator.data.tariffs[self._number - 1]

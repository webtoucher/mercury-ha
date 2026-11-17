"""Константы интеграции со счётчиками Меркурий."""

from typing import Final

DOMAIN: Final = "mercury_proxy"

# Имя устройства — префикс entity_id, поэтому оно задаётся латиницей.
MANUFACTURER: Final = "Incotex"

# Адрес, которым мастер предзаполняет поле подключения к прокси.
DEFAULT_URL: Final = "http://localhost:5054"

# Прокси общается со счётчиком по одному кадру за раз, поэтому частый опрос
# только копит очередь запросов.
DEFAULT_SCAN_INTERVAL: Final = 60
MIN_SCAN_INTERVAL: Final = 10
MAX_SCAN_INTERVAL: Final = 3600

CONF_SERIAL_NUMBER: Final = "serial_number"

# Ответ идёт через шлюз и шину, поэтому тайм-аут взят с запасом.
REQUEST_TIMEOUT: Final = 30

# Признак в паспорте счётчика, по которому видно, есть ли смысл опрашивать реле.
FEATURE_RELAY: Final = "relay"

# Протокол mercury_v1 отдаёт не больше четырёх аккумуляторов активной энергии,
# поэтому тарифов у счётчика может быть от одного до четырёх.
MAX_TARIFFS: Final = 4

# Команды mercury_base.mercury_v1, которые интеграция вызывает через прокси.
COMMAND_ENERGY_ACCUMULATORS: Final = "get_energy_accumulators"
COMMAND_IS_RELAY_ON: Final = "get_is_relay_on"
COMMAND_MAINS_PARAMETERS: Final = "get_mains_parameters"
COMMAND_TARIFFS_COUNT: Final = "get_tariffs_count"
COMMAND_VCP: Final = "get_vcp"

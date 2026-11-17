"""Мастер подключения счётчика через mercury-proxy."""

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_SCAN_INTERVAL, CONF_TOKEN, CONF_URL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import MercuryProxyApi, MercuryProxyAuthError, MercuryProxyError, Meter
from .const import (
    CONF_SERIAL_NUMBER,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL, default="http://"): TextSelector(
            TextSelectorConfig(type=TextSelectorType.URL)
        ),
        vol.Required(CONF_TOKEN): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)

TOKEN_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TOKEN): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        )
    }
)


def _api(hass: HomeAssistant, data: Mapping[str, Any]) -> MercuryProxyApi:
    """Создаёт клиент прокси по данным мастера."""
    return MercuryProxyApi(
        async_get_clientsession(hass), data[CONF_URL], data[CONF_TOKEN]
    )


def _meter_title(meter: Meter) -> str:
    """Подпись счётчика в списке выбора и в заголовке записи."""
    return f"Меркурий {meter.model} ({meter.serial_number})"


class MercuryProxyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Подключение к прокси: адрес, токен и выбор счётчика."""

    VERSION = 1

    def __init__(self) -> None:
        """Готовит данные мастера и список счётчиков прокси."""
        self._data: dict[str, Any] = {}
        self._meters: list[Meter] = []

    async def _async_validate(
        self, data: Mapping[str, Any]
    ) -> tuple[list[Meter], dict[str, str]]:
        """Проверяет адрес и токен, возвращая счётчики прокси или ошибку."""
        try:
            api = _api(self.hass, data)
            return await api.meters(), {}
        except MercuryProxyAuthError:
            return [], {"base": "invalid_auth"}
        except ValueError:
            return [], {"base": "invalid_url"}
        except MercuryProxyError:
            return [], {"base": "cannot_connect"}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Спрашивает адрес прокси и токен."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._meters, errors = await self._async_validate(user_input)
            if not errors and not self._meters:
                errors = {"base": "no_meters"}
            if not errors:
                self._data = user_input
                return await self.async_step_meter()

        return self.async_show_form(
            step_id="user", data_schema=USER_SCHEMA, errors=errors
        )

    async def async_step_meter(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Выбирает счётчик, если к прокси подключено несколько."""
        if user_input is None and len(self._meters) > 1:
            return self.async_show_form(
                step_id="meter",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_SERIAL_NUMBER): SelectSelector(
                            SelectSelectorConfig(
                                options=[
                                    SelectOptionDict(
                                        value=str(meter.serial_number),
                                        label=_meter_title(meter),
                                    )
                                    for meter in self._meters
                                ]
                            )
                        )
                    }
                ),
            )

        meter = (
            self._meters[0]
            if user_input is None
            else next(
                meter
                for meter in self._meters
                if str(meter.serial_number) == user_input[CONF_SERIAL_NUMBER]
            )
        )
        await self.async_set_unique_id(str(meter.serial_number))
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=_meter_title(meter),
            data={**self._data, CONF_SERIAL_NUMBER: meter.serial_number},
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Прокси перестал принимать токен — просим новый."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Проверяет новый токен и обновляет запись."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {**entry.data, CONF_TOKEN: user_input[CONF_TOKEN]}
            _, errors = await self._async_validate(data)
            if not errors:
                return self.async_update_reload_and_abort(entry, data=data)

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=TOKEN_SCHEMA,
            errors=errors,
            description_placeholders={CONF_URL: entry.data[CONF_URL]},
        )

    @classmethod
    @callback
    def async_get_options_flow(cls, config_entry: ConfigEntry) -> OptionsFlowWithReload:
        """Создаёт обработчик настроек записи."""
        return MercuryProxyOptionsFlow()


class MercuryProxyOptionsFlow(OptionsFlowWithReload):
    """Настройка периода опроса счётчика."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Спрашивает период опроса в секундах."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=MIN_SCAN_INTERVAL,
                            max=MAX_SCAN_INTERVAL,
                            step=1,
                            mode=NumberSelectorMode.BOX,
                        )
                    )
                }
            ),
        )

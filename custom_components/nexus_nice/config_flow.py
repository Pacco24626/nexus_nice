"""Config flow: quale cancello del gateway, come si chiama, che tipologia e' e da che parte apre."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import selector

from .const import (
    CONF_NOME,
    CONF_SLOT,
    CONF_TIPOLOGIA,
    CONF_VERSO,
    DOMAIN,
    TIPOLOGIA_PREDEFINITA,
    TIPOLOGIE,
    TIPOLOGIE_CON_VERSO,
    VERSI,
    VERSO_PREDEFINITO,
)
from .logica import cancelli_disponibili, nome_predefinito


def _selettore_tipologia() -> selector.SelectSelector:
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=TIPOLOGIE, translation_key="tipologia", mode=selector.SelectSelectorMode.LIST
        )
    )


def _schema_verso(tipologia: str, predefinito: str) -> vol.Schema:
    # Le etichette dipendono dalla tipologia: uno scorrevole «scorre verso», un
    # cancello a un'anta ha «la cerniera a».
    return vol.Schema(
        {
            vol.Required(CONF_VERSO, default=predefinito): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=VERSI,
                    translation_key=f"verso_{tipologia}",
                    mode=selector.SelectSelectorMode.LIST,
                )
            )
        }
    )


class NexusNiceConfigFlow(ConfigFlow, domain=DOMAIN):
    """Un cancello per voce: il gateway ne gestisce fino a cinque."""

    VERSION = 1

    def __init__(self) -> None:
        self._dati: dict[str, Any] = {}
        self._nome = ""

    def _disponibili(self) -> list[tuple[int, str]]:
        configurati = []
        for voce in self._async_current_entries(include_ignore=False):
            try:
                configurati.append(int(voce.data[CONF_SLOT]))
            except (KeyError, TypeError, ValueError):
                continue
        dispositivi = [
            (dispositivo.identifiers, dispositivo.name_by_user or dispositivo.name)
            for dispositivo in dr.async_get(self.hass).devices.values()
        ]
        return cancelli_disponibili(dispositivi, configurati)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        disponibili = self._disponibili()
        if not disponibili:
            return self.async_abort(reason="nessun_cancello")

        if user_input is not None:
            slot = int(user_input[CONF_SLOT])
            await self.async_set_unique_id(f"nexus_nice_{slot}")
            self._abort_if_unique_id_configured()
            nome_dispositivo = dict(disponibili).get(slot)
            nome = (user_input.get(CONF_NOME) or "").strip()
            # Il nome proposto e' quello del primo cancello dell'elenco: se si e'
            # scelto un altro slot senza toccarlo, vale il nome di quello scelto.
            if not nome or (slot != disponibili[0][0] and nome == nome_predefinito(disponibili[0][1])):
                nome = nome_predefinito(nome_dispositivo)
            self._nome = nome
            self._dati = {CONF_SLOT: slot, CONF_TIPOLOGIA: user_input[CONF_TIPOLOGIA]}
            if user_input[CONF_TIPOLOGIA] in TIPOLOGIE_CON_VERSO:
                return await self.async_step_verso()
            return self.async_create_entry(title=self._nome, data=self._dati)

        schema = vol.Schema(
            {
                vol.Required(CONF_SLOT, default=str(disponibili[0][0])): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(value=str(slot), label=f"{nome} (slot {slot})")
                            for slot, nome in disponibili
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(CONF_NOME, default=nome_predefinito(disponibili[0][1])): str,
                vol.Required(CONF_TIPOLOGIA, default=TIPOLOGIA_PREDEFINITA): _selettore_tipologia(),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_verso(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        tipologia = self._dati[CONF_TIPOLOGIA]
        if user_input is not None:
            return self.async_create_entry(
                title=self._nome, data={**self._dati, CONF_VERSO: user_input[CONF_VERSO]}
            )
        return self.async_show_form(
            step_id="verso", data_schema=_schema_verso(tipologia, VERSO_PREDEFINITO)
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return NexusNiceOptionsFlow()


class NexusNiceOptionsFlow(OptionsFlow):
    """Tipologia e verso si cambiano senza reinstallare; il nome si cambia rinominando la voce."""

    def __init__(self) -> None:
        self._tipologia = TIPOLOGIA_PREDEFINITA

    @property
    def _attuali(self) -> dict[str, Any]:
        return {**self.config_entry.data, **self.config_entry.options}

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self._tipologia = user_input[CONF_TIPOLOGIA]
            if self._tipologia in TIPOLOGIE_CON_VERSO:
                return await self.async_step_verso()
            return self.async_create_entry(data={CONF_TIPOLOGIA: self._tipologia})

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_TIPOLOGIA, default=self._attuali.get(CONF_TIPOLOGIA, TIPOLOGIA_PREDEFINITA)
                ): _selettore_tipologia()
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)

    async def async_step_verso(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                data={CONF_TIPOLOGIA: self._tipologia, CONF_VERSO: user_input[CONF_VERSO]}
            )
        return self.async_show_form(
            step_id="verso",
            data_schema=_schema_verso(self._tipologia, self._attuali.get(CONF_VERSO, VERSO_PREDEFINITO)),
        )

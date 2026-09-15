"""Prove a tavolino del config flow e del flusso delle opzioni.

La 1.0.0 falliva con un errore 500 appena aperto il flusso, su un impianto con
un bridge HomeKit (identificativo di tre elementi): questa prova rifa' quel caso.

    python tests/test_config_flow.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import finto_ha  # noqa: E402,F401  (moduli di base di Home Assistant)


def _modulo(nome: str, **attributi):
    m = types.ModuleType(nome)
    for chiave, valore in attributi.items():
        setattr(m, chiave, valore)
    sys.modules[nome] = m
    return m


# --- voluptuous, quanto basta: gli schemi si leggono, non si validano --------
class _Chiave(str):
    def __new__(cls, nome, default=None):
        s = super().__new__(cls, nome)
        s.default = default
        return s


class Required(_Chiave):
    pass


class Optional(_Chiave):
    pass


class Schema(dict):
    pass


_modulo("voluptuous", Schema=Schema, Required=Required, Optional=Optional)


# --- selettori ----------------------------------------------------------------
class SelectSelectorConfig(dict):
    def __init__(self, **kw):
        super().__init__(**kw)


class SelectSelector:
    def __init__(self, config):
        self.config = config


class SelectSelectorMode:
    LIST = "list"
    DROPDOWN = "dropdown"


def SelectOptionDict(**kw):  # noqa: N802
    return dict(kw)


_modulo(
    "homeassistant.helpers.selector",
    SelectSelector=SelectSelector,
    SelectSelectorConfig=SelectSelectorConfig,
    SelectSelectorMode=SelectSelectorMode,
    SelectOptionDict=SelectOptionDict,
)
sys.modules["homeassistant.helpers"].selector = sys.modules["homeassistant.helpers.selector"]


# --- config entries -------------------------------------------------------------
class AbortFlow(Exception):
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


class ConfigFlow:
    def __init_subclass__(cls, domain=None, **kw):
        super().__init_subclass__(**kw)
        cls.DOMAIN = domain

    def _async_current_entries(self, include_ignore=None):
        return self.hass.voci

    async def async_set_unique_id(self, unique_id):
        self.unique_id = unique_id

    def _abort_if_unique_id_configured(self):
        if any(getattr(v, "unique_id", None) == self.unique_id for v in self.hass.voci):
            raise AbortFlow("already_configured")

    def async_show_form(self, step_id, data_schema=None, errors=None):
        return {"type": "form", "step_id": step_id, "schema": data_schema}

    def async_create_entry(self, title=None, data=None):
        return {"type": "create_entry", "title": title, "data": data}

    def async_abort(self, reason):
        return {"type": "abort", "reason": reason}


class OptionsFlow:
    def async_show_form(self, step_id, data_schema=None, errors=None):
        return {"type": "form", "step_id": step_id, "schema": data_schema}

    def async_create_entry(self, title=None, data=None):
        return {"type": "create_entry", "data": data}

    def async_show_menu(self, step_id, menu_options):
        return {"type": "menu", "step_id": step_id}


_modulo(
    "homeassistant.config_entries",
    ConfigEntry=object,
    ConfigFlow=ConfigFlow,
    ConfigFlowResult=dict,
    OptionsFlow=OptionsFlow,
)


class Dispositivo:
    def __init__(self, identifiers, name, name_by_user=None):
        self.identifiers = identifiers
        self.name = name
        self.name_by_user = name_by_user


class RegistroDispositivi:
    def __init__(self, dispositivi):
        self.devices = {str(i): d for i, d in enumerate(dispositivi)}


_modulo("homeassistant.helpers.device_registry", async_get=lambda hass: hass.dispositivi)
sys.modules["homeassistant.helpers"].device_registry = sys.modules["homeassistant.helpers.device_registry"]

from nexus_nice.config_flow import NexusNiceConfigFlow, NexusNiceOptionsFlow  # noqa: E402

passate = 0
fallite: list[str] = []


def v(condizione: bool, descrizione: str) -> None:
    global passate
    if condizione:
        passate += 1
        print(f"  ok  {descrizione}")
    else:
        fallite.append(descrizione)
        print(f"  NO  {descrizione}")


class Voce:
    def __init__(self, slot, unique_id=None, data=None, options=None):
        self.data = data or {"slot": slot, "tipologia": "scorrevole", "verso": "sinistra"}
        self.options = options or {}
        self.unique_id = unique_id or f"nexus_nice_{slot}"


def hass_con(dispositivi, voci=()):
    h = types.SimpleNamespace()
    h.dispositivi = RegistroDispositivi(dispositivi)
    h.voci = list(voci)
    return h


IMPIANTO = [
    Dispositivo({("homekit", "01J8XBRIDGE", "accessory")}, "HASS Bridge"),
    Dispositivo({("mqtt", "tecnoalarm_gateway")}, "Centrale Tecnoalarm"),
    Dispositivo({("mqtt", "nexus_nice_1")}, "Nexus-T Cancello"),
    Dispositivo({("mqtt", "nexus_nice_2")}, "Nexus-T Garage", name_by_user="Box auto"),
]


def schema_campi(risultato):
    return {str(k): k for k in (risultato.get("schema") or {})}


async def flusso(hass, *passi):
    f = NexusNiceConfigFlow()
    f.hass = hass
    risultato = await f.async_step_user()
    esiti = [risultato]
    for dati in passi:
        passo = getattr(f, f"async_step_{risultato['step_id']}")
        try:
            risultato = await passo(dati)
        except AbortFlow as fine:
            risultato = {"type": "abort", "reason": fine.reason}
        esiti.append(risultato)
    return esiti


async def main():
    print("\n1. Apertura del flusso (il caso della 1.0.0)")
    [primo] = await flusso(hass_con(IMPIANTO))
    v(primo["type"] == "form" and primo["step_id"] == "user", "con un bridge HomeKit nell'impianto il modulo si apre")
    campi = schema_campi(primo)
    opzioni = campi["slot"] and primo["schema"][campi["slot"]].config["options"]
    v([o["value"] for o in opzioni] == ["1", "2"], "cancelli del gateway in ordine, niente centrale ne' bridge")
    v(opzioni[1]["label"] == "Box auto (slot 2)", "nome scelto dall'utente per il dispositivo")
    v(campi["nome"].default == "Cancello" and campi["tipologia"].default == "scorrevole", "nome proposto «Cancello», tipologia scorrevole")

    print("\n2. Scorrevole: si chiede il verso")
    esiti = await flusso(hass_con(IMPIANTO), {"slot": "1", "nome": "Cancello", "tipologia": "scorrevole"}, {"verso": "destra"})
    v(esiti[1]["step_id"] == "verso", "secondo passo: verso")
    etichette = esiti[1]["schema"][schema_campi(esiti[1])["verso"]].config["translation_key"]
    v(etichette == "verso_scorrevole", "etichette del verso dello scorrevole")
    v(esiti[2]["type"] == "create_entry" and esiti[2]["data"] == {"slot": 1, "tipologia": "scorrevole", "verso": "destra"}, "voce creata con slot, tipologia e verso")
    v(esiti[2]["title"] == "Cancello", "titolo = nome")

    print("\n3. Due ante: niente verso; nome vuoto e slot diverso")
    esiti = await flusso(hass_con(IMPIANTO), {"slot": "2", "nome": "Cancello", "tipologia": "sezionale"})
    v(esiti[1]["type"] == "create_entry" and "verso" not in esiti[1]["data"], "sezionale: voce creata senza chiedere il verso")
    v(esiti[1]["title"] == "Box auto", "scelto lo slot 2 senza toccare il nome: vale il nome di quel cancello")
    esiti = await flusso(hass_con(IMPIANTO), {"slot": "1", "nome": "  ", "tipologia": "due_ante"})
    v(esiti[1]["title"] == "Cancello" and esiti[1]["data"]["tipologia"] == "due_ante", "nome vuoto: nome del dispositivo")

    print("\n4. Cancelli gia' configurati")
    [primo] = await flusso(hass_con(IMPIANTO, [Voce(1)]))
    v([o["value"] for o in primo["schema"][schema_campi(primo)["slot"]].config["options"]] == ["2"], "lo slot gia' configurato non compare")
    [primo] = await flusso(hass_con(IMPIANTO, [Voce(1), Voce(2)]))
    v(primo["type"] == "abort" and primo["reason"] == "nessun_cancello", "tutti configurati: interruzione con spiegazione")
    [primo] = await flusso(hass_con([IMPIANTO[0], IMPIANTO[1]]))
    v(primo["type"] == "abort" and primo["reason"] == "nessun_cancello", "nessun gateway Nice: interruzione con spiegazione")
    [primo] = await flusso(hass_con(IMPIANTO, [Voce(9, data={"rotta": True})]))
    v(primo["type"] == "form", "una voce senza slot nei dati non blocca il flusso")

    print("\n5. Opzioni")
    voce = Voce(1, data={"slot": 1, "tipologia": "scorrevole", "verso": "sinistra"})
    o = NexusNiceOptionsFlow()
    o.config_entry = voce
    r = await o.async_step_init()
    v(r["step_id"] == "init" and schema_campi(r)["tipologia"].default == "scorrevole", "tipologia attuale proposta")
    r = await o.async_step_init({"tipologia": "una_anta"})
    v(r["step_id"] == "verso" and r["schema"][schema_campi(r)["verso"]].config["translation_key"] == "verso_una_anta", "un'anta: etichette della cerniera")
    v(schema_campi(r)["verso"].default == "sinistra", "verso attuale proposto")
    r = await o.async_step_verso({"verso": "destra"})
    v(r["type"] == "create_entry" and r["data"] == {"tipologia": "una_anta", "verso": "destra"}, "opzioni salvate")
    o = NexusNiceOptionsFlow()
    o.config_entry = voce
    r = await o.async_step_init({"tipologia": "basculante"})
    v(r["type"] == "create_entry" and r["data"] == {"tipologia": "basculante"}, "basculante: salvato senza verso")


asyncio.run(main())
totale = passate + len(fallite)
print(f"\nCONFIG FLOW: {passate}/{totale} superate")
sys.exit(1 if fallite else 0)

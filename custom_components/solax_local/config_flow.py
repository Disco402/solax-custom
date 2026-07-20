import voluptuous as vol
import aiohttp
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD

DOMAIN = "solax_local"

class SolaXConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SolaX Local."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the step where the user enters IP and Password."""
        errors = {}

        if user_input is not None:
            try:
                url = f"http://{user_input[CONF_HOST]}/"
                payload = {
                    "pwd": user_input[CONF_PASSWORD],
                    "optType": "ReadRealTimeData"
                }
                
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, data=payload, timeout=10) as response:
                        response.raise_for_status()
                        json_response = await response.json(content_type=None)
                        
                        if "Data" not in json_response:
                            errors["base"] = "invalid_auth"
                        else:
                            # Parse the serial number from the Information array
                            info_data = json_response.get("Information", [])
                            if len(info_data) > 2:
                                serial = str(info_data[2]).strip() 
                            else:
                                serial = json_response.get("sn", "Unknown_SolaX")
                            
                            # Prevent adding the same inverter twice
                            await self.async_set_unique_id(serial)
                            self._abort_if_unique_id_configured()

                            return self.async_create_entry(
                                title=f"SolaX ({serial})",
                                data=user_input,
                            )
                            
            except config_entries.exceptions.AbortFlow:
                raise
            except Exception:
                errors["base"] = "cannot_connect"

        data_schema = vol.Schema({
            vol.Required(CONF_HOST): str,
            vol.Required(CONF_PASSWORD): str,
        })

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )
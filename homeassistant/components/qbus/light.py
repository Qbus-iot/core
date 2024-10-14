"""Support for Qbus light."""

from typing import Any

from qbusmqttapi.discovery import QbusMqttOutput
from qbusmqttapi.state import QbusMqttAnalogState, StateType

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.components.mqtt.models import ReceiveMessage
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.color import brightness_to_value, value_to_brightness

from .const import DOMAIN
from .coordinator import QbusDataCoordinator
from .entity import QbusEntity
from .qbus import QbusEntry

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, add_entities: AddEntitiesCallback
) -> None:
    """Set up light entities."""

    hub: QbusDataCoordinator = hass.data[DOMAIN][entry.entry_id]
    hub.register_platform("analog", QbusLight, add_entities)


class QbusLight(QbusEntity, LightEntity):
    """Representation of a Qbus light entity."""

    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_color_mode = ColorMode.BRIGHTNESS

    def __init__(
        self,
        mqtt_output: QbusMqttOutput,
        qbus_entry: QbusEntry,
    ) -> None:
        """Initialize light entity."""

        super().__init__(mqtt_output, qbus_entry)

        self._is_on = False
        self._brightness_percentage = 0.0

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        return self._is_on

    @property
    def brightness(self) -> int | None:
        """Return the brightness of this light between 0..255."""
        return value_to_brightness((1, 100), self._brightness_percentage)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)

        if brightness is None:
            brightness = 255

        percentage = brightness_to_value((1, 100), brightness)

        state = QbusMqttAnalogState(id=self._mqtt_output.id, type=StateType.STATE)
        state.write_percentage(percentage)

        await self._async_publish_output_state(state)
        self._is_on = True
        self._brightness_percentage = percentage

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        state = QbusMqttAnalogState(id=self._mqtt_output.id, type=StateType.STATE)
        state.write_percentage(0)

        await self._async_publish_output_state(state)
        self._is_on = False
        self._brightness_percentage = 0.0

    async def _state_received(self, msg: ReceiveMessage) -> None:
        output = self._message_factory.parse_output_state(
            QbusMqttAnalogState, msg.payload
        )

        if output is not None:
            self._brightness_percentage = output.read_percentage()
            self._is_on = self._brightness_percentage > 0
            self.async_schedule_update_ha_state()

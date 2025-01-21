"""Support for Qbus light."""

from typing import Any

from qbusmqttapi.discovery import QbusMqttOutput
from qbusmqttapi.state import QbusMqttAnalogState, StateType

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.components.mqtt import ReceiveMessage
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.color import brightness_to_value, value_to_brightness

from .coordinator import QbusConfigEntry
from .entity import QbusEntity, add_new_outputs

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: QbusConfigEntry, add_entities: AddEntitiesCallback
) -> None:
    """Set up light entities."""

    coordinator = entry.runtime_data
    added_outputs: list[QbusMqttOutput] = []

    def _check_outputs() -> None:
        add_new_outputs(
            coordinator,
            added_outputs,
            lambda output: output.type == "analog",
            QbusLight,
            add_entities,
        )

    _check_outputs()
    entry.async_on_unload(coordinator.async_add_listener(_check_outputs))


class QbusLight(QbusEntity, LightEntity):
    """Representation of a Qbus light entity."""

    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_color_mode = ColorMode.BRIGHTNESS

    def __init__(self, mqtt_output: QbusMqttOutput) -> None:
        """Initialize light entity."""

        super().__init__(mqtt_output)

        self._set_state(0)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)

        if brightness is None:
            brightness = 255

        percentage = round(brightness_to_value((1, 100), brightness))

        state = QbusMqttAnalogState(id=self._mqtt_output.id, type=StateType.STATE)
        state.write_percentage(percentage)

        await self._async_publish_output_state(state)
        self._set_state(percentage)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        state = QbusMqttAnalogState(id=self._mqtt_output.id, type=StateType.STATE)
        state.write_percentage(0)

        await self._async_publish_output_state(state)
        self._set_state(0)

    async def _state_received(self, msg: ReceiveMessage) -> None:
        output = self._message_factory.parse_output_state(
            QbusMqttAnalogState, msg.payload
        )

        if output is not None:
            percentage = round(output.read_percentage())
            self._set_state(percentage)
            self.async_schedule_update_ha_state()

    def _set_state(self, percentage: int) -> None:
        self._attr_is_on = percentage > 0
        self._attr_brightness = value_to_brightness((1, 100), percentage)

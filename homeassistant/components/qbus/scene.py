"""Support for Qbus scene."""

from typing import Any

from qbusmqttapi.discovery import QbusMqttOutput
from qbusmqttapi.state import QbusMqttState, StateAction, StateType

from homeassistant.components.scene import Scene
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import QbusDataCoordinator
from .entity import QbusEntity
from .qbus import QbusEntry

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, add_entities: AddEntitiesCallback
) -> None:
    """Set up scene entities."""

    hub: QbusDataCoordinator = hass.data[DOMAIN][entry.entry_id]
    hub.register_platform("scene", QbusScene, add_entities)


class QbusScene(QbusEntity, Scene):
    """Representation of a Qbus scene entity."""

    def __init__(
        self,
        mqtt_output: QbusMqttOutput,
        qbus_entry: QbusEntry,
    ) -> None:
        """Initialize scene entity."""

        super().__init__(mqtt_output, qbus_entry)

    async def async_activate(self, **kwargs: Any) -> None:
        """Activate scene."""
        state = QbusMqttState(
            id=self._mqtt_output.id, type=StateType.ACTION, action=StateAction.ACTIVE
        )
        await self._async_publish_output_state(state)

"""Support for Qbus cover."""

from typing import Any

from qbusmqttapi.discovery import QbusMqttOutput
from qbusmqttapi.state import QbusMqttShutterState, StateType

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.components.mqtt.models import ReceiveMessage
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
    """Set up cover entities."""

    hub: QbusDataCoordinator = hass.data[DOMAIN][entry.entry_id]
    hub.register_platform("shutter", QbusCover, add_entities)


class QbusCover(QbusEntity, CoverEntity):
    """Representation of a Qbus cover entity."""

    _attr_device_class = CoverDeviceClass.BLIND

    def __init__(
        self,
        mqtt_output: QbusMqttOutput,
        qbus_entry: QbusEntry,
    ) -> None:
        """Initialize cover entity."""

        super().__init__(mqtt_output, qbus_entry)

        self._attr_supported_features = (
            CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
        )

        if "shutterStop" in mqtt_output.actions:
            self._attr_supported_features |= CoverEntityFeature.STOP
            self._attr_assumed_state = True

        if "shutterPosition" in mqtt_output.properties:
            self._attr_supported_features |= CoverEntityFeature.SET_POSITION

        if "slatPosition" in mqtt_output.properties:
            self._attr_supported_features |= CoverEntityFeature.SET_TILT_POSITION
            self._attr_supported_features |= CoverEntityFeature.OPEN_TILT
            self._attr_supported_features |= CoverEntityFeature.CLOSE_TILT

        self._target_shutter_position: int | None = None
        self._target_slat_position: int | None = None

        self._previous_state: str | None = None
        self._target_state: str | None = None

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed or not."""

        if self._attr_supported_features is not None:
            if self._attr_supported_features & CoverEntityFeature.SET_POSITION:
                if self._attr_supported_features & CoverEntityFeature.SET_TILT_POSITION:
                    return (
                        self._target_shutter_position == 0
                        and self._target_slat_position in (0, 100)
                    )

                return self._target_shutter_position == 0

        return self._previous_state == "down" and self._target_state == "stop"

    @property
    def current_cover_position(self) -> int | None:
        """Return current position of cover."""

        if (
            self._attr_supported_features is not None
            and self._attr_supported_features & CoverEntityFeature.SET_POSITION
        ):
            return self._target_shutter_position

        return None

    @property
    def current_cover_tilt_position(self) -> int | None:
        """Return current position of cover tilt."""

        if (
            self._attr_supported_features is not None
            and self._attr_supported_features & CoverEntityFeature.SET_TILT_POSITION
        ):
            return self._target_slat_position

        return None

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""

        state = QbusMqttShutterState(id=self._mqtt_output.id, type=StateType.STATE)

        if (
            self._attr_supported_features is not None
            and self._attr_supported_features & CoverEntityFeature.SET_POSITION
        ):
            state.write_position(100)
        else:
            state.write_state("up")

        await self._async_publish_output_state(state)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""

        state = QbusMqttShutterState(id=self._mqtt_output.id, type=StateType.STATE)

        if (
            self._attr_supported_features is not None
            and self._attr_supported_features & CoverEntityFeature.SET_POSITION
        ):
            state.write_position(0)

            if self._attr_supported_features & CoverEntityFeature.SET_TILT_POSITION:
                state.write_slat_position(0)

        else:
            state.write_state("down")

        await self._async_publish_output_state(state)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        state = QbusMqttShutterState(id=self._mqtt_output.id, type=StateType.STATE)
        state.write_state("stop")
        await self._async_publish_output_state(state)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        state = QbusMqttShutterState(id=self._mqtt_output.id, type=StateType.STATE)
        state.write_position(int(kwargs[ATTR_POSITION]))
        await self._async_publish_output_state(state)

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Open the cover tilt."""
        state = QbusMqttShutterState(id=self._mqtt_output.id, type=StateType.STATE)
        state.write_slat_position(50)
        await self._async_publish_output_state(state)

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Close the cover tilt."""
        state = QbusMqttShutterState(id=self._mqtt_output.id, type=StateType.STATE)
        state.write_slat_position(0)
        await self._async_publish_output_state(state)

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the cover tilt to a specific position."""
        state = QbusMqttShutterState(id=self._mqtt_output.id, type=StateType.STATE)
        state.write_slat_position(int(kwargs[ATTR_TILT_POSITION]))
        await self._async_publish_output_state(state)

    async def _state_received(self, msg: ReceiveMessage) -> None:
        output = self._message_factory.parse_output_state(
            QbusMqttShutterState, msg.payload
        )

        if output is None:
            return

        state = output.read_state()
        shutter_position = output.read_position()
        slat_position = output.read_slat_position()

        if state is not None:
            self._previous_state = self._target_state
            self._target_state = state

        if shutter_position is not None:
            self._target_shutter_position = shutter_position

        if slat_position is not None:
            self._target_slat_position = slat_position

        self.async_schedule_update_ha_state()

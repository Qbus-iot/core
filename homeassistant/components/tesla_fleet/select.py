"""Select platform for Tesla Fleet integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from itertools import chain

from tesla_fleet_api.const import EnergyExportMode, EnergyOperationMode, Scope, Seat

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TeslaFleetConfigEntry
from .entity import TeslaFleetEnergyInfoEntity, TeslaFleetVehicleEntity
from .helpers import handle_command, handle_vehicle_command
from .models import TeslaFleetEnergyData, TeslaFleetVehicleData

OFF = "off"
LOW = "low"
MEDIUM = "medium"
HIGH = "high"

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class SeatHeaterDescription(SelectEntityDescription):
    """Seat Heater entity description."""

    position: Seat
    available_fn: Callable[[TeslaFleetSeatHeaterSelectEntity], bool] = lambda _: True


SEAT_HEATER_DESCRIPTIONS: tuple[SeatHeaterDescription, ...] = (
    SeatHeaterDescription(
        key="climate_state_seat_heater_left",
        position=Seat.FRONT_LEFT,
    ),
    SeatHeaterDescription(
        key="climate_state_seat_heater_right",
        position=Seat.FRONT_RIGHT,
    ),
    SeatHeaterDescription(
        key="climate_state_seat_heater_rear_left",
        position=Seat.REAR_LEFT,
        available_fn=lambda self: self.get("vehicle_config_rear_seat_heaters") != 0,
        entity_registry_enabled_default=False,
    ),
    SeatHeaterDescription(
        key="climate_state_seat_heater_rear_center",
        position=Seat.REAR_CENTER,
        available_fn=lambda self: self.get("vehicle_config_rear_seat_heaters") != 0,
        entity_registry_enabled_default=False,
    ),
    SeatHeaterDescription(
        key="climate_state_seat_heater_rear_right",
        position=Seat.REAR_RIGHT,
        available_fn=lambda self: self.get("vehicle_config_rear_seat_heaters") != 0,
        entity_registry_enabled_default=False,
    ),
    SeatHeaterDescription(
        key="climate_state_seat_heater_third_row_left",
        position=Seat.THIRD_LEFT,
        available_fn=lambda self: self.get("vehicle_config_third_row_seats") != "None",
        entity_registry_enabled_default=False,
    ),
    SeatHeaterDescription(
        key="climate_state_seat_heater_third_row_right",
        position=Seat.THIRD_RIGHT,
        available_fn=lambda self: self.get("vehicle_config_third_row_seats") != "None",
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TeslaFleetConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the TeslaFleet select platform from a config entry."""

    async_add_entities(
        chain(
            (
                TeslaFleetSeatHeaterSelectEntity(
                    vehicle, description, entry.runtime_data.scopes
                )
                for description in SEAT_HEATER_DESCRIPTIONS
                for vehicle in entry.runtime_data.vehicles
            ),
            (
                TeslaFleetWheelHeaterSelectEntity(vehicle, entry.runtime_data.scopes)
                for vehicle in entry.runtime_data.vehicles
            ),
            (
                TeslaFleetOperationSelectEntity(energysite, entry.runtime_data.scopes)
                for energysite in entry.runtime_data.energysites
                if energysite.info_coordinator.data.get("components_battery")
            ),
            (
                TeslaFleetExportRuleSelectEntity(energysite, entry.runtime_data.scopes)
                for energysite in entry.runtime_data.energysites
                if energysite.info_coordinator.data.get("components_battery")
                and energysite.info_coordinator.data.get("components_solar")
            ),
        )
    )


class TeslaFleetSeatHeaterSelectEntity(TeslaFleetVehicleEntity, SelectEntity):
    """Select entity for vehicle seat heater."""

    entity_description: SeatHeaterDescription

    _attr_options = [
        OFF,
        LOW,
        MEDIUM,
        HIGH,
    ]

    def __init__(
        self,
        data: TeslaFleetVehicleData,
        description: SeatHeaterDescription,
        scopes: list[Scope],
    ) -> None:
        """Initialize the vehicle seat select entity."""
        self.entity_description = description
        self.scoped = Scope.VEHICLE_CMDS in scopes
        super().__init__(data, description.key)

    def _async_update_attrs(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_available = self.entity_description.available_fn(self)
        value = self._value
        if value is None:
            self._attr_current_option = None
        else:
            self._attr_current_option = self._attr_options[value]

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        self.raise_for_read_only(Scope.VEHICLE_CMDS)
        await self.wake_up_if_asleep()
        level = self._attr_options.index(option)
        # AC must be on to turn on seat heater
        if level and not self.get("climate_state_is_climate_on"):
            await handle_vehicle_command(self.api.auto_conditioning_start())
        await handle_vehicle_command(
            self.api.remote_seat_heater_request(self.entity_description.position, level)
        )
        self._attr_current_option = option
        self.async_write_ha_state()


class TeslaFleetWheelHeaterSelectEntity(TeslaFleetVehicleEntity, SelectEntity):
    """Select entity for vehicle steering wheel heater."""

    _attr_options = [
        OFF,
        LOW,
        HIGH,
    ]

    def __init__(
        self,
        data: TeslaFleetVehicleData,
        scopes: list[Scope],
    ) -> None:
        """Initialize the vehicle steering wheel select entity."""
        self.scoped = Scope.VEHICLE_CMDS in scopes
        super().__init__(
            data,
            "climate_state_steering_wheel_heat_level",
        )

    def _async_update_attrs(self) -> None:
        """Handle updated data from the coordinator."""

        value = self._value
        if value is None:
            self._attr_current_option = None
        else:
            self._attr_current_option = self._attr_options[value]

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        self.raise_for_read_only(Scope.VEHICLE_CMDS)
        await self.wake_up_if_asleep()
        level = self._attr_options.index(option)
        # AC must be on to turn on steering wheel heater
        if level and not self.get("climate_state_is_climate_on"):
            await handle_vehicle_command(self.api.auto_conditioning_start())
        await handle_vehicle_command(
            self.api.remote_steering_wheel_heat_level_request(level)
        )
        self._attr_current_option = option
        self.async_write_ha_state()


class TeslaFleetOperationSelectEntity(TeslaFleetEnergyInfoEntity, SelectEntity):
    """Select entity for operation mode select entities."""

    _attr_options: list[str] = [
        EnergyOperationMode.AUTONOMOUS,
        EnergyOperationMode.BACKUP,
        EnergyOperationMode.SELF_CONSUMPTION,
    ]

    def __init__(
        self,
        data: TeslaFleetEnergyData,
        scopes: list[Scope],
    ) -> None:
        """Initialize the operation mode select entity."""
        self.scoped = Scope.ENERGY_CMDS in scopes
        super().__init__(data, "default_real_mode")

    def _async_update_attrs(self) -> None:
        """Update the attributes of the entity."""
        self._attr_current_option = self._value

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        self.raise_for_read_only(Scope.ENERGY_CMDS)
        await handle_command(self.api.operation(option))
        self._attr_current_option = option
        self.async_write_ha_state()


class TeslaFleetExportRuleSelectEntity(TeslaFleetEnergyInfoEntity, SelectEntity):
    """Select entity for export rules select entities."""

    _attr_options: list[str] = [
        EnergyExportMode.NEVER,
        EnergyExportMode.BATTERY_OK,
        EnergyExportMode.PV_ONLY,
    ]

    def __init__(
        self,
        data: TeslaFleetEnergyData,
        scopes: list[Scope],
    ) -> None:
        """Initialize the export rules select entity."""
        self.scoped = Scope.ENERGY_CMDS in scopes
        super().__init__(data, "components_customer_preferred_export_rule")

    def _async_update_attrs(self) -> None:
        """Update the attributes of the entity."""
        self._attr_current_option = self.get(self.key, EnergyExportMode.NEVER.value)

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        self.raise_for_read_only(Scope.ENERGY_CMDS)
        await handle_command(
            self.api.grid_import_export(customer_preferred_export_rule=option)
        )
        self._attr_current_option = option
        self.async_write_ha_state()

"""Platform form Swicth Integration."""

from homeassistant.components.switch import SwitchEntity
import logging

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
  """Add switch."""
  hub = hass.data[DOMAIN][config_entry.entry_id]

  new_devices = []
  for vm in hub.vms:

    new_devices.append(VMSwitch(vm))
  for cd in hub.cdomains:
    new_devices.append(CDSwitch(cd))
    # new_devices.append(CDSwitch(vm))
    # new_devices.append(CDSwitch(vm))
  if new_devices:
    async_add_entities(new_devices)


class VMSwitch(SwitchEntity):
  """Virtual Machine Switch."""

  _attr_has_entity_name = True

  should_poll = False

  def __init__(self, vm):
    """Init."""
    self._vm = vm
    # self.log(self._vm)
    self._attr_unique_id = f"{self._vm.vm_id}_vm_switch"
    self._attr_name = "vm power" # self._vm.name
    self._power_state = self._vm.status
    self._is_on = False
    self._status = self._vm.status
    self.on_status = "Running"

  def log(self, data):
    """Log."""
    _LOGGER.info(data)

  @property
  def device_info(self):
    """Device Info."""
    return {
      "identifiers": {(DOMAIN, self._vm.vm_id)},
      "name": f"vm_{self._vm.name}"
    }

  @property
  def is_on(self):
    """If VM is Running."""
    return self.on_status == self._vm.status

  async def async_added_to_hass(self):
    """Add to callback."""
    await self._vm.register_callback(self.async_write_ha_state)

  async def async_will_remove_from_hass(self):
    """Remove from callback."""
    await self._vm.remove_callback(self.async_write_ha_state)

  def turn_on(self, **kwargs):
    """Turn ON VM."""
    self._is_on = True

  async def async_turn_on(self, **kwargs):
    """Turn on VM."""
    self.log(f"STARTING VM: {self._vm.vm_id}")
    # self._vm._vmi["power_state"] = self.on_status
    await self._vm.start()

  def turn_off(self, **kwargs):
    """Turn OFF VM."""
    self._is_on = False

  async def async_turn_off(self, **kwargs):
    """Turn off VM."""
    self.log(f"STOPPING VM: {self._vm.vm_id}")
    # self._vm._vmi["power_state"] = "OFF"
    await self._vm.stop()

  # async def async_update(self):
  #   """Update VM Data."""
  #   # self.log(f"{self._attr_unique_id}: Updating...")
  #   await self._vm.update()
  #   self._status = self._vm.status
  #   # self.log(f"{self._attr_unique_id}: Updated...")


class CDSwitch(SwitchEntity):
  """Virtual Machine Switch."""

  _attr_has_entity_name = True

  should_poll = False

  def __init__(self, vm):
    """Init."""
    self._vm = vm
    self._attr_unique_id = f"{self._vm.vm_id}_cd_switch"
    self._attr_name = "cd power" # self._vm.name
    self._is_on = False
    self.on_status = "Running"

  @property
  def device_info(self):
    """Device Info."""
    return {
      "identifiers": {(DOMAIN, self._vm.vm_id)},
      "name": f"cd_{self._vm.name}"

    }

  @property
  def is_on(self):
    """If VM is Running."""
    return self.on_status == self._vm.status

  def turn_on(self, **kwargs):
    """Turn ON VM."""
    self._is_on = True

  async def async_turn_on(self, **kwargs):
    """Turn on VM."""

  def turn_off(self, **kwargs):
    """Turn OFF VM."""
    self._is_on = False

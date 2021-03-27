from datetime import timedelta
import requests

from homeassistant.helpers.update_coordinator import (
  CoordinatorEntity,
  DataUpdateCoordinator,
  UpdateFailed,
)
import logging

from .const import DOMAIN, DEVICES, CONF_FAN_NAME, CONF_FAN_HOST, CONF_ENABLE_LIGHT

_LOGGER = logging.getLogger(__name__)

def setup(hass, config):
  hass.data[DOMAIN] = {}
  hass.data[DOMAIN][DEVICES] = {}

  return True

async def async_setup_entry(hass, config_entry):
  fan = config_entry.data
  name = fan.get(CONF_FAN_NAME)
  host = fan.get(CONF_FAN_HOST)
  has_light = fan.get(CONF_ENABLE_LIGHT)

  device = ModernFormsDevice(name, host, has_light)

  async def update_status():
    try:
      await hass.async_add_executor_job(device.update_status)
    except Exception as err:
      raise UpdateFailed(f"Error communicating with modern forms device: {err}")

  coordinator = DataUpdateCoordinator(
    hass,
    _LOGGER,
    # Name of the data. For logging purposes.
    name="sensor",
    update_method=update_status,
    # Polling interval. Will only be polled if there are subscribers.
    update_interval=timedelta(seconds=60),
  )

  hass.data[DOMAIN][DEVICES][host] = {
    "device": device,
    "coordinator": coordinator
  }

  # Fetch initial data so we have data when entities subscribe
  await coordinator.async_refresh()

  hass.async_create_task(
    hass.config_entries.async_forward_entry_setup(
      config_entry, "fan"
    )
  )

  if has_light:
    hass.async_create_task(
      hass.config_entries.async_forward_entry_setup(
        config_entry, "light"
      )
    )

  return True

class ModernFormsBaseEntity(CoordinatorEntity):
  def __init__(self, device, coordinator: DataUpdateCoordinator):
    super().__init__(coordinator)
    self.device = device
    self.device._attach(self)

  def _device_updated(self):
    self.schedule_update_ha_state()

  @property
  def device_state_attributes(self):
    return self.device.data

class ModernFormsDevice:
  def __init__(self, name, host, has_light=False):
    self.url = "http://{}/mf".format(host)
    self.name = name
    self.data = {}
    self.has_light = has_light
    self.subscribers = []


  def _attach(self, sub):
    self.subscribers.append(sub)

  def _notify(self):
    for sub in self.subscribers:
      sub._device_updated()

  def clientId(self):
    return self.data.get("clientId", None)

  def fanOn(self):
    return self.data.get("fanOn", False)

  def fanSpeed(self):
    return self.data.get("fanSpeed", None)

  def fanDirection(self):
    return self.data.get("fanDirection", None)

  def lightOn(self):
    return self.data.get("lightOn", False)

  def lightBrightness(self):
    return self.data.get("lightBrightness", 0)

  def set_fan_on(self):
    self._send_request({"fanOn": 1})

  def set_fan_off(self):
    self._send_request({"fanOn": 0})

  def set_fan_speed(self, speed):
    if speed < 1:
      speed = 1
    elif speed > 6:
      speed = 6
    self._send_request({"fanOn": 1, "fanSpeed": speed})

  def set_fan_direction(self, direction):
    self._send_request({"fanDirection": direction})

  def set_light_on(self):
    self._send_request({"lightOn": 1})

  def set_light_off(self):
    self._send_request({"lightOn": 0})

  def set_light_brightness(self, level):
    if level < 1:
      level = 1
    elif level > 100:
      level = 100
    self._send_request({"lightOn": 1, "lightBrightness": level})

  def update_status(self):
    self._send_request({"queryDynamicShadowData": 1})

  def _send_request(self, data):
    r = requests.post(self.url, json=data)
    r.raise_for_status()
    self.data = r.json()
    self._notify()

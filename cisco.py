"""Support for Cisco 3850 series switches.

Handles stacking of switches.
"""
import abc
import device


class CiscoSwitch(device.DeviceModel):

  def clear_config(self):
    """Remove all persistent configuration from device."""
    self._write(b'set SWITCH_IGNORE_STARTUP_CFG 1\n')
    # Needed for reseting the above later, but also good to have in general
    self._write(b'set ENABLE_BREAK 1\n')
    self._read_line(['switch: '])

  def boot(self):
    """Boot device."""
    self._write(b'boot\n')

  def set_switch_number(self, num):
    """Configure switch stack identity."""
    # Set stack member 1 to prio 14, stack member 2 prio 13 and so on
    prio = 15 - num
    self._write(b'set SWITCH_NUMBER ' + str(num).encode() + b'\n')
    self._read_line(['switch: '])
    self._write(b'set SWITCH_PRIORITY ' + str(prio).encode() + b'\n')
    self._read_line(['switch: '])

  def wait_for_boot_complete(self):
    """Wait for system bootup complete."""
    while True:
      cisco_config_prompt = (
              'Would you like to enter the initial configuration dialog\? \[yes/no\]: ')
      cisco_booted = '.*Press RETURN to get started.*'
      line = self._read_line([cisco_config_prompt, cisco_booted, '.*Switch>'])
      if line == cisco_config_prompt:
        self._write(b'no\n')
        continue
      # Even though Cisco says that you can press enter to get started,
      # it might take a while to wake up
      old_timeout = self.port.timeout
      self.port.timeout = 10
      for i in range(10):
        try:
          self._write(b'\r')
          self._read_line(['.*Switch>'])
          break
        except device.DeviceTimeoutError:
          print('Console not responsive yet, retrying')
      self.port.timeout = old_timeout
      self._clear_buffer()
      return


class Cisco3850(CiscoSwitch):

  def __init__(self, port):
    self.port = port
    self._is_stack_primary = None

  @staticmethod
  def matches_model(model):
    return model.startswith('WS-C3850-')

  def is_potentially_stack(self):
    """If the device will potentially be part of a stack."""
    return True

  def is_stack_primary(self):
    """If the device is the primary switch in the stack."""
    # If the mgmt if is up, we consider this device to be the primary.
    if self._is_stack_primary == None:
      self._is_stack_primary = self._probe_mgmt_if()
    return self._is_stack_primary

  def _probe_mgmt_if(self):
    """Detect management if port status."""
    self._write(b'mgmt_init\n')
    mgmt_up = 'switch: '
    mgmt_down = '.*PHY link is down'
    line = self._read_line([mgmt_up, mgmt_down])
    if line != mgmt_up:
      # Make sure to read the extra stuff before we return
      self._read_line(['switch: '])
    return (line == mgmt_up)

  def configure(self):
    """Bring the device to a state where swboot can configure it."""
    # Password recovery on Cisco devices shuts down all interfaces,
    # so we have to bring them up explicitly and then reload for
    # auto install to do its thing
    # Erase config on master device and reload both
    if self._is_stack_primary:
      self._clear_buffer()
      self.poke()
      self._write(b'en\n')
      self._write(b'wr erase\n')
      self._write(b'\n')
      self._write(b'reload\n')
      self._write(b'\n')
    self.wait_for_bootloader()
    self._write(b'set SWITCH_IGNORE_STARTUP_CFG 0\n')
    self._read_line(['switch: '])
    self._write(b'boot\n')



from absl import app
from absl import flags
import os
import re
import serial
import sys


FLAGS = flags.FLAGS
flags.DEFINE_string('serial', '/dev/ttyUSB0', 'Serial device to manage')
flags.DEFINE_integer('baud', 9600, 'Serial baud rate')
flags.DEFINE_integer('timeout', 180, 'Device timeout before resetting state')
flags.DEFINE_bool('boot', True, 'Execute boot after init')


class Error(Exception):
  """Base exception for this module"""


class DeviceTimeoutError(Error):
  """A timeout happened while reading from device."""


class UnsupportedDeviceError(Error):
  """The operation is not known how to do on the given device."""


class Device(object):
  def __init__(self, port):
    self.port = port
    self.model = None
    self.mgmt_if_status = None

  def _read_line(self, stops, rest=False):
    line = ''
    while True:
      b = self.port.read()
      if len(b) == 0:
        raise DeviceTimeoutError()

      try:
        # Skip invalid UTF-8 characters
        b.decode()
      except UnicodeDecodeError:
        continue

      if b == b'\n' or b == b'\r':
        if rest:
          # If asked for the rest of line, abort if we hit it
          print()
          return line
        if line != '':
          print()
        line = ''
      else:
        line = line + b.decode()
        sys.stdout.write('Line is now: "' + line + '"\r')
        sys.stdout.flush()
      for stop in stops:
        if re.match(stop, line):
          print()
          return stop

  def wait_for_bootloader(self):
    """Wait for bootloader, most commonly ROMMON.

    During boot we will try to identify the device and
    return when the device is in this bootloader.
    """
    # TODO(bluecmd): Only cisco switches are supported right now
    self._read_line(['switch: '])

  def learn_model(self):
    """Figure out what model the device is."""

    self.port.write(b'set\n')
    self._read_line(['MODEL_NUM='])
    self.model = self._read_line([], rest=True)
    self._read_line(['switch: '])
    print('Model is:', self.model)

  def has_mgmt_interface(self):
    """If the device has an Ethernet management interface."""
    if self.model.startswith('WS-C3850-'):
      return True
    return False

  def probe_mgmt_if(self):
    """Detect management if port status."""
    self.port.write(b'mgmt_init\n')
    mgmt_up = 'switch: '
    mgmt_down = '.*PHY link is down'
    line = self._read_line([mgmt_up, mgmt_down])
    self.mgmt_if_status = (line == mgmt_up)
    if line != mgmt_up:
      # Make sure to read the extra stuff before we return
      self._read_line(['switch: '])

  def poke(self):
    """Send CR to solicit any response from the device."""
    self.port.write(b'\n')

  def clear_config(self):
    """Remove all persistent configuration from device."""
    if self.model.startswith('WS-C3850-'):
      self.port.write(b'set SWITCH_IGNORE_STARTUP_CFG 1\n')
    else:
      raise UnsupportedDeviceError(self.model)
    self._read_line(['switch: '])

  def boot(self):
    """Boot device."""
    self.port.write(b'boot\n')

  def set_switch_number(self, num, prio):
    """Configure switch stack identity."""
    if self.model.startswith('WS-C3850-'):
      self.port.write(b'set SWITCH_NUMBER ' + str(num).encode() + b'\n')
      self._read_line(['switch: '])
      self.port.write(b'set SWITCH_PRIORITY ' + str(prio).encode() + b'\n')
      self._read_line(['switch: '])

  def wait_for_boot_complete(self):
    """Wait for system bootup complete."""
    cisco_config_prompt = (
            'Would you like to enter the initial configuration dialog\? \[yes/no\]: ')
    cisco_booted = 'Press RETURN to get started'
    line = self._read_line([cisco_config_prompt, cisco_booted])
    if line == cisco_config_prompt:
      self.port.write(b'no\n')
    return

  def configure(self):
    """Bring the device to a state where swboot can configure it."""
    # Password recovery on Cisco devices shuts down all interfaces,
    # so we have to bring them up explicitly and then reload for
    # auto install to do its thing
    if self.model.startswith('WS-C3850-') and self.mgmt_if_status:
      self.poke()
      self.port.write(b'en\n')
      self.port.write(b'conf t\n')
      self.port.write(b'int vlan 1\n')
      self.port.write(b'no shut\n')
      self.port.write(b'end\n')
      self.port.write(b'reload\n')
      self.port.write(b'no\n')
      self.port.write(b'\n')


class Events(object):

  def __init__(self):
    self.last_state = 'timeout'

  def detected(self):
    """Play discovery sound to inform operator we have it from here."""
    self.last_state = 'detected'
    os.system('aplay detected.wav')

  def timeout(self):
    """Play reset sound to inform operator we're ready again."""
    # Never loop this if we haven't detected a device since last time
    if self.last_state == 'timeout':
      return
    self.last_state = 'timeout'
    os.system('aplay reset.wav')


def main(argv):
  del argv  # Unused
  print('Using device', FLAGS.serial)
  # Why are we using a timeout?
  # This means that we will get an interupt exception after a while
  # so we can avoid getting stuck if somebody disconnects the switch
  # mid-way.
  port = serial.Serial(FLAGS.serial, FLAGS.baud, timeout=FLAGS.timeout)
  device = Device(port)
  events = Events()

  while True:
    try:
      # Poke the port in case it's already ready
      device.poke()

      # State 0: wait for bootloader prompt (ROMMON or so)
      device.wait_for_bootloader()

      print('Detected bootloader')
      events.detected()

      device.learn_model()

      if device.has_mgmt_interface():
        print('Probing management interface')
        device.probe_mgmt_if()
        # If the mgmt if is up, we consider this device to be the no 1 switch
        # otherwise no 2.
        if device.mgmt_if_status:
          print('Switch is no 1')
          device.set_switch_number(1, 14)
        else:
          print('Switch is no 2')
          device.set_switch_number(2, 1)

      device.clear_config()
      print('Done')
      if not FLAGS.boot:
        print('No-boot mode, sleeping for 10 seconds instead')
        import time
        time.sleep(10)
        continue

      device.boot()

      # Boot and answer any init prompts
      device.wait_for_boot_complete()

      # Install basic configure for the device for it to continue with
      # using swboot for real configuration
      device.configure()

    except DeviceTimeoutError:
      print('Device timed out, resetting state')
      events.timeout()


if __name__ == '__main__':
  app.run(main)

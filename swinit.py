from absl import app
from absl import flags
import os
import re
import serial
import sys
import time


FLAGS = flags.FLAGS
flags.DEFINE_string('serial', '/dev/ttyUSB0', 'Serial device to manage')
flags.DEFINE_integer('baud', 9600, 'Serial baud rate')
flags.DEFINE_integer('timeout', 600, 'Device timeout before resetting state')
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
          print('->', line)
          return line
        if line != '':
          print('>', line)
        line = ''
      else:
        line = line + b.decode()
      for stop in stops:
        if re.match(stop, line):
          print('->', line)
          return stop

  def _write(self, data):
    print('<', data)
    self.port.write(data)

  def wait_for_bootloader(self):
    """Wait for bootloader, most commonly ROMMON.

    During boot we will try to identify the device and
    return when the device is in this bootloader.
    """
    # TODO(bluecmd): Only cisco switches are supported right now
    break_prompt = (
            'Interrupt the system within 5 seconds to intervene\.')
    boot_prompt = 'switch: '
    line = self._read_line([break_prompt, boot_prompt])
    if line == break_prompt:
      for i in range(1, 3):
        time.sleep(1)
        self.port.send_break()
      # Sending breaks is a bit messy as can be seen above, so clear
      # buffer
      old_timeout = self.port.timeout
      self.port.timeout = 1
      while len(self.port.read()) > 0:
        pass
      self.port.timeout = old_timeout
      self.poke()
      self._read_line([boot_prompt])
    print('Entered bootloader')

  def learn_model(self):
    """Figure out what model the device is."""

    self._write(b'set\n')
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
    self._write(b'mgmt_init\n')
    mgmt_up = 'switch: '
    mgmt_down = '.*PHY link is down'
    line = self._read_line([mgmt_up, mgmt_down])
    self.mgmt_if_status = (line == mgmt_up)
    if line != mgmt_up:
      # Make sure to read the extra stuff before we return
      self._read_line(['switch: '])

  def poke(self):
    """Send CR to solicit any response from the device."""
    self._write(b'\n')

  def clear_config(self):
    """Remove all persistent configuration from device."""
    if self.model.startswith('WS-C3850-'):
      self._write(b'set SWITCH_IGNORE_STARTUP_CFG 1\n')
      # Needed for reseting the above later, but also good to have in general
      self._write(b'set ENABLE_BREAK 1\n')
    else:
      raise UnsupportedDeviceError(self.model)
    self._read_line(['switch: '])

  def boot(self):
    """Boot device."""
    self._write(b'boot\n')

  def set_switch_number(self, num, prio):
    """Configure switch stack identity."""
    if self.model.startswith('WS-C3850-'):
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
      line = self._read_line([cisco_config_prompt, cisco_booted])
      if line == cisco_config_prompt:
        self._write(b'no\n')
      if line == cisco_booted:
        # Even though Cisco says that you can press enter to get started,
        # it might take a while to wake up
        time.sleep(1)
        self.poke()
        time.sleep(1)
        self.poke()
        time.sleep(1)
        self.poke()
        return

  def configure(self):
    """Bring the device to a state where swboot can configure it."""
    # Password recovery on Cisco devices shuts down all interfaces,
    # so we have to bring them up explicitly and then reload for
    # auto install to do its thing
    if self.model.startswith('WS-C3850-'):
      # Erase config on master device and reload both
      if self.mgmt_if_status:
        self.poke()
        self._write(b'en\n')
        self._write(b'wr erase\n')
        self._write(b'\n')
        self._write(b'reload\n')
        self._write(b'no\n')
        self._write(b'\n')
      self.wait_for_bootloader()
      self._write(b'set SWITCH_IGNORE_STARTUP_CFG 0\n')
      self._read_line(['switch: '])
      self._write(b'boot\n')


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

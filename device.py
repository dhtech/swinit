import abc
import re
import time


class Error(Exception):
  """Base exception for this module"""


class DeviceTimeoutError(Error):
  """A timeout happened while reading from device."""


class UnsupportedDeviceError(Error):
  """The operation is not known how to do on the given device."""


class Device(object):

  def __init__(self, port, model=None):
    self.port = port
    self.model = None

  def _read_line(self, stops, rest=False):
    line = ''
    while True:
      b = self.port.read()
      if len(b) == 0:
        print('T>', line)
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

  def _clear_buffer(self):
    old_timeout = self.port.timeout
    self.port.timeout = 1
    while len(self.port.read()) > 0:
      pass
    self.port.timeout = old_timeout

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
      for i in range(0, 3):
        time.sleep(1)
        self.port.send_break()
      # Sending breaks is a bit messy as can be seen above, so clear buffer
      self._clear_buffer()
      self.poke()
      self._read_line([boot_prompt])
    print('Entered bootloader')

  def learn_model(self):
    """Figure out what model the device is."""
    self._write(b'version\n')
    self._write(b'set\n')
    c2950_marker = '.*C2950-HBOOT.*'
    has_model_marker = 'MODEL_NUM='
    hit = self._read_line([has_model_marker, c2950_marker])
    model = None
    if hit == c2950_marker:
      model = 'WS-C2950'
    elif hit == has_model_marker:
      model = self._read_line([], rest=True)
    self._read_line(['switch: '])
    return model

  def poke(self):
    """Send LF to solicit a response from the device."""
    self._write(b'\n')


class DeviceModel(Device, metaclass=abc.ABCMeta):

  @staticmethod
  @abc.abstractmethod
  def matches_model(model):
    """Whether this model is associated with the given model string."""
    pass

  @abc.abstractmethod
  def is_potentially_stack(self):
    """If the device will potentially be part of a stack."""
    pass

  @abc.abstractmethod
  def is_stack_primary(self):
    """If the device is the primary switch in the stack."""
    pass

  @abc.abstractmethod
  def clear_config(self):
    """Remove all persistent configuration from device."""
    pass

  @abc.abstractmethod
  def boot(self):
    """Boot device."""
    pass

  @abc.abstractmethod
  def set_switch_number(self, num, prio):
    """Configure switch stack identity."""
    pass

  @abc.abstractmethod
  def wait_for_boot_complete(self):
    """Wait for system bootup complete."""
    pass

  @abc.abstractmethod
  def configure(self):
    """Bring the device to a state where swboot can configure it."""
    pass

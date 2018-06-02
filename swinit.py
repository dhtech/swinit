from absl import app
from absl import flags
import os
import serial


FLAGS = flags.FLAGS
flags.DEFINE_string('serial', '/dev/ttyUSB0', 'Serial device to manage')
flags.DEFINE_integer('baud', 9600, 'Serial baud rate')
flags.DEFINE_integer('timeout', 60, 'Device timeout before resetting state')


class Error(Exception):
  """Base exception for this module"""


class DeviceTimeoutError(Error):
  """A timeout happened while reading from device."""


class Device(object):
  def __init__(self, port):
    self.port = port

  def wait_for_bootloader(self):
    """Wait for bootloader, most commonly ROMMON.

    During boot we will try to identify the device and
    return when the device is in this bootloader.
    """
    # TODO(bluecmd): Only cisco switches are supported right now
    line = ""
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
        line = ""
      else:
        line = line + b.decode()
      print("Line is now: '" + line + "'")
      if line == "switch: ":
        return

  def poke(self):
    """Send CR to solicit any response from the device."""
    self.port.write(b'\n')


class Events(object):

  def __init__(self):
    self.last_state = 'reset'

  def detected(self):
    """Play discovery sound to inform operator we have it from here."""
    self.last_state = 'detected'
    os.system("aplay detected.wav")

  def reset(self):
    """Play reset sound to inform operator we're ready again."""
    # Never loop this if we haven't detected a device since last time
    if self.last_state == 'reset':
      return
    self.last_state = 'reset'
    os.system("aplay reset.wav")


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

      print("Detected bootloader")
      events.detected()

      print("Done")
    except DeviceTimeoutError:
      print("Device timed out, resetting state")
      events.reset()


if __name__ == '__main__':
  app.run(main)

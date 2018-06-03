#!/usr/bin/env python3.6
from absl import app
from absl import flags
import os
import serial
import sys

# Device support
import cisco
import device


FLAGS = flags.FLAGS
flags.DEFINE_string('serial', '/dev/ttyUSB0', 'Serial device to manage')
flags.DEFINE_integer('baud', 9600, 'Serial baud rate')
flags.DEFINE_integer('timeout', 600, 'Device timeout before resetting state')


class Error(Exception):
  """Base exception for this module"""


class UnsupportedDeviceError(Error):
  """The operation is not known how to do on the given device."""


class Events(object):

  def __init__(self):
    self.last_state = 'timeout'

  def detected(self):
    """Play discovery sound to inform operator we have it from here."""
    self.last_state = 'detected'
    os.system('aplay detected.wav')

  def unsupported(self):
    """Play sound to inform operator we don't support this device."""
    self.last_state = 'unsupported'
    # TODO(bluecmd): Other sound for this
    os.system('aplay reset.wav')
    os.system('aplay reset.wav')
    os.system('aplay reset.wav')

  def timeout(self):
    """Play reset sound to inform operator we're ready again."""
    # Never loop this if we haven't detected a device since last time
    if self.last_state == 'timeout':
      return
    self.last_state = 'timeout'
    os.system('aplay reset.wav')


def loop(port, events):
  # Start with a unknwon anonymous device and try to learn what device we have
  thing = device.Device(port)

  # Poke the port in case it's already ready
  thing.poke()

  # Wait for bootloader prompt (ROMMON or so)
  thing.wait_for_bootloader()

  print('Detected bootloader')
  events.detected()

  model = thing.learn_model()
  print('Model is', model)
  if cisco.Cisco3850.matches_model(model):
    thing = cisco.Cisco3850(port)
  elif cisco.Cisco2950.matches_model(model):
    thing = cisco.Cisco2950(port)
  else:
    raise UnsupportedDeviceError(model)

  if thing.is_potentially_stack():
    if thing.is_stack_primary():
      print('Switch is no 1')
      thing.set_switch_number(1)
    else:
      # TODO(bluecmd): We only support stacks of two right now
      print('Switch is no 2')
      thing.set_switch_number(2)

  thing.clear_config()

  thing.boot()

  thing.wait_for_boot_complete()

  # Install basic configure for the device for it to continue with
  # using swboot for real configuration
  thing.configure()

  # Return the final thing object for testing frameworks to be able
  # to verify state
  return thing


def main(argv):
  del argv  # Unused
  print('Using device', FLAGS.serial)

  # Why are we using a timeout?
  # This means that we will get an interupt exception after a while
  # so we can avoid getting stuck if somebody disconnects the switch
  # mid-way.
  port = serial.Serial(FLAGS.serial, FLAGS.baud, timeout=FLAGS.timeout)
  events = Events()

  while True:
    try:
      loop(port, events)
      print('#### Configuration done, resetting state for new device ####')
    except UnsupportedDeviceError as e:
      print('Unsupported device encountered, resetting state: ', str(e))
      events.unsupported()
    except device.DeviceTimeoutError:
      print('Device timed out, resetting state')
      events.timeout()


if __name__ == '__main__':
  app.run(main)

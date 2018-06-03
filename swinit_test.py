#!/usr/bin/env python3.6
from absl.testing import absltest
from unittest import mock

import device
import swinit
import swinit_test_lib


class GenericTestCase(absltest.TestCase):

  def test_unsupported_device_flow(self):
    port = swinit_test_lib.FakeSerial()
    port.wait_for('\n')
    port.say('switch: ')
    port.wait_for('set\n')
    port.say('MODEL_NUM=superswitch\n')
    port.say('switch: ')
    events = mock.MagicMock(swinit.Events)
    self.assertRaises(
            swinit.UnsupportedDeviceError, swinit.loop, port.fake, events)

  def test_timeout_initially_flow(self):
    port = swinit_test_lib.FakeSerial()
    events = mock.MagicMock(swinit.Events)
    self.assertRaises(
            device.DeviceTimeoutError, swinit.loop, port.fake, events)


if __name__ == '__main__':
  absltest.main()

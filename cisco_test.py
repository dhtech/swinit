#!/usr/bin/env python3.6
from absl.testing import absltest
from unittest import mock

import device
import swinit
import swinit_test_lib


class CiscoTestCase(absltest.TestCase):

  # Mock out time to make sleep a no-op
  # (used during BREAK to get into bootloader)
  @mock.patch.object(device, 'time')
  def test_3850_primary_flow(self, mock_time):
    port = swinit_test_lib.FakeSerial()
    port.wait_for('\n')
    port.say('switch: ')
    port.wait_for('set\n')
    port.say('MODEL_NUM=WS-C3850-12S\n')
    port.say('switch: ')
    port.wait_for('mgmt_init\n')
    #port.say('Interface GE 0 link down***ERROR: PHY link is down')
    port.say('switch: ')
    port.wait_for('set SWITCH_NUMBER 1\n')
    port.say('switch: ')
    port.wait_for('set SWITCH_PRIORITY 14\n')
    port.say('switch: ')
    port.wait_for('set SWITCH_IGNORE_STARTUP_CFG 1\n')
    port.say('switch: ')
    port.wait_for('set ENABLE_BREAK 1\n')
    port.say('switch: ')
    port.wait_for('boot\n')
    port.say('Would you like to enter the initial configuration dialog? [yes/no]: ')
    port.wait_for('no\n')
    port.say('Press RETURN to get started!')
    port.wait_for('\r')
    port.say('YUNKYUMNKYNKSwitch>YNKYUNK')
    port.wait_for('reload\n')
    port.say('Interrupt the system within 5 seconds to intervene.')
    port.wait_for_break()
    port.wait_for_break()
    port.wait_for_break()
    port.wait_for('\n')
    port.say('switch: ')
    port.wait_for('set SWITCH_IGNORE_STARTUP_CFG 0\n')
    port.say('switch: ')
    port.wait_for('boot\n')
 
    events = mock.MagicMock(swinit.Events)
    thing = swinit.loop(port.fake, events)
    assert thing.is_stack_primary()


if __name__ == '__main__':
  absltest.main()

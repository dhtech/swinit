#!/usr/bin/env python3.6
from absl.testing import absltest
from unittest import mock

import device
import swinit
import swinit_test_lib


class CiscoTestCase(absltest.TestCase):

  def setup_c3850_script(self, port, primary):
    port.wait_for('\n')
    port.say('switch: ')
    port.wait_for('set\n')
    port.say('MODEL_NUM=WS-C3850-12S\n')
    port.say('switch: ')
    port.wait_for('mgmt_init\n')
    if not primary:
      port.say('Interface GE 0 link down***ERROR: PHY link is down')
    port.say('switch: ')
    if primary:
      port.wait_for('set SWITCH_NUMBER 1\n')
      port.say('switch: ')
      port.wait_for('set SWITCH_PRIORITY 14\n')
      port.say('switch: ')
    else:
      port.wait_for('set SWITCH_NUMBER 2\n')
      port.say('switch: ')
      port.wait_for('set SWITCH_PRIORITY 13\n')
      port.say('switch: ')
    port.wait_for('set SWITCH_IGNORE_STARTUP_CFG 1\n')
    port.say('switch: ')
    port.wait_for('set ENABLE_BREAK 1\n')
    port.say('switch: ')
    port.wait_for('boot\n')
    port.say('Would you like to enter the initial configuration dialog? [yes/no]: ')
    port.wait_for('no\n')
    port.say('Press RETURN to get started!')
    # Ignore the first \r to run the retry-logic
    port.wait_for('\r')
    port.wait_for('\r')
    port.say('YUNKYUMNKYNKSwitch>YNKYUNK')
    # We're purging any log lines we don't care about at this point, so
    # emulate a clean terminal to say "things have calmed down, continue".
    port.timeout()
    if primary:
      port.wait_for('reload\n')
    port.say('\nInterrupt the system within 5 seconds to intervene.')
    port.wait_for_break()
    port.wait_for_break()
    port.wait_for_break()
    port.wait_for('\n')
    port.say('switch: ')
    port.wait_for('set SWITCH_IGNORE_STARTUP_CFG 0\n')
    port.say('switch: ')
    port.wait_for('boot\n')

  # Mock out time to make sleep a no-op
  # (used during BREAK to get into bootloader)
  @mock.patch.object(device, 'time')
  def test_3850_primary_flow(self, mock_time):
    port = swinit_test_lib.FakeSerial()
    self.setup_c3850_script(port, primary=True)
    events = mock.MagicMock(swinit.Events)
    thing = swinit.loop(port.fake, events)
    assert thing.is_stack_primary()

  @mock.patch.object(device, 'time')
  def test_3850_secondary_flow(self, mock_time):
    port = swinit_test_lib.FakeSerial()
    self.setup_c3850_script(port, primary=False)
    events = mock.MagicMock(swinit.Events)
    thing = swinit.loop(port.fake, events)
    assert not thing.is_stack_primary()

  def test_2950_flow(self):
    port = swinit_test_lib.FakeSerial()
    port.wait_for('\n')
    port.say('switch: ')
    port.wait_for('version\n')
    port.say('C2950 Boot Loader (C2950-HBOOT-M) Version 12.1(11r)EA1\n')
    port.say('Compiled blahbahba\n')
    port.say('switch: ')
    port.wait_for('flash_init\n')
    port.say('...done initializing flash.')
    port.say('switch: ')
    for i in ['config.text', 'vlan.dat', 'private-config.text', 'env_vars']:
      port.wait_for('del flash:/' + i + '\n')
      port.say('Are you sure you want to delete "flash:/' + i + '" (y/n)?\n')
      port.wait_for('y\n')
      port.say('switch: ')
    port.wait_for('boot\n')
    port.say('Would you like to enter the initial configuration dialog? [yes/no]: ')
    port.wait_for('no\n')
    port.say('Press RETURN to get started!')
    # Ignore the first \r to run the retry-logic
    port.wait_for('\r')
    port.wait_for('\r')
    port.say('YUNKYUMNKYNKSwitch>YNKYUNK')
    # We're purging any log lines we don't care about at this point, so
    # emulate a clean terminal to say "things have calmed down, continue".
    port.timeout()
    port.wait_for('reload\n')
    events = mock.MagicMock(swinit.Events)
    thing = swinit.loop(port.fake, events)

if __name__ == '__main__':
  absltest.main()

import swinit


TRIGGER_BREAK = 'BREAK'


class _FakeSerialImpl(object):
  def __init__(self, parent):
    self.parent = parent
    self.timeout = None

  def send_break(self):
    self.parent.mock_send_break()

  def write(self, data):
    for c in data:
      self.parent.mock_write(bytes([c]))

  def read(self):
    return self.parent.mock_read()


class FakeSerial(object):
  """Scripted serial conversation emulator.

  The way this works is by having a script buffer and a
  trigger queue.

  Every time you call say(X) it will concatenate X with the
  previous buffer and output this when read() is called on
  the fake port.

  If you call wait_for(X) the active buffer is swapped to a new
  buffer that will be active first when the fake port
  has read the data X.

  Calling these functions when reading/writing to the fake port
  has started is *unsupported*.

  Example:
    port.say("switch: ")     # Print straight away
    port.wait_for("set\n")   # Wait for incoming text
    port.say("Hello")        # Then write this
  """

  def __init__(self):
    self.fake = _FakeSerialImpl(self)
    self.buffers = [b'']
    self.read_idx = 0
    self.write_buffer = b''
    self.triggers = []

  def say(self, text):
    """Put a new text on the buffer queue."""
    self.buffers[-1] += text.encode()

  def wait_for(self, text):
    """New wait_for text trigger."""
    self.triggers.append(text.encode())
    self.buffers.append(b'')

  def timeout(self):
    """Emulate a read timeout."""
    # NULL will not be part of tests, use it to emulate timeout
    self.buffers[-1] += bytes([0])

  def wait_for_break(self):
    """New wait_for break trigger."""
    self.triggers.append(TRIGGER_BREAK)
    self.buffers.append(b'')

  def mock_read(self):
    if self.read_idx < len(self.buffers[0]):
      b = self.buffers[0][self.read_idx]
      self.read_idx += 1
      if b == 0:
        # NULL will not be part of tests, use it to emulate timeout
        return b''
      return bytes([b])
    else:
      return b''

  def _trig(self):
    self.triggers = self.triggers[1:]
    self.buffers = self.buffers[1:]
    self.write_buffer = b''
    self.read_idx = 0

  def mock_write(self, data):
    self.write_buffer += data
    if not self.triggers:
      return
    if self.triggers[0] == TRIGGER_BREAK:
      return
    if self.write_buffer.endswith(self.triggers[0]):
      self._trig()

  def mock_send_break(self):
    # If only accept break if we're waiting on a break trigger
    assert self.triggers[0] == TRIGGER_BREAK, (
            'Got break but was not waiting for one')
    print('BREAK trigger')
    self._trig()


# swinit

Initialize switches over serial port.

Tired of manually configuring stacking of switches? Of sitting through
long nights of password recovery and `wr erase`? No more! This software
suite will take over from when it notices a ROMMON prompt and execute the
following:

 * Configuration wipe
 * Stacking setup
 * Basic configuration for TFTP/DHCP bootup

## Usage

Use either the .service file for systemd, or start it like this:

```
# Linux
python3.6 ./swinit.py --serial /dev/ttyUSB0
# BSD / Possibly OSX
python3.6 ./swinit.py --serial /dev/cuaU0
```

If you want helpful audio commentary along the way, make sure you
have `aplay` installed. For non-Linux systems, create a script that
takes a sound file and plays it, like this:
```
cat << _EOF_ > /usr/local/bin/aplay
#!/usr/bin/env bash
exec mplayer "$@"
_EOF_
chmod +x /usr/local/bin/aplay
```

## License

Code is MIT, things in sounds/ are copyrighted and borrowed under fair use.

## Developing

Make sure to run `make test` before submitting any changes.

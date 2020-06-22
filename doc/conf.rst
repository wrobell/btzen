.. NOTE: this is partially covered in the readme file


Bluez Configuration
===================
Daemon Configuration
--------------------

- enable Bluez experimental API in Bluez systemd file
- set auto enable parameter for Bluetooh controllers in Bluez daemon
  configuration file
- optionally, increase priority of the Bluez daemon

BTZen uses experimental API of Bluez adapter interface to connect to
Bluetooth devices. The `bluetoothd` daemon has to be started with
`-E` option. This can be permanently achieved by copying
`/usr/lib/systemd/system/bluetooth.service` file into
`/etc/systemd/system/` directory and by modifying the `ExecStart` line.

Change `AutoEnable` option to true in `/etc/bluetooth/main.conf` to
automate powering up of Bluetooth controllers. Otherwise a controller might
need to be switched on manually with `bluetoothctl` tool. BTZen library
does not perform this operation.

If host system is under heavy load, Bluez daemon might not be able to
respond to Bluetooth devices in time, which can cause disconnection of
devices. Increasing Bluez daemon priority might prevent such situations.

To summarize, `bluetooth.service` file can look like::

    ...
    ExecStart=/usr/lib/bluetooth/bluetoothd -E  # obligatory, at the moment
    ...
    CPUSchedulingPolicy=fifo
    CPUSchedulingPriority=99
    ...

Bluetooth Connection Parameters
-------------------------------
The following connection parameters might need to be set for a HCI
subsystem in `/sys/kernel/debug/bluetooth` directory

`conn_min_interval`
    Set the parameter to a low value (i.e. `6` or 7.25 ms) if reading data
    frequently (i.e. once per second) and/or from multiple devices.
`conn_max_interval`
    Set the parameter to a value to allow transmitting data without your
    application timeout. Consider sequential reads, i.e. reading data from
    multiple Sensor Tag device sensors and parallel reads, i.e. reading
    data from two Sensor Tag devices.
`supervision_timeout`
    Set the parameter to as low value as possible to allow BTZen connection
    manager to disable disconnected device as soon as possible. It needs to
    be high enough to avoid disabling devices, which are affected by an
    interference (this includes high load on host device or running
    Bluetooh NAP server on the same Bluetooh device). Value of 100
    or 1000 ms seems to be a good compromise.

.. vim: sw=4:et:ai

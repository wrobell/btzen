Using the Library
=================
The module provides classes for multiple sensors of a device.  It is
required to connect to a device after creating an instance of a sensor,
i.e. :py:meth:`Temperature.connect` method.  Each sensor object provides
:py:meth:`btzen.Sensor.read` method and :py:func:`btzen.Sensor.read_async`
coroutine to return data of a sensor.

Example usage for single read from a device::

    import asyncio
    import btzen

    async def read_data():
        device = btzen.temperature('00:...:00', make=btzen.Make.SENSOR_TAG)
        # once reading from the sensor is finished, the session will be
        # properly shutdown
        with btzen.connect([device]):
            # reading from the sensor will not start until BTZen
            # connects to the device
            temperature = await btzen.read(sensor)
            print(temperature)

    asyncio.run(read_data())

Example usage for constant read from a device::

    import asyncio
    import btzen

    async def read_sensor(sensor):
        while True:
            try:
                # reading from the sensor will not start until BTZen
                # connects to the device
                temperature = await btzen.read(sensor)
            except CancelledError as ex:
                # reading can be cancelled due to disconnected device,
                # catch the exception to restart reading from the sensor
                print('sensor read cancelled')
            else:
                print(temperature)

    async def read_data():
        sensor = btzen.temperature('00:...:00', make=btzen.Make.SENSOR_TAG)
        with btzen.connect([sensor]) as session:
            # await session to allow proper application shutdown on exit
            await asyncio.gather(session, read_sensor(sensor))

    asyncio.run(read_data())

.. vim: sw=4:et:ai

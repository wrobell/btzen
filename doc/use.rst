Using the Library
=================
The module provides classes for multiple sensors of a device.  It is
required to connect to a device after creating an instance of a sensor,
i.e. :py:meth:`Temperature.connect` method.  Each sensor object provides
:py:meth:`btzen.Sensor.read` method and :py:func:`btzen.Sensor.read_async`
coroutine to return data of a sensor.

Example usage::

    async def read_data(sensor):
        while True:
            temperature = await sensor.read_async()
            print(temperature)

    loop = asyncio.get_event_loop()
    sensor = btzen.Temperature('... mac address ...')
    sensor.connect()
    loop.run_until_complete(read_data(sensor))

.. vim: sw=4:et:ai

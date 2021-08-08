Using the Library
=================
- create devices
- create connection session using `btzen.connect`
- read data

Example usage for reading data from a device::

    import asyncio
    import btzen

    async def read_sensor(sensor):
        # reading from the sensor will not start until BTZen connects to
        # the device
        async for temperature in btzen.read_all(sensor):
            temperature = await btzen.read(sensor)
            print(temperature)

    async def read_data():
        sensor = btzen.temperature('00:...:00', make=btzen.Make.SENSOR_TAG)
        with btzen.connect([sensor]) as session:
            # await session to allow proper application shutdown on exit
            await asyncio.gather(session, read_sensor(sensor))

    asyncio.run(read_data())

.. vim: sw=4:et:ai

# vsslctrl

Python package for controlling [VSSL's](https://www.vssl.com/) range of streaming amplifiers.

## Coverage

Test suite run on:

| Model       | Software Version 
| ------------|---------  
| `A.1x`       | p15243.022.3703     
| `A.3x`       | p15305.016.3701     


Home Assistant [integration](https://github.com/vsslctrl/integration.home-assistant) with basic functionality working on:

| Model       | Software Version | User Reported |
| ------------|---------  | -------------
| `A.1`       | p15265.033.3703    | ✔️
| `A.3`      | p12013.141.3703     | ✔️
| `A.3x`       | p15305.016.3701     | 
| `A.6x`       | p15305.017.3701     | ✔️


## Testers Needed

I am looking for testers with any VSSL amplifier models, please get in touch if you interested in helping. <vsslcontrolled@proton.me>



## Important

There should not be any *[VSSL Agent's](https://vssl.gitbook.io/vssl-rest-api/getting-started/start)* running on the network. If you dont know what this is, then you can ignore this notice.

 **`vsslctrl` is not endorsed or affiliated with [VSSL](https://www.vssl.com/) in any manner.**

## Basic Usage

`vsslctrl` needs to be running inside a **[asyncio](https://docs.python.org/3/library/asyncio.html)** event loop.

### `A.1(x)` Example

```python
import asyncio
from vsslctrl import Vssl

async def main():
  
  # Represents a physical VSSL amplifier
  vssl = Vssl()
  
  a1 = vssl.add_zone('192.168.1.10')

  # Connect and initialise zone.
  await vssl.initialise()

  """Control Examples"""
  # Print zone/device name
  print(a1.settings.name)
  # Set volume to 25%
  a1.volume = 25
  # Pause
  a1.pause()
  # Print track name
  print(a1.track.name)

  # Shutdown and disconnect all zones
  await vssl.shutdown()

asyncio.run(main())
```

### `A.3(x)` Example

```python
import asyncio
from vsslctrl import Vssl

async def main():
	
  # Represents a physical VSSL amplifier
  vssl = Vssl()

  # Add each you wish to control
  zone1 = vssl.add_zone('192.168.1.10')
  zone2 = vssl.add_zone('192.168.1.11')
  zone3 = vssl.add_zone('192.168.1.12')
  #... up to 6 zones for A.6(x)

  # Connect and initialise zones.
  await vssl.initialise()

  """Control Examples"""
  # Print zone1 name
  print(zone1.settings.name)
  # Set zone2 volume to 25%
  zone2.volume = 25
  # Pause zone3
  zone3.pause()
  # or zone3.transport.pause()
  # Print zone1 track name
  print(zone1.track.name)


  # Shutdown and disconnect all zones
  await vssl.shutdown()


asyncio.run(main())
```

### Device Discovery Helper

You can discover VSSL devices on the network using [mDNS](https://wikipedia.org/wiki/Multicast_DNS) / Bonjour if you have the [`zeroconf`](https://pypi.org/project/zeroconf/) package installed.

This uses airplay service string `_airplay._tcp.local.`, therefore airplay needs to available and will not work across VLANs without other provisions.

**Note:** This is designed to be a helper and its not recommended to be used for the initialization of the VSSL class.

```python
import asyncio
from vsslctrl import Vssl

async def main():
  
  print(await Vssl.discover())

  """
    {
        'XXXXXXXXXXXX': [
            {
                'host': '192.168.168.25',
                'name': 'Living Room',
                'model': 'A1x',
                'mac_addr': 'AA:BB:CC:DD:EE:FF',
                'zone_id': '7',
                'serial': 'XXXXXXXXXXXX'
            }
        ]
    }

  """

asyncio.run(main())
```


# API Functionality

Most functionality is achieved via `getters` and `setters` of the two main classes `Vssl`, `Zone`. 

The classes will update the physical VSSL device when setting a property and once feedback has been received, the classes internal state will be updated. For example:

```python
# Setting the zone name
zone1.settings.name = 'Living Room'
>>> 'Old Zone Name'

# Printing zone name
print(zone1.settings.name)
>>> 'Living Room'
```

**Important** in the above example, `zone1.settings.name` won't be set to its new value until after the VSSL device has changed the name and the `Zone` class has received confirmation feedback. If you need to wait for the value change, you can await a `[property_name]_CHANGE` events as below:

```python
from vsslctrl.settings import ZoneSettings
# Setting the zone name and wait for feedback
future_name = vssl.event_bus.future(ZoneSettings.Events.NAME_CHANGE, zone1.id)
zone1.settings.name = 'Bathroom' 
# Helper to await a future with timeout
new_name = await vssl.event_bus.wait_future(future_name)
# Printing zone name
print(new_name)
>>> 'Bathroom'
# or
print(zone1.settings.name)
>>> 'Bathroom'
```

# API Reference

# `Vssl`

| Property      	| Description | Type 		| 
| ---------------------- 	| ----------- | ----------- |
| `sw_version`   			| Software version        |	`str` readonly
| `serial`   			| Serial number        |	`str` readonly
| `model`   			| Device Model        |	`int` readonly
| `reboot()`   			| Reboot all zones        |	`func`  |
| `factory_reset()`        | Factory reset device        | `func`  |


```python
"""Example"""
# Reboot all zones
vssl.reboot()
# Do a factory reset (reset all settings)
vssl.factory_reset()
```

## `Vssl.settings`

`A.1(x)` doesn't use `Vssl.settings.name` use `Zone.settings.name` instead.

| Property      	| Description | Type 		| Model: Default |
| ---------------------- 	| ----------- | ----------- | ----------- |
| `name`     			 	| Device name |	`str` | 
| `bus_1_name`   			| Name of Bus 1        |	`str` | <ul><li>`A.1`: Optical Input</li><li>`A.3x`/`A.6x`: Not Used</li></ul>
| `bus_2_name`        | Name of Bus 2        |  `str` | <ul><li>`A.1`: Coax Input</li><li>`A.3x`/`A.6x`: Optical Input</li></ul>
| `bluetooth`        | Bluetooth enabled / disabled        |  `bool` |
| `bluetooth_toggle()`        | Toggle Bluetooth        | `func`  |

```python
"""Example"""
# Setting device name
vssl.settings.name = 'My House'
# Setting bus 2 name
vssl.settings.bus_2_name = 'Optical Input'
# Enable Bluetooth
vssl.settings.bluetooth = True
# Toggle Bluetooth
vssl.settings.bluetooth_toggle()
```

## `Vssl.settings.power`

| Property      	| Description | Type		| Values 		| 
| ---------------------- 	| ----------- | ----------- |----------- |
| `state`     			 	| Power state |	`int` readonly	| `VsslPowerSettings.States`
| `adaptive`   			| Power adaptive        |	`bool`

```python
"""Example"""
# Setting power adaptive
vssl.settings.power.adaptive = True
```


# `Zone`

| Property      	| Description | Type		| Values 		| 
| ---------------------- 	| ----------- | ----------- |----------- |
| `id`     			 	| Zone number / ID |	`int` readonly	| `ZoneIDs`
| `host`   			| IP address        |	`str` readonly
| `volume`   			| Volume        |	`int`  | `0...100`
| `volume_raise([step=1])`   			| Raise volume by `step`       |	`func`  | step: `int` `1...100`
| `volume_lower([step=1])`   			| Lower volume by `step`      |	`func`  | step: `int` `1...100`
| `mute`   			| Volume muted        |	`bool`  |
| `mute_toggle()`   			| Mute / Unmute        |	`func`  |
| `play()`   			| Play        |	`func`  |
| `stop()`   			| Stop        |	`func`  |
| `pause()`   			| Pause        |	`func`  |
| `next()`   			| Next track       |	`func`  |
| `prev()`   			| Begining of track or previous track        |	`func`  |
| `reboot()`   			| Reboot zone        |	`func`  |
| `play_url([url], [all_zones])`   			| Play a URL       |	`func`  | url: `str`, all_zones: `bool`


```python
"""Examples"""
# Set volume to 50%
zone1.volume = 50
# Raise volume by 5%
zone1.volume_raise(5)
# Mute
zone1.mute = True
# Toggle mute
zone1.mute_toggle()
# Pause transport
zone1.pause()
# Next track
zone1.next()
# Play a URL on this zone1
zone1.play_url('http://soundbible.com/grab.php?id=2217&type=mp3')
# Play a URL on all zones
zone1.play_url('http://soundbible.com/grab.php?id=2217&type=mp3', True)
```

## `Zone.transport`

A VSSL amplifier can not start a stream except for playing a URL directly. This is a limitation of the hardware itself.

| Property      	| Description | Type		| Values 		| 
| ---------------------- | ----------- | ----------- |----------- |
| `state`     			 | Transport state. i.e Play, Stop, Pause | `int`	| `ZoneTransport.States`
| `play()`   		 | Play   |	`func`  |
| `stop()`   		 | Stop     |	`func`  |
| `pause()`   		 | Pause     |	`func`  |
| `next()`   			| Next track       |	`func`  |
| `prev()`   			| Begining of track or previous track        |	`func`  |
| `is_playing`   			| Is the zone playing        |	`bool` readonly
| `is_stopped`   			| Is the zone stopped        |	`bool` readonly
| `is_pasued`   			| Is the zone pasued        |	`bool` readonly
| `is_repeat`     			 | Repeat state. i.e all, one, off | `int` readonly	| `ZoneTransport.Repeat`
| `is_shuffle`   			| Is shuffle enabled       |	`bool` readonly
| `has_next`   			| Is the next button enabled       |	`bool` readonly
| `has_prev`   			| Is the prev button enabled       |	`bool` readonly

```python
"""Example"""
# Pause the stream
zone1.transport.pause()
# or
zone1.transport.state = ZoneTransport.States.PAUSE
```

## `Zone.track`

* Not all sources have complete metadata - missing value will be set to defaults.
* Airplay track `progress` is not available.

| Property      	| Description | Type		| Values 		| 
| ---------------------- | ----------- | ----------- |----------- |
| `title`     			 | Title | `str` readonly	| 
| `album`     			 | Album | `str` readonly	| 
| `artist`     			 | Artist | `str` readonly	| 
| `genre`     			 | Genre | `str` readonly	| 
| `duration`     		| Length in miliseconds (ms) | `int` readonly	| 
| `progress`     		| Current position in miliseconds (ms) | `int` readonly	|
| `cover_art_url`     	| URL to cover art | `str` readonly	| 
| `source`     			| Track source e.g Spotify |	`int` readonly	| `TrackMetadata.Sources`
| `url`     	| URL of file or track | `str` readonly	| 


## `Zone.input`

| Property      	| Description | Type		| Values 		| 
| ---------------------- 	| ----------- | ----------- |----------- |
| `source`     			 	| Change input source.<br/>Source to be played out the zones speakers |	`int`	| `InputRouter.Sources`
| `priority`     			| Change input priority.<br/>Stream or local to have precedence  |	`int`	| `InputRouter.Priorities`


### `A.1(x)` Source Routing Order
`A.1` and `A.1x` don't support manually changing the input source. Instead a fixed source routing order is used:
  
  1. Optical Input
  2. Coaxial Input
  3. Analog Input
  
Input `InputRouter.Priorities` still apply.

### Input Priority / Precedence

| `InputRouter.Priorities`       | Priority Order |
| ----------------------  | ----------- |
| **`STREAM`**  | <ol><li>Stream</li><li>Party Zone</li><li>Bus 1</li><li>Bus 2</li><li>Optical</li><li>Coaxial</li><li>Analog</li></ol>
|  **`LOCAL`**  | <ol><li>Bus 1</li><li>Bus 2</li><li>Optical</li><li>Coaxial</li><li>Analog</li><li>Stream</li><li>Party Zone</li></ol>

```python
"""Example"""
# Change zone 1 to listen to analog input 4
zone1.input.source = InputRouter.Sources.ANALOG_IN_4

# Change zone 1 to perfer local inputs over stream
zone1.input.priority = InputRouter.Priorities.LOCAL
```

## `Zone.group`

Unsupported on X series amplifiers.

| Property      	| Description | Type		| Values 		| 
| ---------------------- 	| ----------- | ----------- |----------- |
| `source`     			 	| Zone ID of group master / source |	`int` readonly	| `ZoneIDs`
| `is_master`   			| This zone is the group master        |	`bool` readonly
| `add_member()`   			| Add zone to group / create group |	`func`  | `ZoneIDs`
| `remove_member()`   		| Remove zone from group      |	`func`  | `ZoneIDs`
| `dissolve()`   			| Dissolve group / remove all members       |	`func`  |
| `leave()`   				| Leave the group if a member       |	`func`  |
| `is_party_zone_member`  | Member of Party Zone |  `bool`  |

```python
"""Examples"""
# Add group 2 to a group with zone 1 as master
zone1.group.add_member(ZoneIDs.ZONE_2)
# Remove zone 2 from group
zone2.group.leave() # or
zone1.group.remove_member(ZoneIDs.ZONE_2)
# If zone 1 is a master, remove all members
zone1.group.dissolve()
# Add zone to the party zone group
zone1.group.is_party_zone_member = True
# Toggle Party Zone Membership
zone1.group.is_party_zone_member_toggle()
```

## `Zone.analog_output`

| Property      	| Description | Type		| Values 		| Default |
| ---------------------- 	| ----------- | ----------- |----------- |----------- |
| `source`     			 	| Where the AO is routed from. i.e stream, optical input or off |	`int`	| `AnalogOutput.Sources` | `Off`
| `is_fixed_volume`   			| Fix the output volume. Output wont respond to volume control        |	`bool` | |`False`
| `is_fixed_volume_toggle()`   			| Toggle fixed volume      |	`func`  |

```python
"""Examples"""
# Change analog output of zone1 to be outputting the optical input
zone1.analog_output.source = AnalogOutput.Sources.OPTICAL_IN

# Change analog output of zone1 to be outputting the zone 2 source (whatever zone 2 is using as a source)
zone1.analog_output.source = AnalogOutput.Sources.ZONE_2

# Fix the analog output volume. 
zone1.analog_output.is_fixed_volume = True
```

## `Zone.settings`

| Property      	| Description | Type		| Values 		| Default |
| ---------------------- 	| ----------- | ----------- |----------- |----------- |
| `name`     			 	| Name |	`str`	| 
| `disabled`   			| Disable the zone        |	`bool` || `False`
| `disabled_toggle()`   			| disable / enable        |	`func`  |
| `mono`   			| Set output to mono or stereo        |	`int`  | `ZoneSettings.StereoMono` | `STEREO`
| `mono_toggle()`   			| Toggle mono or stereo        |	`func`  |

```python
"""Examples"""
# Set name
zone1.settings.name = 'Living Room'
# Disable Zone
zone1.settings.disabled = True
# Toggle mono output
zone1.settings.mono_toggle()
```

## `Zone.settings.analog_input`

| Property      	| Description | Type		| Values 		| Default |
| ---------------------- 	| ----------- | ----------- |----------- |----------- |
| `name`     			 	| Name |	`str`	| 
| `fixed_gain`   		| Fix the input gain to a specific value       |`int` | `0...100` | `0` is disabled or variable gain

```python
"""Examples"""
# Change zone1 analog input name
zone1.settings.analog_input.name = 'BluRay Player'

# Fix zone1 analog input gain to 50%.
zone1.settings.analog_input.fixed_gain = 50
```


## `Zone.settings.volume`

| Property      	| Description | Type		| Values 		| Default |
| ---------------------- 	| ----------- | ----------- |----------- |----------- |
| `default_on`     			 	| Default on volume  |	`int`  | `0...100` | `0` is disabled
| `max_left`     			 	| Max volume left channel  |	`int`  | `0...100` | `75`
| `max_right`     			 	| Max volume right channel  |	`int`  | `0...100` | `75`

```python
"""Examples"""
# Set default on volume to 50%
zone1.settings.volume.default_on = 50
# Set maximum volume for left channel to 75%
zone1.settings.volume.max_left = 75
```

## `Zone.settings.eq`

| Property      	| Description | Type		| Values 		| Default |
| ---------------------- 	| ----------- | ----------- |----------- |----------- |
| `enabled`     			 	| Enable / disable EQ        |	`bool` | | `False`

EQ to be set in [decibel](https://en.wikipedia.org/wiki/Decibel) using a range `-10`dB to `+10`dB

| Property      	| Description | Type		| Values 		| Default |
| ---------------------- 	| ----------- | ----------- |----------- | ----------- |
| `hz60_db`     			 	| 60Hz |	`int`  | `-10...10` | `0`
| `hz200_db`     			 	| 200Hz |	`int`  | `-10...10` | `0`
| `hz500_db`     			 	| 500Hz |	`int`  | `-10...10` | `0`
| `khz1_db`     			 	| 1kHz |	`int`  | `-10...10` | `0`
| `khz4_db`     			 	| 4kHz |	`int`  | `-10...10` | `0`
| `khz8_db`     			 	| 8kHz |	`int`  | `-10...10` | `0`
| `khz15_db`     			 	| 15kHz |	`int`  | `-10...10` | `0`

```python
"""Examples"""
# Set 1kHz EQ to -2
zone1.settings.eq.khz1_db = -2
```

## `Zone.settings.subwoofer`

* **A.1 and A.1x only**
* Set `0` for full frequency range

| Property        | Description | Type    | Values    | Default |
| ----------------------  | ----------- | ----------- |----------- |----------- |
| `crossover`             | Set "sub out" crossover frequency from 50-200Hz.       |  `int` | `0` or `50...200` | `0`

```python
"""Examples"""
# Set subwoofer ouput crossover to 100hz
zone1.settings.subwoofer.crossover = 100
```

## Credit

Thanks to [@dj-jam](https://github.com/dj-jam) for the continued testing.

The VSSL API was reverse engineered using Wireshark, VSSLs native "legacy" iOS app and their deprecated [vsslagent](https://vssl.gitbook.io/vssl-rest-api/getting-started/start).

Motivation for this project was to integrate VSSLs amplifiers into [Home Assistant](https://www.home-assistant.io/) and have control over different subnets (not mDNS dependant)

## Known Issues & Limitiations

* VSSL can not start a stream except for playing a URL directly. This is a limitation of the hardware itself.
* Not all sources set the volume to 0 when the zone is muted
* Airplay `Zone.track.progress` is not available.
* VSSL likes to cache old track metadata. For example when playing a URL after Spotify, often the device will respond with the previous (Spotify) tracks metadata
* `stop()` is intended to disconnect the client and pause the stream. Doesn’t always function this way, depending on stream source


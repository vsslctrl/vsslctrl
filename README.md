# vsslctrl
 Package for controlling [VSSL](https://www.vssl.com/) range of streaming amplifiers.

 Motovation for this project was to intergrate my VSSL A.3x into [Home Assistant](https://www.home-assistant.io/) and I wanted control which didnt have to rely on mDNS discovery. The VSSL API was discovered using Wireshark packet captures while using their native app.

 I am looking for testers with any VSSL models, please get in touch if you interested in helping.

## Important

`vsslctrl` is not endorsed or affiliated with [VSSL](https://www.vssl.com/) in any manner

## Known Issues & Limitiations

* Tested on VSSL **A.3x** software version **p15305.016.3701**
* Not tested on A.1x, A.6.x or original A series range of amplifiers (testers welcome)
* VSSL can not start a stream except for playing a URL directly. This is a limitation of the hardware itself.
* Not all sources set the volume to 0 when the zone is muted
* Grouping feedback is flaky on the X series amplifiers
* VSSL likes to cache old track metadata. For example when playing a URL after Spotify for example, sometimes it the device will respond with the previous tracks metadata
* `stop()` is intended to disconnect the client and pause the stream. Doesnt always function this way, depending on stream source 



Basic Usage
-----------

**Vsslctrl** needs to be running inside a **asyncio** event loop.

```python
import asyncio
from vsslctrl import Vssl, Zone

async def main():
	
	# Represents a physical VSSL amplifier
	vssl = Vssl()

	# Add each zone of above VSSL amplifier
	zone1 = vssl.add_zone(Zone.IDs.ZONE_1, '192.168.1.10')
	zone2 = vssl.add_zone(Zone.IDs.ZONE_2, '192.168.1.11')
	zone3 = vssl.add_zone(Zone.IDs.ZONE_3, '192.168.1.12')
	#... up to 6 zones

	# Connect and initiate above zones.
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
   	vssl.shutdown()


asyncio.run(main())
```

API
-----------

Most functionality is achived via `getters` and `setters` of the two main classes `Vssl`, `Zone`. 

The classes will update the physical VSSL device when setting a property and once feedback has been received, the classes internal state will be updated. For example:

```python
# Setting the zones name
zone1.settings.name = 'Living Room'
>>> None

# Printing zone name
zone_name = zone1.settings.name
print(zone_name)
>>> 'Living Room'
```

Note, in the above example, `zone_name` wont be set to its new value until after the VSSL device has changed the name and the `Zone` class has received confimation feedback. If you need to wait for the value change, you can await a `[property_name]_CHANGE` events.


### `Vssl`

| Property      	| Description | Type 		| 
| ---------------------- 	| ----------- | ----------- |
| `name`     			 	| Device name |	`str`
| `sw_version`   			| Software version        |	`str` readonly
| `serial`   			| Serial number        |	`str` readonly
| `model_zone_qty`   			| Number of zones the device has        |	`int` readonly
| `optical_input_name`   			| Name of the optical input        |	`str`

```python
"""Example"""
# Setting device name
vssl.name = 'My House'
# Setting optical input name
vssl.optical_input_name = 'Optical Input 1'
```

### `Vssl.power`

| Property      	| Description | Type		| Values 		| 
| ---------------------- 	| ----------- | ----------- |----------- |
| `state`     			 	| Power state |	`int` readonly	| `VsslPowerSettings.States`
| `adaptive`   			| Power adaptive        |	`bool`

```python
"""Example"""
# Setting power adaptive
zone1.power.adaptive = True
>>> None
```


### `Zone`

| Property      	| Description | Type		| Values 		| 
| ---------------------- 	| ----------- | ----------- |----------- |
| `id`     			 	| Zone number / ID |	`int` readonly	| `Zone.IDs`
| `host`   			| IP address        |	`str` readonly
| `volume`   			| Volume        |	`int`  | 0...100
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
# Mute
zone1.mute = True
# Toggle mute
zone1.mute_toggle()
# Pause transport
zone1.pause()
# Next track
zone1.next()
# Play a URL on this zone
zone1.play_url('http://soundbible.com/grab.php?id=2217&type=mp3')
# Play a URL on all zones
zone1.play_url('http://soundbible.com/grab.php?id=2217&type=mp3', True)
```

### `Zone.settings`

| Property      	| Description | Type		| Values 		| 
| ---------------------- 	| ----------- | ----------- |----------- |
| `name`     			 	| Name |	`str`	| 
| `disabled`   			| Disable the zone        |	`bool`
| `disabled_toggle()`   			| disable / enable        |	`func`  |
| `mono`   			| Set output to mono or stereo        |	`int`  | `ZoneSettings.StereoMono`
| `mono_toggle()`   			| Toggle mono or stereo        |	`func`  |

```python
"""Examples"""
# Set name
zone1.settings.name = 'Living Room'
# Disable Zone
zone1.disabled = True
# Toggle mono output
zone1.mono_toggle()
```

### `Zone.settings.volume`

| Property      	| Description | Type		| Values 		| 
| ---------------------- 	| ----------- | ----------- |----------- |
| `default_on`     			 	| Default on volume  |	`int`  | 0...100 
| `max_left`     			 	| Max volume left channel  |	`int`  | 0...100 
| `max_right`     			 	| Max volume right channel  |	`int`  | 0...100 

```python
"""Examples"""
# Set default on volume to 50%
zone1.settings.volume.default_on = 50
# Set maximum volume for left channel to 75%
zone1.settings.volume.default_on = 75
```

### `Zone.settings.eq`

EQ settings can either be set using `int` values of `90` to `110` or dB values of `-10` to `10`. Be sure to use the correct property.

| Property      	| Description | Type		| Values 		| 
| ---------------------- 	| ----------- | ----------- |----------- |
| `enabled`     			 	| Enable / disable EQ        |	`bool` 
| `hz60`     			 	| 60Hz EQ  |	`int`  | 90...110 
| `hz60_db`     			 	| 60Hz EQ in dB |	`int`  | -10...10
| `hz200`     			 	| 200Hz EQ  |	`int`  | 90...110 
| `hz200_db`     			 	| 200Hz EQ in dB |	`int`  | -10...10
| `hz500`     			 	| 500Hz EQ  |	`int`  | 90...110 
| `hz500_db`     			 	| 500Hz EQ in dB |	`int`  | -10...10
| `khz1`     			 	| 1kHz EQ  |	`int`  | 90...110 
| `khz1_db`     			 	| 1kHz EQ in dB |	`int`  | -10...10
| `khz4`     			 	| 4kHz EQ  |	`int`  | 90...110 
| `khz4_db`     			 	| 4kHz EQ in dB |	`int`  | -10...10
| `khz8`     			 	| 8kHz EQ  |	`int`  | 90...110 
| `khz8_db`     			 	| 8kHz EQ in dB |	`int`  | -10...10
| `khz15`     			 	| 15kHz EQ  |	`int`  | 90...110 
| `khz15_db`     			 	| 15kHz EQ in dB |	`int`  | -10...10

```python
"""Examples"""
# Set 1kHz EQ to -2
zone1.settings.eq.khz1_db = -2
# or
zone1.settings.eq.khz1 = 98
```



### Awaiting Property Updates

```python
zone_name = await zone1.settings.set_name('Living Room')
print(zone_name)
>>> 'Living Room'
```

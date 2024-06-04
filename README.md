# vsslctrl
 Package for controlling [VSSL](https://www.vssl.com/) range of streaming amplifiers.

 **`vsslctrl` is not endorsed or affiliated with [VSSL](https://www.vssl.com/) in any manner.**

 Motovation for this project was to intergrate VSSLs amplifiers into [Home Assistant](https://www.home-assistant.io/) and not soley rely on mDNS for control (as per the offical VSSL app) 

 I am looking for testers with any VSSL amplifier models, please get in touch if you interested in helping.

 Only tested on VSSL **A.3x** software version **p15305.016.3701**.

## TODOs

* Test on other models (hardware needed)
* Home Assistant integration (in progress)
* Function scoping to supported feature / models
* Better test coverage

Basic Usage
-----------

`vsslctrl` needs to be running inside a **[asyncio](https://docs.python.org/3/library/asyncio.html)** event loop.

```python
import asyncio
from vsslctrl import Vssl, Zone

async def main():
	
	# Represents a physical VSSL amplifier
	vssl = Vssl()

	# Add each you wish to control
	zone1 = vssl.add_zone(Zone.IDs.ZONE_1, '192.168.1.10')
	zone2 = vssl.add_zone(Zone.IDs.ZONE_2, '192.168.1.11')
	zone3 = vssl.add_zone(Zone.IDs.ZONE_3, '192.168.1.12')
	#... up to 6 zones

	# Connect and initiate zones.
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

**Important** in the above example, `zone1.settings.name` wont be set to its new value until after the VSSL device has changed the name and the `Zone` class has received confimation feedback. If you need to wait for the value change, you can await a `[property_name]_CHANGE` events.


# `Vssl`

| Property      	| Description | Type 		| 
| ---------------------- 	| ----------- | ----------- |
| `sw_version`   			| Software version        |	`str` readonly
| `serial`   			| Serial number        |	`str` readonly
| `model_zone_qty`   			| Number of zones the device has        |	`int` readonly
| `reboot()`   			| Reboot all zones        |	`func`  |

```python
"""Example"""
# Reboot all zones
vssl.reboot()
```

## `Vssl.settings`

| Property      	| Description | Type 		| 
| ---------------------- 	| ----------- | ----------- |
| `name`     			 	| Device name |	`str`
| `optical_input_name`   			| Name of the optical input        |	`str`

```python
"""Example"""
# Setting device name
vssl.settings.name = 'My House'
# Setting optical input name
vssl.settings.optical_input_name = 'Optical Input 1'
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
| `id`     			 	| Zone number / ID |	`int` readonly	| `Zone.IDs`
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
* Airplay track position is not avaiable.

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
| `source`     			 	| Change input source |	`int`	| `InputRouter.Sources`
| `priority`     			| Change input priority. Stream or analog in higher priority  |	`int`	| `InputRouter.Priorities`

```python
"""Example"""
# Change zone 1 to listen to analog input 4
zone1.input.source = InputRouter.Sources.ANALOG_IN_4

# Change zone 1 to perfer analog input (local) over stream
zone1.input.priority = InputRouter.Priorities.LOCAL
```

## `Zone.group`

Working on A.3x but offically unsupported in x series amplifiers.

| Property      	| Description | Type		| Values 		| 
| ---------------------- 	| ----------- | ----------- |----------- |
| `source`     			 	| Zone ID of group master / source |	`int` readonly	| `Zone.IDs`
| `is_master`   			| This zone is the group master        |	`bool` readonly
| `add_member()`   			| Add zone to group / create group |	`func`  | `Zone.IDs`
| `remove_member()`   		| Remove zone from group      |	`func`  | `Zone.IDs`
| `dissolve()`   			| Dissolve group / remove all members       |	`func`  |
| `leave()`   				| Leave the group if a member       |	`func`  |

```python
"""Examples"""
# Add group 2 to a group with zone 1 as master
zone1.group.add_member(Zone.IDs.ZONE_2)
# Remove zone 2 from group.
zone2.group.leave() # or
zone1.group.remove_member(Zone.IDs.ZONE_2)
# If zone 1 is a master, remove all members
zone1.group.dissolve()
```

## `Zone.analog_output`

| Property      	| Description | Type		| Values 		| 
| ---------------------- 	| ----------- | ----------- |----------- |
| `source`     			 	| Where the AO is routed from. i.e a zone, optical input or off |	`int`	| `AnalogOutput.Sources`
| `is_fixed_volume`   			| Fix the output volume. Output wont respond to volume control        |	`bool` readonly
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

## `Zone.settings.analog_input`

| Property      	| Description | Type		| Values 		| 
| ---------------------- 	| ----------- | ----------- |----------- |
| `name`     			 	| Name |	`str`	| 
| `fixed_gain`   		| Fix the input gain to a specific value       |`int` | `0...100`

```python
"""Examples"""
# Change zone1 analog input name
zone1.settings.analog_input.name = 'BluRay Player'

# Fix zone1 analog input gain to 50%.
zone1.settings.analog_input.fixed_gain = 50
```


## `Zone.settings.volume`

| Property      	| Description | Type		| Values 		| 
| ---------------------- 	| ----------- | ----------- |----------- |
| `default_on`     			 	| Default on volume  |	`int`  | `0...100` 
| `max_left`     			 	| Max volume left channel  |	`int`  | `0...100` 
| `max_right`     			 	| Max volume right channel  |	`int`  | `0...100` 

```python
"""Examples"""
# Set default on volume to 50%
zone1.settings.volume.default_on = 50
# Set maximum volume for left channel to 75%
zone1.settings.volume.default_on = 75
```

## `Zone.settings.eq`

| Property      	| Description | Type		| Values 		| 
| ---------------------- 	| ----------- | ----------- |----------- |
| `enabled`     			 	| Enable / disable EQ        |	`bool` 

EQ be set in [decibel](https://en.wikipedia.org/wiki/Decibel) using a range `-10`dB to `+10`dB

| Property      	| Description | Type		| Values 		| 
| ---------------------- 	| ----------- | ----------- |----------- | 
| `hz60_db`     			 	| 60Hz |	`int`  | `-10...10`
| `hz200_db`     			 	| 200Hz |	`int`  | `-10...10`
| `hz500_db`     			 	| 500Hz |	`int`  | `-10...10`
| `khz1_db`     			 	| 1kHz |	`int`  | `-10...10`
| `khz4_db`     			 	| 4kHz |	`int`  | `-10...10`
| `khz8_db`     			 	| 8kHz |	`int`  | `-10...10`
| `khz15_db`     			 	| 15kHz |	`int`  | `-10...10`

```python
"""Examples"""
# Set 1kHz EQ to -2
zone1.settings.eq.khz1_db = -2
```

## Credit

The VSSL API was reverse engineered using Wireshark, VSSLs native "legacy" iOS app and their deprecated [vsslagent](https://vssl.gitbook.io/vssl-rest-api/getting-started/start). VSSLs non-legacy iOS app version 1.1.3(1) is crashing my A.3x.

## Known Issues & Limitiations

* Tested on VSSL **A.3x** software version **p15305.016.3701**
* Not tested on A.1x, A.6.x or original A series range of amplifiers (testers welcome)
* VSSL can not start a stream except for playing a URL directly. This is a limitation of the hardware itself.
* Not all sources set the volume to 0 when the zone is muted
* Grouping feedback is flaky on the X series amplifiers
* Cant stop a URL playback, feedback is worng at least
* VSSL likes to cache old track metadata. For example when playing a URL after Spotify, often the device will respond with the previous (Spotify) tracks metadata
* `stop()` is intended to disconnect the client and pause the stream. Doesnt always function this way, depending on stream source
* Occasionally a zones might stop responding to certain commands, issuing the `reboot` command generally corrects


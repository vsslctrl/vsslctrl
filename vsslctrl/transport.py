import logging
from typing import Dict, Union
from .track import TrackMetadata
from .utils import clamp_volume
from .data_structure import VsslIntEnum, ZoneDataClass

class ZoneTransport(ZoneDataClass):

    #
    # Transport States
    #
    # DO NOT CHANGE - VSSL Defined
    #
    class States(VsslIntEnum):
        STOP = 0
        PLAY = 1
        PAUSE = 2

    #
    # Repeat
    #
    # DO NOT CHANGE - VSSL Defined
    #
    class Repeat(VsslIntEnum):
        OFF = 0 # No repeat
        ONE = 1 # Repeat single track
        ALL = 2 # Repeat queue / playlist / album

    #
    # Transport Events
    #
    class Events():
        PREFIX              = 'zone.transport.'
        STATE_CHANGE        = PREFIX+'state_change'
        STATE_CHANGE_STOP   = PREFIX+'state_change.stop'
        STATE_CHANGE_PLAY   = PREFIX+'state_change.play'
        STATE_CHANGE_PAUSE  = PREFIX+'state_change.pause'

        REPEAT_CHANGE       = PREFIX+'repeat_change'
        SHUFFLE_CHANGE      = PREFIX+'shuffle_change'
        NEXT_FLAG_CHANGE    = PREFIX+'next_flag_change'
        PREV_FLAG_CHANGE    = PREFIX+'prev_flag_change'


    DEFAULTS = {
        'state': States.STOP,
        'repeat': Repeat.OFF,
        'shuffle': False,
        'next_flag': False,
        'prev_flag': False
    }

    KEY_MAP = {
        'Next': 'next_flag',
        'Prev': 'prev_flag',
        'Shuffle': 'shuffle',
        'Repeat': 'repeat',
    }

    def __init__(self, zone: 'zone.Zone'):
        self._zone = zone

        self._state = ZoneTransport.States.STOP
        self._repeat = ZoneTransport.Repeat.OFF
        self._shuffle = False
        self._next_flag = False
        self._prev_flag = False

    #
    # VSSL doenst clear some vars on stopping of the stream, so we will do it
    #
    # Doing this will fire the change events on the bus. Instead of conditionally
    # using the getter functions since we want the changes to be propogated
    #
    # VSSL has a happit of caching the last song played, so we need to clear it
    #
    def set_defaults(self):
        for key, default_value in ZoneTransport.DEFAULTS.items():
            set_func = f'_set_{key}'
            if hasattr(self, set_func):
                getattr(self, set_func)(default_value)

    # 
    # Set value based on transport state.
    #
    def _default_on_state_stop(self, value, default = None):
        return default if self.state == ZoneTransport.States.STOP else value

    #
    # Update from a JSON dict passed
    #
    def _map_response_dict(self, track_data: Dict[str, int]) -> None:
        for track_data_key, metadata_key in ZoneTransport.KEY_MAP.items():
            if track_data_key in track_data:
                self._set_property(metadata_key, track_data[track_data_key])

    #
    # Update from a JSON dict passed
    #
    def _set_bool_property(self, prop_key: str, new_value: int, event: str) -> None:
        new_value = self._default_on_state_stop(not not new_value, ZoneTransport.DEFAULTS[prop_key])
        cur_value = getattr(self, prop_key)

        if cur_value != new_value:
            setattr(self, f'_{prop_key}', new_value)
            return True

    #
    # Transport State
    #
    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, state: int):
        if ZoneTransport.States.is_valid(state):
            state = ZoneTransport.States(state)
            self._zone._api_alpha.request_action_3D(state)

            # Changing state wont work if we are part of a group
            # So if we are wanting to stop, leave the group
            if state == ZoneTransport.States.STOP and self._zone.group.is_member:
                self._zone.group.leave()
        else:
            self._zone._log_error(f"ZoneTransport.States {state} doesnt exist")


    def _set_state(self, state: int):
        if self.state != state:
            if ZoneTransport.States.is_valid(state):
                self._state = ZoneTransport.States(state)
                self._zone._event_publish(
                    getattr(ZoneTransport.Events, f'STATE_CHANGE_{self.state.name.upper()}'), 
                    True
                )
                return True
            else:
                self._zone._log_warning(f"ZoneTransport.States {state} doesnt exist")

    #
    # Transport Commands
    #
    def play(self):
        self.state = ZoneTransport.States.PLAY

    """
        note: stopping a stream will disconnect the client as will pausing an Airplay stream.

        note2: streams (Airplay, Chromecast, Spotify.Connect) have higher priority than analog inputs. 
        Therefore, if both input types are playing to a zone then the higher priority will play. Likewise, 
        if both types of input are playing to a zone and the stream is stopped then the zone will switch 
        to playing the lower priority content.

        ref: https://vssl.gitbook.io/vssl-rest-api/zone-control/play-control
    """
    def stop(self):
        self.state = ZoneTransport.States.STOP

    def pause(self):
        self.state = ZoneTransport.States.PAUSE

    #
    # Transport States
    #
    @property
    def is_playing(self):
        return self.state == ZoneTransport.States.PLAY

    @property
    def is_stopped(self):
        return self.state == ZoneTransport.States.STOP

    @property
    def is_paused(self):
        return self.state == ZoneTransport.States.PAUSE

    #
    # Track Control
    #
    def next(self):
        self._zone._api_alpha.request_action_40_next()

    def prev(self):
        self._zone._api_alpha.request_action_40_prev()

    def back(self):
        self.prev()
        self.prev()

    #
    # Track Next_flag
    #
    @property
    def next_flag(self):
        return self._next_flag

    @next_flag.setter
    def set_next_flag(self, val: int):
        pass #read-only

    def _set_next_flag(self, val: int):
        return self._set_bool_property('next_flag', val, ZoneTransport.Events.NEXT_FLAG_CHANGE)

    #
    # Track Prev_flag
    #
    @property
    def prev_flag(self):
        return self._prev_flag

    @prev_flag.setter
    def prev_flag(self, val: int):
        pass #read-only

    def _set_prev_flag(self, val: int):
        return self._set_bool_property('prev_flag', val, ZoneTransport.Events.PREV_FLAG_CHANGE)

    #
    # Track Shuffle
    #
    @property
    def shuffle(self):
        return self._shuffle

    @shuffle.setter
    def shuffle(self, val: int):
        pass #read-only

    def _set_shuffle(self, val: int):
        return self._set_bool_property('shuffle', val, ZoneTransport.Events.SHUFFLE_CHANGE)

    #
    # Track Repeat
    #
    @property
    def repeat(self):
        return self._repeat

    @repeat.setter
    def repeat(self, val: int):
        pass #read-only

    def _set_repeat(self, val: int):
        val = self._default_on_state_stop(val, ZoneTransport.DEFAULTS['repeat'])
        if self.repeat != val: 
            if ZoneTransport.Repeat.is_valid(val):
                self._repeat = ZoneTransport.Repeat(val)
                return True
            else:
                self._zone._log_error(f"ZoneTransport.Repeat {val} doesnt exist")
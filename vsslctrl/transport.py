import logging
from typing import Dict, Union
from .track import TrackMetadata
from .utils import clamp_volume
from .data_structure import VsslIntEnum, ZoneDataClass


class ZoneTransport(ZoneDataClass):
    class States(VsslIntEnum):
        """Transport States

        DO NOT CHANGE - VSSL Defined
        """

        STOP = 0
        PLAY = 1
        PAUSE = 2

    class Repeat(VsslIntEnum):
        """Repeat

        DO NOT CHANGE - VSSL Defined
        """

        OFF = 0  # No repeat
        ONE = 1  # Repeat single track
        ALL = 2  # Repeat queue / playlist / album

    class Events:
        """Transport Events"""

        PREFIX = "zone.transport."
        STATE_CHANGE = PREFIX + "state_change"
        STATE_CHANGE_STOP = PREFIX + "state_change.stop"
        STATE_CHANGE_PLAY = PREFIX + "state_change.play"
        STATE_CHANGE_PAUSE = PREFIX + "state_change.pause"

        IS_REPEAT_CHANGE = PREFIX + "is_repeat_change"
        IS_SHUFFLE_CHANGE = PREFIX + "is_shuffle_change"
        HAS_NEXT_CHANGE = PREFIX + "has_next_change"
        HAS_PREV_CHANGE = PREFIX + "has_prev_change"

    DEFAULTS = {
        "state": States.STOP,
        "is_repeat": Repeat.OFF,
        "is_shuffle": False,
        "has_next": False,
        "has_prev": False,
    }

    KEY_MAP = {
        "Next": "has_next",
        "Prev": "has_prev",
        "Shuffle": "is_shuffle",
        "Repeat": "is_repeat",
    }

    def __init__(self, zone: "zone.Zone"):
        self.zone = zone

        self._state = self.States.STOP
        self._is_repeat = self.Repeat.OFF
        self._is_shuffle = False
        self._has_next = False
        self._has_prev = False

    def set_defaults(self):
        """VSSL doenst clear some vars on stopping of the stream, so we will do it

        Doing this will fire the change events on the bus. Instead of conditionally
        using the getter functions since we want the changes to be propogated

        VSSL has a happit of caching the last song played, so we need to clear it
        """
        for key, default_value in self.DEFAULTS.items():
            set_func = f"_set_{key}"
            if hasattr(self, set_func):
                getattr(self, set_func)(default_value)

    def _default_on_state_stop(self, value, default=None):
        """Set value based on transport state."""
        return default if self.state == self.States.STOP else value

    def _map_response_dict(self, track_data: Dict[str, int]) -> None:
        """Update from a JSON dict"""
        for track_data_key, metadata_key in self.KEY_MAP.items():
            if track_data_key in track_data:
                self._set_property(metadata_key, track_data[track_data_key])

    def _set_bool_property(self, prop_key: str, new_value: int, event: str) -> None:
        """Set a bool property"""
        new_value = self._default_on_state_stop(
            not not new_value, self.DEFAULTS[prop_key]
        )
        cur_value = getattr(self, prop_key)

        if cur_value != new_value:
            setattr(self, f"_{prop_key}", new_value)
            return True

    #
    # Transport State
    #
    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, state: int):
        if self.States.is_valid(state):
            state = self.States(state)
            self.zone.api_alpha.request_action_3D(state)

            # Changing state wont work if we are part of a group
            # So if we are wanting to stop, leave the group
            if state == self.States.STOP and self.zone.group.is_member:
                self.zone.group.leave()
        else:
            self.zone._log_error(f"ZoneTransport.States {state} doesnt exist")

    def _set_state(self, state: int):
        if self.state != state:
            if self.States.is_valid(state):
                self._state = self.States(state)
                self.zone._event_publish(
                    getattr(self.Events, f"STATE_CHANGE_{self.state.name.upper()}"),
                    True,
                )
                return True
            else:
                self.zone._log_warning(f"ZoneTransport.States {state} doesnt exist")

    #
    # Transport Commands
    #
    def play(self):
        self.state = self.States.PLAY

    def stop(self):
        """note: stopping a stream will disconnect the client as will pausing an Airplay stream.

        note2: streams (Airplay, Chromecast, Spotify.Connect) have higher priority than analog inputs.
        Therefore, if both input types are playing to a zone then the higher priority will play. Likewise,
        if both types of input are playing to a zone and the stream is stopped then the zone will switch
        to playing the lower priority content.

        ref: https://vssl.gitbook.io/vssl-rest-api/zone-control/play-control
        """
        self.state = self.States.STOP

    def pause(self):
        self.state = self.States.PAUSE

    #
    # Transport States
    #
    @property
    def is_playing(self):
        return self.state == self.States.PLAY

    @property
    def is_stopped(self):
        return self.state == self.States.STOP

    @property
    def is_paused(self):
        return self.state == self.States.PAUSE

    #
    # Track Control
    #
    def next(self):
        self.zone.api_bravo.request_action_40_next()

    def prev(self):
        self.zone.api_bravo.request_action_40_prev()

    def back(self):
        self.prev()
        self.prev()

    #
    # Is the next button enabled
    #
    @property
    def has_next(self):
        return self._has_next

    @has_next.setter
    def set_has_next(self, val: int):
        pass  # read-only

    def _set_has_next(self, val: int):
        return self._set_bool_property("has_next", val, self.Events.HAS_NEXT_CHANGE)

    #
    # Track Prev_flag
    #
    @property
    def has_prev(self):
        return self._has_prev

    @has_prev.setter
    def has_prev(self, val: int):
        pass  # read-only

    def _set_has_prev(self, val: int):
        return self._set_bool_property("has_prev", val, self.Events.HAS_PREV_CHANGE)

    #
    # Track Shuffle
    #
    @property
    def is_shuffle(self):
        return self._is_shuffle

    @is_shuffle.setter
    def is_shuffle(self, val: int):
        pass  # read-only

    def _set_is_shuffle(self, val: int):
        return self._set_bool_property("is_shuffle", val, self.Events.IS_SHUFFLE_CHANGE)

    #
    # Track Repeat
    #
    @property
    def is_repeat(self):
        return self._is_repeat

    @is_repeat.setter
    def is_repeat(self, val: int):
        pass  # read-only

    def _set_is_repeat(self, val: int):
        val = self._default_on_state_stop(val, self.DEFAULTS["is_repeat"])
        if self.is_repeat != val:
            if self.Repeat.is_valid(val):
                self._is_repeat = self.Repeat(val)
                return True
            else:
                self.zone._log_error(f"ZoneTransport.Repeat {val} doesnt exist")

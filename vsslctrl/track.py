import logging
from . import zone
from typing import Dict, Union
from .data_structure import VsslIntEnum, ZoneDataClass

class TrackMetadata(ZoneDataClass):
    
    # https://florimond.dev/en/posts/2018/10/reconciling-dataclasses-and-properties-in-python

    #
    # Stream Sources
    #
    # DO NOT CHANGE - VSSL Defined
    #
    class Sources(VsslIntEnum):
        NOT_STREAMING = 0
        AIRPLAY = 1
        SPOTIFY = 4
        TUNEIN = 9
        ANALOG_IN = 15
        APPLE_DEVICE = 16
        DIRECT_URL = 17 # e.g play_url
        BLUETOOTH = 19
        TIDAL = 22
        GOOGLECAST = 24
        EXTERNAL = 25

    #
    # Transport Events
    #
    class Events():
        PREFIX               = 'track.'
        CHANGE               = PREFIX+'change'
        UPDATES              = PREFIX+'updates'
        TITLE_CHANGE         = PREFIX+'title_change'
        ALBUM_CHANGE         = PREFIX+'album_change'
        ARTIST_CHANGE        = PREFIX+'artist_change'
        GENRE_CHANGE         = PREFIX+'genre_change'
        DURATION_CHANGE      = PREFIX+'duration_change'
        PROGRESS_CHANGE      = PREFIX+'progress_change'
        COVER_ART_URL_CHANGE = PREFIX+'cover_art_url_change'
        SOURCE_CHANGE        = PREFIX+'source_change'
        URL_CHANGE           = PREFIX+'url_change'


    DEFAULTS = {
        'title': None,
        'album': None,
        'artist': None,
        'genre': None,
        'duration': 0,
        'progress': 0,
        'cover_art_url': None,
        'source': Sources.NOT_STREAMING,
        'url': None,
    }

    KEY_MAP = {
        'TotalTime': 'duration',
        'TrackName': 'title',
        'Album': 'album',
        'Artist': 'artist',
        'CoverArtUrl': 'cover_art_url',
        'Current Source': 'source',
        'Genre': 'genre',
        'PlayUrl': 'url'
    }

    def __init__(self, zone: 'zone.Zone'):
        self._zone = zone

        self._title: str = None
        self._album: str = None
        self._artist: str = None
        self._genre: str = None
        self._duration: int = 0
        self._progress: int = 0
        self._cover_art_url: str = None
        self._source = self.Sources.NOT_STREAMING
        self._url: str = None


    def as_dict(self):
        dic = super().as_dict()
        dic['progress_display'] = self.progress_display
        return dic

    #
    # VSSL doenst clear some vars on stopping of the stream, so we will do it
    #
    # Doing this will fire the change events on the bus. Instead of conditionally
    # using the getter functions since we want the changes to be propogated
    #
    # VSSL has a happit of caching the last song played, so we need to clear it
    #
    def set_defaults(self):
        for key, default_value in self.DEFAULTS.items():
            self._update_property(key, default_value, True)

    #
    # Updade a property and emit and event if changed
    #
    # Transport state is ignored when part of a group for its initial pull from master
    #
    def _update_property(self, key: str, new_value, ignore_transport_state = False):
        #Default if stopped
        if self._zone.transport.is_stopped and not ignore_transport_state:
            new_value = self.DEFAULTS[key]

        if getattr(self, key) != new_value:
            setattr(self, f'_{key}', new_value) #set private var
            new_set_value = getattr(self, key)

            self._zone._event_publish(
                getattr(self.Events, f'{key.upper()}_CHANGE'), 
                new_set_value
            )
            self._zone._event_publish(self.Events.CHANGE, (key, new_set_value))            

    #
    # Update the track properties from a group master when part of a group.
    # This is handled via the Eventbus
    #
    async def _update_property_from_group_master(self, data: Dict[str, int], *args, **kwargs) -> None:
        if hasattr(self, data[0]):
            setattr(self, data[0], data[1])

    #
    # Update from a JSON dict passed
    #
    def _map_response_dict(self, track_data: Dict[str, int]) -> None:

        """ Ignore the track data if zone is part of a group.

            VSSL has a happit of caching old track meta when part of a group

        """
        if not self._zone.group.is_member:

            for track_data_key, metadata_key in self.KEY_MAP.items():
                if track_data_key in track_data:
                    setattr(self, metadata_key, track_data[track_data_key])

    """ TODO!

        Now we added the child, lets propage the track to the new member.
        This only needs to happen once, as after wards the track data will
        be updated by the event bus

        Sometime, the VSSL responses with old cached track metadata, on the member zones
        but generally it responds with a BrowseView when its a member of a group

        When a group is created, the child will get the group index first (generally this will be the same
        as the index_id) then its transport state will be
        updated on the VSSL side.
        When the transport state is changed, the zone will request the track meta. VSSL will respond
        with the last cached metadata from the zone and not the correct meta from the current zone master.

    """
    def _pull_from_zone(self, zone: int) -> None:

        master = self._zone.vssl.get_zone(zone)

        if not master:
            self._log_error(f'Zone {zone} was not avaiable on VSSL, maybe we are not managing it')
            return

        for key, default_value in self.DEFAULTS.items():
            if hasattr(master.track, key):
                self._update_property(key, getattr(master.track, key), True)

    #
    # Track Title
    #
    @property
    def title(self) -> str:
        return self._title

    @title.setter
    def title(self, value: str) -> None:
        self._update_property('title', value)
    #
    # Track Album
    #
    @property
    def album(self) -> str:
        return self._album

    @album.setter
    def album(self, value: str) -> None:
        self._update_property('album', value)

    #
    # Track Artist
    #
    @property
    def artist(self) -> str:
        return self._artist

    @artist.setter
    def artist(self, value: str) -> None:
        self._update_property('artist', value)

    #
    # Track Genre
    #
    @property
    def genre(self) -> str:
        return self._genre

    @genre.setter
    def genre(self, value: str) -> None:
        self._update_property('genre', value)

    #
    # Track Duration
    #
    @property
    def duration(self) -> int:
        return self._duration

    @duration.setter
    def duration(self, value: int) -> None:
        self._update_property('duration', value)

    #
    # Track Duration
    #
    @property
    def progress(self) -> int:
        return self._progress

    @progress.setter
    def progress(self, value: int) -> None:
        self._update_property('progress', value)

    @property
    def progress_display(self):
        milliseconds = self.progress if self.progress != None else 0

        seconds, milliseconds = divmod(milliseconds, 1000)
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)

        formatted_time = ""

        if hours > 0:
            formatted_time += "{}:".format(hours)

        formatted_time += "{:02}:{:02}".format(minutes, seconds) if hours > 0 else "{}:{:02}".format(minutes, seconds)

        return formatted_time

    #
    # Track Cover Art
    #
    @property
    def cover_art_url(self) -> str:
        return self._cover_art_url

    @cover_art_url.setter
    def cover_art_url(self, value: str) -> None:
        self._update_property('cover_art_url', value)

    #
    # Track Source
    #
    @property
    def source(self) -> Sources:
        return self._source

    @source.setter
    def source(self, src: Sources) -> None:
        if self.Sources.is_valid(src):
            self._update_property('source', self.Sources(src))
        else:
            self._zone._log_error(f"TrackMetadata.Sources {src} doesnt exist")


    #
    # Track Duration
    #
    @property
    def url(self) -> str:
        return self._url

    @url.setter
    def url(self, value: str) -> None:
        self._update_property('url', value)
        
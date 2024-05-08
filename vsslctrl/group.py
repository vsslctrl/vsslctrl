import logging
from . import zone
from typing import Dict, Union
from .data_structure import ZoneDataClass


"""
    Note from VSSSL API, here for archive purpose

    AddZoneToGroup: If z1 is currently playing then you can create a new group by adding z2 by ~SetGroup(vsslSerial, 1, 2).  Z1 and z2
    will now be playing the z1 stream.  If the z1 stream is stopped then the group will automatically dissolve.  If a stream is
    started on z2 while z2 is in the group then the z2 content will not output on the z2 speaker until z2 is removed from the group.

    RemoveZoneFromGroup: If a group exists with z1 as the parent and (z2, z3) as children then you can remove z2 from the group by
    setting its parent to 255 ~SetGroup(vsslSerial, 255, 2).

    DissolveGroup: If a group exists with z1 as the parent and (z2, z3) as children then you can remove z2 from the group by
    setting the child group to 255 ~SetGroup(vsslSerial, 1, 255).

    Ref: https://vssl.gitbook.io/vssl-rest-api/zone-control/set-group

"""


class ZoneGroup(ZoneDataClass):
    #
    # Group Events
    #
    class Events:
        PREFIX = "zone.group."
        INDEX_CHANGE = PREFIX + "index_change"
        SOURCE_CHANGE = PREFIX + "source_change"
        IS_MASTER_CHANGE = PREFIX + "is_master_change"

    DEFAULTS = {"index": 0, "source": None, "is_master": False}

    def __init__(self, zone: "zone.Zone"):
        self._zone = zone

        """ On a A3.x the group index are, Im not sure if this is consistant with A1.x or A6.x:

            Zone 1: 9
            Zone 2: 10
            Zone 3: 11

            This can be assigned to other group members when this zone is the source.

            I have not idea if this is how it was intended, but its working on the A3.x

        """
        self._index_id = zone.id + 8

        # index is assigned when a stream is started (see action_32)
        self._index = 0
        self._source = None
        self._is_master = False

    #
    # Group Add Zone
    #
    def add_member(self, zone_id: "zone.Zone.IDs"):
        if self._zone.id == zone_id:
            self._zone._log_error(f"Zone {zone_id} cant be parent and member")
            return False

        if zone.Zone.IDs.is_not_valid(zone_id):
            self._zone._log_error(f"Zone {zone_id} doesnt exist")
            return False

        if self.is_member:
            self._zone._log_error(
                f"Zone {self._zone.id} already a member of Zone {self.source} group"
            )
            return False

        if self._zone.transport.is_stopped:
            self._zone._log_error(
                f"Zone {self._zone.id} cant be a group master when not playing a source"
            )
            return False

        self._zone._api_alpha.request_action_4B_add(zone_id)

    #
    # Group Remove Child
    #
    def remove_member(self, zone_id: "zone.Zone.IDs"):
        self._zone._api_alpha.request_action_4B_remove(zone_id)

    #
    # Group Dissolve
    #
    def dissolve(self):
        self._zone._api_alpha.request_action_4B_dissolve()

    #
    # Leave any groups if is a member
    #
    def leave(self) -> None:
        self._zone._api_alpha.request_action_4B_remove(self._zone.id)

    @property
    def index_id(self):
        return self._index_id

    @index_id.setter
    def index_id(self, index_id: int):
        pass  # read-only

    #
    # Group Index
    #
    # The index is assigned when the zone starts a stream.
    #
    @property
    def index(self):
        return self._index

    @index.setter
    def index(self, index: int):
        pass  # read-only

    #
    # Group Source
    #
    @property
    def source(self):
        return self._source

    @source.setter
    def source(self, grs: int):
        pass  # read-only

    def _set_source(self, grs: int):
        new_source = (
            zone.Zone.IDs(grs) if grs != 255 and zone.Zone.IDs.is_valid(grs) else None
        )

        if self.source != new_source:
            self._source = new_source
            return True

    @property
    def is_member(self):
        return self.source is not None

    #
    # Group: This zone is a master for a group
    #
    # TODO: propogate track meta to member zones.
    # Only play state is propgated by the VSSL device
    #
    @property
    def is_master(self):
        return self._is_master

    @is_master.setter
    def is_master(self, grm: int):
        pass  # read-only

    def _set_is_master(self, grm: int):
        if self.is_master != bool(grm):
            self._is_master = grm != 0
            return True

    #
    # Get zone members of this groups
    #
    @property
    def members(self):
        if not self.is_master:
            return []
        return [
            zone
            for zone in self._zone.vssl.zones.values()
            if zone.group.index == self.index and zone.group.is_member
        ]

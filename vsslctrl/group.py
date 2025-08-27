import logging
from . import zone
from typing import Dict, Union
from .data_structure import ZoneDataClass, ZoneIDs, DeviceFeatureFlags


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
    SLAVE_CLEAR_BYTE = 255

    #
    # Group Events
    #
    class Events:
        PREFIX = "zone.group."
        SOURCE_CHANGE = PREFIX + "source_change"
        IS_MASTER_CHANGE = PREFIX + "is_master_change"
        IS_PARTY_ZONE_MEMBER_CHANGE = PREFIX + "is_party_zone_member_change"

    DEFAULTS = {
        "source": None,
        "is_master": False,
        "is_party_zone_member": False,
    }

    def __init__(self, zone: "zone.Zone"):
        self.zone = zone
        self._source = self.DEFAULTS["source"]
        self._is_master = self.DEFAULTS["is_master"]
        self._is_party_zone_member = self.DEFAULTS["is_party_zone_member"]

    #
    # Group Add Zone
    #
    def add_member(self, zone_id: ZoneIDs):
        # Check this device is a multizone device
        if not self.zone.vssl.model.supports_feature(DeviceFeatureFlags.GROUPING):
            self.zone._log_error(
                f"VSSL {self.zone.vssl.model.name} doesnt support grouping"
            )
            return False

        if self.zone.id == zone_id:
            self.zone._log_error(f"Zone {zone_id} cant be parent and member")
            return False

        if ZoneIDs.is_not_valid(zone_id):
            self.zone._log_error(f"Zone {zone_id} doesnt exist")
            return False

        if self.is_member:
            self.zone._log_error(
                f"Zone {self.zone.id} already a member of Zone {self.source} group"
            )
            return False

        if self.zone.transport.is_stopped:
            self.zone._log_error(
                f"Zone {self.zone.id} cant be a group master when not playing a source"
            )
            return False

        self.zone.api_alpha.request_action_4B_add(zone_id)

    #
    # Group Remove Child
    #
    def remove_member(self, zone_id: ZoneIDs):
        self.zone.api_alpha.request_action_4B_remove(zone_id)

    #
    # Group Dissolve
    #
    def dissolve(self):
        self.zone.api_alpha.request_action_4B_dissolve()

    #
    # Leave any groups if is a member
    #
    def leave(self):
        self.zone.api_alpha.request_action_4B_remove(self.zone.id)

    #
    # Group Source Zone
    #
    @property
    def source(self):
        return self._source

    @source.setter
    def source(self, zone_id: int):
        pass  # read-only

    def _set_source(self, zone_id: int):
        new_source = (
            ZoneIDs(zone_id)
            if zone_id != self.SLAVE_CLEAR_BYTE and ZoneIDs.is_valid(zone_id)
            else None
        )

        if self.source != new_source:
            self._source = new_source

    #
    # Is this zone a member of a group
    #
    @property
    def is_member(self):
        return self.source is not None

    #
    # This zone is a master of a group
    #
    @property
    def is_master(self):
        return self._is_master

    @is_master.setter
    def is_master(self, is_master: bool):
        pass  # read-only

    def _set_is_master(self, is_master: bool):
        if self.is_master != is_master:
            self._is_master = bool(is_master)

    #
    # Get the groups master zone
    #
    @property
    def master(self):
        if self.is_master:
            return self
        if self.source is not None:
            return self.zone.vssl.get_zone_by_id(self.source)

    #
    # Get group member zones
    #
    # TODO : Currently this will only return group members if they are manged by
    # vsslctrl - we could change the API to not check zone ID and get the
    # group status of all zones
    #
    @property
    def members(self):
        if not self.is_master:
            return []
        return [
            zone
            for zone in self.zone.vssl.zones.values()
            if zone.group.index == self.index and zone.group.is_member
        ]

    #
    # Party Mode - Is this zone a party mode member
    #
    # Think this might be obsolete since airplay-2 has grouping built-in
    #
    @property
    def is_party_zone_member(self):
        return bool(self._is_party_zone_member)

    @is_party_zone_member.setter
    def is_party_zone_member(self, state: int):
        # Check this device supports party mode
        if not self.zone.vssl.model.supports_feature(DeviceFeatureFlags.PARTY_ZONE):
            self.zone._log_error(f"VSSL {self.zone.vssl.model.name} doesnt party zone")
            return

        self.zone.api_alpha.request_action_0C(state)

    def is_party_zone_member_toggle(self):
        self.is_party_zone_member = not self.is_party_zone_member

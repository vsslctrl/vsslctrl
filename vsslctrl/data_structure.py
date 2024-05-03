from enum import IntEnum
from abc import ABC, abstractmethod
from .decorators import sterilizable


class VsslIntEnum(IntEnum):

    @classmethod
    def is_valid(cls, value):
        try:
            cls(value)
            return True
        except ValueError:
            return False

    @classmethod
    def is_not_valid(cls, value):
        return not cls.is_valid(value)

    @classmethod
    def get(cls, value, default = None):
        try:
            return cls(value)
        except ValueError:
            return default


@sterilizable
class VsslDataClass(ABC):

    def _set_property(self, property_name: str, new_value):
        log = False
        direct_setter = f'_set_{property_name}'

        if hasattr(self, direct_setter):
            log = getattr(self, direct_setter)(new_value)
        else:
            current_value = getattr(self, property_name)
            if current_value != new_value:
                setattr(self, f'_{property_name}', new_value)
                log = True
                
        if log:
            updated_value = getattr(self, property_name)

            message = ''
            if isinstance(updated_value, IntEnum):
                message = f'{self.__class__.__name__} set {property_name}: {updated_value.name} ({updated_value.value})'
            else:
                message = f'{self.__class__.__name__} set {property_name}: {updated_value}'

            self._vssl._log_debug(message) 

            self._vssl.event_bus.publish(
                getattr(self.Events, property_name.upper() + '_CHANGE'),
                self._vssl.ENTITY_ID,
                updated_value
            )

@sterilizable
class ZoneDataClass(ABC):

    def _set_property(self, property_name: str, new_value):
        log = False
        direct_setter = f'_set_{property_name}'

        if hasattr(self, direct_setter):
            log = getattr(self, direct_setter)(new_value)
        else:
            current_value = getattr(self, property_name)
            if current_value != new_value:
                setattr(self, f'_{property_name}', new_value)
                log = True
                
        if log:
            updated_value = getattr(self, property_name)

            message = ''
            if isinstance(updated_value, IntEnum):
                message = f'{self.__class__.__name__} set {property_name}: {updated_value.name} ({updated_value.value})'
            else:
                message = f'{self.__class__.__name__} set {property_name}: {updated_value}'

            self._zone._log_debug(message) 

            self._zone._event_publish(
                getattr(self.Events, property_name.upper() + '_CHANGE'), 
                updated_value
            )
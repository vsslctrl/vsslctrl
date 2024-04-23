from .utils import IntEnum

def zone_data_class(cls):
    def default_set_property(self, property_name: str, new_value):
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
                getattr(getattr(self.__class__, 'Events'), property_name.upper() + '_CHANGE'), 
                updated_value
            )

    cls._set_property = default_set_property
    return cls
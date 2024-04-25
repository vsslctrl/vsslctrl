import json

def sterilizable(cls):

    # Define __iter__ method
    def __iter__(self):
        if hasattr(self.__class__, 'DEFAULTS'):
            for key in getattr(self.__class__, 'DEFAULTS'):
                yield key, getattr(self, key)
        else:        
            for attr_name in dir(self):
                if not attr_name.startswith('_'):  # Exclude private attributes
                    yield attr_name, getattr(self, attr_name)

    cls.__iter__ = __iter__

    def _as_dict(self):
        return dict(self)

    cls.as_dict = _as_dict

    def _as_json(self):
        return json.dumps(self.as_dict())

    cls.as_json = _as_json

    return cls
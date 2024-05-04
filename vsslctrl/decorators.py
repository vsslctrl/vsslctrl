import json
import logging


def sterilizable(cls):
    # Define __iter__ method
    def __iter__(self):
        if hasattr(self.__class__, "DEFAULTS"):
            for key in getattr(self.__class__, "DEFAULTS"):
                yield key, getattr(self, key)
        else:
            for attr_name in dir(self):
                if not attr_name.startswith("_"):  # Exclude private attributes
                    yield attr_name, getattr(self, attr_name)

    cls.__iter__ = __iter__

    def _as_dict(self):
        return dict(self)

    cls.as_dict = _as_dict

    def _as_json(self):
        return json.dumps(self.as_dict())

    cls.as_json = _as_json

    return cls


def logging_helpers(prefix=""):
    def decorator(cls):
        logger = logging.getLogger(__name__)

        def _is_log_level(self, level: str):
            level = level.upper()
            if hasattr(logging, level):
                return getattr(logging, level) == logger.getEffectiveLevel()
            else:
                return False

        setattr(cls, "_is_log_level", _is_log_level)

        LOG_LEVELS = {"debug", "info", "warning", "error", "critical"}

        def create_log_function(log_level, prefix=prefix):  # Pass prefix here
            def log_function(self, message):  # Rename prefix to custom_prefix
                final_prefix = getattr(self, "_log_prefix", prefix)
                log_level(f"{final_prefix} {message}")

            return log_function

        for level in LOG_LEVELS:
            log_func = getattr(logger, level)
            setattr(
                cls, f"_log_{level}", create_log_function(log_func)
            )  # Pass prefix here

        return cls

    return decorator

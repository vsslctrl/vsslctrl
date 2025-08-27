import json
import logging
from functools import wraps
from . import LOG_DIVIDER


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


#
# Validate response lengths
#
def validate_response_length(expected_length: int = 2):
    def decorator(func):
        @wraps(func)
        def wrapper(
            self,
            frame_header: bytes,
            frame_data: bytes,
            *args,
            **kwargs,
        ):
            # frame header is always 3 bytes in length
            if len(frame_header) != 3:
                self._log_debug(LOG_DIVIDER)
                self._log_warning(
                    f"response header validation failed: frame header requires 3 bytes, but got {len(frame_header)}."
                )
                self._log_debug(LOG_DIVIDER)
                return None

            # check length of data is expected
            if frame_header[2] != expected_length:
                self._log_debug(LOG_DIVIDER)
                self._log_warning(
                    f"response length validation failed: expected {expected_length}, but got {frame_header[2]}"
                )
                self._log_debug(LOG_DIVIDER)
                return None

            # check data has correct length
            if frame_header[2] != len(frame_data):
                self._log_debug(LOG_DIVIDER)
                self._log_warning(
                    f"response data length validation failed: expected {expected_length}, but got {len(frame_data)}"
                )
                self._log_debug(LOG_DIVIDER)
                return None

            return func(self, frame_header, frame_data, *args, **kwargs)

        return wrapper

    return decorator


#
# Validate response Zone ID
#
def validate_response_zone_id(index: int = 0):
    def decorator(func):
        @wraps(func)
        def wrapper(
            self,
            frame_header: bytes,
            frame_data: bytes,
            *args,
            **kwargs,
        ):
            if len(frame_data) < 1:
                self._log_debug(LOG_DIVIDER)
                self._log_warning(
                    f"response zone ID validation failed: frame has no data."
                )
                self._log_debug(LOG_DIVIDER)
                return None

            if self.zone.id and frame_data[index] != self.zone.id:
                self._log_debug(LOG_DIVIDER)
                self._log_warning(
                    f"response zone ID validation failed: expecting zone ID {self.zone.id}, but got {frame_data[index]}."
                )
                self._log_debug(LOG_DIVIDER)
                return None

            return func(self, frame_header, frame_data, *args, **kwargs)

        return wrapper

    return decorator

"""Helper functions for datetime and timestamp conversions.

Warning:
    Contents of this module are intended to be used internally by the library and *not* by the
    user. Changes to this module are not considered breaking changes and may not be documented in
    the changelog.
"""
import datetime as dtm
import time
from typing import TYPE_CHECKING, Optional, Union

if TYPE_CHECKING:
    from zalo_bot import Bot

# pytz workaround - only available if installed as APScheduler dependency
DTM_UTC = dtm.timezone.utc
try:
    import pytz

    UTC = pytz.utc
except ImportError:
    UTC = DTM_UTC  # type: ignore[assignment]


def _localize(datetime: dtm.datetime, tzinfo: dtm.tzinfo) -> dtm.datetime:
    """Localize datetime, handling UTC based on pytz availability"""
    if tzinfo is DTM_UTC:
        return datetime.replace(tzinfo=DTM_UTC)
    return tzinfo.localize(datetime)  # type: ignore[attr-defined]


def to_float_timestamp(
    time_object: Union[float, dtm.timedelta, dtm.datetime, dtm.time],
    reference_timestamp: Optional[float] = None,
    tzinfo: Optional[dtm.tzinfo] = None,
) -> float:
    """Convert time object to float POSIX timestamp.

    Args:
        time_object: Time value to convert:
            * float: seconds from reference_timestamp
            * timedelta: time increment from reference_timestamp
            * datetime: absolute date/time value
            * time: specific time of day
        reference_timestamp: POSIX timestamp for relative calculations. Defaults to now.
        tzinfo: Timezone for naive datetime objects. Defaults to UTC.

    Returns:
        float: POSIX timestamp

    Raises:
        TypeError: If time_object type is not supported.
        ValueError: If time_object is datetime and reference_timestamp is not None.
    """
    if reference_timestamp is None:
        reference_timestamp = time.time()
    elif isinstance(time_object, dtm.datetime):
        raise ValueError("t is an (absolute) datetime while reference_timestamp is not None")

    if isinstance(time_object, dtm.timedelta):
        return reference_timestamp + time_object.total_seconds()
    if isinstance(time_object, (int, float)):
        return reference_timestamp + time_object

    if tzinfo is None:
        tzinfo = UTC

    if isinstance(time_object, dtm.time):
        reference_dt = dtm.datetime.fromtimestamp(
            reference_timestamp, tz=time_object.tzinfo or tzinfo
        )
        reference_date = reference_dt.date()
        reference_time = reference_dt.timetz()

        aware_datetime = dtm.datetime.combine(reference_date, time_object)
        if aware_datetime.tzinfo is None:
            aware_datetime = _localize(aware_datetime, tzinfo)

        # Use tomorrow if time of day has passed today
        if reference_time > aware_datetime.timetz():
            aware_datetime += dtm.timedelta(days=1)
        return _datetime_to_float_timestamp(aware_datetime)
    if isinstance(time_object, dtm.datetime):
        if time_object.tzinfo is None:
            time_object = _localize(time_object, tzinfo)
        return _datetime_to_float_timestamp(time_object)

    raise TypeError(f"Unable to convert {type(time_object).__name__} object to timestamp")


def to_timestamp(
    dt_obj: Union[float, dtm.timedelta, dtm.datetime, dtm.time, None],
    reference_timestamp: Optional[float] = None,
    tzinfo: Optional[dtm.tzinfo] = None,
) -> Optional[int]:
    """Wrapper over to_float_timestamp returning integer timestamp."""
    return (
        int(to_float_timestamp(dt_obj, reference_timestamp, tzinfo))
        if dt_obj is not None
        else None
    )


def from_timestamp(
    unixtime: Optional[int],
    tzinfo: Optional[dtm.tzinfo] = None,
) -> Optional[dtm.datetime]:
    """Convert unix timestamp to timezone aware datetime.

    Args:
        unixtime: Integer POSIX timestamp.
        tzinfo: Timezone for conversion. Defaults to UTC.

    Returns:
        Timezone aware datetime or None.
    """
    if unixtime is None:
        return None

    return dtm.datetime.fromtimestamp(unixtime, tz=UTC if tzinfo is None else tzinfo)


def extract_tzinfo_from_defaults(bot: Optional["Bot"]) -> Union[dtm.tzinfo, None]:
    """Extract timezone info from bot defaults."""
    # Don't use isinstance(bot, ExtBot) to avoid job-queue dependencies
    if bot is None:
        return None

    if hasattr(bot, "defaults") and bot.defaults:
        return bot.defaults.tzinfo
    return None


def _datetime_to_float_timestamp(dt_obj: dtm.datetime) -> float:
    """Convert datetime to float timestamp with sub-second precision."""
    if dt_obj.tzinfo is None:
        dt_obj = dt_obj.replace(tzinfo=dtm.timezone.utc)
    return dt_obj.timestamp()

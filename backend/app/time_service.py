"""TimeService - Authoritative timezone-aware time operations.

This service provides the single source of truth for all time/date operations
in the Antigen application. It ensures that Llama/Ollama never invents or
calculates dates/times, and that all time operations are timezone-aware.

The service defaults to Africa/Nairobi timezone but supports per-user
timezone configuration.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
import pytz

# Default timezone for the application
DEFAULT_TIMEZONE = "Africa/Nairobi"


class TimeService:
    """Centralized time service for all application time operations."""
    
    @staticmethod
    def now_utc() -> datetime:
        """Get current UTC time as timezone-aware datetime."""
        return datetime.now(timezone.utc)
    
    @staticmethod
    def now_local(user_timezone: str = DEFAULT_TIMEZONE) -> datetime:
        """Get current time in user's timezone as timezone-aware datetime."""
        try:
            tz = pytz.timezone(user_timezone)
            return datetime.now(tz)
        except Exception:
            # Fallback to default timezone if user timezone is invalid
            tz = pytz.timezone(DEFAULT_TIMEZONE)
            return datetime.now(tz)
    
    @staticmethod
    def today(user_timezone: str = DEFAULT_TIMEZONE) -> datetime:
        """Get today's date at midnight in user's timezone."""
        local_now = TimeService.now_local(user_timezone)
        return local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    @staticmethod
    def current_time(user_timezone: str = DEFAULT_TIMEZONE) -> str:
        """Get current time as HH:MM format in user's timezone."""
        local_now = TimeService.now_local(user_timezone)
        return local_now.strftime("%H:%M")
    
    @staticmethod
    def current_weekday(user_timezone: str = DEFAULT_TIMEZONE) -> str:
        """Get current weekday name in user's timezone."""
        local_now = TimeService.now_local(user_timezone)
        return local_now.strftime("%A")
    
    @staticmethod
    def current_timestamp(user_timezone: str = DEFAULT_TIMEZONE) -> float:
        """Get current timestamp in user's timezone."""
        local_now = TimeService.now_local(user_timezone)
        return local_now.timestamp()
    
    @staticmethod
    def format_date(user_timezone: str = DEFAULT_TIMEZONE) -> str:
        """Get current date as YYYY-MM-DD format in user's timezone."""
        local_now = TimeService.now_local(user_timezone)
        return local_now.strftime("%Y-%m-%d")
    
    @staticmethod
    def convert_utc_to_local(utc_datetime: datetime, user_timezone: str = DEFAULT_TIMEZONE) -> datetime:
        """Convert UTC datetime to user's local timezone."""
        if utc_datetime.tzinfo is None:
            # Assume naive datetime is UTC
            utc_datetime = utc_datetime.replace(tzinfo=timezone.utc)
        
        try:
            tz = pytz.timezone(user_timezone)
            return utc_datetime.astimezone(tz)
        except Exception:
            # Fallback to default timezone
            tz = pytz.timezone(DEFAULT_TIMEZONE)
            return utc_datetime.astimezone(tz)
    
    @staticmethod
    def convert_local_to_utc(local_datetime: datetime, user_timezone: str = DEFAULT_TIMEZONE) -> datetime:
        """Convert local datetime in user's timezone to UTC."""
        if local_datetime.tzinfo is None:
            # Assume naive datetime is in user's timezone
            try:
                tz = pytz.timezone(user_timezone)
                local_datetime = tz.localize(local_datetime)
            except Exception:
                tz = pytz.timezone(DEFAULT_TIMEZONE)
                local_datetime = tz.localize(local_datetime)
        
        return local_datetime.astimezone(timezone.utc)
    
    @staticmethod
    def tomorrow(user_timezone: str = DEFAULT_TIMEZONE) -> datetime:
        """Get tomorrow's date at midnight in user's timezone."""
        today = TimeService.today(user_timezone)
        return today + timedelta(days=1)
    
    @staticmethod
    def yesterday(user_timezone: str = DEFAULT_TIMEZONE) -> datetime:
        """Get yesterday's date at midnight in user's timezone."""
        today = TimeService.today(user_timezone)
        return today - timedelta(days=1)
    
    @staticmethod
    def days_until(target_weekday: str, user_timezone: str = DEFAULT_TIMEZONE) -> int:
        """Calculate days until a specific weekday (e.g., "Friday").
        
        Args:
            target_weekday: Full weekday name (e.g., "Monday", "Friday")
            user_timezone: User's timezone string
            
        Returns:
            Number of days until the target weekday (0-6)
        """
        now = TimeService.now_local(user_timezone)
        current_weekday = now.strftime("%A")
        
        # Map weekday names to numbers (0=Monday, 6=Sunday)
        weekday_map = {
            "Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3,
            "Friday": 4, "Saturday": 5, "Sunday": 6
        }
        
        target_num = weekday_map.get(target_weekday)
        current_num = weekday_map.get(current_weekday)
        
        if target_num is None or current_num is None:
            raise ValueError(f"Invalid weekday: {target_weekday}")
        
        if target_num >= current_num:
            return target_num - current_num
        else:
            return (7 - current_num) + target_num
    
    @staticmethod
    def is_today(date: datetime, user_timezone: str = DEFAULT_TIMEZONE) -> bool:
        """Check if a given date is today in user's timezone."""
        today = TimeService.today(user_timezone)
        if date.tzinfo is None:
            date = TimeService.convert_utc_to_local(date.replace(tzinfo=timezone.utc), user_timezone)
        else:
            date = TimeService.convert_utc_to_local(date, user_timezone)
        
        return date.date() == today.date()
    
    @staticmethod
    def is_tomorrow(date: datetime, user_timezone: str = DEFAULT_TIMEZONE) -> bool:
        """Check if a given date is tomorrow in user's timezone."""
        tomorrow = TimeService.tomorrow(user_timezone)
        if date.tzinfo is None:
            date = TimeService.convert_utc_to_local(date.replace(tzinfo=timezone.utc), user_timezone)
        else:
            date = TimeService.convert_utc_to_local(date, user_timezone)
        
        return date.date() == tomorrow.date()
    
    @staticmethod
    def is_in_past(date: datetime, user_timezone: str = DEFAULT_TIMEZONE) -> bool:
        """Check if a given date is in the past in user's timezone."""
        now = TimeService.now_local(user_timezone)
        if date.tzinfo is None:
            date = TimeService.convert_utc_to_local(date.replace(tzinfo=timezone.utc), user_timezone)
        else:
            date = TimeService.convert_utc_to_local(date, user_timezone)
        
        return date < now
    
    @staticmethod
    def is_in_future(date: datetime, user_timezone: str = DEFAULT_TIMEZONE) -> bool:
        """Check if a given date is in the future in user's timezone."""
        now = TimeService.now_local(user_timezone)
        if date.tzinfo is None:
            date = TimeService.convert_utc_to_local(date.replace(tzinfo=timezone.utc), user_timezone)
        else:
            date = TimeService.convert_utc_to_local(date, user_timezone)
        
        return date > now
    
    @staticmethod
    def days_between(date1: datetime, date2: datetime) -> int:
        """Calculate the number of days between two dates."""
        if date1.tzinfo is None:
            date1 = date1.replace(tzinfo=timezone.utc)
        if date2.tzinfo is None:
            date2 = date2.replace(tzinfo=timezone.utc)
        
        delta = date2 - date1
        return abs(delta.days)
    
    @staticmethod
    def hours_between(timestamp1: datetime, timestamp2: datetime) -> float:
        """Calculate the number of hours between two timestamps."""
        if timestamp1.tzinfo is None:
            timestamp1 = timestamp1.replace(tzinfo=timezone.utc)
        if timestamp2.tzinfo is None:
            timestamp2 = timestamp2.replace(tzinfo=timezone.utc)
        
        delta = timestamp2 - timestamp1
        return abs(delta.total_seconds() / 3600)
    
    @staticmethod
    def beginning_of_day(date: datetime, user_timezone: str = DEFAULT_TIMEZONE) -> datetime:
        """Get the beginning of the day for a given date in user's timezone."""
        if date.tzinfo is None:
            date = TimeService.convert_utc_to_local(date.replace(tzinfo=timezone.utc), user_timezone)
        else:
            date = TimeService.convert_utc_to_local(date, user_timezone)
        
        return date.replace(hour=0, minute=0, second=0, microsecond=0)
    
    @staticmethod
    def end_of_day(date: datetime, user_timezone: str = DEFAULT_TIMEZONE) -> datetime:
        """Get the end of the day for a given date in user's timezone."""
        if date.tzinfo is None:
            date = TimeService.convert_utc_to_local(date.replace(tzinfo=timezone.utc), user_timezone)
        else:
            date = TimeService.convert_utc_to_local(date, user_timezone)
        
        return date.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    @staticmethod
    def beginning_of_week(date: datetime, user_timezone: str = DEFAULT_TIMEZONE) -> datetime:
        """Get the beginning of the week (Monday) for a given date in user's timezone."""
        if date.tzinfo is None:
            date = TimeService.convert_utc_to_local(date.replace(tzinfo=timezone.utc), user_timezone)
        else:
            date = TimeService.convert_utc_to_local(date, user_timezone)
        
        # Monday is weekday 0
        days_since_monday = date.weekday()
        beginning = date - timedelta(days=days_since_monday)
        return beginning.replace(hour=0, minute=0, second=0, microsecond=0)
    
    @staticmethod
    def end_of_week(date: datetime, user_timezone: str = DEFAULT_TIMEZONE) -> datetime:
        """Get the end of the week (Sunday) for a given date in user's timezone."""
        if date.tzinfo is None:
            date = TimeService.convert_utc_to_local(date.replace(tzinfo=timezone.utc), user_timezone)
        else:
            date = TimeService.convert_utc_to_local(date, user_timezone)
        
        # Sunday is weekday 6
        days_until_sunday = 6 - date.weekday()
        end = date + timedelta(days=days_until_sunday)
        return end.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    @staticmethod
    def get_time_context(user_timezone: str = DEFAULT_TIMEZONE) -> dict:
        """Get comprehensive time context for system prompts.
        
        Returns a dictionary with all time information needed for LLM context.
        """
        now_utc = TimeService.now_utc()
        now_local = TimeService.now_local(user_timezone)
        
        return {
            "utc": now_utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "local": now_local.strftime("%Y-%m-%d %H:%M:%S"),
            "date": TimeService.format_date(user_timezone),
            "time": TimeService.current_time(user_timezone),
            "weekday": TimeService.current_weekday(user_timezone),
            "timezone": user_timezone,
            "timestamp": TimeService.current_timestamp(user_timezone),
            "tomorrow": TimeService.tomorrow(user_timezone).strftime("%Y-%m-%d"),
            "yesterday": TimeService.yesterday(user_timezone).strftime("%Y-%m-%d"),
        }
    
    @staticmethod
    def is_valid_timezone(timezone_str: str) -> bool:
        """Check if a timezone string is a valid IANA timezone."""
        try:
            pytz.timezone(timezone_str)
            return True
        except Exception:
            return False
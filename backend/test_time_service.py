"""Test TimeService functionality."""
from app.time_service import TimeService

# Test basic time functions
print("Testing TimeService...")

# Test current time
print(f"Current UTC: {TimeService.now_utc()}")
print(f"Current local (Africa/Nairobi): {TimeService.now_local('Africa/Nairobi')}")
print(f"Current time: {TimeService.current_time('Africa/Nairobi')}")
print(f"Current date: {TimeService.format_date('Africa/Nairobi')}")
print(f"Current weekday: {TimeService.current_weekday('Africa/Nairobi')}")

# Test timezone conversion
utc_time = TimeService.now_utc()
local_time = TimeService.convert_utc_to_local(utc_time, 'Africa/Nairobi')
print(f"UTC to local conversion: {utc_time} -> {local_time}")

# Test date calculations
print(f"Tomorrow: {TimeService.tomorrow('Africa/Nairobi')}")
print(f"Yesterday: {TimeService.yesterday('Africa/Nairobi')}")

# Test time context
context = TimeService.get_time_context('Africa/Nairobi')
print(f"Time context: {context}")

# Test timezone validation
print(f"Is Africa/Nairobi valid: {TimeService.is_valid_timezone('Africa/Nairobi')}")
print(f"Is Invalid/Timezone valid: {TimeService.is_valid_timezone('Invalid/Timezone')}")

print("TimeService tests completed successfully!")

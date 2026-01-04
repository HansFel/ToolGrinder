"""Einfacher Test für JSON-Validierung in Grinder.py"""
from Grinder import validate_json_string

valid_json = '{"a": 1, "b": [true, false, null]}'
invalid_json = '{"a": 1, "b": [true, false, null]'

print('Valid test:', validate_json_string(valid_json))
print('Invalid test:', validate_json_string(invalid_json))

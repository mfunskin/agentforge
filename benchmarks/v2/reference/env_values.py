"""Parse deployment variable lines into a string mapping."""

import re


NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")


def parse_env(lines):
    values = {}
    for line in lines:
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        key, separator, raw_value = text.partition("=")
        key = key.strip()
        if not separator or not NAME.fullmatch(key):
            raise ValueError("invalid environment variable name or assignment")
        value = raw_value.strip()
        if value.startswith('"') or value.endswith('"'):
            if len(value) < 2 or not (value.startswith('"') and value.endswith('"')):
                raise ValueError("unclosed quoted environment value")
            value = value[1:-1]
        values[key] = value
    return values

"""Parse deployment variable lines into a string mapping."""


def parse_env(lines):
    values = {}
    for line in lines:
        if not line:
            continue
        key, value = line.split("=")
        values[key] = value.strip().strip('"')
    return values

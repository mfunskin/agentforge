def parse_record(line: str) -> list[str]:
    return [field.strip('"') for field in line.strip().split(",")]

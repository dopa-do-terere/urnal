def only_digits(value: str | None) -> str:
    return "".join(c for c in (value or "") if c.isdigit())

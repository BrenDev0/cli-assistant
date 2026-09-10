AUTO = {"on": False}


def auto() -> bool:
    return AUTO["on"]


def toggle_auto() -> bool:
    AUTO["on"] = not AUTO["on"]
    return AUTO["on"]

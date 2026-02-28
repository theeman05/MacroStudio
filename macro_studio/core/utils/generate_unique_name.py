import re
from typing import Union, Iterable


def generateUniqueName(existing: Union[set, dict, list, Iterable], base_name):
    """
    Generates a unique name by appending (1), (2), etc., if the base_name is taken.
    """
    if isinstance(existing, (set, dict)):
        existing_names = existing
    else:
        existing_names = set(existing)

    match_existing = re.match(r"^(.*?)\s\(\d+\)$", base_name)
    if match_existing:
        core_name = match_existing.group(1)
    else:
        core_name = base_name

    i = 1
    test_name = base_name
    # If base_name exists, start appending numbers
    if base_name in existing_names:
        while True:
            test_name = f"{core_name} ({i})"
            if test_name not in existing_names:
                break
            i += 1

    return test_name
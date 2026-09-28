import json
import os
import sys


PREFIX = "window.ATLAS="


def load_atlas(path):
    with open(path, encoding="utf-8") as f:
        source = f.read().strip()
    if not source.startswith(PREFIX) or not source.endswith(";"):
        raise ValueError("data.js does not contain the expected window.ATLAS assignment")
    return json.loads(source[len(PREFIX):-1])


def validate_atlas(data):
    errors = []
    if int(data.get("totalStars", 0)) <= 0:
        errors.append("totalStars must be greater than zero")
    if not data.get("cities"):
        errors.append("cities must not be empty")
    if not data.get("countries"):
        errors.append("countries must not be empty")
    if errors:
        raise ValueError("; ".join(errors))


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "data.js")
    data = load_atlas(path)
    validate_atlas(data)
    print(
        f"atlas data valid: stars={data['totalStars']} "
        f"cities={len(data['cities'])} countries={len(data['countries'])}"
    )


if __name__ == "__main__":
    main()

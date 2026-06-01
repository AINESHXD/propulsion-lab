"""Python-API export (Day 26).

Turns a console/engine configuration into a standalone, runnable ``.py`` script
that reproduces the simulation by calling the PropulsionLab HTTP API. The script
uses only the Python standard library (``urllib``), so it runs anywhere with no
pip installs, and - because it POSTs the exact same inputs to the same endpoint
the UI uses - it produces the same numbers by construction.
"""

from __future__ import annotations

import datetime as _dt
import pprint

_TEMPLATE = '''#!/usr/bin/env python3
"""PropulsionLab - generated {label} script.

Reproduces the cycle you configured in the PropulsionLab web console by calling
the public HTTP API. Standard library only - no pip installs required.

Generated {timestamp} from the console UI state.
Point BASE_URL at your own deployment if you are not running locally.
"""
from __future__ import annotations

import json
import urllib.request

BASE_URL = "{base_url}"
ENDPOINT = "{endpoint}"

# Exact inputs from the console UI state.
INPUTS = {inputs_literal}


def run(base_url: str = BASE_URL) -> dict:
    """POST the inputs to the PropulsionLab API and return the result dict."""
    payload = json.dumps(INPUTS).encode("utf-8")
    request = urllib.request.Request(
        base_url + ENDPOINT,
        data=payload,
        headers={{"Content-Type": "application/json"}},
        method="POST",
    )
    with urllib.request.urlopen(request) as response:
        return json.load(response)


def main() -> None:
    result = run()
    print("PropulsionLab - {label}")
    print(f"  Net thrust   : {{result['thrust_kN']:.3f}} kN")
    print(f"  TSFC         : {{result['TSFC_kg_per_kN_hr']:.3f}} kg/(kN.hr)")
    print(f"  Overall eff. : {{result['overall_efficiency_estimate'] * 100:.2f}} %")
    # Full result payload (station table, warnings, etc.):
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
'''


def generate_python_script(
    label: str,
    endpoint: str,
    inputs: dict,
    base_url: str = "http://127.0.0.1:8000",
    generated_at: _dt.datetime | None = None,
) -> str:
    """Render a runnable, stdlib-only API-client script for ``inputs``.

    ``inputs`` is embedded as a Python dict literal (so ``True``/``False``/``None``
    are valid) and re-serialised to JSON at run time by the script itself.
    """

    timestamp = (generated_at or _dt.datetime.now(_dt.timezone.utc)).strftime(
        "%Y-%m-%d %H:%M UTC"
    )
    inputs_literal = pprint.pformat(inputs, indent=4, width=84, sort_dicts=True)
    return _TEMPLATE.format(
        label=label,
        timestamp=timestamp,
        base_url=base_url,
        endpoint=endpoint,
        inputs_literal=inputs_literal,
    )

"""Error tracking (Task 19.6, M19): Sentry, per the approved stack (D25).

Off unless `SENTRY_DSN` is set, so local runs send nothing anywhere. This
product handles confidential deal documents, so events are deliberately
thin: no local variables in stack traces (Sentry includes them by default,
and here they can hold document text or credentials), no request bodies, no
personal data. `DEAL_LAB_ENVIRONMENT` (e.g. `staging`) tags each event.
"""

from __future__ import annotations

import os


def init(component: str) -> bool:
    dsn = os.environ.get("SENTRY_DSN", "").strip()
    if not dsn:
        return False
    import sentry_sdk

    sentry_sdk.init(
        dsn=dsn,
        environment=os.environ.get("DEAL_LAB_ENVIRONMENT", "development"),
        send_default_pii=False,
        include_local_variables=False,
        max_request_body_size="never",
        traces_sample_rate=0.0,
    )
    sentry_sdk.set_tag("component", component)
    return True

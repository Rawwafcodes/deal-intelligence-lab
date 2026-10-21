"""Backend test package.

Importing this package (which `unittest discover -s tests -t .` and
`python -m unittest tests.test_x` both do) makes the store refuse the real
`public` schema, so a test that forgets its own schema - or forgets to create
a table in it - fails deterministically instead of falling through to the
live `deal_lab` database.

It also neutralizes `.env.local` for the whole test run. Several application
modules (ai_client.py, mandate_planning.py, xlsx_inspection.py and others)
call `dotenv.load_dotenv(".env.local")` as a side effect of being imported -
harmless for local dev, but `.env.local` can carry a real hosted
`DATABASE_URL` (password included) for a developer who has set up staging
access, per docs/deployment/staging-setup.md. A test run must never be able
to reach that database, by accident of import order, regardless of which
test file happens to import one of those modules first. CI is unaffected: it
has no `.env.local` file and sets `DATABASE_URL` directly as a real
environment variable, which this does not touch.
"""

import dotenv

dotenv.load_dotenv = lambda *args, **kwargs: False

import store  # noqa: E402 (must follow the load_dotenv patch above)

store.REFUSE_PUBLIC_SCHEMA = True

"""Backend test package.

Importing this package (which `unittest discover -s tests -t .` and
`python -m unittest tests.test_x` both do) makes the store refuse the real
`public` schema, so a test that forgets its own schema - or forgets to create
a table in it - fails deterministically instead of falling through to the
live `deal_lab` database.
"""

import store

store.REFUSE_PUBLIC_SCHEMA = True

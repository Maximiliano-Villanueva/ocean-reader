"""Default organization bootstrap id for single-tenant / dev installs.

Production will create real organizations per company; retrieval and imports must always
associate projects with exactly one ``organization_id`` so corpus rows never leak across tenants.
"""

from __future__ import annotations

import uuid

# Stable UUID referenced by Alembic seed + default FK on ``projects.organization_id``.
DEFAULT_ORGANIZATION_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")

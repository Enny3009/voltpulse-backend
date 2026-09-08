"""create core relational tables

Revision ID: 001_initial_metadata
Revises: 
Create Date: 2026-09-02 20:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001_initial_metadata"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. organizations
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("timezone", sa.String(64), server_default="UTC", nullable=False),
        sa.Column("status", sa.String(32), server_default="ACTIVE", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_organizations_slug", "organizations", ["slug"])

    # 2. users
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("role", sa.String(32), server_default="OPERATOR", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("organization_id", "email", name="uq_user_org_email"),
    )
    op.create_index("idx_users_org_id", "users", ["organization_id"])

    # 3. sites
    op.create_table(
        "sites",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("latitude", sa.Numeric(10, 7), nullable=True),
        sa.Column("longitude", sa.Numeric(10, 7), nullable=True),
        sa.Column("timezone", sa.String(64), server_default="UTC", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("organization_id", "code", name="uq_site_org_code"),
    )
    op.create_index("idx_sites_org_id", "sites", ["organization_id"])

    # 4. device_types
    op.create_table(
        "device_types",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("manufacturer", sa.String(100), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("metric_definitions", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
    )

    # 5. devices
    op.create_table(
        "devices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("device_type_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("device_types.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("device_code", sa.String(64), nullable=False),
        sa.Column("serial_number", sa.String(128), nullable=True),
        sa.Column("installation_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(32), server_default="OFFLINE", nullable=False),
        sa.Column("sampling_rate_seconds", sa.Integer(), server_default="5", nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("site_id", "device_code", name="uq_device_site_code"),
    )
    op.create_index("idx_devices_site_id", "devices", ["site_id"])
    op.create_index("idx_devices_last_seen", "devices", ["last_seen_at"])

    # 6. device_credentials
    op.create_table(
        "device_credentials",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("devices.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("credential_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 7. device_status
    op.create_table(
        "device_status",
        sa.Column("device_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("devices.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("status", sa.String(32), server_default="UNKNOWN", nullable=False),
        sa.Column("health_score", sa.Integer(), server_default="100", nullable=False),
        sa.Column("current_power_kw", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("current_temperature", sa.Float(), nullable=True),
        sa.Column("is_online", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("last_telemetry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_device_status_online", "device_status", ["is_online"])


def downgrade() -> None:
    op.drop_table("device_status")
    op.drop_table("device_credentials")
    op.drop_table("devices")
    op.drop_table("device_types")
    op.drop_table("sites")
    op.drop_table("users")
    op.drop_table("organizations")
"""Add CEO system tables - universities and academic backgrounds

Revision ID: 971f77f87519
Revises:
Create Date: 2025-07-01 05:19:36.915814-04:00

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "971f77f87519"
down_revision: Union[str, Sequence[str], None] = "7920cbe92cd1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Create CEO system tables."""
    # Create universities table
    op.create_table(
        'universities',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False, comment='Official university name'),
        sa.Column('state_id', postgresql.UUID(as_uuid=True), nullable=False, comment='State where university is located'),
        sa.Column('city', sa.String(length=100), nullable=False, comment='City where main campus is located'),
        sa.Column('institution_type', sa.String(length=50), nullable=False, server_default='4-year', comment='Type: 4-year, 2-year, graduate-only'),
        sa.Column('control', sa.String(length=50), nullable=False, server_default='private', comment='Control: public, private, for-profit'),
        sa.Column('enrollment', sa.Numeric(precision=8, scale=0), nullable=True, comment='Total student enrollment'),
        sa.Column('has_business_school', sa.Boolean(), nullable=False, server_default='true', comment='Whether university has a business school'),
        sa.Column('has_rmi_program', sa.Boolean(), nullable=False, server_default='false', comment='Whether university has Risk Management & Insurance program'),
        sa.Column('aliases', sa.String(length=500), nullable=True, comment='Common aliases separated by semicolons (e.g., UGA;Georgia)'),
        sa.ForeignKeyConstraint(['state_id'], ['states.id'], name=op.f('fk_universities_state_id_states')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_universities'))
    )
    op.create_index(op.f('ix_universities_name'), 'universities', ['name'], unique=True)
    op.create_index(op.f('ix_universities_state_id'), 'universities', ['state_id'], unique=False)
    
    # Create academic_backgrounds table
    op.create_table(
        'academic_backgrounds',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False, comment='Unique code for the background (e.g., rmi_finance)'),
        sa.Column('name', sa.String(length=100), nullable=False, comment='Display name (e.g., Risk Management & Finance)'),
        sa.Column('description', sa.String(length=500), nullable=False, comment="Description of the background's focus and benefits"),
        sa.Column('primary_major', sa.String(length=100), nullable=False, server_default='Risk Management & Insurance', comment='Primary major (always RMI for this game)'),
        sa.Column('secondary_major', sa.String(length=100), nullable=False, comment='Secondary major or concentration'),
        sa.Column('attribute_bonuses', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}', comment='CEO attribute bonuses from this background'),
        sa.Column('special_perks', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]', comment='Special perks or abilities from this background'),
        sa.Column('is_active', sa.String(length=5), nullable=False, server_default='true', comment='Whether this background is available for selection'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_academic_backgrounds'))
    )
    op.create_index(op.f('ix_academic_backgrounds_code'), 'academic_backgrounds', ['code'], unique=True)
    
    # Add trigger to update updated_at timestamp for universities
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)
    
    op.execute("""
        CREATE TRIGGER update_universities_updated_at BEFORE UPDATE
        ON universities FOR EACH ROW EXECUTE PROCEDURE
        update_updated_at_column();
    """)
    
    op.execute("""
        CREATE TRIGGER update_academic_backgrounds_updated_at BEFORE UPDATE
        ON academic_backgrounds FOR EACH ROW EXECUTE PROCEDURE
        update_updated_at_column();
    """)


def downgrade() -> None:
    """Downgrade schema - Drop CEO system tables."""
    # Drop triggers
    op.execute("DROP TRIGGER IF EXISTS update_academic_backgrounds_updated_at ON academic_backgrounds")
    op.execute("DROP TRIGGER IF EXISTS update_universities_updated_at ON universities")
    
    # Drop tables
    op.drop_index(op.f('ix_academic_backgrounds_code'), table_name='academic_backgrounds')
    op.drop_table('academic_backgrounds')
    
    op.drop_index(op.f('ix_universities_state_id'), table_name='universities')
    op.drop_index(op.f('ix_universities_name'), table_name='universities')
    op.drop_table('universities')

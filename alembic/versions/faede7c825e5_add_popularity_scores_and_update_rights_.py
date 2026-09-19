"""add_popularity_scores_and_update_rights_records

Revision ID: faede7c825e5
Revises: 05b983977d7a
Create Date: 2026-09-19 19:35:06.784012

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'faede7c825e5'
down_revision: Union[str, None] = '05b983977d7a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


evidence_status_enum = sa.Enum(
    'OWNED',
    'LICENSED',
    'CREATIVE_COMMONS_VERIFIED',
    'PERMISSION_GRANTED',
    'UNKNOWN',
    'REJECTED',
    'EXPIRED',
    name='evidencestatus',
)


def upgrade() -> None:
    # 1. Create popularity_scores table
    op.create_table(
        'popularity_scores',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('source_id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=True),
        sa.Column('algorithm_version', sa.String(length=50), nullable=False),
        sa.Column('input_snapshot', sa.JSON(), nullable=True),
        sa.Column('component_scores', sa.JSON(), nullable=True),
        sa.Column('final_score', sa.Float(), nullable=False),
        sa.Column('rationale', sa.Text(), nullable=False),
        sa.Column('missing_inputs', sa.JSON(), nullable=True),
        sa.Column('scored_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['source_id'], ['sources.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_popularity_scores_final_score'), 'popularity_scores', ['final_score'], unique=False)
    op.create_index(op.f('ix_popularity_scores_project_id'), 'popularity_scores', ['project_id'], unique=False)
    op.create_index(op.f('ix_popularity_scores_scored_at'), 'popularity_scores', ['scored_at'], unique=False)
    op.create_index(op.f('ix_popularity_scores_source_id'), 'popularity_scores', ['source_id'], unique=False)

    # 2. Add columns to rights_records
    op.add_column('rights_records', sa.Column('project_id', sa.String(length=36), nullable=True))
    op.create_foreign_key(
        'fk_rights_records_project_id',
        'rights_records',
        'projects',
        ['project_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_index(op.f('ix_rights_records_project_id'), 'rights_records', ['project_id'], unique=False)

    op.add_column(
        'rights_records',
        sa.Column('evidence_status', evidence_status_enum, server_default='UNKNOWN', nullable=False),
    )
    op.create_index(op.f('ix_rights_records_evidence_status'), 'rights_records', ['evidence_status'], unique=False)


def downgrade() -> None:
    # 2. Revert rights_records columns (if still present)
    try:
        op.drop_index(op.f('ix_rights_records_evidence_status'), table_name='rights_records')
        op.drop_column('rights_records', 'evidence_status')
    except Exception:
        pass

    try:
        op.drop_constraint('fk_rights_records_project_id', 'rights_records', type_='foreignkey')
        op.drop_index(op.f('ix_rights_records_project_id'), table_name='rights_records')
        op.drop_column('rights_records', 'project_id')
    except Exception:
        pass

    # 1. Drop popularity_scores table directly (MySQL drops associated indexes automatically)
    op.drop_table('popularity_scores')


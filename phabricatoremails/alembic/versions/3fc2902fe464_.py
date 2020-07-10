# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Initializes query_position and thread tables.

Revision ID: 3fc2902fe464
Revises:
Create Date: 2020-04-09 09:57:09.401710

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "3fc2902fe464"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "query_position",
        sa.Column("id", sa.Boolean(), nullable=False, default=True),
        sa.Column("up_to_key", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("id"),
    )
    op.create_table(
        "thread",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("phabricator_revision_id", sa.Integer(), nullable=False),
        sa.Column("email_count", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("phabricator_revision_id"),
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("thread")
    op.drop_table("query_position")
    # ### end Alembic commands ###
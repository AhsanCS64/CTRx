"""SQLAlchemy declarative base used by all model classes.

The ``Base`` object is imported by each ``models/*.py`` file and is also
referenced by Alembic's ``env.py`` for autogeneration.
"""

from sqlalchemy.orm import declarative_base

Base = declarative_base()

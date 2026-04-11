"""SQLAlchemy models for the trialcat database.

Every table is a physical, inspectable structure — no magic lazy loads into
a Rails-style ActiveRecord blob. The goal is that you can look at a model
class, read the columns, and know exactly what ends up on disk.

Relationship cardinality:
    Trial ──< Location    (one trial, many study sites)
    Trial ──< Intervention (one trial, many interventions)
    Trial ──< Condition   (many-to-many via TrialCondition)
    Trial ──< Outcome     (one trial, many primary/secondary outcomes)

A Trial row is our normalized unit of aggregation. Everything else hangs
off it. When we run `/api/stats?country=US&area=cardiovascular`, the query
is essentially: find Trials, join Locations, filter by country, join
Conditions, filter by therapeutic area, aggregate.
"""

from app.models.base import Base
from app.models.trial import Trial
from app.models.location import Location
from app.models.intervention import Intervention
from app.models.condition import Condition, TrialCondition
from app.models.outcome import Outcome

__all__ = [
    "Base",
    "Trial",
    "Location",
    "Intervention",
    "Condition",
    "TrialCondition",
    "Outcome",
]

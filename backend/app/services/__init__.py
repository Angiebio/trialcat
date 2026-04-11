"""Business logic services — where the code that touches the outside world lives.

Services in trialcat are the things that fetch from CT.gov, parse dates,
normalize countries, walk MeSH trees. They're deliberately kept separate
from the models (pure data) and the routes (HTTP plumbing) so each layer
has one job.

If you need to test something, you test the service. If you need to swap
out CT.gov for another registry, you swap the service. The models and
routes don't care where the data came from.
"""

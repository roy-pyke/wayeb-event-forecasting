"""Isolated compiler substitution; unchanged source propagation and mass flight."""
import propagate as occupancy_module
from constants import without_constants
from finite_features import FiniteOccupancyFeatures


def finite_estimate(source,mon,q,budget,rng,certificate=False):
    original_features=occupancy_module.OccupancyFeatures
    original_compression=occupancy_module.compress
    try:
        occupancy_module.OccupancyFeatures=FiniteOccupancyFeatures
        occupancy_module.compress=without_constants
        return occupancy_module.basis_propagate(source,mon,q,budget,rng,'occupancy_symbol',certificate)
    finally:
        occupancy_module.OccupancyFeatures=original_features
        occupancy_module.compress=original_compression

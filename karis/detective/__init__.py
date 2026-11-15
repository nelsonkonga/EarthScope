"""Earth System Trend Detective — Eva's molettes of dynamics on NASA Earth science data.

NASA Space Apps Challenge 2026, « Be An Earth System Trend Detective! ». The tool helps a
user find Earth science variables, get them for a region, see how they change over time,
and decide what is changing, where, how much, and whether the change is significant.

- ``mcp``        : client of NASA's earthdata-mcp server (CMR discovery, no login needed)
- ``power``      : NASA POWER API (MERRA-2, GPM IMERG, CERES data for any region, no login)
- ``regions``    : named regions and bounding boxes
- ``variables``  : the suspects — curated variables with plain-language definitions and the
                   NASA collection each one comes from
- ``catalog``    : the detective's questions -> GCMD keywords -> NASA datasets (earthdata-mcp)
- ``stats``      : classical trend statistics (OLS + t-test, Mann-Kendall, Sen's slope...)
- ``watch``      : Eva watches the series — norms, extremes, departures, bends, meta molettes
                   (the engine is ``eva.dynamics.Dynamics``, unchanged and domain-agnostic)
- ``investigate``: the pipeline (screening, investigation, two-region comparison, map)
- ``report``     : the investigation as a self-contained page

Eva's core (``eva/``) knows nothing of the Earth: this package is the domain layer.
"""

"""
parameter_estimation.py
-----------------------
Module for estimating physical parameters of exoplanets from transit observations.
"""

# Conversion factor: 1 Solar radius = 10.9733 Jupiter radii
_SOLAR_TO_JUPITER_RADII = 10.9733


def estimate_planet_radius(star_radius_solar: float, transit_depth_fraction: float) -> float:
    """
    Estimate the planet radius from transit depth using the standard relation:

        R_planet = R_star * sqrt(transit_depth)

    Parameters
    ----------
    star_radius_solar : float
        Host star radius in solar radii (R_sun).
    transit_depth_fraction : float
        Fractional transit depth, i.e. delta_flux / flux  (value between 0 and 1).
        Example: a 1% depth should be passed as 0.01.

    Returns
    -------
    float
        Estimated planet radius in Jupiter radii (R_Jup).

    Raises
    ------
    ValueError
        If either argument is non-positive or transit_depth_fraction >= 1.
    """
    if star_radius_solar <= 0:
        raise ValueError(
            f"star_radius_solar must be positive, got {star_radius_solar}"
        )
    if not (0 < transit_depth_fraction < 1):
        raise ValueError(
            f"transit_depth_fraction must be in (0, 1), got {transit_depth_fraction}"
        )

    # R_planet in solar radii
    planet_radius_solar = star_radius_solar * (transit_depth_fraction ** 0.5)

    # Convert to Jupiter radii
    planet_radius_jupiter = planet_radius_solar * _SOLAR_TO_JUPITER_RADII

    return planet_radius_jupiter


# ---------------------------------------------------------------------------
# Quick verification block
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    examples = [
        # (star_radius_solar, transit_depth_fraction, description)
        (1.0,  0.01,   "Sun-like star, 1% depth  -> ~Jupiter-sized"),
        (1.5,  0.005,  "Slightly larger star, 0.5% depth"),
        (0.45, 0.0256, "M-dwarf (0.45 R_sun), 2.56% depth -> ~sub-Jupiter"),
    ]

    print(f"{'Star R (R_sun)':<18} {'Depth':<12} {'Planet R (R_Jup)':<18} Description")
    print("-" * 72)
    for r_star, depth, desc in examples:
        r_planet = estimate_planet_radius(r_star, depth)
        print(f"{r_star:<18.4f} {depth:<12.4f} {r_planet:<18.4f} {desc}")

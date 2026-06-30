"""
parameter_estimation.py
-----------------------
Module for estimating physical parameters of exoplanets from transit observations.
"""

# Conversion factor: 1 Solar radius = 10.9733 Jupiter radii
_SOLAR_TO_JUPITER_RADII = 10.9733

# Physical constants (SI)
_G           = 6.674e-11   # gravitational constant, m^3 kg^-1 s^-2
_M_SUN_KG    = 1.989e30    # solar mass in kg
_AU_M        = 1.496e11    # 1 AU in metres
_R_SUN_M     = 6.957e8     # solar radius in metres


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


def estimate_semimajor_axis(star_mass_solar: float, period_days: float) -> float:
    """
    Estimate the orbital semi-major axis using Kepler's third law:

        a^3 = (G * M * P^2) / (4 * pi^2)

    Parameters
    ----------
    star_mass_solar : float
        Host star mass in solar masses (M_sun).
    period_days : float
        Orbital period in days.

    Returns
    -------
    float
        Semi-major axis in astronomical units (AU).

    Raises
    ------
    ValueError
        If either argument is non-positive.
    """
    import math

    if star_mass_solar <= 0:
        raise ValueError(
            f"star_mass_solar must be positive, got {star_mass_solar}"
        )
    if period_days <= 0:
        raise ValueError(
            f"period_days must be positive, got {period_days}"
        )

    # Convert inputs to SI
    M = star_mass_solar * _M_SUN_KG          # kg
    P = period_days * 86400.0                # seconds

    # Kepler's third law: a = ( G*M*P^2 / (4*pi^2) )^(1/3)
    a_metres = ((_G * M * P ** 2) / (4 * math.pi ** 2)) ** (1.0 / 3.0)

    # Convert to AU
    a_au = a_metres / _AU_M

    return a_au


def estimate_transit_duration(
    star_density_gcc: float,
    period_days: float,
    semimajor_axis_au: float,
) -> float:
    """
    Estimate the expected transit duration for a central (b=0) transit.

    Derivation
    ----------
    1. Recover R_star from the stellar density (assuming M_star = 1 M_sun):

           rho = M / (4/3 * pi * R^3)  =>  R_star = (3*M / (4*pi*rho))^(1/3)

    2. Apply the standard chord-transit formula with b=0 and k->0
       (k = R_planet/R_star; for the duration estimate k is small, so (1+k)~1):

           T_dur = (P / pi) * arcsin( R_star / a )

    Parameters
    ----------
    star_density_gcc : float
        Mean stellar density in g/cm^3 (g/cc).
    period_days : float
        Orbital period in days.
    semimajor_axis_au : float
        Orbital semi-major axis in AU.

    Returns
    -------
    float
        Expected transit duration in hours.

    Raises
    ------
    ValueError
        If any argument is non-positive, or if R_star >= a (unphysical).
    """
    import math

    if star_density_gcc <= 0:
        raise ValueError(
            f"star_density_gcc must be positive, got {star_density_gcc}"
        )
    if period_days <= 0:
        raise ValueError(
            f"period_days must be positive, got {period_days}"
        )
    if semimajor_axis_au <= 0:
        raise ValueError(
            f"semimajor_axis_au must be positive, got {semimajor_axis_au}"
        )

    # --- Step 1: derive R_star (metres) from density ---
    # Convert density: 1 g/cc = 1000 kg/m^3
    rho_si = star_density_gcc * 1000.0                         # kg/m^3
    M_star = 1.0 * _M_SUN_KG                                  # assume 1 M_sun
    R_star_m = ((3.0 * M_star) / (4.0 * math.pi * rho_si)) ** (1.0 / 3.0)

    # --- Step 2: semi-major axis in metres ---
    a_m = semimajor_axis_au * _AU_M

    ratio = R_star_m / a_m
    if ratio >= 1.0:
        raise ValueError(
            f"R_star/a = {ratio:.4f} >= 1; unphysical geometry "
            f"(star larger than orbit)."
        )

    # --- Step 3: transit duration ---
    P_seconds = period_days * 86400.0
    T_seconds = (P_seconds / math.pi) * math.asin(ratio)

    # Convert to hours
    T_hours = T_seconds / 3600.0

    return T_hours


def estimate_snr(
    tmag: float,
    transit_depth_fraction: float,
    n_transits: int,
    transit_duration_hours: float,
) -> float:
    """
    Estimate the signal-to-noise ratio (SNR) of a transit detection with TESS.

    Noise model
    -----------
    TESS photometric precision is approximately 60 ppm/hr^0.5 at Tmag = 10.
    For other magnitudes it scales as:

        noise_floor (ppm/hr^0.5) = 60 * 10^(0.2 * (Tmag - 10))

    Per-transit noise (ppm) integrated over one transit of duration T (hours):

        noise_per_transit = noise_floor / sqrt(T)

    Combined noise over N independent transits:

        noise_combined = noise_per_transit / sqrt(N)

    SNR:

        SNR = depth_ppm / noise_combined
            = depth_ppm * sqrt(N * T) / noise_floor

    Parameters
    ----------
    tmag : float
        TESS magnitude of the host star.
    transit_depth_fraction : float
        Fractional transit depth (0 < depth < 1). E.g. 0.01 for 1%.
    n_transits : int
        Number of observed transits to co-add.
    transit_duration_hours : float
        Duration of a single transit in hours.

    Returns
    -------
    float
        Estimated SNR (dimensionless).

    Raises
    ------
    ValueError
        If any argument is out of its valid range.
    """
    if not (0 < transit_depth_fraction < 1):
        raise ValueError(
            f"transit_depth_fraction must be in (0, 1), got {transit_depth_fraction}"
        )
    if n_transits < 1:
        raise ValueError(
            f"n_transits must be >= 1, got {n_transits}"
        )
    if transit_duration_hours <= 0:
        raise ValueError(
            f"transit_duration_hours must be positive, got {transit_duration_hours}"
        )

    # TESS noise floor at this magnitude (ppm per sqrt-hour)
    _TESS_NOISE_REF_PPM = 60.0   # ppm/hr^0.5 at Tmag = 10
    noise_floor = _TESS_NOISE_REF_PPM * (10.0 ** (0.2 * (tmag - 10.0)))

    # Transit depth in ppm
    depth_ppm = transit_depth_fraction * 1e6

    # SNR = depth * sqrt(N * T) / noise_floor
    snr = depth_ppm * (n_transits * transit_duration_hours) ** 0.5 / noise_floor

    return snr


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

    # --- estimate_semimajor_axis examples ---
    print()
    sma_examples = [
        # (star_mass_solar, period_days, description)
        (1.0,   365.25, "Earth orbit (should be ~1.00 AU)"),
        (1.0,  4332.59, "Jupiter orbit (should be ~5.20 AU)"),
        (0.5,    10.0,  "M-dwarf host, 10-day period"),
    ]
    print(f"{'Star M (M_sun)':<18} {'Period (days)':<16} {'a (AU)':<12} Description")
    print("-" * 72)
    for m_star, period, desc in sma_examples:
        a = estimate_semimajor_axis(m_star, period)
        print(f"{m_star:<18.4f} {period:<16.2f} {a:<12.4f} {desc}")

    # --- estimate_transit_duration examples ---
    print()
    dur_examples = [
        # (density_gcc, period_days, a_au, description)
        (1.41,  365.25, 1.0,   "Sun/Earth geometry  -> ~13 h"),
        (1.41,    3.52, 0.045, "Hot Jupiter (3.5-day orbit)"),
        (56.0,   10.0,  0.072, "M-dwarf (high density), 10-day period"),
    ]
    print(f"{'Density (g/cc)':<18} {'Period (days)':<16} {'a (AU)':<10} {'T_dur (h)':<12} Description")
    print("-" * 80)
    for rho, per, a_au, desc in dur_examples:
        t = estimate_transit_duration(rho, per, a_au)
        print(f"{rho:<18.2f} {per:<16.2f} {a_au:<10.3f} {t:<12.4f} {desc}")

    # --- estimate_snr examples ---
    print()
    snr_examples = [
        # (tmag, depth, n_transits, t_dur_h, description)
        (10.0, 0.01,  13, 13.0, "Jupiter analog, Tmag=10, 13 transits"),
        (12.0, 0.005,  5,  3.0, "Smaller planet, fainter star"),
        ( 8.0, 0.001, 50,  2.0, "Bright star, many short transits"),
    ]
    print(f"{'Tmag':<8} {'Depth':<10} {'N_tr':<8} {'T_dur(h)':<12} {'SNR':<10} Description")
    print("-" * 76)
    for tmag, depth, n_tr, t_dur, desc in snr_examples:
        snr = estimate_snr(tmag, depth, n_tr, t_dur)
        print(f"{tmag:<8.1f} {depth:<10.4f} {n_tr:<8d} {t_dur:<12.1f} {snr:<10.2f} {desc}")

"""Feature extraction helpers for Stage 4 classification.

Example:
    >>> star_data = {"Tmag": 10.5, "Teff": 5800, "logg": 4.44, "rad": 1.0,
    ...              "mass": 1.0, "rho": 1.41, "contratio": 0.01, "ebv": 0.02, "d": 100.0}
    >>> transit_data = {"depth": 0.008, "duration": 0.2, "period": 3.5, "SNR": 25.0}
    >>> build_feature_vector(star_data, transit_data)
    {'Tmag': 10.5, 'Teff': 5800, 'logg': 4.44, 'rad': 1.0, 'mass': 1.0, 'rho': 1.41,
     'contratio': 0.01, 'ebv': 0.02, 'd': 100.0, 'depth': 0.008, 'duration': 0.2,
     'period': 3.5, 'SNR': 25.0}
"""


def build_feature_vector(star_data: dict, transit_data: dict) -> dict:
    """Extract and validate the Stage 4 feature set from stellar and transit inputs.

    Inputs:
        star_data: Dictionary containing stellar attributes: Tmag, Teff, logg,
            rad, mass, rho, contratio, ebv, and d.
        transit_data: Dictionary containing transit attributes: depth,
            duration, period, and SNR.

    Outputs:
        dict: A dictionary with the requested feature names and values.

    Raises:
        ValueError: If required keys are missing or if values fall outside basic sanity ranges.
    """
    star_required = ["Tmag", "Teff", "logg", "rad", "mass", "rho", "contratio", "ebv", "d"]
    transit_required = ["depth", "duration", "period", "SNR"]

    missing_star = [key for key in star_required if key not in star_data]
    if missing_star:
        raise ValueError(f"missing required key(s) in star_data: {', '.join(missing_star)}")

    missing_transit = [key for key in transit_required if key not in transit_data]
    if missing_transit:
        raise ValueError(f"missing required key(s) in transit_data: {', '.join(missing_transit)}")

    depth = transit_data["depth"]
    period = transit_data["period"]

    if not 0 < depth < 1:
        raise ValueError("depth must be between 0 and 1")
    if period <= 0:
        raise ValueError("period must be greater than 0")

    features = {
        "Tmag": star_data["Tmag"],
        "Teff": star_data["Teff"],
        "logg": star_data["logg"],
        "rad": star_data["rad"],
        "mass": star_data["mass"],
        "rho": star_data["rho"],
        "contratio": star_data["contratio"],
        "ebv": star_data["ebv"],
        "d": star_data["d"],
        "depth": depth,
        "duration": transit_data["duration"],
        "period": period,
        "SNR": transit_data["SNR"],
    }
    return features


def compute_features(
    tmag=None,
    teff=None,
    logg=None,
    rad=None,
    mass=None,
    rho=None,
    contratio=None,
    ebv=None,
    d=None,
    depth=None,
    duration=None,
    period=None,
    snr=None,
):
    """Construct and return the Stage 4 feature dictionary.

    Inputs:
        tmag: Target apparent magnitude.
        teff: Stellar effective temperature.
        logg: Stellar surface gravity.
        rad: Stellar radius.
        mass: Stellar mass.
        rho: Stellar density.
        contratio: Blend or contaminant ratio.
        ebv: Interstellar extinction value.
        d: Stellar distance.
        depth: Transit depth.
        duration: Transit duration.
        period: Orbital period.
        snr: Signal-to-noise ratio.

    Outputs:
        dict: A feature dictionary containing the requested Stage 4 fields.
    """
    return build_feature_vector(
        {
            "Tmag": tmag,
            "Teff": teff,
            "logg": logg,
            "rad": rad,
            "mass": mass,
            "rho": rho,
            "contratio": contratio,
            "ebv": ebv,
            "d": d,
        },
        {
            "depth": depth,
            "duration": duration,
            "period": period,
            "SNR": snr,
        },
    )

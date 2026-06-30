"""Model interface stubs for Stage 4 classification."""


def classify_candidate(features=None):
    """Classify a candidate into one of the Stage 4 output classes.

    Inputs:
        features: Feature dictionary produced by the feature extraction step.

    Outputs:
        str: One of the supported classes: planet, EB, blend, noise, or false_positive.
    """
    raise NotImplementedError

"""Command-line interface for running Stage 4 classification on JSON input."""

import argparse
import json
from pathlib import Path

from stage4_classifier.pipeline import classify_candidate


def build_parser():
    """Create the CLI argument parser."""
    parser = argparse.ArgumentParser(description="Run Stage 4 classification on a JSON input file")
    parser.add_argument("input_json", help="Path to a JSON file containing star/transit/light-curve records")
    parser.add_argument("output_json", help="Path to the JSON file where results will be written")
    parser.add_argument("--model", default=None, help="Path to a serialized scikit-learn model (optional)")
    return parser


def main(argv=None):
    """Run the CLI entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    input_path = Path(args.input_json)
    output_path = Path(args.output_json)

    with input_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if isinstance(payload, dict) and "records" in payload:
        records = payload["records"]
    else:
        records = payload

    if args.model is not None:
        from stage4_classifier.model import load_model

        model = load_model(args.model)
    else:
        model = None

    results = []
    for record in records:
        if model is None:
            raise ValueError("A trained model is required for classification")

        result = classify_candidate(
            record.get("star_data", {}),
            record.get("transit_data", {}),
            record.get("light_curve"),
            record.get("t0", 0.0),
            model,
        )
        results.append(result)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2)

    return results


if __name__ == "__main__":
    main()

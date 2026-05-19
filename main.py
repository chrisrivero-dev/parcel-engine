from __future__ import annotations

import argparse
import json
from pathlib import Path

from exporters.dxf import export_dxf
from exporters.geojson import export_geojson
from geometry.builder import build_geometry
from transcription.parser_v2 import parse_legal_description


def main() -> None:
    parser = argparse.ArgumentParser(description="COGO Validator + DXF Export")
    parser.add_argument("input_file", help="Path to text file containing legal-description courses")
    parser.add_argument("--start-x", type=float, default=0.0)
    parser.add_argument("--start-y", type=float, default=0.0)
    parser.add_argument("--out-dxf", type=str, default=None)
    parser.add_argument("--out-geojson", type=str, default=None)
    parser.add_argument("--report-json", type=str, default=None)
    args = parser.parse_args()

    input_path = Path(args.input_file)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    text = input_path.read_text(encoding="utf-8")
    calls, _reference_ties, parse_errors = parse_legal_description(text)

    if parse_errors:
        print("PARSE ERRORS:")
        for err in parse_errors:
            print(f"  - {err}")
        raise SystemExit(1)

    result = build_geometry(
        start_point=(args.start_x, args.start_y),
        calls=calls,
    )

    points = result["points"]
    validation = result["validation"]

    print("BUILD COMPLETE")
    print(f"Points: {len(points)}")
    print(f"Closure misclosure: {validation['closure']['misclosure']}")
    print(f"Intersections: {len(validation['intersections'])}")
    print(f"Curve error groups: {len(validation['curve_errors'])}")

    if args.out_dxf:
        export_dxf(points, args.out_dxf)
        print(f"DXF written: {args.out_dxf}")

    if args.out_geojson:
        feature_collection = export_geojson(
            boundary_points=points,
            commencement_path=None,
            properties={"source": str(input_path.name)},
        )
        Path(args.out_geojson).write_text(
            json.dumps(feature_collection, indent=2),
            encoding="utf-8",
        )
        print(f"GeoJSON written: {args.out_geojson}")

    if args.report_json:
        Path(args.report_json).write_text(
            json.dumps(validation, indent=2, default=str),
            encoding="utf-8",
        )
        print(f"Validation report written: {args.report_json}")


if __name__ == "__main__":
    main()
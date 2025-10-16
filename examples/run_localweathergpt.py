"""Minimal script demonstrating how to call LocalWeatherGPT programmatically."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from localweathergpt import WeatherSource, get_weather_data


def main() -> None:
    parser = argparse.ArgumentParser(description="Run LocalWeatherGPT for a location/date range")
    parser.add_argument("location", help="Location string e.g. 'Buchanan, MI'")
    parser.add_argument("start", help="Start date (YYYY-MM-DD)")
    parser.add_argument("end", help="End date (YYYY-MM-DD)")
    parser.add_argument(
        "--base-temp",
        type=float,
        default=50.0,
        help="Base temperature in °F for Growing Degree Days (default: 50)",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/weather",
        help="Directory where charts will be stored (default: artifacts/weather)",
    )
    parser.add_argument(
        "--export-csv",
        default=None,
        help="Optional path to write the combined dataset as CSV",
    )
    parser.add_argument(
        "--prompt-api-keys",
        action="store_true",
        help="Ask for API keys at runtime when environment variables are missing",
    )
    parser.add_argument(
        "--providers",
        nargs="+",
        choices=[source.value for source in WeatherSource],
        help="Optional subset of providers to query (default: all)",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    result = get_weather_data(
        location=args.location,
        start_date=args.start,
        end_date=args.end,
        base_temp=args.base_temp,
        output_dir=str(output_dir),
        export_csv=args.export_csv,
        prompt_for_api_keys=args.prompt_api_keys,
        providers=args.providers,
    )

    print(f"Combined rows: {len(result.combined):,}")
    print(f"Annual stats rows: {len(result.annual_stats):,}")
    print("Charts:")
    for name, path in result.charts.items():
        print(f"  {name}: {path}")

    if args.export_csv:
        print(f"CSV saved to: {args.export_csv}")

    print("\nCrop recommendations:\n")
    print(result.crop_recommendations)

    print("\nActivity & planting guidance:\n")
    print(result.planning_guidance)


if __name__ == "__main__":
    # Ensure required environment variables are set before running.
    # VISUAL_CROSSING_API_KEY and NOAA_TOKEN can be supplied via env vars or prompted when --prompt-api-keys is used.
    # GEOCODER_USER_AGENT must be set to comply with Nominatim's usage policy.
    os.environ.setdefault("GEOCODER_USER_AGENT", "localweathergpt")
    main()

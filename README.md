# LocalWeatherGPT

LocalWeatherGPT provides Python utilities for downloading and analyzing historical weather records for agricultural planning. The workflow targets Buchanan, MI by default but works for any U.S. location supported by the aggregated data sources (Meteostat, Open-Meteo, NOAA CDO, and Visual Crossing).

## Features
- Geocode any location and download daily weather observations (temperature, rainfall, humidity, snow, wind).
- Pull parallel observations from [Meteostat](https://meteostat.net/), [Open-Meteo](https://open-meteo.com/), [NOAA Climate Data Online](https://www.ncei.noaa.gov/cdo-web/), and [Visual Crossing](https://www.visualcrossing.com/).
- Convert units to Fahrenheit and inches for farm planning.
- Compute annual and monthly summaries, frost/heatwave counts, growing degree days (GDD), and drought-risk proxies.
- Generate Matplotlib/Seaborn charts (trend lines, histograms, scatter plots).
- Export cleaned data to CSV for downstream modeling.
- Provide heuristic crop recommendations based on accumulated climate metrics.
- Fetch 7-day forecasts (Open-Meteo + Visual Crossing) and translate them into outdoor work and planting guidance.

## Requirements
Install dependencies inside a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and adjust values to stay compliant with Nominatim usage policy and provide API credentials:

```bash
cp .env.example .env
```

Set the following keys before running the CLI:

- `GEOCODER_USER_AGENT`: Required by OpenStreetMap Nominatim usage policy.
- `VISUAL_CROSSING_API_KEY`: Required by Visual Crossing (paid/free tiers available).
- `NOAA_TOKEN`: Required for NOAA CDO API access (free registration).
- `NOAA_STATION_ID` (optional): Manually specify a GHCND station; otherwise the script auto-selects the nearest station.
- `METEOSTAT_CACHE_DIR` (optional): Speed up repeated Meteostat queries.

## Quick Start
1. Install dependencies and copy the environment template:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

2. Edit `.env` with your own `GEOCODER_USER_AGENT`, `VISUAL_CROSSING_API_KEY`, and `NOAA_TOKEN` values.

3. Call LocalWeatherGPT via the CLI or Python helper:

### CLI Usage
Run the CLI to analyze the last 30 years for Buchanan, MI:

```bash
python localweathergpt.py \
  --start 1995-01-01 \
  --end 2024-12-31 \
  --export-csv artifacts/weather/buchanan.csv
```

Key flags:

- `--location`: `"City, State"`, ZIP code, or `"latitude,longitude"` (the latter skips geocoding).
- `--start` / `--end`: ISO date strings.
- `--base-temp`: GDD base temperature (°F). Default 50°F.
- `--output-dir`: Directory for saved charts.
- `--forecast-days`: Number of days to forecast for fieldwork/planting guidance (default 7).
- `--cache-dir`: Optional Meteostat cache directory (defaults to `METEOSTAT_CACHE_DIR` env var when set).
- `--export-csv`: Path for CSV export.
- `--visual-crossing-key`: Override `VISUAL_CROSSING_API_KEY`.
- `--noaa-token`: Override `NOAA_TOKEN`.
- `--noaa-station`: Force a specific NOAA station ID if the auto-selected option is unsuitable.
- `--providers`: Limit downloads to specific sources (e.g., `--providers "Meteostat" "Open-Meteo"`)—helpful when you lack paid API keys.
- `--prompt-api-keys`: Interactively request missing Visual Crossing/NOAA credentials (useful when running from a prompt or REPL).
- `--require-visual-crossing-key` / `--require-noaa-token`: Fail-fast unless the corresponding credential is supplied—handy when exposing LocalWeatherGPT inside public chat prompts to prevent anonymous abuse.

### Python Script Usage
Prefer a lightweight script instead of the CLI? Use the bundled example:

```bash
python examples/run_localweathergpt.py "Buchanan, MI" 1995-01-01 2024-12-31 \
  --export-csv artifacts/weather/buchanan.csv
```

Add `--prompt-api-keys` if you want the script to ask for the Visual Crossing/NOAA credentials at runtime. Supply `--providers "Meteostat" "Open-Meteo"` for a credential-free run that only uses public data sources.

### Calling from ChatGPT or Other Prompt Runtimes

LocalWeatherGPT can be invoked from the main ChatGPT prompt (or any similar conversational interface) by importing `get_weather_data` inside your tool handler and setting `prompt_for_api_keys=True`. This instructs the library to request credentials from the end-user when they trigger the tool, ensuring each caller supplies their own API token:

```python
from localweathergpt import get_weather_data

result = get_weather_data(
    location="Buchanan, MI",
    start_date="2000-01-01",
    end_date="2024-12-31",
    prompt_for_api_keys=True,
    require_visual_crossing_key=True,
    require_noaa_token=True,
)
```

When you expose LocalWeatherGPT through ChatGPT, require per-user API keys so that anonymous traffic is blocked. Combine this with your chatbot's moderation or rate-limiting layer to reduce automated scraping and abuse.

The script prints a summary, chart locations, heuristic crop insights, and forecast-driven activity guidance. Cite all upstream sources (Meteostat, Open-Meteo, NOAA CDO, Visual Crossing) when sharing outputs.

## Notes on Reliability & Performance
- Network access may be rate-limited; enable caching via the environment variable or CLI flag to reduce repeated downloads.
- Missing humidity or precipitation data is carried forward as `NaN`. Downstream models should handle gaps explicitly.
- Visualizations are generated with the non-interactive Matplotlib backend to support CI/CD execution.
- Consider wrapping the CLI with job scheduling (e.g., GitHub Actions, cron) and storing outputs in cloud object storage for reproducibility.

## Extending Toward AI Crop Decisions
- Combine the exported CSV with soil moisture probes or USDA soil surveys to enrich agronomic features.
- Feed rolling GDD, frost risk, and drought streak metrics into a crop recommendation engine (e.g., gradient boosted trees) to prioritize hybrids per planting window.
- Integrate satellite NDVI or evapotranspiration data for spatial variability and tie into variable-rate irrigation playbooks.
- Use the `annual_stats` and `monthly_stats` DataFrames as features for predicting yield anomalies or scheduling field operations.

## SEO Checklist
- Suggested page title: "LocalWeatherGPT | Buchanan, MI Climate Analytics for Smarter Crop Planning".
- Meta description: "Use LocalWeatherGPT to download Buchanan, MI weather history, compute growing degree days, frost risk, and visualize rainfall trends for crop strategy."
- Suggested alt text for charts: "Line chart showing Buchanan daily temperature extremes".
- Internal link idea: link from agronomy documentation to this toolkit's usage guide.

## License
MIT (follow Meteostat attribution requirements when redistributing data).

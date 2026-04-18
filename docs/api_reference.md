# Module & API Reference — Fitness Bridge AI

Technical details of the internal Python modules and algorithms.

## 1. Analysis Algorithms

### Readiness Score
Located in `src/analysis/readiness.py`. 
Computes a 0–100 score based on three components:
- **Sleep (40%)**: Total minutes asleep + efficiency bonus.
- **HRV (40%)**: RMSSD value compared to a 45ms baseline.
- **Resting HR (20%)**: Delta from the historical baseline.

### ACWR (Acute:Chronic Workload Ratio)
Located in `src/analysis/load.py`.
Measures the risk of injury:
- **Acute Load**: Average volume of the last 7 days.
- **Chronic Load**: Average volume of the last 28 days.
- **Ratio**: Acute / Chronic. (Optimal: 0.8–1.3).

### Strength 1RM (Epley)
Located in `src/analysis/strength.py`.
Estimated 1RM = `weight * (1 + reps / 30)`.

## 2. Sync Engine

The Sync Engine (`src/sync/engine.py`) is idempotent. It uses a composite primary key `(source, activity_id)` in SQLite to ensure that re-fetching the same activity multiple times never duplicates training records.

**Ingestion Workflow:**
1. Fetch Strava activities.
2. Fetch Fitbit biometrics for the corresponding dates.
3. Parse Hevy descriptions from Strava.
4. Join all data into a daily `workouts` record.

## 3. Database Schema

### `workouts` Table
The central store for all metrics.
- `activity_id`: Provider's ID (Strava/Fitbit).
- `source`: 'strava' or 'fitbit'.
- `total_volume_kg`: Calculated from sets.
- `muscle_groups`: JSON list of groups trained.
- `readiness_score`: Computed at sync time.

### `api_tokens` Table
The secure vault for OAuth credentials.
- `provider`: 'strava', 'fitbit', or 'spotify'.
- `access_token`: Active token.
- `refresh_token`: Used to get new access tokens.
- `expires_at`: Unix timestamp.

## 4. Parser (Hevy)

The Hevy parser (`src/parsers/hevy_parser.py`) uses regex to extract structured data from plaintext descriptions. It maps exercise names to muscle groups using a comprehensive internal mapping. To add new exercises, update the `MUSCLE_MAP` in `hevy_parser.py`.

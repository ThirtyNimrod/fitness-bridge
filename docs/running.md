# Running Fitness Bridge AI

The application consists of a Python backend and a Next.js frontend. They must both be running for the full experience.

## 1. Start the Backend (FastAPI)

Prerequisite: Ensure [Ollama](https://ollama.com/) is running for AI features.

```bash
# Pull the model if you haven't yet
ollama pull qwen3.5:4b

# Run the backend
python main.py
```

The backend starts on **http://localhost:8000**.
- **Self-Healing Sync**: On startup, the backend automatically triggers an initial sync and starts a background thread to poll for new data every 2 hours.
- **API Docs**: Interactive Swagger documentation is available at [http://localhost:8000/docs](http://localhost:8000/docs).

## 2. Start the Frontend (Next.js)

Open a new terminal:

```bash
cd frontend
npm run dev
```

The frontend starts on **http://localhost:3000**.

## 3. Workflow Example

1. Ensure your `.env` is configured.
2. Run `python main.py`.
3. Observe logs for "Background sync task triggered".
4. Open the dashboard at `http://localhost:3000`.
5. Use the **Sync** button in the dashboard to trigger an immediate update from Strava/Fitbit.

## 4. Troubleshooting

- **401 Unauthorized**: If API logs show authentication errors, run `python scripts/setup_tokens.py` to re-authorize.
- **CORS Errors**: Ensure the frontend is running on `localhost:3000` and the backend is on `:8000`. These are hardcoded in the default CORS config.
- **Missing Workouts**: Check that your Hevy workouts are exported to Strava successfully and that the activity descriptions include the workout text.
- **Ollama Connection Refused**: Ensure Ollama is running (`ollama serve`).

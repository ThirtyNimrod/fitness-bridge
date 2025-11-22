Root Directory

app.py: The command center. It imports clients from src/, fetches data, calls the optimizer, and executes updates.

config.py: Uses python-dotenv to load variables like HEVY_API_KEY so you don't hardcode them.
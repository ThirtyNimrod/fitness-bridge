# Fitness Bridge AI

A Streamlit-powered AI fitness coach that integrates with Hevy and Fitbit to provide personalized workout recommendations based on your training data and biological metrics.

## Features

- **AI-Powered Coaching**: Conversational AI agent using LangGraph and Azure OpenAI to analyze workouts and suggest optimizations.
- **Hevy Integration**: Fetch workout routines, recent workouts, and update routines.
- **Fitbit Integration**: Retrieve sleep data and heart rate for readiness assessment.
- **Chat Interface**: Persistent chat sessions with history stored in SQLite.
- **Connection Monitoring**: Real-time status checks for API connections.

## Prerequisites

- Python 3.11+
- Hevy API Key (from [Hevy Developer Portal](https://api.hevyapp.com/))
- Fitbit Access Token (via OAuth2 from [Fitbit Developer](https://dev.fitbit.com/))
- Azure OpenAI Account (for the AI agent)

## Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/ThirtyNimrod/fitness-bridge.git
   cd fitness-bridge
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

## Setup

1. Create a `.env` file in the root directory:

   ```env
   HEVY_API_KEY=your_hevy_api_key
   FITBIT_ACCESS_TOKEN=your_fitbit_access_token
   AZURE_OPENAI_API_KEY=your_azure_openai_key
   AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
   AZURE_OPENAI_API_VERSION=2024-02-15-preview
   ```

2. Ensure your Azure OpenAI deployment is set to "gpt-4o" (or update `src/graph/agent.py` accordingly).

## Usage

Run the application:

```bash
streamlit run app.py
```

Open your browser to the provided URL. The app will:

- Check API connections in the sidebar.
- Allow creating new chat sessions or loading past ones.
- Enable chatting with the AI coach about workouts, recovery, and routine updates.

### Example Queries

- "How were my last 3 workouts?"
- "Am I ready to train today based on my sleep?"
- "Find my 'Push Day' routine."

## Architecture

- **app.py**: Main Streamlit application handling UI, chat logic, and API status.
- **src/clients/**: API client classes for Hevy and Fitbit.
- **src/graph/agent.py**: LangGraph-based AI agent with tool integration.
- **src/tools/fitness_tools.py**: LangChain tools for data fetching.
- **src/utils/database.py**: SQLite database for chat history.
- **config.py**: (Currently unused; reserved for configuration management).

## Contributing

Contributions are welcome! Please open issues or pull requests on GitHub.

## License

MIT License - see [LICENSE](LICENSE) for details.

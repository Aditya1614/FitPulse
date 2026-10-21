# 🏋️‍♂️ FitPulse - AI Personal Fitness & Workout Coach

FitPulse is an intelligent, agent-first fitness and nutrition coach built on Google Cloud's Agent Platform and Vertex AI. It helps athletes and fitness enthusiasts discover exercises, calculate strength targets, plan workouts, track training logs, estimate nutritional needs, and generate instructional form visuals and demonstration videos.

---

## 🌟 Implemented Features & Google Cloud Integrations

FitPulse is built with the Google Agent Development Kit (ADK) and directly connects to the following Google Cloud services and tools:

| Feature / Integration | Description | Powered By |
|---|---|---|
| 🧠 **Cross-Session Long-Term Memory** | Remembers user allergies, injuries, dietary restrictions, and fitness preferences across conversations and sessions. | **Vertex AI Memory Bank** (`VertexAiMemoryBankService` + `PreloadMemoryTool`) |
| 🗄️ **Exercise Catalog & Workout Logging** | Queries exercise movements, filters by target muscle or difficulty, adds custom exercises, and logs completed workout sessions. | **Google Cloud Firestore** (`exercises` and `workout_logs` collections) |
| 🖼️ **Image Generation** | Generates visual form guides, recovery meals, and milestone badges, saves them as ADK artifacts, and uploads them to public storage. | **Vertex AI Imagen** (`gemini-3.1-flash-lite-image`) |
| 🎬 **Exercise Video Generation** | Generates instructional exercise motion demonstrations, saves them as ADK artifacts, and uploads MP4 bytes to public storage. | **Vertex AI Omni** (`gemini-omni-flash-preview`) |
| ☁️ **Media Hosting** | Hosts generated exercise visuals and motion demonstration videos for direct web rendering. | **Google Cloud Storage** |
| 🧪 **Python Code Execution Sandbox** | Securely executes Python calculations (e.g. 1RM estimations, Karvonen heart rate zones, caloric expenditure) in an isolated container. | **Agent Engine Sandbox Code Executor** (`AgentEngineSandboxCodeExecutor`) |
| 🪟 **Agent-to-UI Cards (A2UI)** | Formats workout routines and fitness metrics as structured visual cards (`beginRendering` + `surfaceUpdate` v0.8) rather than plain text. | **A2UI Schema Manager** (`a2ui-agent-sdk`) |
| 🌐 **A2A Chat Frontend** | Custom dark-themed athletic web interface with quick-action prompt pills and real-time A2UI card rendering over the A2A protocol. | **FastAPI Proxy** + Vanilla Web UI |

---

## 🛠️ Implemented Agent Tools

The agent (`app/agent.py`) implements and exposes the following function tools:

- `list_or_search_exercises(target_muscle, difficulty, category)`: Searches Firestore exercise database.
- `get_exercise_details(exercise_id)`: Fetches step-by-step instructions, equipment, and target muscles.
- `log_workout_session(user_name, routine_name, exercises_completed, duration_minutes, notes)`: Saves session logs with timestamps.
- `get_user_workout_history(user_name, limit)`: Retrieves recent logged workouts and total training minutes.
- `add_custom_exercise(...)`: Allows users to add custom movements to their catalog.
- `calculate_one_rep_max(weight_lbs, reps)`: Calculates 1RM and percentage-based training loads via Epley & Brzycki formulas.
- `calculate_heart_rate_zones(age, resting_hr)`: Computes cardio training Zones 1–5 via Karvonen and Max HR formulas.
- `estimate_nutrition_and_macros(food_query)`: Provides caloric and macronutrient breakdowns (protein, carbs, fats) for post-workout meals.
- `check_outdoor_workout_weather(city_name)`: Checks temperature, precipitation, and running conditions via Open-Meteo API.
- `generate_fitness_visual(prompt, title)`: Generates high-res image visual via `gemini-3.1-flash-lite-image` and uploads to Cloud Storage.
- `generate_exercise_video(prompt, title)`: Generates short demonstration video via `gemini-omni-flash-preview` and uploads to Cloud Storage.

---

## 🚀 Running Locally

### 1. Prerequisites
- Python `>=3.11, <3.14`
- [uv](https://docs.astral.sh/uv/) package manager
- Google Cloud SDK (`gcloud`) authenticated with Application Default Credentials (`gcloud auth application-default login`)

### 2. Environment Variables
Set your Google Cloud project and region:
```bash
export GOOGLE_CLOUD_PROJECT="<your-gcp-project-id>"
export GOOGLE_CLOUD_LOCATION="us-east1"
export GOOGLE_GENAI_USE_VERTEXAI="true"
```

### 3. Launch the Agent in ADK Web (Dev Playground)
To test the agent with long-term memory and A2UI card rendering in the ADK web dev environment:
```bash
uv run adk web --memory_service_uri=agentengine://<your-memory-bank-id> --host=0.0.0.0 --port=8000
```

### 4. Run the Custom FitPulse Web Frontend
To run the lightweight FastAPI proxy and custom FitPulse chat UI:
```bash
cd frontend
export AGENT_ENGINE_RESOURCE_NAME="projects/<project-id>/locations/us-east1/reasoningEngines/<engine-id>"
export AGENT_DIRECTORY="app"
uv run python main.py
```

---

## 📁 Repository Structure

```
.
├── app/
│   ├── agent.py               # Main agent configuration, tools, memory, and A2UI wiring
│   ├── a2ui_utils.py          # A2UI response parser and renderer callback
│   └── fast_api_app.py        # Local API server entrypoint
├── frontend/
│   ├── main.py                # FastAPI proxy connecting browser to Agent Engine over A2A
│   ├── requirements.txt       # Frontend proxy dependencies
│   └── static/
│       └── index.html         # Custom FitPulse chat UI and A2UI component renderer
├── agents-cli-manifest.yaml   # Agent manifest configuration
├── deployment_metadata.json   # Agent Engine runtime and deployment metadata
├── project_brief.md           # Project architecture and design specification
└── pyproject.toml             # Python project dependencies and ADK configuration
```

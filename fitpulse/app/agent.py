# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
import re
from typing import Any, Dict, List, Optional
import uuid
import requests

from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.manager import A2uiSchemaManager
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.memory.vertex_ai_memory_bank_service import VertexAiMemoryBankService
from google.adk.models import Gemini
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.adk.tools.tool_context import ToolContext
from google.cloud import firestore, storage
from google import genai
from google.genai import types

from .a2ui_utils import a2ui_callback


MODEL = "gemini-2.5-flash"
IMAGE_MODEL = "gemini-3.1-flash-lite-image"
PROJECT_ID = "qwiklabs-gcp-04-59fb1dbb96b2"
LOCATION = "us-east1"
BUCKET_NAME = "fitpulse-media-rselow"
AGENT_ENGINE_RUNTIME_ID = "projects/951944629530/locations/us-east1/reasoningEngines/2889493468051144704"
MEMORY_BANK_ID = "2889493468051144704"

db = firestore.Client(project=PROJECT_ID)
storage_client = storage.Client(project=PROJECT_ID)
storage_bucket = storage_client.bucket(BUCKET_NAME)
genai_client = genai.Client(vertexai=True, project=PROJECT_ID, location="global")
code_executor = AgentEngineSandboxCodeExecutor(agent_engine_resource_name=AGENT_ENGINE_RUNTIME_ID)


def memory_bank_service_builder() -> VertexAiMemoryBankService:
    """Build VertexAiMemoryBankService pointing to the Agent Engine Memory Bank instance."""
    return VertexAiMemoryBankService(
        project=PROJECT_ID,
        location=LOCATION,
        agent_engine_id=MEMORY_BANK_ID,
    )


async def generate_memories_callback(callback_context: CallbackContext) -> None:
    """Extract durable facts and preferences from the session into Memory Bank."""
    await callback_context.add_session_to_memory()
    return None


def list_or_search_exercises(
    target_muscle: Optional[str] = None,
    difficulty: Optional[str] = None,
    category: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Search or list exercises from the Firestore exercise catalog.

    Args:
        target_muscle: Optional muscle group to filter by (e.g. 'Chest', 'Quadriceps', 'Back', 'Shoulders', 'Core', 'Hamstrings').
        difficulty: Optional difficulty level (e.g. 'Beginner', 'Intermediate', 'Advanced').
        category: Optional exercise category (e.g. 'Strength', 'Hypertrophy', 'Bodyweight', 'Endurance').

    Returns:
        A list of exercise dictionaries matching the query filters.
    """
    collection_ref = db.collection("exercises")
    docs = collection_ref.stream()
    results = []
    for doc in docs:
        data = doc.to_dict()
        if target_muscle and target_muscle.lower() not in data.get("target_muscle", "").lower():
            continue
        if difficulty and difficulty.lower() != data.get("difficulty", "").lower():
            continue
        if category and category.lower() != data.get("category", "").lower():
            continue
        results.append(data)
    return results


def get_exercise_details(exercise_id: str) -> Dict[str, Any]:
    """Retrieve detailed instructions, target muscles, and equipment for a specific exercise ID.

    Args:
        exercise_id: The unique identifier of the exercise (e.g. 'barbell-bench-press', 'barbell-back-squat', 'pull-ups').

    Returns:
        A dictionary with the exercise details or an error message if not found.
    """
    doc_ref = db.collection("exercises").document(exercise_id)
    doc = doc_ref.get()
    if not doc.exists:
        return {"error": f"Exercise '{exercise_id}' not found in the catalog."}
    return doc.to_dict()


def log_workout_session(
    user_name: str,
    routine_name: str,
    exercises_completed: List[Dict[str, Any]],
    duration_minutes: int,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Log a completed workout session to Firestore.

    Args:
        user_name: Name or ID of the user logging the workout.
        routine_name: Name of the routine performed (e.g. 'Upper Body Hypertrophy', 'Leg Day').
        exercises_completed: List of exercises performed with details (e.g. [{"exercise_id": "barbell-bench-press", "sets": 4, "reps": "8-10", "weight_lbs": 185}]).
        duration_minutes: Total duration of the workout in minutes.
        notes: Optional user notes on RPE, fatigue, or performance.

    Returns:
        Confirmation dictionary with the generated workout log ID and timestamp.
    """
    log_data = {
        "user_name": user_name,
        "routine_name": routine_name,
        "exercises_completed": exercises_completed,
        "duration_minutes": duration_minutes,
        "notes": notes or "",
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    _, doc_ref = db.collection("workout_logs").add(log_data)
    return {
        "status": "success",
        "log_id": doc_ref.id,
        "message": f"Successfully logged workout '{routine_name}' for {user_name}.",
        "created_at": log_data["created_at"],
    }


def add_custom_exercise(
    exercise_id: str,
    name: str,
    target_muscle: str,
    equipment: str,
    difficulty: str,
    instructions: str,
    category: str = "Strength",
    default_sets: int = 3,
    default_reps: str = "10",
) -> Dict[str, Any]:
    """Add a new custom exercise to the Firestore exercise catalog.

    Args:
        exercise_id: Slug/ID for the exercise (e.g. 'incline-dumbbell-curl').
        name: Name of the exercise.
        target_muscle: Primary muscle worked.
        equipment: Required equipment.
        difficulty: 'Beginner', 'Intermediate', or 'Advanced'.
        instructions: How to perform the movement.
        category: Category such as 'Strength', 'Hypertrophy', or 'Endurance'.
        default_sets: Suggested number of sets.
        default_reps: Suggested reps or time.

    Returns:
        Status dictionary confirming the addition.
    """
    data = {
        "id": exercise_id,
        "name": name,
        "target_muscle": target_muscle,
        "equipment": equipment,
        "difficulty": difficulty,
        "instructions": instructions,
        "category": category,
        "default_sets": default_sets,
        "default_reps": default_reps,
    }
    db.collection("exercises").document(exercise_id).set(data)
    return {"status": "success", "exercise": data}


def calculate_one_rep_max(weight_lbs: float, reps: int) -> Dict[str, Any]:
    """Calculate estimated One-Rep Max (1RM) and percentage-based training loads.

    Uses Epley and Brzycki standard formulas to estimate the maximum weight the user
    can lift for 1 repetition, and provides weight targets for different rep ranges / intensities.

    Args:
        weight_lbs: Weight lifted in pounds (must be > 0).
        reps: Number of repetitions completed with good form (typically between 1 and 15).

    Returns:
        Dictionary containing estimated 1RM, formula breakdowns, and recommended working weights for various goals.
    """
    if weight_lbs <= 0 or reps <= 0:
        return {"error": "Weight and reps must be positive numbers."}

    if reps == 1:
        estimated_1rm = weight_lbs
        epley = weight_lbs
        brzycki = weight_lbs
    else:
        epley = weight_lbs * (1 + (reps / 30.0))
        brzycki = weight_lbs * (36.0 / (37.0 - reps)) if reps < 37 else epley
        estimated_1rm = round((epley + brzycki) / 2.0, 1)

    percentages = {
        "100% (1RM)": round(estimated_1rm, 1),
        "95% (~2 reps, Peak Strength)": round(estimated_1rm * 0.95, 1),
        "90% (~3-4 reps, Heavy Strength)": round(estimated_1rm * 0.90, 1),
        "85% (~5-6 reps, Strength/Hypertrophy)": round(estimated_1rm * 0.85, 1),
        "80% (~7-8 reps, Hypertrophy)": round(estimated_1rm * 0.80, 1),
        "75% (~9-10 reps, Hypertrophy)": round(estimated_1rm * 0.75, 1),
        "70% (~11-12 reps, Hypertrophy/Endurance)": round(estimated_1rm * 0.70, 1),
        "65% (~15 reps, Muscular Endurance)": round(estimated_1rm * 0.65, 1),
    }

    return {
        "input_weight_lbs": weight_lbs,
        "input_reps": reps,
        "estimated_1rm_lbs": round(estimated_1rm, 1),
        "epley_estimate_lbs": round(epley, 1),
        "brzycki_estimate_lbs": round(brzycki, 1),
        "training_percentages": percentages,
    }


def calculate_heart_rate_zones(age: int, resting_hr: Optional[int] = None) -> Dict[str, Any]:
    """Calculate target heart rate training zones using the Tanaka / Karvonen formulas.

    Args:
        age: Age of the user in years.
        resting_hr: Optional resting heart rate in beats per minute (BPM) for enhanced Karvonen precision.

    Returns:
        Dictionary containing estimated Max HR, Heart Rate Reserve (if RHR provided), and BPM ranges for Zones 1-5.
    """
    if age < 10 or age > 100:
        return {"error": "Age must be between 10 and 100."}

    max_hr = round(208 - (0.7 * age))

    if resting_hr and 30 <= resting_hr <= 120:
        hrr = max_hr - resting_hr  # Heart Rate Reserve
        calc = lambda pct: round((hrr * pct) + resting_hr)
        method = "Karvonen (Heart Rate Reserve)"
    else:
        calc = lambda pct: round(max_hr * pct)
        method = "Percentage of Max HR"

    zones = {
        "Zone 1: Active Recovery (50-60%)": f"{calc(0.50)} - {calc(0.60)} BPM",
        "Zone 2: Aerobic / Fat Burn (60-70%)": f"{calc(0.60)} - {calc(0.70)} BPM",
        "Zone 3: Tempo / Aerobic Endurance (70-80%)": f"{calc(0.70)} - {calc(0.80)} BPM",
        "Zone 4: Threshold / Anaerobic (80-90%)": f"{calc(0.80)} - {calc(0.90)} BPM",
        "Zone 5: Maximum Effort / VO2 Max (90-100%)": f"{calc(0.90)} - {max_hr} BPM",
    }

    return {
        "age": age,
        "resting_hr": resting_hr,
        "estimated_max_hr": max_hr,
        "calculation_method": method,
        "target_zones": zones,
    }


def get_user_workout_history(user_name: str, limit: int = 5) -> Dict[str, Any]:
    """Fetch recent workout session logs for a given user from Firestore.

    Args:
        user_name: Name or ID of the user.
        limit: Maximum number of recent workout logs to retrieve (default: 5).

    Returns:
        Dictionary containing past logged sessions, total workouts found, and summary details.
    """
    collection_ref = db.collection("workout_logs")
    query = collection_ref.where("user_name", "==", user_name).limit(limit)
    docs = query.stream()

    logs = []
    total_minutes = 0
    for doc in docs:
        data = doc.to_dict()
        data["log_id"] = doc.id
        logs.append(data)
        total_minutes += data.get("duration_minutes", 0)

    return {
        "user_name": user_name,
        "workout_count": len(logs),
        "total_minutes_logged": total_minutes,
        "recent_workouts": logs,
    }


def estimate_nutrition_and_macros(food_query: str) -> Dict[str, Any]:
    """Estimate macronutrients (calories, protein, carbohydrates, fats) and serving guidelines for recovery foods.

    Uses nutrition reference databases and USDA standard macro profiles to calculate
    nutritional breakdown for whole foods, athletic recovery snacks, and supplements.

    Args:
        food_query: Food item or post-workout meal description (e.g. 'Greek yogurt', 'Chicken breast', 'Oatmeal with whey', 'Eggs', 'Salmon').

    Returns:
        Dictionary with calories, protein (g), carbs (g), fat (g), and recovery recommendations.
    """
    food_db = {
        "chicken breast": {"calories_per_100g": 165, "protein_g": 31.0, "carbs_g": 0.0, "fat_g": 3.6, "serving": "150g fillet (~46g protein, 248 kcal)"},
        "greek yogurt": {"calories_per_100g": 59, "protein_g": 10.0, "carbs_g": 3.6, "fat_g": 0.4, "serving": "1 cup / 200g (~20g protein, 118 kcal)"},
        "egg": {"calories_per_100g": 143, "protein_g": 12.6, "carbs_g": 0.7, "fat_g": 9.5, "serving": "2 large eggs / 100g (~13g protein, 143 kcal)"},
        "salmon": {"calories_per_100g": 208, "protein_g": 20.4, "carbs_g": 0.0, "fat_g": 13.4, "serving": "150g fillet (~31g protein, 312 kcal)"},
        "oatmeal": {"calories_per_100g": 389, "protein_g": 16.9, "carbs_g": 66.3, "fat_g": 6.9, "serving": "1/2 cup dry / 40g (~7g protein, 26g carbs, 155 kcal)"},
        "whey protein": {"calories_per_100g": 400, "protein_g": 80.0, "carbs_g": 6.0, "fat_g": 4.0, "serving": "1 scoop / 30g (~24g protein, 120 kcal)"},
        "banana": {"calories_per_100g": 89, "protein_g": 1.1, "carbs_g": 22.8, "fat_g": 0.3, "serving": "1 medium banana / 118g (~27g carbs, 105 kcal)"},
        "peanut butter": {"calories_per_100g": 588, "protein_g": 25.1, "carbs_g": 20.0, "fat_g": 50.4, "serving": "2 tbsp / 32g (~8g protein, 188 kcal)"},
        "rice": {"calories_per_100g": 130, "protein_g": 2.7, "carbs_g": 28.2, "fat_g": 0.3, "serving": "1 cup cooked / 158g (~4.3g protein, 45g carbs, 205 kcal)"},
        "beef": {"calories_per_100g": 250, "protein_g": 26.0, "carbs_g": 0.0, "fat_g": 15.0, "serving": "150g lean ground beef (~39g protein, 375 kcal)"},
    }

    q = food_query.lower().strip()
    match = None
    for key, val in food_db.items():
        if key in q or q in key:
            match = (key, val)
            break

    if match:
        key, profile = match
        return {
            "query": food_query,
            "matched_item": key.title(),
            "per_100g": {
                "calories_kcal": profile["calories_per_100g"],
                "protein_g": profile["protein_g"],
                "carbohydrates_g": profile["carbs_g"],
                "fat_g": profile["fat_g"],
            },
            "typical_serving_estimate": profile["serving"],
            "recovery_tip": "Pair with adequate water and 20-40g high-quality protein within 1-2 hours post-workout."
        }

    return {
        "query": food_query,
        "matched_item": food_query.title(),
        "general_guidelines": "For strength & hypertrophy recovery: aim for 0.7 - 1.0g protein per lb of body weight daily.",
        "note": "For precise packaged food barcodes, query exact items like 'chicken breast', 'greek yogurt', 'salmon', or 'whey protein'."
    }


def check_outdoor_workout_weather(city_name: str) -> Dict[str, Any]:
    """Check current outdoor weather conditions and outdoor workout viability using the Open-Meteo public API.

    Args:
        city_name: Name of the city (e.g. 'San Francisco', 'New York', 'London', 'Tokyo').

    Returns:
        Dictionary with temperature (Celsius & Fahrenheit), humidity, wind speed, precipitation, and coach recommendations for running/cycling.
    """
    try:
        geo_url = "https://geocoding-api.open-meteo.com/v1/search"
        geo_res = requests.get(geo_url, params={"name": city_name, "count": 1}, timeout=5)
        geo_res.raise_for_status()
        geo_data = geo_res.json().get("results", [])

        if not geo_data:
            return {"error": f"City '{city_name}' could not be located."}

        loc = geo_data[0]
        lat, lon = loc["latitude"], loc["longitude"]
        full_name = f"{loc.get('name')}, {loc.get('country')}"

        weather_url = "https://api.open-meteo.com/v1/forecast"
        weather_params = {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,wind_speed_10m",
        }
        w_res = requests.get(weather_url, params=weather_params, timeout=5)
        w_res.raise_for_status()
        current = w_res.json().get("current", {})

        temp_c = current.get("temperature_2m", 20.0)
        temp_f = round((temp_c * 9 / 5) + 32, 1)
        humidity = current.get("relative_humidity_2m", 50)
        wind_kmh = current.get("wind_speed_10m", 0)
        precip = current.get("precipitation", 0.0)

        viability = "Optimal"
        advice = "Great conditions for outdoor running or conditioning."
        if precip > 0.5:
            viability = "Caution: Rain"
            advice = "Wet surface; prioritize traction footwear or indoor cardio."
        elif temp_f > 85:
            viability = "Warm / Hot"
            advice = "High heat; increase electrolyte & water intake, seek shaded routes."
        elif temp_f < 38:
            viability = "Chilly / Cold"
            advice = "Cold air; dress in thermal layers and extend warm-up duration."

        return {
            "city": full_name,
            "temperature_f": temp_f,
            "temperature_c": temp_c,
            "relative_humidity_pct": humidity,
            "wind_speed_kmh": wind_kmh,
            "precipitation_mm": precip,
            "outdoor_workout_viability": viability,
            "coach_advice": advice,
        }

    except Exception as e:
        return {"error": f"Failed to fetch weather for {city_name}: {str(e)}"}


def generate_fitness_visual(
    prompt: str,
    title: str,
    tool_context: Optional[ToolContext] = None,
) -> Dict[str, Any]:
    """Generate a high-quality fitness visual (e.g. gym exercise posture guide, meal recommendation photo, or workout milestone badge) using Gemini image generation.

    Saves the image as an ADK artifact for the local playground and uploads it to public Cloud Storage for web display.

    Args:
        prompt: Detailed visual prompt describing the exercise form, plated meal, or achievement badge.
        title: Short title/subject for the visual (e.g. 'Barbell Squat Form Guide', 'Post-Workout Salmon Bowl').
        tool_context: ToolContext injected automatically by ADK runtime for artifact handling.

    Returns:
        Dictionary containing the public image URL, artifact filename, and status.
    """
    try:
        response = genai_client.models.generate_content(
            model=IMAGE_MODEL,
            contents=f"Professional athletic fitness visual, clear lighting, high resolution: {prompt}",
        )

        image_bytes = None
        mime_type = "image/jpeg"

        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if part.inline_data:
                    image_bytes = part.inline_data.data
                    mime_type = part.inline_data.mime_type or "image/jpeg"
                    break

        if not image_bytes:
            return {"error": "Failed to generate image bytes from model response."}

        slug = re.sub(r"[^a-zA-Z0-9_-]", "_", title.lower().strip()) or "fitness_visual"
        unique_suffix = uuid.uuid4().hex[:6]
        filename = f"{slug}_{unique_suffix}.jpg"

        # 1. Save as ADK artifact so it appears in Playground's artifacts panel
        if tool_context is not None:
            tool_context.save_artifact(filename, image_bytes)

        # 2. Upload to public Cloud Storage bucket
        blob = storage_bucket.blob(filename)
        blob.upload_from_string(image_bytes, content_type=mime_type)
        public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{filename}"

        return {
            "status": "success",
            "title": title,
            "artifact_filename": filename,
            "public_image_url": public_url,
            "mime_type": mime_type,
            "message": f"Successfully generated and published visual for '{title}'.",
        }

    except Exception as e:
        return {"error": f"Image generation failed: {str(e)}"}


schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

instruction = schema_manager.generate_system_prompt(
    role_description=(
        "You are FitPulse, an expert AI fitness, workout, and nutrition coach. "
        "CRITICAL MEMORY & ALLERGY RULE: You must remember, track, and strictly enforce all user allergies "
        "(e.g., peanuts, shellfish, dairy, gluten, soy, eggs, tree nuts) as well as dietary restrictions, "
        "injuries, and fitness preferences across conversations and sessions. "
        "When recommending meals, recovery snacks, or nutrition strategies, always cross-reference the user's stored "
        "memories and ensure no allergens are ever suggested. "
        "You also help users discover exercises, calculate strength targets (1RM), "
        "compute cardiovascular heart rate zones, check outdoor running weather conditions, "
        "estimate nutrition & macronutrients for recovery meals, generate illustrative form/meal visuals, "
        "build tailored workout routines, analyze complex training metrics with Python sandbox code execution, "
        "and track/log their training sessions using your tools."
    ),
    workflow_description=(
        "Analyze the user request, call any appropriate tools, and return structured UI. "
        "When responding, emit an A2UI JSON array containing exactly two messages: beginRendering followed by surfaceUpdate."
    ),
    ui_description=(
        "The A2UI response MUST be a JSON array containing two message objects: "
        "[{\"beginRendering\": {\"surfaceId\": \"default\", \"root\": \"card_1\"}}, "
        "{\"surfaceUpdate\": {\"surfaceId\": \"default\", \"components\": [...]}}]. "
        "Inside surfaceUpdate.components: "
        "- First component MUST be {\"id\": \"card_1\", \"component\": {\"Card\": {\"child\": \"col_1\"}}}. "
        "- Second component MUST be {\"id\": \"col_1\", \"component\": {\"Column\": {\"children\": {\"explicitList\": [\"text_1\", \"text_2\", ...]}}}}. "
        "- Followed by the Text components referenced in explicitList. "
        "Keep surfaces small and flat. Use ONLY Card, Column, Row, Text, and Image. "
        "Never omit the beginRendering and surfaceUpdate wrapper objects. "
        "Output ONLY the raw A2UI JSON array starting with '[' and ending with ']'. "
        "No conversational prose outside the JSON."
    ),
    include_schema=True,
    include_examples=True,
)




root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model=MODEL,
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=instruction,
    code_executor=code_executor,
    tools=[
        PreloadMemoryTool(),
        list_or_search_exercises,
        get_exercise_details,
        log_workout_session,
        get_user_workout_history,
        add_custom_exercise,
        calculate_one_rep_max,
        calculate_heart_rate_zones,
        estimate_nutrition_and_macros,
        check_outdoor_workout_weather,
        generate_fitness_visual,
    ],
    after_model_callback=a2ui_callback,
    after_agent_callback=generate_memories_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)









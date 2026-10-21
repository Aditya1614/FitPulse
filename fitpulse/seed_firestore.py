import sys
from google.cloud import firestore

PROJECT_ID = "qwiklabs-gcp-04-59fb1dbb96b2"

db = firestore.Client(project=PROJECT_ID)

exercises = [
    {
        "id": "barbell-bench-press",
        "name": "Barbell Bench Press",
        "target_muscle": "Chest",
        "secondary_muscles": ["Triceps", "Anterior Deltoids"],
        "equipment": "Barbell, Bench",
        "difficulty": "Intermediate",
        "instructions": "Lie flat on the bench, grip barbell slightly wider than shoulder-width. Lower bar to mid-chest, press up explosively until arms extend.",
        "default_sets": 4,
        "default_reps": "8-10",
        "category": "Strength"
    },
    {
        "id": "barbell-back-squat",
        "name": "Barbell Back Squat",
        "target_muscle": "Quadriceps",
        "secondary_muscles": ["Glutes", "Hamstrings", "Core"],
        "equipment": "Barbell, Squat Rack",
        "difficulty": "Intermediate",
        "instructions": "Place bar on upper traps. Feet shoulder-width apart. Squat down hips below knees while keeping chest upright, then drive upward through heels.",
        "default_sets": 4,
        "default_reps": "6-8",
        "category": "Strength"
    },
    {
        "id": "conventional-deadlift",
        "name": "Conventional Deadlift",
        "target_muscle": "Hamstrings",
        "secondary_muscles": ["Glutes", "Lower Back", "Traps", "Forearms"],
        "equipment": "Barbell",
        "difficulty": "Advanced",
        "instructions": "Feet hip-width apart under the barbell. Hinge at hips, grip bar. Keep back straight, brace core, and drive through floor to full lockout.",
        "default_sets": 3,
        "default_reps": "5",
        "category": "Strength"
    },
    {
        "id": "dumbbell-overhead-press",
        "name": "Dumbbell Overhead Press",
        "target_muscle": "Shoulders",
        "secondary_muscles": ["Triceps", "Upper Chest"],
        "equipment": "Dumbbells",
        "difficulty": "Beginner",
        "instructions": "Hold dumbbells at shoulder height with palms facing forward. Press dumbbells overhead until arms are extended, then slowly lower.",
        "default_sets": 3,
        "default_reps": "10-12",
        "category": "Hypertrophy"
    },
    {
        "id": "pull-ups",
        "name": "Pull-Ups",
        "target_muscle": "Lats",
        "secondary_muscles": ["Biceps", "Upper Back", "Core"],
        "equipment": "Pull-Up Bar",
        "difficulty": "Intermediate",
        "instructions": "Grip pull-up bar with palms facing away. Pull chest up toward the bar by driving elbows down, pause briefly at top, and lower with control.",
        "default_sets": 3,
        "default_reps": "8-12",
        "category": "Bodyweight"
    },
    {
        "id": "plank",
        "name": "Standard Core Plank",
        "target_muscle": "Core",
        "secondary_muscles": ["Shoulders", "Glutes"],
        "equipment": "Bodyweight, Yoga Mat",
        "difficulty": "Beginner",
        "instructions": "Rest on forearms and toes. Keep spine neutral and core tight. Hold position without letting hips sag.",
        "default_sets": 3,
        "default_reps": "45-60s hold",
        "category": "Endurance"
    }
]

def seed_data():
    print(f"Seeding exercises collection into Firestore project: {PROJECT_ID}...")
    collection_ref = db.collection("exercises")
    for ex in exercises:
        doc_id = ex["id"]
        collection_ref.document(doc_id).set(ex)
        print(f"  ✓ Added exercise: {ex['name']} ({doc_id})")
    print("Seeding completed successfully!")

if __name__ == "__main__":
    seed_data()

#!/usr/bin/env python3
"""
Convert SBS (Stronger By Science) CSV workout files to match the workout JSON format.
"""

import csv
import json
import os
import re
from typing import Dict, List, Any

def clean_filename(filename: str) -> str:
    """Convert filename to a clean format for JSON output."""
    clean_name = filename.replace('.csv', '')
    clean_name = re.sub(r'[^\w\-_\.]', '_', clean_name)
    clean_name = re.sub(r'_+', '_', clean_name)
    clean_name = clean_name.strip('_')
    return clean_name.lower()

def determine_program_details(filename: str) -> Dict[str, str]:
    """Extract program details from filename."""

    # Parse filename for program type and frequency
    filename_lower = filename.lower()

    # Determine program type
    if 'linear progression' in filename_lower:
        program_type = 'Linear Progression'
        main_goal = 'Build Strength'
        training_level = 'Beginner'
        if 'lf' in filename_lower:
            program_type += ' (Low Fatigue)'
    elif 'hypertrophy' in filename_lower:
        program_type = 'Hypertrophy Template'
        main_goal = 'Build Muscle'
        if 'novice' in filename_lower:
            training_level = 'Beginner'
        else:
            training_level = 'Intermediate'
    elif 'strength program' in filename_lower:
        program_type = 'Strength Program (Low Fatigue)'
        main_goal = 'Build Strength'
        training_level = 'Intermediate'
    else:
        program_type = 'Unknown'
        main_goal = 'General Fitness'
        training_level = 'Intermediate'

    # Extract frequency
    frequency_match = re.search(r'(\d+)x', filename_lower)
    if frequency_match:
        days_per_week = frequency_match.group(1)
    else:
        days_per_week = "3"

    # Determine duration
    if 'novice' in filename_lower:
        duration = "53 weeks"
    else:
        duration = "21 weeks"

    return {
        'program_type': program_type,
        'main_goal': main_goal,
        'training_level': training_level,
        'days_per_week': days_per_week,
        'duration': duration
    }

def parse_sbs_csv_to_workout_format(csv_file_path: str) -> Dict[str, Any]:
    """Parse an SBS CSV file and convert to workout JSON format."""

    with open(csv_file_path, 'r', newline='', encoding='utf-8') as file:
        csv_reader = csv.reader(file)
        rows = list(csv_reader)

    if not rows:
        return {}

    # Extract program details
    filename = os.path.basename(csv_file_path)
    program_details = determine_program_details(filename)

    # Clean program name
    program_name = filename.replace('.csv', '').replace('_', ' ').title()
    program_name = program_name.replace('Sbs ', 'SBS ')

    # Initialize the workout data structure
    workout_data = {
        "title": program_name,
        "url": "https://www.strongerbyscience.com/program-bundle/",
        "summary": {
            "main_goal": program_details['main_goal'],
            "workout_type": "Split",
            "training_level": program_details['training_level'],
            "program_duration": program_details['duration'],
            "days_per_week": program_details['days_per_week'],
            "time_per_workout": "60-90 minutes",
            "equipment_required": "Barbell, Dumbbells, Machines",
            "target_gender": "Male & Female",
            "reads": "SBS Program",
            "recommended_supplements": ["Whey Protein", "Creatine", "Beta-Alanine", "Multivitamin"]
        },
        "description": f"Stronger By Science {program_details['program_type']} program focusing on {program_details['main_goal'].lower()} with {program_details['days_per_week']} training sessions per week.",
        "workout_schedule": {},
        "additional_info": {
            "rest_periods": "2-3 minutes between sets for main lifts, 1-2 minutes for accessories",
            "progression": "Progressive overload with RIR (Reps In Reserve) based autoregulation",
            "schedule": f"{program_details['days_per_week']} days per week training schedule",
            "nutrition": "Adequate protein intake (0.8-1g per lb bodyweight) to support training goals",
            "notes": "SBS programs use RIR-based autoregulation. Adjust weights based on bar speed and perceived exertion.",
            "pdf_download": "https://www.strongerbyscience.com/program-bundle/"
        }
    }

    # Parse exercise data by day
    current_day = None
    day_exercises = []

    for row_idx, row in enumerate(rows[2:], start=2):  # Skip header rows
        if not row or not any(row):
            continue

        exercise_name = row[0].strip() if row[0] else ""

        # Check if this is a day marker
        if exercise_name.startswith('Day '):
            # Save previous day if exists
            if current_day and day_exercises:
                workout_data["workout_schedule"][current_day] = {
                    "muscle_groups": determine_muscle_groups(day_exercises),
                    "exercises": day_exercises
                }

            current_day = exercise_name
            day_exercises = []
            continue

        # Skip empty rows, accessories sections, and training max rows
        if (not exercise_name or
            exercise_name.lower() in ['accessories', ''] or
            exercise_name.endswith('TM')):
            continue

        # Extract basic exercise info from first week
        if len(row) >= 4:
            try:
                # Get weight from first week (column 1)
                weight = row[1] if row[1] else ""

                # Get reps from first week (column 2)
                reps = row[2] if row[2] else ""

                # Get sets from first week (column 4, set goal)
                sets = row[4] if len(row) > 4 and row[4] else "3"

                # Clean up the data
                if 'single' in str(reps).lower():
                    reps = "1"
                elif not str(reps).replace('-', '').isdigit():
                    reps = "8-12"  # Default

                if not str(sets).isdigit():
                    sets = "3"  # Default

                # Skip if we couldn't extract meaningful data
                if not weight or weight == '':
                    continue

                exercise_info = {
                    "name": exercise_name,
                    "sets": sets,
                    "reps": str(reps)
                }

                day_exercises.append(exercise_info)

            except (ValueError, IndexError):
                continue

    # Save the last day
    if current_day and day_exercises:
        workout_data["workout_schedule"][current_day] = {
            "muscle_groups": determine_muscle_groups(day_exercises),
            "exercises": day_exercises
        }

    return workout_data

def determine_muscle_groups(exercises: List[Dict]) -> str:
    """Determine muscle groups based on exercise names."""

    exercise_names = [ex['name'].lower() for ex in exercises]
    muscle_groups = []

    # Check for specific muscle groups
    if any('squat' in name or 'leg press' in name or 'lunge' in name for name in exercise_names):
        muscle_groups.append('Legs')

    if any('bench' in name or 'press' in name and 'leg' not in name for name in exercise_names):
        muscle_groups.append('Chest')

    if any('row' in name or 'pull' in name or 'deadlift' in name for name in exercise_names):
        muscle_groups.append('Back')

    if any('curl' in name for name in exercise_names):
        muscle_groups.append('Biceps')

    if any('extension' in name or 'press' in name for name in exercise_names):
        if 'tricep' in ' '.join(exercise_names) or 'overhead' in ' '.join(exercise_names):
            muscle_groups.append('Triceps')

    if any('shoulder' in name or 'lateral' in name or 'overhead' in name for name in exercise_names):
        muscle_groups.append('Shoulders')

    # Default groupings
    if not muscle_groups:
        muscle_groups = ['Full Body']

    return ' & '.join(muscle_groups)

def convert_all_sbs_files():
    """Convert all SBS CSV files to workout JSON format."""

    sbs_dir = "/Users/navinislam/workout-AI/sbs"

    # Remove old JSON directory and create new one
    import shutil
    old_json_dir = "/Users/navinislam/workout-AI/sbs_json"
    if os.path.exists(old_json_dir):
        shutil.rmtree(old_json_dir)

    # Create new output directory in main folder
    output_dir = "/Users/navinislam/workout-AI"

    # Get all CSV files in the SBS directory
    csv_files = [f for f in os.listdir(sbs_dir) if f.endswith('.csv')]

    print(f"Converting {len(csv_files)} SBS CSV files to workout JSON format...")

    converted_files = []

    for csv_file in csv_files:
        csv_path = os.path.join(sbs_dir, csv_file)

        try:
            print(f"Converting: {csv_file}")

            # Parse the CSV
            workout_data = parse_sbs_csv_to_workout_format(csv_path)

            # Skip empty conversions
            if not workout_data.get("workout_schedule"):
                print(f"⚠️  Skipped {csv_file} - no exercise data found")
                continue

            # Generate output filename
            clean_name = clean_filename(csv_file)
            json_filename = f"{clean_name}.json"
            json_path = os.path.join(output_dir, json_filename)

            # Write JSON file
            with open(json_path, 'w', encoding='utf-8') as json_file:
                json.dump(workout_data, json_file, indent=2, ensure_ascii=False)

            converted_files.append({
                "source": csv_file,
                "output": json_filename,
                "title": workout_data.get("title", "Unknown"),
                "days": len(workout_data.get("workout_schedule", {})),
                "total_exercises": sum(len(day.get("exercises", [])) for day in workout_data.get("workout_schedule", {}).values())
            })

            print(f"✓ Converted to: {json_filename}")

        except Exception as e:
            print(f"✗ Error converting {csv_file}: {str(e)}")

    print(f"\n✅ Conversion complete!")
    print(f"📁 Output directory: {output_dir}")
    print(f"📊 Successfully converted: {len(converted_files)}/{len(csv_files)} files")

    return converted_files

if __name__ == "__main__":
    convert_all_sbs_files()
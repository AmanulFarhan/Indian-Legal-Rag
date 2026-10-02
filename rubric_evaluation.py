import os
import json
import time
import pandas as pd
import google.generativeai as genai

from google.api_core.exceptions import ResourceExhausted

# ==========================
# CONFIG
# ==========================
import os

API_KEY = os.getenv("GEMINI_API_KEY")

genai.configure(api_key=API_KEY)

model = genai.GenerativeModel("gemini-3.8-flash")

INPUT_CSV = "evaluation_dataset.csv"
OUTPUT_CSV = "rubric_results.csv"

BATCH_SIZE = 5

# ==========================
# LOAD DATA
# ==========================

df = pd.read_csv(INPUT_CSV)

# Required columns:
# question
# reference_answer
# generated_answer

records = df.to_dict("records")


# ==========================
# BUILD PROMPT
# ==========================

def build_prompt(batch):

    prompt = """
You are an expert evaluator.

Evaluate each generated answer against the reference answer.

Score each criterion from 1-5.

Criteria:
1. Faithfulness
2. Correctness
3. Completeness
4. Clarity

Return ONLY valid JSON.

Format:

[
 {
   "question_id": 1,
   "faithfulness": 5,
   "correctness": 4,
   "completeness": 5,
   "clarity": 4
 }
]

"""

    for idx, item in enumerate(batch, start=1):

        prompt += f"""

Question ID: {idx}

QUESTION:
{item['question']}

REFERENCE ANSWER:
{item['reference_answer']}

GENERATED ANSWER:
{item['model_generated_answer']}
"""

    return prompt


# ==========================
# GEMINI CALL
# ==========================

def evaluate_batch(batch):

    prompt = build_prompt(batch)

    while True:

        try:

            response = model.generate_content(prompt)

            text = response.text.strip()

            if text.startswith("```json"):
                text = text.replace("```json", "")
                text = text.replace("```", "")
                text = text.strip()

            return json.loads(text)

        except ResourceExhausted:

            print("Rate limit reached.")
            print("Waiting 30 seconds...")

            time.sleep(30)

        except Exception as e:

            print("ERROR:", e)
            return []


# ==========================
# CREATE BATCHES
# ==========================

batches = [
    records[i:i+BATCH_SIZE]
    for i in range(0, len(records), BATCH_SIZE)
]

# ==========================
# RUN EVALUATION
# ==========================

all_results = []

for i, batch in enumerate(batches):

    print(f"\nEvaluating batch {i+1}/{len(batches)}")

    batch_results = evaluate_batch(batch)

    all_results.extend(batch_results)

    temp_df = pd.DataFrame(all_results)
    temp_df.to_csv(OUTPUT_CSV, index=False)

    if i < len(batches) - 1:

        print("Waiting 30 seconds before next batch...")
        time.sleep(30)

# ==========================
# FINAL SAVE
# ==========================

results_df = pd.DataFrame(all_results)

results_df.to_csv(OUTPUT_CSV, index=False)

# ==========================
# MEAN SCORES
# ==========================

print("\n========== RESULTS ==========")

for col in [
    "faithfulness",
    "correctness",
    "completeness",
    "clarity"
]:

    if col in results_df.columns:
        print(
            f"{col}: {results_df[col].mean():.2f}"
        )

print("\nSaved to:")
print(OUTPUT_CSV)
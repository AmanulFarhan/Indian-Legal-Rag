import pandas as pd
from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction
from rouge_score import rouge_scorer

df = pd.read_csv("evaluation_dataset.csv")

smoothie = SmoothingFunction().method4

rouge = rouge_scorer.RougeScorer(
    ["rouge1", "rouge2", "rougeL"],
    use_stemmer=True
)

results = []

for _, row in df.iterrows():

    reference = str(row["reference_answer"])
    generated = str(row["model_generated_answer"])

    bleu = sentence_bleu(
        [reference.split()],
        generated.split(),
        smoothing_function=smoothie
    )

    rouge_scores = rouge.score(reference, generated)

    results.append({
        "question_id": row["question_id"],
        "BLEU": bleu,
        "ROUGE1": rouge_scores["rouge1"].fmeasure,
        "ROUGE2": rouge_scores["rouge2"].fmeasure,
        "ROUGEL": rouge_scores["rougeL"].fmeasure
    })

results_df = pd.DataFrame(results)

# Save per-question scores
results_df.to_csv("bleu_rouge_results.csv", index=False)

# Calculate averages
avg_bleu = results_df["BLEU"].mean()
avg_rouge1 = results_df["ROUGE1"].mean()
avg_rouge2 = results_df["ROUGE2"].mean()
avg_rougel = results_df["ROUGEL"].mean()

print("\n===== AVERAGE SCORES =====")
print(f"Average BLEU    : {avg_bleu:.4f}")
print(f"Average ROUGE-1 : {avg_rouge1:.4f}")
print(f"Average ROUGE-2 : {avg_rouge2:.4f}")
print(f"Average ROUGE-L : {avg_rougel:.4f}")
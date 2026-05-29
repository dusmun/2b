import re
import sys
import os
import json
import csv
import numpy as np
from sentence_transformers import SentenceTransformer, util

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def preprocess(text):
    sentences = text.replace('\n', ' ').split('.')
    return [sentence.strip() for sentence in sentences if sentence.strip()]

def lcs_length(mapped_g):
    if not mapped_g:
        return 0
    dp = [1] * len(mapped_g)
    for i in range(1, len(mapped_g)):
        for j in range(i):
            if mapped_g[i] > mapped_g[j]:
                dp[i] = max(dp[i], dp[j] + 1)
    return max(dp)

def sim_matrix(orig, gen, model):
    if not orig or not gen:
        return np.array([])
        
    embeddings_orig = model.encode(orig)
    embeddings_gen = model.encode(gen)
    
    # Calculate cosine similarity using the built-in utility
    similarity_matrix = util.cos_sim(embeddings_orig, embeddings_gen).numpy()
    
    # Ensure no negative similarities and round to 4 decimals
    similarity_matrix = np.clip(similarity_matrix, 0, None)
    return np.round(similarity_matrix, 4)

def run_similarity(scenario_path, visitor_path, llm_path):
    if not os.path.exists(scenario_path):
        sys.exit(f"Error: {scenario_path} not found")
        
    with open(scenario_path, encoding="utf-8") as f:
        u_orig = preprocess(f.read())
        
    model = SentenceTransformer("all-MiniLM-L6-v2")
    results = {}
    all_metrics = []
    
    comparisons = [
        ("Original_vs_Visitor", visitor_path),
        ("Original_vs_LLM", llm_path)
    ]
    
    for name, path in comparisons:
        if not os.path.exists(path):
            continue
            
        with open(path, encoding="utf-8") as f:
            u_gen = preprocess(f.read())
            
        mat = sim_matrix(u_orig, u_gen, model)
        
        matches = []
        if mat.size > 0:
            for i, row in enumerate(mat):
                if np.max(row) >= 0.3:
                    matches.append({
                        'o': i,
                        'g': int(np.argmax(row)),
                        's': float(np.max(row))
                    })
        
        name_lower = name.lower()
        
        # Output Matrix CSV
        matrix_csv_path = f"output/matrix_{name_lower}.csv"
        with open(matrix_csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            header = [''] + [f'NT{i+1}' for i in range(len(u_gen))]
            writer.writerow(header)
            for i, row in enumerate(mat):
                writer.writerow([f'OT{i+1}'] + list(row))
                
        # Output Matching CSV
        matching_csv_path = f"output/matching_{name_lower}.csv"
        with open(matching_csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['original_id', 'original_text', 'new_text_id', 'new_text', 'similarity'])
            for m in matches:
                writer.writerow([
                    f'OT{m["o"]+1}', u_orig[m["o"]],
                    f'NT{m["g"]+1}', u_gen[m["g"]],
                    m['s']
                ])
                
        matched_g = {m['g'] for m in matches}
        
        # Metrics
        precision = len(matched_g) / len(u_gen) if u_gen else 0
        recall = len(matches) / len(u_orig) if u_orig else 0
        f1_score = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        
        mapped_g = [m['g'] for m in matches]
        sqst = lcs_length(mapped_g) / max(len(u_orig), len(u_gen)) if max(len(u_orig), len(u_gen)) > 0 else 0
        
        metrics_dict = {
            "precision": precision,
            "recall": recall,
            "f1_score": f1_score,
            "sqst": sqst
        }
        
        all_metrics.append({
            "comparison": name,
            **metrics_dict
        })
        
        results[name] = {
            "matrix_csv": matrix_csv_path,
            "matching_csv": matching_csv_path,
            "metrics": metrics_dict
        }

    if all_metrics:
        with open("output/metrics_summary.csv", "w", newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=["comparison", "precision", "recall", "f1_score", "sqst"])
            writer.writeheader()
            writer.writerows(all_metrics)

    with open("output/similarity_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
        
    print("[Similarity] Done -> output/similarity_results.json\nCSVs generated for main comparisons.")

def main():
    scenario_path = sys.argv[1] if len(sys.argv) > 1 else "input/Scenario.txt"
    visitor_path = sys.argv[2] if len(sys.argv) > 2 else "output/text_visitor.txt"
    llm_path = sys.argv[3] if len(sys.argv) > 3 else "output/text_llm.txt"
    
    run_similarity(scenario_path, visitor_path, llm_path)

if __name__ == "__main__":
    main()

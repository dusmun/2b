# Aufgabe 2b — BPMN-to-Text & Text Similarity

## Setup

```bash
pip install -r requirements.txt
set OPENAI_API_KEY=your-key
```

## Ausführung

```bash
python main.py input/Chainsaw_3793544.bpmn
```

Dieser Befehl führt den gesamten Ablauf automatisch aus:
1. **Transformation (BPMN → Text)**
   - **Visitor-basiert** (`visitor_based.py`) — Generiert `output/text_visitor.txt`
   - **LLM-basiert** (`llm_based.py`) — Generiert `output/text_llm.txt` via GPT-Prompting
2. **Similarity-Vergleich** (`similarity.py`)
   - Vergleicht beide Texte im Anschluss und speichert detaillierte Ergebnisse in `output/similarity_results.json`.

*(Optional: Der Ähnlichkeitsvergleich kann auch weiterhin separat über `python similarity.py` aufgerufen werden.)*

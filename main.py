import os
import sys

import visitor_based
import llm_based

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def main():
    if os.path.exists(".env"):
        with open(".env", encoding="utf-8") as env_file:
            for line in env_file:
                clean_line = line.strip()
                if clean_line and not clean_line.startswith("#"):
                    key, value = clean_line.split("=", 1)
                    os.environ[key.strip()] = value.strip()
                
    if len(sys.argv) > 1:
        bpmn_path = sys.argv[1]
    else:
        bpmn_path = "input/Chainsaw_3793544.bpmn"
        
    os.makedirs("output", exist_ok=True)
    
    with open("output/text_visitor.txt", "w", encoding="utf-8") as visitor_file:
        visitor_text = visitor_based.run(bpmn_path)
        visitor_file.write(visitor_text)
    print("[Visitor] Done -> output/text_visitor.txt")
    
    with open("output/text_llm.txt", "w", encoding="utf-8") as llm_file:
        llm_text = llm_based.run(bpmn_path)
        llm_file.write(llm_text)
    print("[LLM] Done -> output/text_llm.txt")

if __name__ == "__main__":
    main()

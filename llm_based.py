import os
import json
from openai import OpenAI
from visitor_based import parse_bpmn

def run(bpmn_path):
    nodes, flows, name, lanes = parse_bpmn(bpmn_path)
    
    elements = []
    for node in nodes.values():
        if not node.get("name"):
            continue
            
        element_data = {
            "type": node["tag"],
            "name": node["name"]
        }
        
        if node.get("dir"):
            element_data["direction"] = node["dir"]
            
        if node.get("default"):
            element_data["default_flow"] = node["default"]
            
        if node["id"] in lanes:
            element_data["lane"] = lanes[node["id"]]
            
        if node["type"] == "subprocess" and node.get("children"):
            sub_steps = []
            for child in node["children"].values():
                if child["type"] == "task":
                    sub_steps.append(child["name"])
            element_data["sub_steps"] = sub_steps
            
        elements.append(element_data)

    flow_info = []
    for _, flow_name, source_id, target_id in flows:
        if source_id in nodes and nodes[source_id].get("name") and \
           target_id in nodes and nodes[target_id].get("name"):
            
            flow_data = {
                "from": nodes[source_id]["name"],
                "to": nodes[target_id]["name"]
            }
            if flow_name:
                flow_data["label"] = flow_name
                
            flow_info.append(flow_data)

    summary_data = {
        "process": name,
        "lanes": sorted(set(lanes.values())),
        "elements": elements,
        "flows": flow_info
    }
    
    summary = json.dumps(summary_data, indent=2)

    prompt = f"""Describe the BPMN process in a clear, natural-language narrative.

CRITICAL RULES:
1. Follow the BPMN sequence flows from the start event to the end events.
2. Preserve BPMN control-flow semantics exactly.
3. If a parallel gateway is reached, explicitly state that the following branches run in parallel. Do not describe parallel branches with sequential wording such as "first", "then", "followed by", or "afterwards" unless the BPMN sequence flow actually defines that order.
4. For parallel branches, state that all branches must be completed before the process continues at the join.
5. If an exclusive gateway is reached, describe it as a decision and describe each alternative branch separately.
6. If an event-based gateway is reached, describe it as a waiting point where one of several events may occur.
7. If a loop exists, explicitly state what repeats and where the process loops back.
8. Describe sub-processes and their internal steps exactly when the sub-process is reached.
9. Wrap every task and sub-process name in double quotes exactly as it appears in the BPMN data. Do not paraphrase task names.
10. Write as flowing paragraphs. Do not use bullet points or numbered lists.

BPMN Process Data:
{summary}"""

    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=2000
    )
    
    return response.choices[0].message.content


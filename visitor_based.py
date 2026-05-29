import xml.etree.ElementTree as ET

NS = {"b": "http://www.omg.org/spec/BPMN/20100524/MODEL"}

def get_node_type(tag_name):
    if "Task" in tag_name:
        return "task"
    elif "Gateway" in tag_name:
        return "gateway"
    elif "Event" in tag_name:
        return "event"
    elif tag_name == "subProcess":
        return "subprocess"
    return None

def parse_bpmn(path):
    tree = ET.parse(path)
    root = tree.getroot()
    process = root.find(".//b:process", NS)
    
    lanes = {}
    for lane in process.findall(".//b:lane", NS):
        for node_ref in lane.findall("b:flowNodeRef", NS):
            lanes[node_ref.text] = lane.get("name", "")
            
    nodes = {}
    flows = []
    
    for element in process:
        tag_name = element.tag.split("}")[-1]
        
        if tag_name == "sequenceFlow":
            flows.append((
                element.get("id"),
                element.get("name", ""),
                element.get("sourceRef"),
                element.get("targetRef")
            ))
            continue
            
        node_type = get_node_type(tag_name)
        if node_type:
            node = {
                "id": element.get("id"),
                "name": element.get("name", ""),
                "type": node_type,
                "tag": tag_name,
                "out": [],
                "dir": element.get("gatewayDirection", ""),
                "default": element.get("default"),
                "children": {}
            }
            
            if node_type == "subprocess":
                sub_flows = []
                for sub_element in element:
                    sub_tag = sub_element.tag.split("}")[-1]
                    if sub_tag == "sequenceFlow":
                        sub_flows.append((sub_element.get("sourceRef"), sub_element.get("targetRef")))
                    
                    sub_node_type = get_node_type(sub_tag)
                    if sub_node_type:
                        node["children"][sub_element.get("id")] = {
                            "id": sub_element.get("id"),
                            "name": sub_element.get("name", ""),
                            "type": sub_node_type,
                            "tag": sub_tag,
                            "out": []
                        }
                
                for source_ref, target_ref in sub_flows:
                    if source_ref in node["children"]:
                        node["children"][source_ref]["out"].append(("","", target_ref))
                        
            nodes[node["id"]] = node

    for flow_id, flow_name, source_ref, target_ref in flows:
        if source_ref in nodes:
            nodes[source_ref]["out"].append((flow_id, flow_name, target_ref))
            
    process_name = process.get("name", "Process")
    return nodes, flows, process_name, lanes

def find_back_edges(nodes, start_id):
    visited = set()
    path = set()
    back_edges = set()
    
    def dfs(node_id):
        if node_id in path or node_id in visited:
            return
            
        visited.add(node_id)
        path.add(node_id)
        
        node = nodes.get(node_id, {})
        for _, _, target_id in node.get("out", []):
            if target_id in path:
                back_edges.add((node_id, target_id))
            else:
                dfs(target_id)
                
        path.remove(node_id)
        
    if start_id:
        dfs(start_id)
        
    return back_edges

def find_matching_join(nodes, start_id, back_edges):
    start_node = nodes.get(start_id)
    if not start_node or len(start_node["out"]) <= 1:
        return None
        
    reachables = []
    for _, _, target_id in start_node["out"]:
        reachable_set = set()
        queue = [target_id]
        
        while queue:
            current_id = queue.pop(0)
            if current_id not in reachable_set:
                reachable_set.add(current_id)
                if current_id in nodes:
                    for _, _, next_id in nodes[current_id]["out"]:
                        if (current_id, next_id) not in back_edges:
                            queue.append(next_id)
                            
        reachables.append(reachable_set)
        
    common_nodes = set.intersection(*reachables) if reachables else set()
    if not common_nodes:
        return None
    
    queue = [start_id]
    visited = set()
    
    while queue:
        current_id = queue.pop(0)
        if current_id in visited:
            continue
            
        visited.add(current_id)
        
        if current_id in common_nodes and nodes.get(current_id, {}).get("dir") == "Converging":
            return current_id
            
        if current_id in nodes:
            for _, _, next_id in nodes[current_id]["out"]:
                if (current_id, next_id) not in back_edges:
                    queue.append(next_id)
                    
    for current_id in common_nodes:
        if nodes.get(current_id, {}).get("dir") == "Converging":
            return current_id
            
    return list(common_nodes)[0] if common_nodes else None

class BPMNVisitor:
    def __init__(self, nodes):
        self.nodes = nodes
        self.visited = set()
        self.sentences = []
        self.back_edges = set()

    def get_next_nodes(self, node):
        next_nodes = []
        for _, flow_condition, target_id in node["out"]:
            if target_id in self.nodes:
                next_nodes.append((flow_condition, self.nodes[target_id]))
        return next_nodes

    def process_single_next_node(self, current_node, next_nodes):
        if len(next_nodes) == 1:
            _, next_node = next_nodes[0]
            
            if (current_node["id"], next_node["id"]) in self.back_edges:
                if next_node["name"]:
                    node_name = f'"{next_node["name"]}"'
                elif next_node["type"] == "gateway":
                    node_name = "the gateway"
                else:
                    node_name = "the node"
                    
                self.sentences.append(f'The process loops back to {node_name}.')
                return None
                
            return next_node
        return None

    def visit_sequence(self, current_node, stop_id=None):
        while current_node and current_node["id"] != stop_id and current_node["id"] not in self.visited:
            self.visited.add(current_node["id"])
            node_type = current_node["type"]
            next_nodes = self.get_next_nodes(current_node)
            
            if node_type == "event":
                self._visit_event(current_node)
                current_node = self.process_single_next_node(current_node, next_nodes)
                
            elif node_type == "task":
                current_node = self._visit_task(current_node, next_nodes, stop_id)
                
            elif node_type == "subprocess":
                self._visit_subprocess(current_node)
                current_node = self.process_single_next_node(current_node, next_nodes)
                
            elif node_type == "gateway":
                if current_node["dir"] == "Converging":
                    current_node = self.process_single_next_node(current_node, next_nodes)
                    if current_node:
                        self.visit_sequence(current_node, stop_id)
                    break
                
                join_id = find_matching_join(self.nodes, current_node["id"], self.back_edges)
                
                if current_node["tag"] == "parallelGateway":
                    self._visit_parallel_gateway(current_node, next_nodes, join_id)
                else:
                    self._visit_exclusive_or_event_gateway(current_node, next_nodes, join_id)
                        
                if join_id:
                    self.visited.discard(join_id)
                    self.visit_sequence(self.nodes[join_id], stop_id)
                break
                
            else:
                current_node = self.process_single_next_node(current_node, next_nodes)

    def _visit_event(self, node):
        name_str = f' "{node["name"]}"' if node["name"] else ""
        
        if node["tag"] == "startEvent":
            self.sentences.append(f"The process starts{name_str}.")
        elif node["tag"] == "endEvent":
            self.sentences.append(f"The process ends{name_str}.")
        elif node["tag"] == "intermediateCatchEvent":
            self.sentences.append(f'The process waits for "{node["name"]}".')
        else:
            self.sentences.append(f'The process triggers the signal "{node["name"]}".')

    def _visit_task(self, start_task, initial_next_nodes, stop_id):
        tasks = [start_task]
        current_next_nodes = initial_next_nodes
        
        while len(current_next_nodes) == 1:
            next_node = current_next_nodes[0][1]
            
            is_stop = (next_node["id"] == stop_id)
            is_visited = (next_node["id"] in self.visited)
            is_not_task = (next_node["type"] != "task")
            is_back_edge = ((tasks[-1]["id"], next_node["id"]) in self.back_edges)
            
            if is_stop or is_visited or is_not_task or is_back_edge:
                break
                
            self.visited.add(next_node["id"])
            tasks.append(next_node)
            current_next_nodes = self.get_next_nodes(next_node)
        
        task_names = [f'"{t["name"]}"' for t in tasks]
        
        if len(tasks) == 1:
            self.sentences.append(f'The task {task_names[0]} is executed.')
        else:
            names_str = ", ".join(task_names[:-1])
            self.sentences.append(f'The tasks {names_str} and {task_names[-1]} are executed sequentially.')
            
        return self.process_single_next_node(tasks[-1], current_next_nodes)

    def _visit_subprocess(self, node):
        if node["name"]:
            self.sentences.append(f'The subprocess "{node["name"]}" is executed.')
        else:
            self.sentences.append("The subprocess is executed.")
            
        children = node["children"]
        start_event = None
        for child in children.values():
            if child["tag"] == "startEvent":
                start_event = child
                break
                
        if start_event:
            subprocess_sentences = []
            
            def walk_subprocess(current, seen):
                if current["id"] not in seen:
                    seen.add(current["id"])
                    
                    if current["type"] == "task":
                        subprocess_sentences.append(f'The step "{current["name"]}" is performed.')
                        
                    for _, _, target_id in current["out"]:
                        if target_id in children:
                            walk_subprocess(children[target_id], seen)
                            
            walk_subprocess(start_event, set())
            
            if subprocess_sentences:
                self.sentences.append(f"Within the subprocess: {' '.join(subprocess_sentences)}")

    def _visit_parallel_gateway(self, gateway, next_nodes, join_id):
        self.sentences.append("The process executes the following branches in parallel.")
        
        for index, (_, next_node) in enumerate(next_nodes):
            if (gateway["id"], next_node["id"]) in self.back_edges:
                if next_node.get("name"):
                    node_name = f'"{next_node["name"]}"'
                elif next_node.get("type") == "gateway":
                    node_name = "the gateway"
                else:
                    node_name = "the node"
                    
                self.sentences.append(f"In parallel branch {index+1}, the process loops back to {node_name}.")
                continue
                
            previous_sentences = self.sentences
            self.sentences = []
            
            self.visit_sequence(next_node, join_id)
            
            if self.sentences:
                previous_sentences.append(f"In parallel branch {index+1}: {' '.join(self.sentences)}")
                
            self.sentences = previous_sentences
            
        self.sentences.append("The process then waits until all parallel branches are completed.")

    def _visit_exclusive_or_event_gateway(self, gateway, next_nodes, join_id):
        if gateway["tag"] == "exclusiveGateway" and gateway["name"]:
            self.sentences.append(f'The decision "{gateway["name"]}" is evaluated.')
        elif gateway["tag"] == "eventBasedGateway":
            self.sentences.append("The process waits for one of the following events to occur.")
        else:
            self.sentences.append("A decision is evaluated.")
            
        for condition, next_node in next_nodes:
            if gateway["tag"] == "exclusiveGateway":
                condition_text = f'If {condition}' if condition else 'Otherwise'
            else:
                event_name = condition or next_node["name"]
                condition_text = f'If the event "{event_name}" occurs'
                
            if (gateway["id"], next_node["id"]) in self.back_edges:
                if next_node.get("name"):
                    node_name = f'"{next_node["name"]}"'
                elif next_node.get("type") == "gateway":
                    node_name = "the gateway"
                else:
                    node_name = "the node"
                    
                self.sentences.append(f'{condition_text}, the process loops back to {node_name}.')
                continue
                
            previous_sentences = self.sentences
            self.sentences = []
            
            self.visit_sequence(next_node, join_id)
            
            if self.sentences:
                first_sentence = self.sentences[0]
                first_sentence_lower = first_sentence[0].lower() + first_sentence[1:]
                previous_sentences.append(f"{condition_text}, {first_sentence_lower}")
                previous_sentences.extend(self.sentences[1:])
            else:
                previous_sentences.append(f"{condition_text}, the process advances.")
                
            self.sentences = previous_sentences

    def transform(self, process_name):
        self.sentences.append(f"Process: {process_name}")
        
        start_event = None
        for node in self.nodes.values():
            if node["tag"] == "startEvent":
                start_event = node
                break
                
        if start_event:
            self.back_edges = find_back_edges(self.nodes, start_event["id"])
            self.visit_sequence(start_event)
            
        return "\n\n".join(self.sentences)

def run(bpmn_path):
    nodes, _, process_name, _ = parse_bpmn(bpmn_path)
    visitor = BPMNVisitor(nodes)
    return visitor.transform(process_name)

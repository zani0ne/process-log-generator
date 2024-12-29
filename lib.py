import graphviz
import xml.etree.ElementTree as ET
from defusedxml import ElementTree as ET

MAX_DEPTH = 15
visited_processes = set()
task_tags = ['task', 'userTask', 'manualTask', 'serviceTask', 'scriptTask', 'businessRuleTask', 'sendTask', 'receiveTask']

def extract_activities_from_bpmn(file):
    tree = ET.parse(file)
    root = tree.getroot()
    ns = {'bpmn': root.tag.split('}')[0].strip('{')}
    
    activities = []
    task_names = set()
    task_found = False  # Track if any tasks are extracted

    # Recursive function to extract tasks
    def extract_tasks_from_element(element, depth=0, stack=None, participant_name=""):
        nonlocal task_found
        
        if stack is None:
            stack = set()
        if depth > MAX_DEPTH:
            print(f"Max recursion depth reached at {depth}. Exiting subprocess.")
            return

        # Extract tasks at the current level
        for tag in task_tags:
            for task in element.findall(f'bpmn:{tag}', ns):
                task_name = task.attrib.get('name', 'Unnamed Task')
                participant_prefix = participant_name.replace(" ", "_") if participant_name else "Global"

                # Append pool/participant name to distinguish duplicates
                unique_task_name = f"{task_name}"

                # Detect duplicates only if they still clash
                if unique_task_name in task_names:
                    print(f"⚠️ Duplicate task detected: {unique_task_name}")
                else:
                    task_names.add(unique_task_name)

                activities.append({
                    'name': unique_task_name,
                    'resource': 'Unknown',
                    'min_time': 1,
                    'max_time': 5,
                    'concurrent': False
                })
                task_found = True  # Mark that tasks were found
                print(f"Extracted Task: {unique_task_name} (Depth: {depth})")

        # Traverse subprocesses (if not circular)
        for subprocess in element.findall('bpmn:subProcess', ns):
            subprocess_id = subprocess.attrib.get('id')
            if subprocess_id in stack:
                print(f"Skipping circular subprocess: {subprocess.attrib.get('name', 'Unnamed Subprocess')}")
                continue

            print(f"Entering subprocess: {subprocess.attrib.get('name', 'Unnamed Subprocess')} (Depth: {depth + 1})")
            stack.add(subprocess_id)
            extract_tasks_from_element(subprocess, depth + 1, stack, participant_name)
            stack.remove(subprocess_id)

    # Extract from processes referenced by participants (pools)
    def extract_from_process(process, participant_name=""):
        process_id = process.attrib.get('id')

        if process_id in visited_processes:
            print(f"Skipping already visited process: {participant_name or process_id}")
            return

        extract_tasks_from_element(process, participant_name=participant_name)
        visited_processes.add(process_id)
        print(f"Marked process as visited: {participant_name or process_id}")

    # Step 1: Extract tasks from participants (pools)
    for participant in root.findall('.//bpmn:participant', ns):
        process_ref = participant.attrib.get('processRef')
        participant_name = participant.attrib.get('name', 'Unnamed Pool')
        for process in root.findall(f'.//bpmn:process[@id="{process_ref}"]', ns):
            extract_from_process(process, participant_name)

    # Step 2: Extract tasks from standalone top-level processes
    for process in root.findall('.//bpmn:process', ns):
        extract_from_process(process)

    # Return extracted activities
    if not task_found:
        print("No tasks found during extraction.")
    else:
        print(f"Extracted {len(activities)} tasks from BPMN (including pools and subprocesses)")

    return activities

# Graphviz Process Flow Visualization
def visualize_variant_flow(variant_name, activities):
    flow = graphviz.Digraph(comment=f'Process Flow for {variant_name}')
    flow.attr(rankdir='LR', size='10')

    # Start Node
    flow.node('start', 'Start', shape='ellipse')

    # Create Nodes for Activities
    for act in activities:
        flow.node(act, act, shape='box')

    # End Node
    flow.node('end', 'End', shape='ellipse')

    # Connect Nodes Sequentially
    flow.edge('start', activities[0])  # Connect start to first activity
    for i in range(len(activities) - 1):
        flow.edge(activities[i], activities[i + 1])  # Sequential edges
    flow.edge(activities[-1], 'end')  # Connect last activity to end

    return flow
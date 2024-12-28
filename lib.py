import graphviz

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
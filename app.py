import streamlit as st
import pandas as pd
from io import BytesIO
import random
from datetime import datetime, timedelta
import lib
import xml.etree.ElementTree as ET

# App Title
st.title("Business Process Event Log Generator")

# Step 1: Basic Process Details
st.header("Step 1: Process Setup")
process_name = st.text_input("Process Name (Optional)")
num_cases = st.number_input("Number of Cases to Simulate", min_value=1, value=10)
file_name = st.text_input("Event Log File Name", value="event_log.xlsx")

st.write("---")  # Separator

# Step 2: Define Activities
st.header("Step 2: Define Process Activities")

if 'activities' not in st.session_state:
    st.session_state.activities = []

# BPMN File Upload
uploaded_file = st.file_uploader("Upload BPMN Diagram (.bpmn)", type=['bpmn'])

# Extract BPMN Activities and Populate
if uploaded_file:
    st.success("BPMN Diagram Uploaded Successfully!")
    
    # Extract activities from the uploaded BPMN file
    extracted_activities = lib.extract_activities_from_bpmn(uploaded_file)
    
    # Append extracted tasks to session state (only if not already added)
    if extracted_activities:
        existing_tasks = [a['name'] for a in st.session_state.activities]
        for act in extracted_activities:
            if act['name'] not in existing_tasks:
                st.session_state.activities.append(act)
        st.rerun()
    else:
        # Fix: Check session state for extracted tasks instead of assuming no tasks
        if st.session_state.activities:
            st.success("Tasks successfully extracted!")
        else:
            st.warning("No tasks found in the uploaded BPMN file.")

def add_activity():
    st.session_state.activities.append({
        "name": "", 
        "resource": "", 
        "min_time": 1,
        "max_time": 5,
        "concurrent": False
    })

st.button("Add Activity", on_click=add_activity)
    
# Display Activity Inputs in Expanders
for i, activity in enumerate(st.session_state.activities):
    with st.expander(f"Activity {i + 1}: {activity['name'] or 'Unnamed'}"):
        # Activity Name and Resource
        activity['name'] = st.text_input(
            "Activity Name", 
            value=activity['name'], 
            key=f"name_{i}"
        )
        activity['resource'] = st.text_input(
            "Resource", 
            value=activity['resource'], 
            key=f"resource_{i}"
        )
        
        #Directly Update Session State for Min and Max Time Inputs
        if f"min_time_{i}" not in st.session_state:
            st.session_state[f"min_time_{i}"] = activity['min_time']
        
        if f"max_time_{i}" not in st.session_state:
            st.session_state[f"max_time_{i}"] = activity['max_time']

        # Time Input for Min and Max Duration (Real-time Update)
        col1, col2 = st.columns(2)
        activity['min_time'] = col1.number_input(
            "Min Time (minutes)", 
            min_value=1, 
            value=st.session_state[f"min_time_{i}"], 
            key=f"min_time_{i}"
        )
        activity['max_time'] = col2.number_input(
            "Max Time (minutes)", 
            min_value=1, 
            value=st.session_state[f"max_time_{i}"], 
            key=f"max_time_{i}"
        )

        # Real-time Session State Sync
        st.session_state.activities[i]['min_time'] = st.session_state[f"min_time_{i}"]
        st.session_state.activities[i]['max_time'] = st.session_state[f"max_time_{i}"]
        
        # Concurrency Checkbox
        activity['concurrent'] = st.checkbox(
            "Allow Parallel Execution", 
            value=activity['concurrent'], 
            key=f"concurrent_{i}"
        )
        
        # Delete Activity Button
        if st.button(f"Delete Activity {i + 1}", key=f"delete_{i}"):
            del st.session_state.activities[i]
            st.experimental_rerun()  # Rerun to reflect deletion immediately
# --- Validation for Unique Activity Names ---
activity_names = [a['name'] for a in st.session_state.activities]

if len(activity_names) != len(set(activity_names)):
    st.error("Activity names must be unique.")

# Step 3: Define Process Variants with BPMN Diagram
st.header("Step 3: Define Process Flow Variants")

if 'variants' not in st.session_state:
    st.session_state.variants = []

def add_variant():
    default_times = {
        a['name']: {'min': a['min_time'], 'max': a['max_time']} 
        for a in st.session_state.activities
    }
    st.session_state.variants.append({
        "name": "",
        "activities": [],
        "frequency": 0,
        "times": default_times  # <-- This ensures "times" exists for new variants
    })

st.button("Add Variant", on_click=add_variant)

# Variant Management and Display
total_frequency = 0

for v_index, variant in enumerate(st.session_state.variants):
    with st.expander(f"Variant {v_index + 1}: {variant['name'] or 'Unnamed'}"):
        variant['name'] = st.text_input(
            f"Variant Name {v_index + 1}",
            key=f"variant_name_{v_index}"
        )

        # Frequency Input
        variant['frequency'] = st.number_input(
            f"Frequency (%) for Variant {v_index + 1}",
            min_value=0,
            max_value=100,
            value=variant['frequency'],
            key=f"freq_{v_index}"
        )
        total_frequency += variant['frequency']

        # Activity Selection (Fix for Missing Defaults)
        selected_activities = st.multiselect(
            f"Select Activities for Variant {v_index + 1}",
            options=[a['name'] for a in st.session_state.activities],  # Get available activity names
            default=[
                act for act in variant['activities'] if act in [a['name'] for a in st.session_state.activities]
            ],  # Filter out missing activities
            key=f"select_activities_{v_index}"
        )
        variant['activities'] = selected_activities

        # Adjust Activity Times (Per Variant)
        if selected_activities:
            adjust_times_toggle = st.toggle(
                f"Adjust Time Ranges for Variant {v_index + 1}",
                key=f"toggle_{v_index}"
            )
            
            if adjust_times_toggle:
                for act in selected_activities:
                    activity_defaults = next(
                        (a for a in st.session_state.activities if a['name'] == act), {}
                    )
                    min_time_key = f"min_time_variant_{v_index}_{act}"
                    max_time_key = f"max_time_variant_{v_index}_{act}"

                    col1, col2 = st.columns(2)
                    act_min = col1.number_input(
                        f"{act} - Min Time (minutes)",
                        min_value=1,
                        value=activity_defaults.get('min_time', 1),
                        key=min_time_key
                    )
                    act_max = col2.number_input(
                        f"{act} - Max Time (minutes)",
                        min_value=1,
                        value=activity_defaults.get('max_time', 5),
                        key=max_time_key
                    )
                    if 'times' not in variant:
                        variant['times'] = {}
                    variant['times'][act] = {'min': act_min, 'max': act_max}


        # Visualize the Flow of Activities for this Variant
        if selected_activities:
            st.subheader("Process Flow Visualization")
            st.graphviz_chart(visualize_variant_flow(variant['name'], selected_activities))

        # Delete Variant Button
        if st.button(f"Delete Variant {v_index + 1}", key=f"delete_variant_{v_index}"):
            del st.session_state.variants[v_index]
            st.experimental_rerun()

# Frequency Validation Feedback
st.write(f"**Total Frequency: {total_frequency}%**")
if total_frequency != 100:
    st.warning("The total frequency should sum to 100% to ensure balanced case distribution.")

# Step 4: Generate Event Log
st.header("Step 4: Generate Event Log")

# Date Inputs for Case Start Time
start_date = st.date_input("Select Start Date", value=datetime.today())
end_date = st.date_input("Select End Date", value=datetime.today() + timedelta(days=7))

# Case Start Gap Inputs
min_case_gap = st.number_input("Minimum Gap Between Cases (minutes)", min_value=0, value=10)
max_case_gap = st.number_input("Maximum Gap Between Cases (minutes)", min_value=30, value=60)

if st.button("Generate Event Log"):
    if not st.session_state.activities or not st.session_state.variants:
        st.error("Please add at least one activity and one variant before generating the event log.")
    elif start_date > end_date:
        st.error("End date must be after start date.")
    else:
        event_log = []
        total_cases = num_cases
        variant_pool = []

        for variant in st.session_state.variants:
            variant_pool.extend([variant] * int(variant['frequency']))

        last_case_end_time = None

        for case_id in range(1, total_cases + 1):
            variant = random.choice(variant_pool)

            # Case start time with optional random gap
            if last_case_end_time:
                gap = random.randint(min_case_gap, max_case_gap)
                case_start_time = last_case_end_time + timedelta(minutes=gap)
            else:
                case_start_time = datetime.combine(
                    random.choice(pd.date_range(start_date, end_date)),
                    datetime.min.time()
                ) + timedelta(hours=random.randint(8, 16))

            start_time = case_start_time
            first_activity_time = start_time
            last_activity_time = start_time
            
            for act in variant['activities']:
                if act not in variant['times']:
                    default_act = next((a for a in st.session_state.activities if a['name'] == act), {})
                    variant['times'][act] = {
                        'min': default_act.get('min_time', 1),
                        'max': default_act.get('max_time', 5)
                    }

                act_time_range = variant['times'].get(act, {})
                min_time = act_time_range.get('min', 1)
                max_time = act_time_range.get('max', 5)

                # Check if activity allows concurrency
                concurrent = any(
                    a['name'] == act and a['concurrent'] 
                    for a in st.session_state.activities
                )

                if concurrent:
                    duration = 0  # Same timestamp for concurrent activities
                else:
                    duration = random.randint(min_time, max_time)
                
                event_log.append({
                    'Case ID': f"Case_{case_id}",
                    'Activity': act,
                    'Resource': [a['resource'] for a in st.session_state.activities if a['name'] == act][0],
                    'Timestamp': start_time.strftime("%Y-%m-%d %H:%M:%S"),
                    'Variant': variant['name']
                })

                # Increment start time for non-concurrent activities
                if not concurrent:
                    last_activity_time = start_time
                    start_time += timedelta(minutes=duration)
            
            # Calculate Cycle Time
            last_activity_duration = random.randint(min_time, max_time)
            last_activity_time += timedelta(minutes=last_activity_duration)

            cycle_time = (last_activity_time - first_activity_time).total_seconds() / 60
            event_log[-len(variant['activities'])]['Cycle Time'] = round(cycle_time, 2)

            # Store end time for next case gap
            last_case_end_time = last_activity_time
        
        # Convert to DataFrame
        df = pd.DataFrame(event_log)
        df['Cycle Time'] = df['Cycle Time'].fillna('')

        # Export to Excel
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Event Log')

        st.download_button(
            label="Download Event Log",
            data=output.getvalue(),
            file_name=file_name,
            mime="application/vnd.ms-excel"
        )

        st.success("Event log successfully generated with concurrency and case gaps!")

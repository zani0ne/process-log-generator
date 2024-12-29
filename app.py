import streamlit as st
import pandas as pd
from io import BytesIO
import random
from datetime import datetime, timedelta
import lib
from lib import visualize_variant_flow
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

DEFAULT_ACTIVITIES = [
    {"name": "Order Received", "resource": "Sales", "min_time": 120, "max_time": 300, "concurrent": False, "pool": "Customer", "lane": "Order Management"},
    {"name": "Verify Stock", "resource": "Inventory", "min_time": 60, "max_time": 180, "concurrent": False, "pool": "Warehouse", "lane": "Stock Verification"},
    {"name": "Process Payment", "resource": "Finance", "min_time": 120, "max_time": 360, "concurrent": False, "pool": "Finance", "lane": "Payments"},
    {"name": "Ship Order", "resource": "Logistics", "min_time": 180, "max_time": 420, "concurrent": False, "pool": "Warehouse", "lane": "Shipping"},
    {"name": "Send Confirmation", "resource": "Customer Service", "min_time": 60, "max_time": 120, "concurrent": False, "pool": "Customer", "lane": "Communication"}
]

# Initialize Session State with Hardcoded Activities
if 'activities' not in st.session_state:
    st.session_state.activities = DEFAULT_ACTIVITIES.copy()

def add_activity():
    st.session_state.activities.append({
        "name": "", 
        "resource": "", 
        "min_time": 1,
        "max_time": 5,
        "concurrent": False,
        "pool": "",
        "lane": ""
    })

st.button("Add Activity", on_click=add_activity)
    
# Display Activity Inputs in Expanders
for i, activity in enumerate(st.session_state.activities):
    with st.expander(f"Activity {i + 1}: {activity['name'] or 'Unnamed'}"):
        # Activity Name and Resource
        updated_name = st.text_input(
            "Activity Name",
            value=activity['name'],
            key=f"name_{i}"
        )

        # Sync name change across all variants
        if updated_name != activity['name']:
            old_name = activity['name']
            st.session_state.activities[i]['name'] = updated_name

            # Update all variants referencing this activity
            for variant in st.session_state.variants:
                variant['activities'] = [
                    updated_name if act == old_name else act for act in variant['activities']
                ]
            
            st.rerun()

        activity['resource'] = st.text_input(
            "Resource", 
            value=activity['resource'], 
            key=f"resource_{i}"
        )

        # Pool and Lane Inputs
        col3, col4 = st.columns(2)
        activity['pool'] = col3.text_input(
            "Pool", 
            value=activity['pool'], 
            key=f"pool_{i}"
        )
        activity['lane'] = col4.text_input(
            "Lane", 
            value=activity['lane'], 
            key=f"lane_{i}"
        )
        
        #Directly Update Session State for Min and Max Time Inputs
        if f"min_time_{i}" not in st.session_state:
            st.session_state[f"min_time_{i}"] = activity['min_time']
        
        if f"max_time_{i}" not in st.session_state:
            st.session_state[f"max_time_{i}"] = activity['max_time']

        # Time Input for Min and Max Duration (Real-time Update)
        col1, col2 = st.columns(2)
        activity['min_time'] = col1.number_input(
            "Min Time (seconds)", 
            min_value=1, 
            value=st.session_state[f"min_time_{i}"], 
            key=f"min_time_{i}"
        )
        activity['max_time'] = col2.number_input(
            "Max Time (seconds)", 
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

DEFAULT_VARIANTS = [
    {
        "name": "Standard Order Flow",
        "activities": ["Order Received", "Verify Stock", "Process Payment", "Ship Order", "Send Confirmation"],
        "frequency": 60,
        "times": {
            "Order Received": {"min": 120, "max": 300},
            "Verify Stock": {"min": 60, "max": 180},
            "Process Payment": {"min": 120, "max": 360},
            "Ship Order": {"min": 180, "max": 420},
            "Send Confirmation": {"min": 60, "max": 120}
        }
    },
    {
        "name": "Express Order Flow",
        "activities": ["Order Received", "Process Payment", "Send Confirmation"],
        "frequency": 30,
        "times": {
            "Order Received": {"min": 60, "max": 180},
            "Process Payment": {"min": 120, "max": 240},
            "Send Confirmation": {"min": 60, "max": 60}
        }
    },
    {
        "name": "Warehouse Restock",
        "activities": ["Verify Stock", "Ship Order"],
        "frequency": 10,
        "times": {
            "Verify Stock": {"min": 120, "max": 240},
            "Ship Order": {"min": 300, "max": 480}
        }
    }
]

# Initialize Session State with Hardcoded Variants
if 'variants' not in st.session_state:
    st.session_state.variants = DEFAULT_VARIANTS.copy()

def add_variant():
    default_times = {
        a['name']: {'min': a['min_time'], 'max': a['max_time']} 
        for a in st.session_state.activities
    }
    st.session_state.variants.append({
        "name": "",
        "activities": [],
        "frequency": 0,
        "times": default_times
    })

st.button("Add Variant", on_click=add_variant)

# Variant Management and Display
total_frequency = 0

for v_index, variant in enumerate(st.session_state.variants):
    with st.expander(f"Variant {v_index + 1}: {variant['name'] or 'Unnamed'}"):
        updated_name = st.text_input(
            f"Variant Name {v_index + 1}",
            value=variant['name'],
            key=f"variant_name_{v_index}"
        )
        if updated_name != variant['name']:
            st.session_state.variants[v_index]['name'] = updated_name
            st.rerun()

        # --- Update Frequency ---
        updated_frequency = st.number_input(
            f"Frequency (%) for Variant {v_index + 1}",
            min_value=0,
            max_value=100,
            value=variant['frequency'],
            key=f"freq_{v_index}"
        )
        if updated_frequency != variant['frequency']:
            st.session_state.variants[v_index]['frequency'] = updated_frequency

        # --- Update Selected Activities ---
        selected_activities = st.multiselect(
            f"Select Activities for Variant {v_index + 1}",
            options=[a['name'] for a in st.session_state.activities],
            default=[
                act for act in variant['activities'] if act in [a['name'] for a in st.session_state.activities]
            ],
            key=f"select_activities_{v_index}"
        )
        if selected_activities != variant['activities']:
            st.session_state.variants[v_index]['activities'] = selected_activities

        # --- Adjust Time Ranges (Optional Per Variant) ---
        if selected_activities:
            adjust_times_toggle = st.toggle(
                f"Adjust Time Ranges for Variant {v_index + 1}",
                key=f"toggle_{v_index}"
            )
            
            if adjust_times_toggle:
                for act in selected_activities:
                    col1, col2 = st.columns(2)
                    act_min = col1.number_input(
                        f"{act} - Min Time (seoconds)",
                        min_value=1,
                        value=variant['times'].get(act, {}).get('min', 1),
                        key=f"min_time_variant_{v_index}_{act}"
                    )
                    act_max = col2.number_input(
                        f"{act} - Max Time (seconds)",
                        min_value=1,
                        value=variant['times'].get(act, {}).get('max', 5),
                        key=f"max_time_variant_{v_index}_{act}"
                    )

                    # Sync time adjustments directly to session state
                    if act_min != variant['times'][act]['min'] or act_max != variant['times'][act]['max']:
                        st.session_state.variants[v_index]['times'][act] = {'min': act_min, 'max': act_max}

        # --- Visualize the Flow of Activities for this Variant ---
        if selected_activities:
            st.subheader("Process Flow Visualization")
            st.graphviz_chart(visualize_variant_flow(variant['name'], selected_activities))

        # --- Delete Variant Button ---
        if st.button(f"Delete Variant {v_index + 1}", key=f"delete_variant_{v_index}"):
            del st.session_state.variants[v_index]
            st.rerun()

# --- Recalculate Total Frequency AFTER Inputs ---
for variant in st.session_state.variants:
    total_frequency += variant['frequency']

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
min_case_gap = st.number_input("Minimum Gap Between Cases (seconds)", min_value=0, value=600)
max_case_gap = st.number_input("Maximum Gap Between Cases (seconds)", min_value=900, value=1800)

if st.button("Generate Event Log"):
    if not st.session_state.activities or not st.session_state.variants:
        st.error("Please add at least one activity and one variant before generating the event log.")
    elif start_date > end_date:
        st.error("End date must be after start date.")
    else:
        event_log = []
        total_cases = num_cases
        variant_pool = []
        log_id = 1

        case_prefix = "ORD-"
        event_prefix = "LOG-"

        for variant in st.session_state.variants:
            variant_pool.extend([variant] * int(variant['frequency']))

        last_case_end_time = None

        for case_id in range(1, total_cases + 1):
            variant = random.choice(variant_pool)

            # Case start time with optional random gap
            if last_case_end_time:
                gap = random.randint(min_case_gap, max_case_gap)
                case_start_time = last_case_end_time + timedelta(seconds=gap)
            else:
                case_start_time = datetime.combine(
                    random.choice(pd.date_range(start_date, end_date)),
                    datetime.min.time()
                ) + timedelta(hours=random.randint(8, 16)) # 8 AM - 4 PM

            start_time = case_start_time
            first_activity_time = start_time
            last_activity_time = start_time
            
            for act in variant['activities']:
                activity_info = next((a for a in st.session_state.activities if a['name'] == act), {})

                if act not in variant['times']:
                    variant['times'][act] = {
                        'min': activity_info.get('min_time', 60),
                        'max': activity_info.get('max_time', 300)
                    }

                act_time_range = variant['times'].get(act, {})
                min_time = act_time_range.get('min', 60)
                max_time = act_time_range.get('max', 300)

                # Check if activity allows concurrency
                concurrent = activity_info.get('concurrent', False)

                duration = 0 if concurrent else random.randint(min_time, max_time)
                
                # --- Calculate Duration (with Jitter) ---
                base_duration = random.randint(min_time, max_time)
                jitter = random.randint(-30, 30)
                duration = max(1, base_duration + jitter) 

                event_log.append({
                    'ID': f"{event_prefix}{log_id}",
                    'Case ID': f"{case_prefix}{case_id}",
                    'Activity': act,
                    'Resource': activity_info.get('resource', 'Unknown'),
                    'Timestamp': start_time.strftime("%Y-%m-%d %H:%M:%S"),
                    'Pool': activity_info.get('pool', 'N/A'),
                    'Lane': activity_info.get('lane', 'N/A')
                })
                log_id += 1

                # Increment start time for non-concurrent activities
                if not concurrent:
                    last_activity_time = start_time
                    start_time += timedelta(seconds=duration)
            
            # Store end time for next case gap
            last_case_end_time = last_activity_time
        
        # Convert to DataFrame
        df = pd.DataFrame(event_log)

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

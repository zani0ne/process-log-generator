import streamlit as st
import pandas as pd
from io import BytesIO
import random
from datetime import datetime, timedelta
import lib
from lib import visualize_variant_flow
import xml.etree.ElementTree as ET
import re

ROUTE_DISTRIBUTION = {
    1: 4,  # Failed stock check
    2: 5,  # Fraud cancel
    3: 8,  # Payment loop fails once
    4: 8,  # Successful fraud check, Paid
    5: 6,  # Successful fraud check, not paid
    6: 8,  # Credit check prepayment, paid
    7: 6,  # Credit check prepayment, not paid
    8: 9, # Any payment successful
    9: 5,
    10: 1,
    11: 3,
    12: 2,
    13: 2,
    14: 3,  # Any payment not successful
}
TOTAL_CASES = sum(ROUTE_DISTRIBUTION.values())
print(TOTAL_CASES)

# App Title
st.title("Business Process Event Log Generator")

# Step 1: Basic Process Details
st.header("Step 1: Process Setup")
process_name = st.text_input("Process Name (Optional)")
num_cases = TOTAL_CASES
st.write(f"Total Cases to Simulate: **{TOTAL_CASES}** (Distributed across routes)")
file_name = st.text_input("Event Log File Name", value="event_log.xlsx")

st.write("---")  # Separator

# Step 2: Define Activities
st.header("Step 2: Define Process Activities")

DEFAULT_ACTIVITIES = [
    {"name": "Order request notification", "min_time": 1, "max_time": 3, "concurrent": False, "pool": "Tchibo", "lane": "Sales"},
    {"name": "Create order request", "min_time": 1, "max_time": 5, "concurrent": False, "pool": "Tchibo", "lane": "Sales"},
    {"name": "Check stock levels", "min_time": 1, "max_time": 3, "concurrent": False, "pool": "Tchibo", "lane": "Sales"},
    {"name": "Update inventory levels", "min_time": 5, "max_time": 10, "concurrent": False, "pool": "Tchibo", "lane": "Sales"},
    {"name": "Check total price of order", "min_time": 1, "max_time": 2, "concurrent": False, "pool": "Tchibo", "lane": "Risk Management"},
    {"name": "Check the order for fraud", "min_time": 2, "max_time": 12, "concurrent": False, "pool": "Tchibo", "lane": "Risk Management"},
    {"name": "Notify customer that order is cancelled due to fraud", "min_time": 1, "max_time": 5, "concurrent": False, "pool": "Tchibo", "lane": "Risk Management"},
    {"name": "Set order to pre-paid condition", "min_time": 1, "max_time": 3, "concurrent": False, "pool": "Tchibo", "lane": "Risk Management"},
    {"name": "Provide payment instructions to customer", "min_time": 3, "max_time": 15, "concurrent": False, "pool": "Tchibo", "lane": "Risk Management"},
    {"name": "Mark the order as paid", "min_time": 5, "max_time": 900, "concurrent": False, "pool": "Tchibo", "lane": "Risk Management"},
    {"name": "Label order as approved", "min_time": 2, "max_time": 10, "concurrent": False, "pool": "Tchibo", "lane": "Sales"},
    {"name": "Create order confirmation and send it to customer", "min_time": 10, "max_time": 30, "concurrent": False, "pool": "Tchibo", "lane": "Sales"},
    {"name": "Create shipment contract for the right distributor", "min_time": 5, "max_time": 30, "concurrent": False, "pool": "Tchibo", "lane": "Sales"},
    {"name": "Create collective shipment order and send to TM", "min_time": 1800, "max_time": 1800, "concurrent": False, "pool": "Tchibo", "lane": "Sales"},
    {"name": "Check Order Legitimacy", "min_time": 2, "max_time": 10, "concurrent": False, "pool": "TM", "lane": "TM"},
    {"name": "Inform systems about failed legitimacy check", "min_time": 1, "max_time": 10, "concurrent": False, "pool": "TM", "lane": "TM"},
    {"name": "Send information to distributor", "min_time": 10800, "max_time": 86400, "concurrent": False, "pool": "TM", "lane": "TM"},
    {"name": "Receive and process shipping confirmation from distributor", "min_time": 60, "max_time": 180, "concurrent": False, "pool": "TM", "lane": "TM"},
    {"name": "Transmit shipping confirmation to Customer", "min_time": 10, "max_time": 60, "concurrent": False, "pool": "Tchibo", "lane": "Sales"},
    {"name": "Inform customer about order cancellation", "min_time": 1, "max_time": 3, "concurrent": False, "pool": "Tchibo", "lane": "Sales"},
    {"name": "Create customer order", "min_time": 25, "max_time": 300, "concurrent": False, "pool": "Tchibo", "lane": "Sales"},
    {"name": "Perform customer credit check", "min_time": 1, "max_time": 3, "concurrent": False, "pool": "Tchibo", "lane": "Risk Management"},
    {"name": "Cancel order and notify customer", "min_time": 5, "max_time": 15, "concurrent": False, "pool": "Tchibo", "lane": "Risk Management"},
    {"name": "Enable customer to choose any payment method", "min_time": 3, "max_time": 10, "concurrent": False, "pool": "Tchibo", "lane": "Risk Management"}
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
        "lane": "",
        "anomaly_possible": False
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
        "name": "Route 1: Failed Stock Availability Check",
        "activities": [
            "Order request notification",
            "Create order request",
            "Check stock levels",
            "Inform customer about order cancellation"
        ],
        "frequency": 0,
        "times": {
        }
    },
    {
        "name": "Route 2: Fraud Cancel",
        "activities": [
            "Order request notification",
            "Create order request",
            "Check stock levels",
            "Update inventory levels",
            "Create customer order",
            "Check total price of order",
            "Check the order for fraud",
            "Notify customer that order is cancelled due to fraud"
        ],
        "frequency": 0,
        "times": {
        }
    },
    {
        "name": "Route 3: Any Payment Successful (but loop failed once)",
        "activities": [
            "Order request notification",
            "Create order request",
            "Check stock levels",
            "Update inventory levels",
            "Create customer order",
            "Check total price of order",
            "Perfom customer credit check",
            "Set order to pre-paid condition",
            "Provide payment instructions to customer",
            "Mark the order as paid",
            "Label order as approved",
            "Create order confirmation and send it to customer",
            "Create shipment contract for the right distributor",
            "Create collective shipment order and send to TM",
            "Check Order Legitimacy",
            "Inform systems about failed legitimacy check",
            "Create shipment contract for the right distributor",
            "Create collective shipment order and send to TM",
            "Check Order Legitimacy",
            "Send information to distributor",
            "Receive and process shipping confirmation from distributor",
            "Transmit shipping confirmation to Customer"
        ],
        "frequency": 0,
        "times": {
        }
    },
    {
        "name": "Route 4: Successful Fraud Check, Paid",
        "activities": [
            "Order request notification",
            "Create order request",
            "Check stock levels",
            "Update inventory levels",
            "Create customer order",
            "Check total price of order",
            "Check the order for fraud",
            "Set order to pre-paid condition",
            "Provide payment instructions to customer",
            "Mark the order as paid",
            "Label order as approved",
            "Create order confirmation and send it to customer",
            "Create shipment contract for the right distributor",
            "Create collective shipment order and send to TM",
            "Check Order Legitimacy",
            "Send information to distributor",
            "Receive and process shipping confirmation from distributor",
            "Transmit shipping confirmation to Customer"
        ],
        "frequency": 0,
        "times": {
        }
    },
    {
        "name": "Route 5: Successful Fraud Check, Not Paid (Canceled)",
        "activities": [
            "Order request notification",
            "Create order request",
            "Check stock levels",
            "Update inventory levels",
            "Create customer order",
            "Check total price of order",
            "Check the order for fraud",
            "Set order to pre-paid condition",
            "Provide payment instructions to customer",
            "Cancel order and notify customer"
        ],
        "frequency": 0,
        "times": {
            "Provide payment instructions to customer": {"min": 901, "max": 901}
        }
    },
    {
        "name": "Route 6: Credit Check Prepayment, Successfully Paid",
        "activities": [
            "Order request notification",
            "Create order request",
            "Check stock levels",
            "Update inventory levels",
            "Create customer order",
            "Check total price of order",
            "Perfom customer credit check",
            "Set order to pre-paid condition",
            "Provide payment instructions to customer",
            "Mark the order as paid",
            "Label order as approved",
            "Create order confirmation and send it to customer",
            "Create shipment contract for the right distributor",
            "Create collective shipment order and send to TM",
            "Check Order Legitimacy",
            "Send information to distributor",
            "Receive and process shipping confirmation from distributor",
            "Transmit shipping confirmation to Customer"
        ],
        "frequency": 0,
        "times": {
        }
    },
    {
        "name": "Route 7: Credit Check Prepayment, Canceled/Not Paid",
        "activities": [
            "Order request notification",
            "Create order request",
            "Check stock levels",
            "Update inventory levels",
            "Create customer order",
            "Check total price of order",
            "Perform customer credit check",
            "Set order to pre-paid condition",
            "Provide payment instructions to customer",
            "Cancel order and notify customer"
        ],
        "frequency": 0,
        "times": {
            "Provide payment instructions to customer": {"min": 901, "max": 901}
        }
    },
    {
        "name": "Route 8: Any Payment Successful (Straightforward)",
        "activities": [
            "Order request notification",
            "Create order request",
            "Check stock levels",
            "Update inventory levels",
            "Create customer order",
            "Check total price of order",
            "Perfom customer credit check",
            "Enable customer to choose any payment method",
            "Provide payment instructions to customer",
            "Mark the order as paid",
            "Label order as approved",
            "Create order confirmation and send it to customer",
            "Create shipment contract for the right distributor",
            "Create collective shipment order and send to TM",
            "Check Order Legitimacy",
            "Send information to distributor",
            "Receive and process shipping confirmation from distributor",
            "Transmit shipping confirmation to Customer"
        ],
        "frequency": 0,
        "times": {
        }
    },
    {
        "name": "Route 9: Any Payment Not Successful",
        "activities": [
            "Order request notification",
            "Create order request",
            "Check stock levels",
            "Update inventory levels",
            "Create customer order",
            "Check total price of order",
            "Perform customer credit check",
            "Enable customer to choose any payment method",
            "Provide payment instructions to customer",
            "Cancel order and notify customer"
        ],
        "frequency": 0,
        "times": {
            "Provide payment instructions to customer": {"min": 901, "max": 901}
        }
    },
    {
        #Update Inventory levels doppelt vorhanden
        "name": "Route 10: Update Inventory Levels Duplicated",
        "activities": [
            "Order request notification",
            "Create order request",
            "Check stock levels",
            "Create customer order",
            "Update inventory levels",
            "Update inventory levels",
            "Check total price of order",
            "Check the order for fraud",
            "Notify customer that order is cancelled due to fraud"
        ],
        "frequency": 0,
        "times": {}
    },
    {
        #Mark Order as Paid was skipped
        "name": "Route 11: Mark Order as Paid Skipped",
        "activities": [
            "Order request notification",
            "Create order request",
            "Check stock levels",
            "Update inventory levels",
            "Create customer order",
            "Check total price of order",
            "Perfom customer credit check",
            "Set order to pre-paid condition",
            "Provide payment instructions to customer",
            "Label order as approved",
            "Create order confirmation and send it to customer",
            "Create shipment contract for the right distributor",
            "Create collective shipment order and send to TM",
            "Check Order Legitimacy",
            "Inform systems about failed legitimacy check",
            "Create shipment contract for the right distributor",
            "Create collective shipment order and send to TM",
            "Check Order Legitimacy",
            "Send information to distributor",
            "Receive and process shipping confirmation from distributor",
            "Transmit shipping confirmation to Customer"
        ],
        "frequency": 0,
        "times": {}
    },
    {
        #Aktivitäten vertrauscht (Mark the order as paid kommt nach Label order as approved)
        "name": "Route 12: Activity Order Confusion",
        "activities": [
            "Order request notification",
            "Create order request",
            "Check stock levels",
            "Update inventory levels",
            "Create customer order",
            "Check total price of order",
            "Perfom customer credit check",
            "Enable customer to choose any payment method",
            "Provide payment instructions to customer",
            "Label order as approved",
            "Mark the order as paid",
            "Create order confirmation and send it to customer",
            "Create shipment contract for the right distributor",
            "Create collective shipment order and send to TM",
            "Check Order Legitimacy",
            "Send information to distributor",
	    "Receive and process shipping confirmation from distributor"
        ],
        "frequency": 0,
        "times": {
		    #"Mark the order as paid": {"min": 2, "max": 7},
            #"Label order as approved": {"min": -4 , "max": -1}
        }
    },
    {
        #Nach Order paid ist Ende
        "name": "Route 13: After Order Paid (End)",
        "activities": [
            "Order request notification",
            "Create order request",
            "Check stock levels",
            "Update inventory levels",
            "Create customer order",
            "Check total price of order",
            "Check the order for fraud",
            "Set order to pre-paid condition",
            "Provide payment instructions to customer",
            "Mark the order as paid",
        ],
        "frequency": 0,
        "times": {
        }
    },
    {
        #Obwohl die Zahlung eingetroffen ist, wurde die Order gecancelt, da sie 1 Sekunde nach 15 Minuten eintraf
        "name": "Route 14: Cancel order although paid",
        "activities": [
            "Order request notification",
            "Create order request",
            "Check stock levels",
            "Update inventory levels",
            "Create customer order",
            "Check total price of order",
            "Perfom customer credit check",
            "Enable customer to choose any payment method",
            "Provide payment instructions to customer",
            "Cancel order and notify customer",
            "Mark the order as paid",
            "Label order as approved",
            "Create order confirmation and send it to customer",
            "Create shipment contract for the right distributor",
            "Create collective shipment order and send to TM",
            "Check Order Legitimacy",
            "Send information to distributor",
            "Receive and process shipping confirmation from distributor",
            "Transmit shipping confirmation to Customer"
        ],
        "frequency": 0,
        "times": {
            "Provide payment instructions to customer": {"min": 901, "max": 901},
            "Cancel order and notify customer": {"min": 1, "max": 1}
        }
    },
]

# Initialize Session State with Hardcoded Variants
if 'variants' not in st.session_state:
    st.session_state.variants = DEFAULT_VARIANTS.copy()

# Ensure each variant has times for all activities based on DEFAULT_ACTIVITIES
for variant in st.session_state.variants:
    for activity in st.session_state.activities:
        if activity['name'] not in variant['times']:
            # If activity doesn't exist at all, set default times
            variant['times'][activity['name']] = {
                'min': activity['min_time'],
                'max': activity['max_time']
            }
        else:
            # If activity exists but min/max are missing, set individually
            if 'min' not in variant['times'][activity['name']]:
                variant['times'][activity['name']]['min'] = activity['min_time']
            if 'max' not in variant['times'][activity['name']]:
                variant['times'][activity['name']]['max'] = activity['max_time']

# Normalize the frequencies to ensure they sum to 100%
normalized_frequencies = []
total_sum = 0

for i, variant in enumerate(st.session_state.variants):
    route_number = i + 1  # Route numbers 1-9
    raw_frequency = ROUTE_DISTRIBUTION.get(route_number, 0)
    frequency = (raw_frequency / TOTAL_CASES) * 100
    rounded_frequency = round(frequency, 10)  # Limit to avoid floating-point issues
    normalized_frequencies.append(rounded_frequency)
    total_sum += rounded_frequency

# Adjust for rounding error
rounding_error = 100 - total_sum
if rounding_error != 0:
    normalized_frequencies[-1] += rounding_error  # Adjust last variant to balance to 100%

# Assign the corrected frequencies back
for i, variant in enumerate(st.session_state.variants):
    variant['frequency'] = normalized_frequencies[i]

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
    with st.expander(f"{variant['name'] or 'Unnamed'}"):
        updated_name = st.text_input(
            "Variant Name",
            value=variant['name'],
            key=f"variant_name_{v_index}"
        )
        if updated_name != variant['name']:
            st.session_state.variants[v_index]['name'] = updated_name
            st.rerun()

        # Display Frequency as Read-Only (calculated from distribution)
        st.write(f"**Frequency:** {variant['frequency']}%")

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
                        min_value=None,
                        value=variant['times'].get(act, {}).get('min', 1),
                        key=f"min_time_variant_{v_index}_{act}"
                    )
                    act_max = col2.number_input(
                        f"{act} - Max Time (seconds)",
                        min_value=None,
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
        route_case_counter = {route: 1 for route in ROUTE_DISTRIBUTION.keys()}
        total_cases = sum(ROUTE_DISTRIBUTION.values())
        variant_pool = []

        case_prefix = "R"
        last_case_end_time = None

        # Bulk Shipment Queue and Timer
        shipment_queue = []
        next_bulk_shipment_time = None

        # --- Fill Variant Pool Based on Exact Distribution ---
        # --- Fill Variant Pool Based on Exact Distribution ---
        for route, num_cases in ROUTE_DISTRIBUTION.items():
            matching_variants = [
                v for v in st.session_state.variants if f"Route {route}" in v['name']
            ]
            
            # Add up to the required number of cases
            selected_variants = matching_variants[:num_cases]
            variant_pool.extend(selected_variants)
            
            print(f"Route {route}: Adding {len(selected_variants)} variants (Required: {num_cases})")

            if len(matching_variants) > num_cases:
                print(f"Warning: Route {route} has {len(matching_variants)} cases, trimming to {num_cases}.")
                matching_variants = matching_variants[:num_cases]
            
            # Add cases to pool
            for variant in matching_variants:
                variant_pool.extend([variant] * num_cases)
                print(variant['name'], num_cases)

        # --- Generate Cases for Each Variant ---
        for variant in variant_pool:  # Randomly select a variant from the pool
            route_number = int(variant['name'].split(':')[0].split()[-1])
            case_num = route_case_counter[route_number]
            route_case_counter[route_number] += 1

            case_id_formatted = (
                f"{case_prefix}{route_number}_{str(case_num).zfill(2)}"
            )

            # Berechne die Differenz zwischen Start- und Enddatum
            date_diff = (end_date - start_date).days

            # Berechne die Anzahl der Fälle, die generiert werden sollen
            total_cases = sum(ROUTE_DISTRIBUTION.values())

            # Berechne den maximalen Zeitraum, der durch die Gaps benötigt wird
            max_required_gap = (total_cases - 1) * max_case_gap / 86400  # in Tagen (3600 Sekunden * 24 Stunden)

            # Überprüfe, ob der Zeitraum zwischen Start- und Enddatum ausreichend ist
            if date_diff < max_required_gap:
                st.error("Der Zeitraum zwischen Start- und Enddatum ist zu kurz, um die gewünschten 'Case Gaps' zu berücksichtigen. Bitte wähle einen längeren Zeitraum.")
            else:
                # Jetzt ist sichergestellt, dass der Zeitraum ausreichend ist
                # Hier wird weiterhin eine zufällige Startzeit für jeden Fall generiert
                case_start_time = datetime.combine(
                    random.choice(pd.date_range(start_date, end_date).tolist()),  # Umwandlung in Liste und Auswahl eines zufälligen Datums
                    datetime.min.time()
                ) + timedelta(hours=random.randint(6, 22), minutes=random.randint(1, 59))  # Der Fall beginnt zwischen 8 Uhr und 16 Uhr

                start_time = case_start_time
                last_activity_time = start_time
            
            # --- Generate Activities for the Case --- 
            bulk_shipment_schedule = {}
            pending_cases = {}

            # --- Generate Activities for the Case ---
            for act in variant['activities']:
                activity_info = next((a for a in st.session_state.activities if a['name'] == act), {})

                # Default activity timing if not set
                if act not in variant['times']:
                    variant['times'][act] = {
                        'min': activity_info.get('min_time', 60),
                        'max': activity_info.get('max_time', 300)
                    }

                if act == "Create collective shipment order and send to TM":
                    case_hour = start_time.replace(minute=0, second=0)  # Track by hour, not day
                    
                    # Queue shipment per hour and route if not already scheduled
                    if (case_hour, route_number) not in bulk_shipment_schedule:
                        bulk_shipment_schedule[(case_hour, route_number)] = case_hour + timedelta(hours=1)
                        
                        shipment_queue.append({
                            'case_id': case_id_formatted,
                            'route': route_number,
                            'activity': act,
                            'start_time': start_time,
                            'pool': activity_info.get('pool', 'N/A'),
                            'lane': activity_info.get('lane', 'N/A'),
                            'shipment_time': bulk_shipment_schedule[(case_hour, route_number)]
                        })
                    
                    # Store pending post-shipment activities for this case
                    pending_cases[case_id_formatted] = {
                        'remaining_activities': variant['activities'][variant['activities'].index(act) + 1:],
                        'start_time': bulk_shipment_schedule[(case_hour, route_number)]
                    }
                    
                    break  # Stop processing further activities for this case until shipment is handled

                # --- Process Pre-Shipment Activities --- #
                act_time_range = variant['times'].get(act, {})
                min_time = act_time_range.get('min', 60)
                max_time = act_time_range.get('max', 300)

                base_duration = random.randint(min_time, max_time)
                jitter = random.randint(-4, 4)
                duration = max(1, base_duration + jitter)

                end_time = start_time + timedelta(seconds=duration)

                # Log pre-shipment activity
                event_log.append({
                    'Case ID': case_id_formatted,
                    'Activity': act,
                    'Timestamp': start_time.strftime("%Y-%m-%d %H:%M:%S"),
                    'Pool': activity_info.get('pool', 'N/A'),
                    'Lane': activity_info.get('lane', 'N/A'),
                    'Route': f"Route {route_number}"
                })

                # Increment time for sequential activities
                if not activity_info.get('concurrent', False):
                    start_time += timedelta(seconds=duration)

            # --- Process Shipments (Per Hour Per Route) --- 
            processed_shipments = set()

            for shipment in shipment_queue:
                shipment_key = (shipment['shipment_time'], shipment['route'], shipment['case_id'])  # Key by hour, route, and case

                # Log shipment only if not already processed for this case, hour, and route
                if shipment_key not in processed_shipments:
                    # Determine the duration of the shipment activity
                    shipment_duration_range = variant['times'].get(
                        "Create collective shipment order and send to TM", 
                        {'min': 1800, 'max': 1800}  # Default 30 min
                    )
                    shipment_base_duration = random.randint(
                        shipment_duration_range['min'], 
                        shipment_duration_range['max']
                    )
                    jitter = random.randint(-4, 4)
                    shipment_duration = max(1, shipment_base_duration + jitter)
                    
                    event_log.append({
                        'Case ID': shipment['case_id'],
                        'Activity': shipment['activity'],
                        'Timestamp': shipment['shipment_time'].strftime("%Y-%m-%d %H:%M:%S"),
                        'Pool': shipment['pool'],
                        'Lane': shipment['lane'],
                        'Route': f"Route {shipment['route']}",
                        'Anomaly': 'No'
                    })
                    processed_shipments.add(shipment_key)  # Mark as processed for this case

                # Resume post-shipment activities for the specific case
                if shipment['case_id'] in pending_cases:
                    remaining_acts = pending_cases[shipment['case_id']]['remaining_activities']
                    start_after_shipment = shipment['shipment_time']

                    for remaining_act in remaining_acts:
                        activity_info = next((a for a in st.session_state.activities if a['name'] == remaining_act), {})
                        act_time_range = variant['times'].get(remaining_act, {})
                        min_time = act_time_range.get('min', 60)
                        max_time = act_time_range.get('max', 300)

                        base_duration = random.randint(min_time, max_time)
                        jitter = random.randint(-4, 4)
                        duration = max(1, base_duration + jitter)

                        event_log.append({
                            'Case ID': shipment['case_id'],
                            'Activity': remaining_act,
                            'Timestamp': start_after_shipment.strftime("%Y-%m-%d %H:%M:%S"),
                            'Pool': activity_info.get('pool', 'N/A'),
                            'Lane': activity_info.get('lane', 'N/A'),
                            'Route': f"Route {shipment['route']}"
                        })

                        start_after_shipment += timedelta(seconds=duration)

        # --- Sorting Event Log by Timestamp ---
        event_log = sorted(event_log, key=lambda x: datetime.strptime(x['Timestamp'], "%Y-%m-%d %H:%M:%S"))

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
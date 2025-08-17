import os
import random
import pandas as pd
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List

# --- Data Loading and Preprocessing ---
# This part is kept as a simple function to be called by the API endpoint
def load_and_preprocess_data():
    """
    Loads and preprocesses the dataset from a local file.
    Raises an exception if the file is not found.
    """
    file_name = "data.xlsx"
    if not os.path.exists(file_name):
        raise FileNotFoundError(f"The file '{file_name}' was not found.")
    
    try:
        df = pd.read_excel(file_name)
    except Exception as e:
        raise Exception(f"Error reading file: {e}")
    
    def find_column(df, possible_names):
        for name in possible_names:
            if name in df.columns:
                return name
        return None

    rename_map = {
        find_column(df, ['MGS', 'mgs']): 'mgs',
        find_column(df, ['DBS', 'dbs']): 'dbs',
        find_column(df, ['lcv_id', 'LCV_ID']): 'lcv_id',
        find_column(df, ['create_date', 'Create_Date']): 'create_date',
        find_column(df, ['update_date', 'Update_Date']): 'update_date',
        find_column(df, ['Distance', 'distance']): 'distance',
        find_column(df, ['Duration', 'duration']): 'duration',
        find_column(df, ['Route_id', 'Route_ID']): 'route_id',
        find_column(df, ['Request_id', 'Request_ID']): 'request_id',
        find_column(df, ['Notification_id', 'Notification_ID']): 'notification_id',
        find_column(df, ['Transaction_id', 'Transaction_ID']): 'transaction_id',
    }
    
    rename_map = {k: v for k, v in rename_map.items() if k is not None}
    df.rename(columns=rename_map, inplace=True)
    
    df.dropna(subset=['mgs', 'dbs', 'lcv_id', 'create_date', 'update_date', 'distance', 'duration', 'route_id', 'request_id', 'notification_id'], inplace=True)

    df['create_date'] = pd.to_datetime(df['create_date'])
    df['update_date'] = pd.to_datetime(df['update_date'])
    df['request_id'] = df['request_id'].astype(str)
    
    return df

# --- API Endpoints ---
app = FastAPI(title="LCV Optimization API", description="API for Vehicle Routing Problem (VRP) heuristic and 6-stage simulation.")

# Pydantic model to define the request body structure
class OptimizationRequest(BaseModel):
    selected_date: str
    selected_mgs: str
    selected_request_ids: List[str]

@app.post("/optimize")
def run_lcv_optimization(request: OptimizationRequest):
    """
    Runs the VRP heuristic and 6-stage simulation.
    """
    try:
        df = load_and_preprocess_data()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Convert string date to datetime object
    try:
        start_date = datetime.strptime(request.selected_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Please use 'YYYY-MM-DD'.")

    # Filter data based on input parameters
    filtered_by_date = df[df['create_date'].dt.date == start_date]
    if filtered_by_date.empty:
        raise HTTPException(status_code=404, detail="No data found for the selected date.")

    filtered_by_mgs_and_date = filtered_by_date[filtered_by_date['mgs'] == request.selected_mgs]
    if filtered_by_mgs_and_date.empty:
        raise HTTPException(status_code=404, detail="No data found for the selected MGS and date.")

    requests_to_process_df = filtered_by_mgs_and_date[
        filtered_by_mgs_and_date['request_id'].isin(request.selected_request_ids)
    ].drop_duplicates(subset=['request_id'])
    
    if requests_to_process_df.empty:
        raise HTTPException(status_code=404, detail="No requests found with the provided IDs.")

    requests_to_process_sorted = requests_to_process_df.sort_values(by='create_date').to_dict('records')

    # --- VRP Heuristic Logic ---
    all_lcvs = sorted(df['lcv_id'].unique().tolist())
    lcv_availability = {lcv: datetime.combine(start_date, datetime.min.time()) for lcv in all_lcvs}
    final_schedule = []
    
    for req in requests_to_process_sorted:
        earliest_stochastic_completion_time = datetime.max
        best_lcv = None
        best_start_time = None
        best_completion_time = None

        for lcv_id in all_lcvs:
            current_lcv_start_time = max(lcv_availability[lcv_id], req['create_date'])
            route_duration = int(req['duration'])
            current_lcv_completion_time = current_lcv_start_time + timedelta(minutes=route_duration)
            stochastic_completion_time = current_lcv_completion_time + timedelta(minutes=random.uniform(0, 5))

            if stochastic_completion_time < earliest_stochastic_completion_time:
                earliest_stochastic_completion_time = stochastic_completion_time
                best_lcv = lcv_id
                best_start_time = current_lcv_start_time
                best_completion_time = current_lcv_completion_time

        if best_lcv:
            final_schedule.append({
                'request': req,
                'assigned_lcv': best_lcv,
                'start_time': best_start_time,
                'completion_time': best_completion_time
            })
            lcv_availability[best_lcv] = best_completion_time

    # --- 6-Stage Simulation and Final Result Formatting ---
    results = {
        "optimal_schedule": [],
        "simulation_timeline": []
    }

    for assignment in final_schedule:
        req = assignment['request']
        lcv_id = assignment['assigned_lcv']
        start_time = assignment['start_time']
        route_duration = int(req['duration'])
        
        # Format optimal schedule data
        results['optimal_schedule'].append({
            'Request ID': req['request_id'],
            'Assigned LCV ID': lcv_id,
            'Historical Route ID': req['route_id'],
            'Historical Distance (km)': f"{req['distance']:.2f}",
            'Historical Duration (min)': f"{req['duration']:.2f}",
            'Start Time': assignment['start_time'].strftime('%Y-%m-%d %H:%M:%S'),
            'Completion Time': assignment['completion_time'].strftime('%Y-%m-%d %H:%M:%S')
        })
        
        # Simulate and format 6-stage timeline
        stage1_time = start_time
        stage2_time = stage1_time + timedelta(minutes=random.randint(4, 6))
        stage3_time = stage2_time + timedelta(minutes=random.randint(28, 32))
        stage4_time = stage3_time + timedelta(minutes=route_duration)
        stage5_time = stage4_time + timedelta(minutes=random.randint(4, 6))
        stage6_time = stage5_time + timedelta(minutes=random.randint(28, 32))
        
        results['simulation_timeline'].append({
            'Request ID': req['request_id'],
            'LCV ID': lcv_id,
            'Stages': {
                '1: Enters MGS': stage1_time.strftime('%Y-%m-%d %H:%M:%S'),
                '2: Starts Filling': stage2_time.strftime('%Y-%m-%d %H:%M:%S'),
                '3: Filled': stage3_time.strftime('%Y-%m-%d %H:%M:%S'),
                '4: Enters DBS': stage4_time.strftime('%Y-%m-%d %H:%M:%S'),
                '5: Starts Emptying': stage5_time.strftime('%Y-%m-%d %H:%M:%S'),
                '6: Emptied': stage6_time.strftime('%Y-%m-%d %H:%M:%S')
            }
        })
    
    return results

# To run the API, save this code as api.py and run the command:
# uvicorn api:app --reload

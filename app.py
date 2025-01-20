# app.py
import streamlit as st
import geopandas as gpd
import matplotlib.pyplot as plt
import plotly.graph_objects as go
import numpy as np
import os
from matplotlib.patches import Patch
import matplotlib.colors as mcolors
import cartopy.crs as ccrs

import plotly.express as px
from app_functions import create_interactive_cost_map, plot_cost_distribution, generate_waterfall_chart, ensure_directory_exists

# Title and description 
st.title("Hydrogen Production Scenarios in Laos")
st.write("Visualization of different hydrogen production scenarios")

# Sidebar controls
st.sidebar.header("Scenario Selection")
generation_type = st.sidebar.selectbox("Select Generation Type", 
                                     ["total_generation", "net_generation"])
hydro_year = st.sidebar.selectbox("Select Hydro Year", ["wet", "dry", "atlite"])
electrolyser_type = st.sidebar.selectbox("Select Electrolyser Type", ["ALK", "PEM"])
scenario_year = st.sidebar.selectbox("Select Scenario Year", ["25", "30"])

# Cost range control in sidebar
st.sidebar.markdown("---")
st.sidebar.header("Cost Range")
max_cost = st.sidebar.slider("Maximum Cost (USD/kgH2)", 
                            min_value=5, 
                            max_value=25, 
                            value=15)

# Load and process data
@st.cache_data
def load_data(generation_type, hydro_year, electrolyser_type, scenario_year):
    try:
        file_path = f'Resources/{generation_type}/Scenario_{hydro_year}_{electrolyser_type}_{scenario_year}/hex_cost_components.geojson'
        data = gpd.read_file(file_path)
        data = data.drop_duplicates(subset=['h3_index'])
        return data
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return None

data = load_data(generation_type, hydro_year, electrolyser_type, scenario_year)

if data is not None:
    tab1, tab2, tab3 = st.tabs(["Cost Map", "Cost Distribution", "Cost Breakdown"])
    
    with tab1:
        st.subheader("Production Cost Map")
        fig = create_interactive_cost_map(
            data,
            'Vientiane trucking production cost',
            max_cost=max_cost
        )
        st.plotly_chart(fig, use_container_width=True)
        
    with tab2:
        st.subheader("Cost Distribution")
        mask = (data['Vientiane trucking production cost'] > 0) & (data['Vientiane trucking production cost'] <= max_cost)
        costs = data[mask]['Vientiane trucking production cost'].sort_values()
        x_values = np.arange(len(costs)) * 1000
        
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.plot(x_values, costs, color='#2ecc71', linewidth=2.5)
        ax.fill_between(x_values, costs, alpha=0.2, color='#2ecc71')
        
        ax.set_xlabel('Cumulative Production Potential (kt)', fontsize=10)
        ax.set_ylabel('LCOH (USD/kgH2)', fontsize=10)
        ax.grid(True, linestyle='--', alpha=0.3)
        ax.set_ylim(0, max_cost)
        
        step = 10000
        ax.set_xticks(np.arange(0, len(costs) * 1000, step))
        ax.set_xticklabels([f'{int(x/1000)}k' for x in ax.get_xticks()])
        
        st.pyplot(fig)

    with tab3:
        st.subheader("Cost Component Breakdown")
        
        waterfall_fig = generate_waterfall_chart(data)
        st.plotly_chart(waterfall_fig, use_container_width=True)

    # Additional stats
    st.sidebar.markdown("---")
    st.sidebar.subheader("Scenario Statistics")
    st.sidebar.write(f"Minimum Cost: {data['Vientiane trucking production cost'].min():.2f} USD/kgH2")
    st.sidebar.write(f"Maximum Cost: {data['Vientiane trucking production cost'].max():.2f} USD/kgH2")
    st.sidebar.write(f"Mean Cost: {data['Vientiane trucking production cost'].mean():.2f} USD/kgH2")
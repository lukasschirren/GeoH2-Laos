import streamlit as st
from streamlit.components.v1 import html
from streamlit.runtime.scriptrunner import get_script_run_ctx
import geopandas as gpd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from config import DISPLAY_MAPPINGS
from app_functions import (create_interactive_cost_map, create_interactive_capacity_map, 
                         generate_waterfall_chart, create_cost_distribution,
                         get_capacity_ranges)

# Page config
st.set_page_config(layout="wide", page_title="Overview of Scenarios")

# Responsive CSS
st.markdown("""
<style>
    .main > div {
        padding-top: 2rem;
    }
    .block-container {
        padding-top: 1rem;
        padding-bottom: 0rem;
    }
    h1 {
        font-size: calc(1.3rem + .6vw);
        margin-bottom: 0.5rem;
    }
    h2 {
        font-size: calc(1.1rem + .4vw);
        margin-bottom: 0.4rem;
    }
    .stSelectbox label {
        font-size: calc(0.8rem + .2vw);
    }
    @media (max-width: 768px) {
        .element-container {
            margin: 0.5rem 0;
        }
    }
</style>
""", unsafe_allow_html=True)

st.title("Green Hydrogen Production in Laos")
# st.markdown("""
# # GeoH2 Framework - Laos Hydrogen Production Scenarios

# This dashboard presents hydrogen production scenarios for Laos, modeled using the GeoH2 framework. 
# The analysis considers four key factors:

# - **Hydro Year**: High (wet), Low (dry), or 5-Year Average water availability
# - **Generation Type**: Optimistic or Conservative renewable energy potential
# - **Electrolyser Type**: Alkaline (ALK) or Proton Exchange Membrane (PEM)
# - **Target Year**: 2025 or 2030

# These factors combine to create 24 unique scenarios (2×3×2×2), which can be selected using the controls on the left side.
# """)
st.markdown('''
<p class="subtitle">
This dashboard presents hydrogen production scenarios for Laos, modeled using the GeoH2 framework with four key factors, resulting in 24 different scenarios. The different scenarios can be selected on the left side. 
</p>

<b>Generation Availability:</b>  
- <i>Optimistic:</i> Assumes more electricity is available for hydrogen production (Total generation).  
- <i>Conservative:</i> Prioritizes household and industrial electricity demand first, using only surplus for hydrogen (Net generation).  

<b>Rainfall Conditions:</b>  
- <i>High:</i> Based on electricity generation in a high-rainfall year (2022).  
- <i>Low:</i> Based on electricity generation in a low-rainfall year (2019).  
- <i>5-Year Average:</i> Uses an estimated long-term average from satellite data (ERA5).  

<b>Electrolyser Technology:</b>  
- Compares two hydrogen production technologies: **Alkaline (ALK)** and **Polymer Electrolyte Membrane (PEM)**.  

<b>Scenario Year:</b>  
- Includes **electricity demand projections** for **2025** and **2030** to help plan for future hydrogen production.  
''', unsafe_allow_html=True)



# Screen size detection
screen_width = st.session_state.get('screen_width', 1200)
html("""
    <script>
        function updateScreenWidth() {
            const width = window.innerWidth;
            window.parent.document.dispatchEvent(
                new CustomEvent('screen_width', {detail: width})
            );
        }
        updateScreenWidth();
        window.addEventListener('resize', updateScreenWidth);
    </script>
""")


# Device detection
is_mobile = screen_width < 768

# Sidebar controls
st.sidebar.header("Scenario Selection")

# Create mapping for display names to values
generation_mapping = {
    "Optimistic": "total_generation",
    "Conservative": "net_generation"
}

# Update selectbox with display names
generation_type_display = st.sidebar.selectbox(
    "Generation Availability", 
    list(generation_mapping.keys())
)

# Convert display name to actual value
generation_type = generation_mapping[generation_type_display]

hydro_mapping = {
    "High": "wet",
    "Low": "dry", 
    "5 Year Average": "atlite"
}

hydro_year_display = st.sidebar.selectbox(
    "Rainfall", 
    list(hydro_mapping.keys())
)

hydro_year = hydro_mapping[hydro_year_display]

electrolyser_type = st.sidebar.selectbox("Electrolyser Type", ["ALK", "PEM"])

scenario_year_display = st.sidebar.selectbox("Year", ["2025", "2030"])
scenario_year = scenario_year_display[-2:]  # Extract last 2 digits

# Capacity settings
# capacity_settings = {
#     'hydro': {'vmin': 0, 'vmax': 100},
#     'solar': {'vmin': 20, 'vmax': 500},
#     'wind': {'vmin': 20, 'vmax': 200},
#     'electrolyzer': {'vmin': 0, 'vmax': 200}
# }

# Load data
@st.cache_data
# def load_all_scenarios():
#     scenarios = []
#     for gen in ["total_generation", "net_generation"]:
#         for hydro in ["wet", "dry", "atlite"]:
#             for elec in ["ALK", "PEM"]:
#                 for year in ["25", "30"]:
#                     try:
#                         path = f'Resources/{gen}/Scenario_{hydro}_{elec}_{year}/hex_cost_components.geojson'
#                         data = gpd.read_file(path)
#                         data = data.drop_duplicates(subset=['h3_index'])
#                         scenarios.append({
#                             'data': data,
#                             'gen': gen,
#                             'hydro': hydro,
#                             'elec': elec,
#                             'year': year
#                         })
#                     except Exception:
#                         continue
#     return scenarios

def load_all_scenarios():
    scenarios = []
    for gen in DISPLAY_MAPPINGS['generation']['internal_to_display'].keys():
        for hydro in DISPLAY_MAPPINGS['hydro']['internal_to_display'].keys():
            for elec in ["ALK", "PEM"]:
                for year in DISPLAY_MAPPINGS['year']['internal_to_display'].keys():
                    try:
                        path = f'Resources/{gen}/Scenario_{hydro}_{elec}_{year}/hex_cost_components.geojson'
                        data = gpd.read_file(path)
                        data = data.drop_duplicates(subset=['h3_index'])
                        scenarios.append({
                            'data': data,
                            'gen': gen,
                            'hydro': hydro,
                            'elec': elec,
                            'year': year,
                            'display_gen': DISPLAY_MAPPINGS['generation']['internal_to_display'][gen],
                            'display_hydro': DISPLAY_MAPPINGS['hydro']['internal_to_display'][hydro],
                            'display_year': DISPLAY_MAPPINGS['year']['internal_to_display'][year]
                        })
                    except Exception:
                        continue
    return scenarios

scenarios_data = load_all_scenarios()
current_data = next(s['data'] for s in scenarios_data 
                   if s['gen'] == generation_type 
                   and s['hydro'] == hydro_year 
                   and s['elec'] == electrolyser_type 
                   and s['year'] == scenario_year)

capacity_settings = get_capacity_ranges(current_data)

# Responsive layout
if is_mobile:
    # Mobile layout - vertical stack
    # st.title("Hydrogen Production Scenarios")
    
    st.subheader("Production Cost Map")
    st.plotly_chart(create_interactive_cost_map(current_data, 
                    'Vientiane trucking production cost'),
                    use_container_width=True)
    
    st.subheader("Capacity Distribution")
    capacity_type = st.selectbox("Select Capacity Type", 
                               list(capacity_settings.keys()))
    st.plotly_chart(create_interactive_capacity_map(
        current_data,
        f'Vientiane trucking {capacity_type} capacity',
        vmin=capacity_settings[capacity_type]['vmin'],
        vmax=capacity_settings[capacity_type]['vmax']
    ), use_container_width=True)
    
    st.subheader("Cost Breakdown")
    st.plotly_chart(generate_waterfall_chart(current_data),
                    use_container_width=True)
    
    st.subheader("Cost Distribution")
    st.plotly_chart(create_cost_distribution(scenarios_data, max_cost), 
                use_container_width=True)

else:
    # Desktop layout - 2x2 grid
    # st.title("Hydrogen Production Scenarios")
    
    left_col, right_col = st.columns([0.4, 0.6])
    
    with left_col:
        st.subheader("Production Cost Map")
        st.plotly_chart(create_interactive_cost_map(current_data,
                        'Vientiane trucking production cost'),
                        use_container_width=True)
        
        st.subheader("Capacity Distribution")
        capacity_type = st.selectbox("Select Capacity Type",
            list(capacity_settings.keys()))
        st.plotly_chart(create_interactive_capacity_map(
            current_data,
            f'Vientiane trucking {capacity_type} capacity',
            vmin=capacity_settings[capacity_type]['vmin'],
            vmax=capacity_settings[capacity_type]['vmax']
        ), use_container_width=True)
    
    with right_col:
        st.subheader("Cost Breakdown")
        st.plotly_chart(generate_waterfall_chart(current_data),
                        use_container_width=True)
    
        st.subheader("Cost Distribution")
        max_cost = st.slider("Max Cost (USD/kgH2)", min_value=5, max_value=25, value=7)
        st.plotly_chart(create_cost_distribution(scenarios_data, max_cost), 
                use_container_width=True)
        
    # Additional stats
    st.sidebar.markdown("---")
    st.sidebar.subheader("Scenario Statistics")
    st.sidebar.write(f"Minimum Cost: {current_data['Vientiane trucking production cost'].min():.2f} USD/kgH2")
    st.sidebar.write(f"Maximum Cost: {current_data['Vientiane trucking production cost'].max():.2f} USD/kgH2")
    st.sidebar.write(f"Mean Cost: {current_data['Vientiane trucking production cost'].mean():.2f} USD/kgH2")
    

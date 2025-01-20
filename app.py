import streamlit as st
from streamlit.components.v1 import html
import geopandas as gpd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from app_functions import (create_interactive_cost_map, create_interactive_capacity_map, 
                         generate_waterfall_chart, create_cost_distribution)

# Page config
st.set_page_config(layout="wide", page_title="Hydrogen Production Scenarios")

# Responsive CSS
st.markdown("""
<style>
    .main > div {
        padding-top: 0rem;
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
generation_type = st.sidebar.selectbox("Generation Type", ["total_generation", "net_generation"])
hydro_year = st.sidebar.selectbox("Hydro Year", ["wet", "dry", "atlite"])
electrolyser_type = st.sidebar.selectbox("Electrolyser Type", ["ALK", "PEM"])
scenario_year = st.sidebar.selectbox("Scenario Year", ["25", "30"])
max_cost = st.sidebar.slider("Max Cost (USD/kgH2)", min_value=5, max_value=25, value=7)

# Capacity settings
capacity_settings = {
    'hydro': {'vmin': 0, 'vmax': 100},
    'solar': {'vmin': 20, 'vmax': 440},
    'wind': {'vmin': 20, 'vmax': 440},
    'electrolyzer': {'vmin': 0, 'vmax': 200}
}

# Load data
@st.cache_data
def load_all_scenarios():
    scenarios = []
    for gen in ["total_generation", "net_generation"]:
        for hydro in ["wet", "dry", "atlite"]:
            for elec in ["ALK", "PEM"]:
                for year in ["25", "30"]:
                    try:
                        path = f'Resources/{gen}/Scenario_{hydro}_{elec}_{year}/hex_cost_components.geojson'
                        data = gpd.read_file(path)
                        data = data.drop_duplicates(subset=['h3_index'])
                        scenarios.append({
                            'data': data,
                            'gen': gen,
                            'hydro': hydro,
                            'elec': elec,
                            'year': year
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

# Responsive layout
if is_mobile:
    # Mobile layout - vertical stack
    st.title("Hydrogen Production Scenarios")
    
    st.subheader("Production Cost Map")
    st.plotly_chart(create_interactive_cost_map(current_data, 
                    'Vientiane trucking production cost', max_cost),
                    use_container_width=True)
    
    st.subheader("Capacity Distribution")
    capacity_type = st.selectbox("Select Capacity Type", 
                               ['hydro', 'solar', 'wind', 'electrolyzer'])
    st.plotly_chart(create_interactive_capacity_map(current_data,
                    f'Vientiane trucking {capacity_type} capacity',
                    vmin=capacity_settings[capacity_type]['vmin'],
                    vmax=capacity_settings[capacity_type]['vmax']),
                    use_container_width=True)
    
    st.subheader("Cost Breakdown")
    st.plotly_chart(generate_waterfall_chart(current_data),
                    use_container_width=True)
    
    st.subheader("Cost Distribution")
    st.plotly_chart(create_cost_distribution(scenarios_data, max_cost), 
                use_container_width=True)

else:
    # Desktop layout - 2x2 grid
    st.title("Hydrogen Production Scenarios")
    
    left_col, right_col = st.columns(2)
    
    with left_col:
        st.subheader("Production Cost Map")
        st.plotly_chart(create_interactive_cost_map(current_data,
                        'Vientiane trucking production cost', max_cost),
                        use_container_width=True)
        
        st.subheader("Capacity Distribution")
        capacity_type = st.selectbox("Select Capacity Type",
                                   ['hydro', 'solar', 'wind', 'electrolyzer'])
        st.plotly_chart(create_interactive_capacity_map(current_data,
                        f'Vientiane trucking {capacity_type} capacity',
                        vmin=capacity_settings[capacity_type]['vmin'],
                        vmax=capacity_settings[capacity_type]['vmax']),
                        use_container_width=True)
    
    with right_col:
        st.subheader("Cost Breakdown")
        st.plotly_chart(generate_waterfall_chart(current_data),
                        use_container_width=True)
    
        st.subheader("Cost Distribution")
        st.plotly_chart(create_cost_distribution(scenarios_data, max_cost), 
                use_container_width=True)
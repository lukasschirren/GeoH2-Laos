import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import cartopy.crs as ccrs
from matplotlib.patches import Patch
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

def ensure_directory_exists(path):
    """Create directory if it doesn't exist"""
    if not os.path.exists(path):
        os.makedirs(path)

def get_cost_categories():
    """Return standardized cost bins and colors"""
    bins = [3, 4, 5, 6, 7, 8, 9, 10, float('inf')]
    labels = ['3-4', '4-5', '5-6', '6-7', '7-8', '8-9', '9-10', '10+']
    colors = px.colors.sample_colorscale("Greens_r", len(labels))
    return bins, labels, colors

def create_interactive_cost_map(hexagons, cost_column, max_cost=10):
    """Creates an interactive cost map with fixed legend categories"""
    bins, labels, colors = get_cost_categories()
    
    # Create bin categories
    hexagons = hexagons.copy()
    hexagons['cost_category'] = pd.cut(
        hexagons[cost_column], 
        bins=bins,
        labels=labels,
        include_lowest=True
    )
    
    # Define hover columns and their display names
    hover_columns = {
        'Vientiane trucking production cost': 'Production Cost [USD/kgH2]',
        'Vientiane trucking solar capacity': 'Solar Capacity [MW]',
        'Vientiane trucking wind capacity': 'Wind Capacity [MW]',
        'Vientiane trucking hydro capacity': 'Hydro Capacity [MW]',
        'Vientiane trucking electrolyzer capacity': 'Electrolyzer Capacity [MW]',
        'Vientiane trucking battery capacity': 'Battery Capacity [MWh]',
        'Vientiane trucking H2 storage capacity': 'H2 Storage Capacity [kg]'
    }
    
    # Create base map
    fig = px.choropleth_mapbox(
        hexagons,
        geojson=hexagons.geometry.__geo_interface__,
        locations=hexagons.index,
        color='cost_category',
        color_discrete_map=dict(zip(labels, colors)),
        category_orders={'cost_category': labels},
        hover_data=list(hover_columns.keys()),
        mapbox_style="carto-positron",
        opacity=0.7,
        center={"lat": 18, "lon": 103},
        zoom=5
    )

    # Update hover template
    hovertemplate = "<br>".join([
        f"<b>{display_name}:</b> %{{customdata[{i}]:.2f}}"
        for i, display_name in enumerate(hover_columns.values())
    ]) + "<extra></extra>"
    
    fig.update_traces(hovertemplate=hovertemplate)

    # Update layout
    fig.update_layout(
        margin={"r":0,"t":0,"l":0,"b":0},
        legend=dict(
            title="LCOH (USD/kgH2)",
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=0.01,
            # bgcolor="rgba(255, 255, 255, 0.8)"
        ),
        hoverlabel=dict(
            bgcolor="black",
            font_size=12
        )
    )

    return fig

def generate_waterfall_chart(gdf):
    """Generate waterfall chart for cost breakdown"""
    # Find min-cost hexagon
    cost_column = f'Vientiane trucking production cost'
    min_hexagon = gdf.loc[gdf[cost_column].idxmin()]

    # Define components
    components = [
        (f'Vientiane LCOH - trucking battery costs portion', 'Battery'),
        (f'Vientiane LCOH - trucking electrolyzer portion', 'Electrolyzer'),
        (f'Vientiane LCOH - trucking H2 storage portion', 'H2 Storage'),
        (f'Vientiane LCOH - trucking wind portion', 'Wind'),
        (f'Vientiane LCOH - trucking solar portion', 'Solar'),
        (f'Vientiane LCOH - trucking hydro portion', 'Hydro')
    ]

    columns, labels = zip(*components)
    labels = list(labels) + ["Total"]

    # Extract values
    values = [min_hexagon[col] for col in columns] + [0]
    texts = [f"{v:.2f}" for v in values[:-1]] + [f"{min_hexagon[cost_column]:.2f}"]

    # Create figure
    fig = go.Figure(go.Waterfall(
        orientation="v",
        measure=["relative"] * len(columns) + ["total"],
        x=labels,
        y=values,
        text=texts,
        connector={"line": {"color": "rgb(63, 63, 63)", "dash": "dot"}},
        increasing={"marker": {"color": "#0000ff"}},
        decreasing={"marker": {"color": "#ff7f0e"}},
        totals={"marker": {"color": "white"}}
    ))

    fig.update_layout(
        xaxis_title="Cost Components",
        yaxis_title="LCOH [USD/kgH2]",
        xaxis={
            'showline': True,
            'linewidth': 1,
            'linecolor': 'black',
            'mirror': True,
            'tickfont': {'size': 14},
            'titlefont': {'size': 16},
            # 'showgrid': True,
            # 'gridwidth': 1,
            # 'gridcolor': 'lightgrey'
        },
        yaxis={
            'showline': True,
            'linewidth': 1,
            'linecolor': 'black',
            'mirror': True,
            'tickfont': {'size': 14},
            'titlefont': {'size': 16},
            'showgrid': True,
            'gridwidth': 1,
            'gridcolor': 'lightgrey'
        },
        # plot_bgcolor='white',
        showlegend=False,
        width=700,
        height=500,
        margin=dict(l=80, r=20, t=80, b=80),
        font=dict(family="Arial")
    )

    return fig

def create_interactive_capacity_map(hexagons, capacity_column, vmin, vmax):
    """Creates an interactive capacity map using Plotly"""
    fig = px.choropleth_mapbox(
        hexagons,
        geojson=hexagons.geometry.__geo_interface__,
        locations=hexagons.index,
        color=capacity_column,
        color_continuous_scale="Viridis",
        range_color=[vmin, vmax],
        hover_data={capacity_column: ':.2f'},
        mapbox_style="carto-positron",
        opacity=0.7,
        center={"lat": 18, "lon": 103},
        zoom=5
    )

    fig.update_layout(
        margin={"r":0,"t":0,"l":0,"b":0},
        coloraxis_colorbar=dict(
            title="Capacity [MW]",
            thicknessmode="pixels",
            thickness=20,
            lenmode="pixels",
            len=300,
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=0.01,
            bgcolor="black"
        )
    )

    return fig

def create_cost_distribution(scenarios_data, max_cost):
    """Creates cost distribution plot comparing net and total generation"""
    fig = go.Figure()
    
    # Sort scenarios by generation type
    net_scenarios = [s for s in scenarios_data if s['gen'] == 'net_generation']
    total_scenarios = [s for s in scenarios_data if s['gen'] == 'total_generation']
    
    # Plot net generation traces
    for scenario in net_scenarios:
        data = scenario['data']
        mask = (data['Vientiane trucking production cost'] > 0) & \
            (data['Vientiane trucking production cost'] <= max_cost)
        costs = data[mask]['Vientiane trucking production cost'].sort_values()
        x_values = np.arange(len(costs))
        
        name = f"{scenario['hydro'].capitalize()} {scenario['elec']} {scenario['year']}"
        
        fig.add_trace(go.Scatter(
            x=x_values,
            y=costs,
            name=name,
            line=dict(dash='dash'),
            showlegend=True,
            legendgroup="net",
            legendgrouptitle_text="Net Generation"
        ))
    
    # Plot total generation traces
    for scenario in total_scenarios:
        data = scenario['data']
        mask = (data['Vientiane trucking production cost'] > 0) & \
            (data['Vientiane trucking production cost'] <= max_cost)
        costs = data[mask]['Vientiane trucking production cost'].sort_values()
        x_values = np.arange(len(costs))
        
        name = f"{scenario['hydro'].capitalize()} {scenario['elec']} {scenario['year']}"
        
        fig.add_trace(go.Scatter(
            x=x_values,
            y=costs,
            name=name,
            line=dict(dash='solid'),
            showlegend=True,
            legendgroup="total",
            legendgrouptitle_text="Total Generation"
        ))
    
    fig.update_layout(
        xaxis_title="Cumulative Production Potential",
        yaxis_title="LCOH (USD/kgH2)",
        showlegend=True,
        legend=dict(
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=1.05,
            groupclick="toggleitem",
            itemsizing="constant",
            font=dict(size=10),
            title=dict(font=dict(size=12)),
            tracegroupgap=40
        ),
        autosize=True,  # Automatically adjust size
        margin=dict(l=20, r=20, t=20, b=20),  # Minimize margins
        width=None,
        # plot_bgcolor='white',
        xaxis=dict(
            showgrid=True,
            gridwidth=1,
            gridcolor='lightgrey',
        ),
        yaxis=dict(
            showgrid=True,
            gridwidth=1,
            gridcolor='lightgrey',
            range=[3, max_cost]
        )
    )
    return fig

# def plot_cost_distribution(data, cost_column, max_cost=10):
#     """Creates cost distribution plot"""
#     mask = (data[cost_column] > 0) & (data[cost_column] <= max_cost)
#     costs = data[mask][cost_column].sort_values()
#     x_values = np.arange(len(costs)) * 1000
    
#     fig, ax = plt.subplots(figsize=(10, 6))
#     ax.plot(x_values, costs, color='#2ecc71', linewidth=2.5)
#     ax.fill_between(x_values, costs, alpha=0.2, color='#2ecc71')
    
#     ax.set_xlabel('Cumulative Production Potential (kt)', fontsize=10)
#     ax.set_ylabel('LCOH (USD/kgH2)', fontsize=10)
#     ax.grid(True, linestyle='--', alpha=0.3)
    
#     step = 10000
#     ax.set_xticks(np.arange(0, len(costs) * 1000, step))
#     ax.set_xticklabels([f'{int(x/1000)}k' for x in ax.get_xticks()])
    
#     return fig, ax

def create_scenario_folder(base_path, hydro_year, electrolyser_type, scenario_year):
    """Create scenario-specific folder and return its path"""
    scenario_folder = os.path.join(base_path, f"Scenario_{hydro_year}_{electrolyser_type}_{scenario_year}")
    ensure_directory_exists(scenario_folder)
    return scenario_folder
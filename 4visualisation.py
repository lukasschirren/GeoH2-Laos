"""
Created on Tue Dec 27th 2024

@author: Lukas Schirren, Imperial College London, lukas.schirren@imperial.ac.uk

This script creates visualisations of the results with parameters for different scenarios.
"""

import os
import geopandas as gpd
import cartopy.crs as ccrs
import matplotlib.pyplot as plt
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import matplotlib.colors as mcolors

def ensure_directory_exists(path):
    """Create directory if it doesn't exist"""
    if not os.path.exists(path):
        os.makedirs(path)

def create_scenario_folder(base_path, hydro_year, electrolyser_type, scenario_year):
    """Create scenario-specific folder and return its path"""
    scenario_folder = os.path.join(base_path, f"Scenario_{hydro_year}_{electrolyser_type}_{scenario_year}")
    ensure_directory_exists(scenario_folder)
    return scenario_folder

def plot_full_cost_map(hexagons, demand_center, cost_column, save_path, provinces=None, vmin=None, vmax=None):
    """Plots and saves a map showing production costs"""
    crs = ccrs.PlateCarree()
    fig, ax = plt.subplots(figsize=(12, 8), subplot_kw={'projection': crs}, dpi=300)
    ax.set_axis_off()

    hexagons_copy = hexagons.copy()
    zero_mask = hexagons_copy[cost_column] == 0
    hexagons_copy.loc[zero_mask, cost_column] = np.nan

    if provinces is not None:
        provinces.to_crs(crs.proj4_init).plot(
            ax=ax, color='none', edgecolor='black', linewidth=0.5)

    plot = hexagons_copy.to_crs(crs.proj4_init).plot(
        ax=ax,
        column=cost_column,
        legend=True,
        cmap='Greens_r',
        legend_kwds={
            'label': 'LCOH (USD/kgH2)',
            'orientation': 'vertical',
            'shrink': 0.5,
            'pad': 0.05,
            'anchor': (-1.1, 1.0)
        },
        missing_kwds={
            "color": "lightgrey",
            "label": "No Data or Zero",
        },
        edgecolor='black',
        linewidth=0.2,
        vmin=vmin,
        vmax=vmax
    )

    if plot.get_legend() is not None:
        legend = plot.get_legend()
        legend.set_bbox_to_anchor((1, 0.5))
        legend.set_frame_on(True)

    fig.savefig(save_path, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close(fig)

def plot_cost_distribution(hexagons, cost_column, save_path, max_cost=10):
    """Creates and saves a cost distribution plot"""
    mask = (hexagons[cost_column] > 0) & (hexagons[cost_column] <= max_cost)
    costs = hexagons[mask][cost_column].sort_values()
    x_values = np.arange(len(costs)) * 1000
    
    fig, ax = plt.subplots(figsize=(10, 6), facecolor='white', dpi=300)
    ax.set_facecolor('white')
    
    ax.plot(x_values, costs, color='#2ecc71', linewidth=2.5)
    
    ax.set_title('Hydrogen Production Cost Distribution', pad=20, fontsize=12)
    ax.set_xlabel('Cumulative Production Potential (kt)', fontsize=10)
    ax.set_ylabel('LCOH (USD/kgH2)', fontsize=10)
    
    ax.grid(True, linestyle='--', alpha=0.3)
    ax.set_ylim(0, max_cost)
    
    step = 50000
    ax.set_xticks(np.arange(0, len(costs) * 1000, step))
    ax.set_xticklabels([f'{int(x/1000)}k' for x in ax.get_xticks()])
    
    plt.tight_layout()
    fig.savefig(save_path, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close(fig)

# def generate_waterfall_chart(gdf, transport_type):
#     # Find the min-cost hexagon in the pipeline or trucking data
#     min_hexagon = gdf.loc[gdf[f'Vientiane {transport_type} production cost'].idxmin()]

#     # Define the columns and their corresponding custom labels
#     columns_and_labels = [
#         (f'Vientiane LCOH - {transport_type} battery costs portion', 'Battery'),
#         (f'Vientiane LCOH - {transport_type} electrolyzer portion', 'Electrolyzer'),
#         (f'Vientiane LCOH - {transport_type} H2 storage portion', 'H2 Storage'),
#         # (f'Vientiane LCOH - {transport_type} wind portion', 'Wind'),
#         (f'Vientiane LCOH - {transport_type} solar portion', 'Solar'),
#         (f'Vientiane LCOH - {transport_type} hydro portion', 'Hydro')
#     ]

#     # Extract columns and labels
#     columns = [item[0] for item in columns_and_labels]
#     labels = [item[1] for item in columns_and_labels] + ["Total"]

#     # Extract the actual cost values from the selected hexagon
#     cost_values = {col: min_hexagon[col] for col in columns}

#     # Calculate total LCOH cost for the transport method
#     total_cost = min_hexagon[f'Vientiane {transport_type} production cost']

#     # Create lists for the waterfall chart
#     measures = ["relative"] * len(columns) + ["total"]
#     values = list(cost_values.values()) + [0]  # 0 for total, as it will be auto-calculated
#     texts = [f"{value:.2f}" for value in cost_values.values()] + [f"{total_cost:.2f}"]

#     # Rest of the function remains the same
#     fig = go.Figure(go.Waterfall(
#         name="LCOH Cost Breakdown",
#         orientation="v",
#         measure=measures,
#         x=labels,
#         y=values,
#         text=texts,
#         connector={"line": {"color": "rgb(63, 63, 63)", "dash": "dot"}},
#         increasing={"marker": {"color": "#0000ff"}},
#         decreasing={"marker": {"color": "#ff7f0e"}},
#         totals={"marker": {"color": "#000000"}}
#     ))

#     fig.update_layout(
#         xaxis_title="Cost Portions",
#         yaxis_title="LCOH [USD/kgH2]",
#         xaxis=dict(
#             tickfont=dict(color='black', size=20),
#             titlefont=dict(color='black', size=22),
#         ),
#         yaxis=dict(
#             tickfont=dict(color='black', size=20),
#             titlefont=dict(color='black', size=22),
#             showgrid=True,
#             gridcolor='lightgrey'
#         ),
#         plot_bgcolor='white',
#         showlegend=False,
#         width=550,
#         height=500,
#         font=dict(size=18),
#         margin=dict(l=50, r=50, t=100, b=50)
#     )
#     fig.show()
    
def plot_capacity_map(hexagons, demand_center, capacity_column, save_path, vmin=20, vmax=440):
    """Plot capacity map with improved visualization"""
    crs = ccrs.PlateCarree()
    fig, ax = plt.subplots(figsize=(12, 8), subplot_kw={'projection': crs}, dpi=300)
    ax.set_axis_off()

    hexagons_copy = hexagons.copy()
    zero_mask = hexagons_copy[capacity_column] == 0
    hexagons_copy.loc[zero_mask, capacity_column] = np.nan

    plot = hexagons_copy.to_crs(crs.proj4_init).plot(
        ax=ax,
        column=capacity_column,
        legend=True,
        cmap='cividis',
        norm=mcolors.Normalize(vmin=vmin, vmax=vmax),
        legend_kwds={
            'label': 'Capacity (MW)',
            'orientation': 'vertical',
            'shrink': 0.5,
            'pad': 0.05,
            'anchor': (-1.1, 1.0)
        },
        missing_kwds={
            "color": "lightgrey",
            "label": "No Data or Zero",
        },
        edgecolor='black',
        linewidth=0.2
    )

    if plot.get_legend() is not None:
        legend = plot.get_legend()
        legend.set_bbox_to_anchor((1, 0.5))
        legend.set_frame_on(True)

    fig.savefig(save_path, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close(fig)

def process_scenario(hydro_year, electrolyser_type, scenario_year, generation_type='total'):
    """Process a single scenario and generate all visualizations"""
    # Set data and output paths
    if generation_type == 'net':
        data_path = f'Resources/net_generation/Scenario_{hydro_year}_{electrolyser_type}_{scenario_year}'
        vis_path = os.path.join('Visualisation', 'net_generation')
    else:
        data_path = f'Resources/Scenario_{hydro_year}_{electrolyser_type}_{scenario_year}'
        vis_path = os.path.join('Visualisation', 'total_generation')
    
    # Create output directory
    scenario_folder = create_scenario_folder(vis_path, hydro_year, electrolyser_type, scenario_year)
    
    try:
        # Load data
        gdf_data = gpd.read_file(os.path.join(data_path, 'hex_cost_components.geojson'))
        
        # Generate cost visualizations
        plot_full_cost_map(gdf_data, 'Vientiane', 'Vientiane trucking production cost',
                          os.path.join(scenario_folder, 'cost_map.png'), vmin=5, vmax=15)
        
        plot_cost_distribution(gdf_data, 'Vientiane trucking production cost',
                             os.path.join(scenario_folder, 'cost_distribution.png'), max_cost=15)
        
        capacity_settings = {
            'hydro': {'vmin': 0, 'vmax': 100},
            'solar': {'vmin': 20, 'vmax': 440},
            'wind': {'vmin': 20, 'vmax': 440}
        }
        
        capacity_types = ['hydro', 'solar', 'wind']
        for capacity_type in capacity_types:
            plot_capacity_map(
                gdf_data,
                'Vientiane',
                f'Vientiane trucking {capacity_type} capacity',
                os.path.join(scenario_folder, f'capacity_map_{capacity_type}.png'),
                vmin=capacity_settings[capacity_type]['vmin'],
                vmax=capacity_settings[capacity_type]['vmax']
            )
            
    except Exception as e:
        print(f"Error processing scenario {hydro_year}_{electrolyser_type}_{scenario_year}: {e}")


def main(generation_type='total'):
    """Main function to process all scenarios"""
    scenarios = [
        ('dry', '25', 'ALK'),
        ('dry', '30', 'ALK'),
        ('wet', '25', 'ALK'),
        ('wet', '30', 'ALK'),
        ('dry', '25', 'PEM'),
        ('dry', '30', 'PEM'),
        ('wet', '25', 'PEM'),
        ('wet', '30', 'PEM'),
        ('atlite', '25', 'ALK'),
        ('atlite', '25', 'PEM')
    ]

    print(f"Processing {generation_type} generation scenarios...")
    for hydro_year, scenario_year, electrolyser_type in scenarios:
        process_scenario(hydro_year, electrolyser_type, scenario_year, generation_type)
    print("Done!")

if __name__ == "__main__":
    generation_type = 'total'  # 'total' or 'net'
    main(generation_type)
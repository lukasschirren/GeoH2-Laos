# -*- coding: utf-8 -*-
"""
Created on Sun Feb 26 11:47:57 2023

@author: Claire Halloran, University of Oxford

Includes code from Nicholas Salmon, University of Oxford, for optimizing
hydrogen plant capacity.

"""

from osgeo import gdal
import atlite
import geopandas as gpd
import pypsa
import matplotlib.pyplot as plt
import pandas as pd
import cartopy.crs as ccrs
import p_H2_aux as aux
from functions import CRF
import numpy as np
import logging
import time

import xarray as xr
from scipy.constants import physical_constants
import pickle
# import warnings

# # Suppress warnings
# warnings.filterwarnings("ignore")

logging.basicConfig(level=logging.ERROR)

def assign_zones_to_plants(plants_gdf, areas_gdf, zone_column="Area_new24"):
    """
    Assign zones to hydropower plants based on their spatial location.

    Args:
        plants_gdf (GeoDataFrame): GeoDataFrame containing hydropower plant locations.
        areas_gdf (GeoDataFrame): GeoDataFrame containing zone polygons with the `zone_column`.
        zone_column (str): Column name in `areas_gdf` representing zones.

    Returns:
        GeoDataFrame: Updated plants GeoDataFrame with assigned zones.
    """
    # Ensure both GeoDataFrames have the same CRS
    plants_gdf = plants_gdf.to_crs(areas_gdf.crs)

    # Perform spatial join to assign zones
    plants_with_zones = gpd.sjoin(plants_gdf, areas_gdf[[zone_column, "geometry"]], how="left", predicate="intersects")

    # Drop duplicate geometry columns if any
    plants_with_zones = plants_with_zones.drop(columns=["index_right"])

    return plants_with_zones

def hydropower_potential(eta,flowrate,head):
    '''
    Calculate hydropower potential in Megawatts

    Parameters
    ----------
    eta : float
        Efficiency of the hydropower plant.
    flowrate : float
        Flowrate calculated with runoff multiplied by the hydro-basin area, in cubic meters per hour.
    head : float
        Height difference at the hydropower site, in meters.

    Returns
    -------
    float
        Hydropower potential in Megawatts (MW).
    '''
    rho = 997 # kg/m3; Density of water
    g = physical_constants['standard acceleration of gravity'][0] # m/s2; Based on the CODATA constants 2018
    Q = (flowrate/(1000/24)) / 3600 # transform flowrate per h into flowrate per second
    return (eta * rho * g * Q * head) / (1000 * 1000) # MW

def hydropower_potential_with_capacity(flowrate, head, capacity, eta):
    '''
    Calculate the hydropower potential considering the capacity limit

    Parameters
    ----------
    flowrate : float
        Flowrate calculated with runoff multiplied by the hydro-basin area, in cubic meters per hour.
    head : float
        Height difference at the hydropower site, in meters.
    capacity : float
        Maximum hydropower capacity in Megawatts (MW).
    eta : float
        Efficiency of the hydropower plant.

    Returns
    -------
    xarray DataArray
        Capacity factor, which is the limited potential divided by the capacity.
    '''
    potential = hydropower_potential(flowrate, head, eta)
    limited_potential = xr.where(potential > capacity, capacity, potential)
    capacity_factor = limited_potential / capacity
    return capacity_factor

def calculate_net_generation(absolute_generation, zone_profiles, plants_with_zones, zone_column):
    """
    Distribute zone-specific hourly demand across plants within each zone,
    and subtract demand from the plants' absolute generation.

    Parameters:
        absolute_generation (xr.DataArray): Absolute generation (MW) for all plants (plants x time).
        zone_profiles (dict): Dictionary mapping zones to their expanded hourly load profiles.
        plants_with_zones (gpd.GeoDataFrame): Plant data with assigned zones and other attributes.
        zone_column (str): Column name in `plants_with_zones` indicating plant zone (e.g., 'north', 'centre', 'south').

    Returns:
        xr.DataArray: Net hourly generation values (plants x time).
    """
    # Create a copy for net generation
    net_generation = absolute_generation.copy()

    # Iterate over each zone
    for zone, hourly_zone_demand in zone_profiles.items():
        # Filter plants belonging to the current zone
        plants_in_zone = plants_with_zones[plants_with_zones[zone_column] == zone]
        plants_in_zone_indices = plants_in_zone.index.tolist()

        if not plants_in_zone_indices:
            continue  # Skip if no plants in the zone

        # Select absolute generation for the plants in the current zone
        zone_generation = absolute_generation.sel(plant=plants_in_zone_indices)

        # Calculate the total hourly generation for the zone
        total_hourly_generation = zone_generation.sum(dim="plant")
        # Avoid division by zero: replace zeros with NaN temporarily
        total_hourly_generation = total_hourly_generation.where(total_hourly_generation != 0, other=np.nan)

        # Distribute demand among plants in the zone based on their hourly generation share
        for plant_index in plants_in_zone_indices:
            # Fractional demand based on hourly generation share
            fractional_demand = (
                (zone_generation.sel(plant=plant_index) / total_hourly_generation) * hourly_zone_demand.values
            )

            # Replace NaN values in fractional_demand with 0
            fractional_demand = fractional_demand.fillna(0)

            # Subtract demand from the plant's generation
            net_generation.loc[dict(plant=plant_index)] -= fractional_demand
    
    return net_generation


#########################################################################################################

# Sizing of electrolysers will need to be based on the average excess electricity available in each time slice
# Input: Minimum load factor of the elctrolyser
def demand_schedule(quantity, transport_state, transport_excel_path,
                             weather_excel_path):
    '''
    calculates hourly hydrogen demand for truck shipment and pipeline transport.

    Parameters
    ----------
    quantity : float
        annual amount of hydrogen to transport in kilograms.
    transport_state : string
        state hydrogen is transported in, one of '500 bar', 'LH2', 'LOHC', or 'NH3'.
    transport_excel_path : string
        path to transport_parameters.xlsx file
    weather_excel_path : string
        path to transport_parameters.xlsx file
            
    Returns
    -------
    trucking_hourly_demand_schedule : pandas DataFrame
        hourly demand profile for hydrogen trucking.
    pipeline_hourly_demand_schedule : pandas DataFrame
        hourly demand profile for pipeline transport.
    '''
    transport_parameters = pd.read_excel(transport_excel_path,
                                         sheet_name = transport_state,
                                         index_col = 'Parameter'
                                         ).squeeze('columns')
    weather_parameters = pd.read_excel(weather_excel_path,
                                       index_col = 'Parameters',
                                       ).squeeze('columns')
    truck_capacity = transport_parameters['Net capacity (kg H2)']
    start_date = "2023/01/01"
    end_date = "2024/01/01" # Not inclusive

    # Adjust capacity based on excess
    # schedule for trucking
    annual_deliveries = quantity/truck_capacity
    quantity_per_delivery = quantity/annual_deliveries
    index = pd.date_range(start_date, end_date, periods=annual_deliveries)
    trucking_demand_schedule = pd.DataFrame(quantity_per_delivery, index=index, columns = ['Demand'])
    trucking_hourly_demand_schedule = trucking_demand_schedule.resample('h').sum().fillna(0.)

    # schedule for pipeline
    index = pd.date_range(start_date, end_date, freq = 'h')
    pipeline_hourly_quantity = quantity/index.size
    pipeline_hourly_demand_schedule = pd.DataFrame(pipeline_hourly_quantity, index=index,  columns = ['Demand'])

    return trucking_hourly_demand_schedule, pipeline_hourly_demand_schedule

def optimize_hydrogen_plant(wind_potential, pv_potential, hydro_potential, times, demand_profile, 
                            wind_max_capacity, pv_max_capacity, hydro_max_capacity,
                            country_series, water_limit=None):
    '''
    Optimizes the size of green hydrogen plant components based on renewable potential, hydrogen demand, and country parameters. 

    Parameters
    ----------
    wind_potential : xarray DataArray
        1D dataarray of per-unit wind potential in hexagon.
    pv_potential : xarray DataArray
        1D dataarray of per-unit solar potential in hexagon.
    times : xarray DataArray
        1D dataarray with timestamps for wind and solar potential.
    demand_profile : pandas DataFrame
        hourly dataframe of hydrogen demand in kg.
    country_series : pandas Series
        interest rate and lifetime information.
    water_limit : float, optional
        annual limit on water available for electrolysis in hexagon, in cubic meters. Default is None.
    hydro_potential : xarray DataArray, optional
        1D dataarray of per-unit hydro potential in hexagon. Default is None.
    hydro_max_capacity : float, optional
        maximum hydro capacity in MW. Default is None.

    Returns
    -------
    lcoh : float
        levelized cost per kg hydrogen.
    wind_capacity: float
        optimal wind capacity in MW.
    solar_capacity: float
        optimal solar capacity in MW.
    hydro_capacity: float
        optimal hydro capacity in MW.
    electrolyzer_capacity: float
        optimal electrolyzer capacity in MW.
    battery_capacity: float
        optimal battery storage capacity in MW/MWh (1 hour batteries).
    h2_storage: float
        optimal hydrogen storage capacity in MWh.
    '''
   
    # if a water limit is given, check if hydrogen demand can be met
    if water_limit != None:
        # total hydrogen demand in kg
        total_hydrogen_demand = demand_profile['Demand'].sum()
        # check if hydrogen demand can be met based on hexagon water availability
        water_constraint =  total_hydrogen_demand <= water_limit * 111.57 # kg H2 per cubic meter of water
        if water_constraint == False:
            print('Not enough water to meet hydrogen demand!')
            # return null values
            lcoh = np.nan
            wind_capacity = np.nan
            solar_capacity = np.nan
            hydro_capacity = np.nan
            electrolyzer_capacity = np.nan
            battery_capacity = np.nan
            h2_storage = np.nan
            return lcoh, wind_capacity, solar_capacity, hydro_capacity, electrolyzer_capacity, battery_capacity, h2_storage

    # Set up network
    n = pypsa.Network(override_component_attrs=aux.create_override_components())
    n.set_snapshots(times)

    # Import the design of the H2 plant into the network
    n.import_from_csv_folder(f"Parameters_{electrolyser_type}_{scenario_year}/Basic_H2_plant")

    # Import demand profile
    # Note: All flows are in MW or MWh, conversions for hydrogen done using HHVs. Hydrogen HHV = 39.4 MWh/t
    n.add('Load', 'Hydrogen demand', bus='Hydrogen', p_set=demand_profile['Demand'] / 1000 * 39.4)

    # Send the weather data to the model
    n.generators_t.p_max_pu['Wind'] = wind_potential
    n.generators_t.p_max_pu['Solar'] = pv_potential
    n.generators_t.p_max_pu['Hydro'] = hydro_potential

    # Specify maximum capacity based on land use
    n.generators.loc['Hydro', 'p_nom_max'] = hydro_max_capacity
    n.generators.loc['Wind', 'p_nom_max'] = wind_max_capacity * 2  # Rated power - here 2 MW
    n.generators.loc['Solar', 'p_nom_max'] = pv_max_capacity * 1  # Power per node - here 1 MW

    # Specify technology-specific and country-specific WACC and lifetime
    n.generators.loc['Hydro', 'capital_cost'] *= CRF(country_series['Hydro interest rate'], 
                                                    country_series['Hydro lifetime'])
    n.generators.loc['Wind', 'capital_cost'] *= CRF(country_series['Wind interest rate'], 
                                                    country_series['Wind lifetime (years)'])
    n.generators.loc['Solar', 'capital_cost'] *= CRF(country_series['Solar interest rate'], 
                                                     country_series['Solar lifetime (years)'])
    for item in [n.links, n.stores, n.storage_units]:
        item.capital_cost = item.capital_cost * CRF(country_series['Plant interest rate'], country_series['Plant lifetime (years)'])

    # Solve the model with unit commitment
    solver = 'gurobi'
    n.lopf(solver_name=solver,
           solver_options={'LogToConsole': 0, 'OutputFlag': 0},
           pyomo=True,  # Enable Pyomo for unit commitment
           extra_functionality=aux.extra_functionalities)

    # Output results
    lcoh = n.objective / (n.loads_t.p_set.sum().iloc[0] / 39.4 * 1000)  # Convert back to kg H2
    wind_capacity = n.generators.p_nom_opt['Wind']
    solar_capacity = n.generators.p_nom_opt['Solar']
    hydro_capacity = n.generators.p_nom_opt.get('Hydro', np.nan)  # Get hydro capacity if it exists
    electrolyzer_capacity = n.links.p_nom_opt['Electrolysis'] 
    battery_capacity = n.storage_units.p_nom_opt.get('Battery', np.nan)
    h2_storage = n.stores.e_nom_opt.get('Compressed H2 Store', np.nan)
    print(lcoh)
    return lcoh, wind_capacity, solar_capacity, hydro_capacity, electrolyzer_capacity, battery_capacity, h2_storage


if __name__ == "__main__":
    
    scenario_year = "25" # 25 30
    electrolyser_type = "ALK" # ALK PEM
    
    transport_excel_path = "Parameters/transport_parameters.xlsx"
    weather_excel_path = "Parameters/weather_parameters.xlsx"
    country_excel_path = 'Parameters/country_parameters.xlsx'
    country_parameters = pd.read_excel(country_excel_path,
                                        index_col='Country')
    demand_excel_path = f'Parameters_{electrolyser_type}_{scenario_year}/demand_parameters.xlsx'
    demand_parameters = pd.read_excel(demand_excel_path,
                                      index_col='Demand center',
                                      ).squeeze("columns")
    demand_centers = demand_parameters.index
    # weather_parameters = pd.read_excel(weather_excel_path,
    #                                    index_col = 'Parameters'
    #                                    ).squeeze('columns')

    hexagons = gpd.read_file(f'Parameters_{electrolyser_type}_{scenario_year}/hex_transport.geojson')
    # !!! change to name of cutout in weather
    cutout = atlite.Cutout('Cutouts_atlite/Laos1Y.nc')
    layout = cutout.uniform_layout()
    
    ###############################################################
    # Added for hydropower / Load data
    gdf_areas = gpd.read_file(r'Parameters\areas_laos.geojson')
    
    with open(f"Parameters/zone_profiles_{scenario_year}.pkl", "rb") as f:
        zone_profiles = pickle.load(f)
    zone_demand = pd.DataFrame(zone_profiles)
    
    location_hydro = gpd.read_file(f'Data_{scenario_year}/hydropower_dams_{scenario_year}.gpkg')
    location_hydro.rename(columns={'Latitude': 'lat', 'Longitude': 'lon'}, inplace=True)
    location_hydro['geometry'] = gpd.points_from_xy(location_hydro.lon, location_hydro.lat)
    
    location_hydro = assign_zones_to_plants(location_hydro, gdf_areas)
    
    runoff = xr.open_dataarray(f'Cutouts_atlite/Laos5AVG_Runoff_{scenario_year}.nc')
    
    ### Actual calculation 
    eta = 0.75 # efficiency of hydropower plant

    capacity_factor = xr.apply_ufunc(
        hydropower_potential_with_capacity,
        runoff,
        xr.DataArray(location_hydro['head'].values, dims=['plant']),
        xr.DataArray(location_hydro['Total capacity (MW)'].values, dims=['plant']), # Take total capacity to calculate the capacity factor, but domestic to multiply in Hexagons
        eta,
        vectorize=True,
        dask='parallelized',  # Dask for parallel computation
        output_dtypes=[float]
    )

    # Rename existing 'index_left' and 'index_right' columns if they exist
    if 'index_left' in location_hydro.columns:
        location_hydro = location_hydro.rename(columns={'index_left': 'index_left_renamed'})
    if 'index_right' in location_hydro.columns:
        location_hydro = location_hydro.rename(columns={'index_right': 'index_right_renamed'})
    if 'index_left' in hexagons.columns:
        hexagons = hexagons.rename(columns={'index_left': 'index_left_renamed'})
    if 'index_right' in hexagons.columns:
        hexagons = hexagons.rename(columns={'index_right': 'index_right_renamed'})

    hydro_hex_mapping = gpd.sjoin(location_hydro, hexagons, how='left', predicate='within')
    hydro_hex_mapping['plant_index'] = hydro_hex_mapping.index
    
    num_hexagons = len(hexagons)
    num_time_steps = len(capacity_factor.time)
    
    absolute_generation = capacity_factor * xr.DataArray(
        location_hydro['Domestic Capacity (MW)'].values, dims=['plant']
    )
    
    net_generation = calculate_net_generation(
        absolute_generation=absolute_generation,
        zone_profiles=zone_demand,
        plants_with_zones=location_hydro,
        zone_column="Area_new24"
    )
    
    hydro_profile = xr.DataArray(
        data=np.zeros((num_hexagons, num_time_steps)),
        dims=['hexagon', 'time'],
        coords={'hexagon': np.arange(num_hexagons), 'time': capacity_factor.time}
    )
    
    
    # Loop over hexagons
    for hex_index in range(num_hexagons):
        # Get plants in the current hexagon
        plants_in_hex = hydro_hex_mapping[hydro_hex_mapping["index_right"] == hex_index]["plant_index"].tolist()
        
        if len(plants_in_hex) > 0:
            # Select net generation and plant capacities for these plants
            hex_net_generation = net_generation.sel(plant=plants_in_hex)
            plant_capacities = xr.DataArray(
                location_hydro.loc[plants_in_hex]["Domestic Capacity (MW)"].values,
                dims=["plant"]
            )
            # Calculate capacity factor as net generation / plant capacity
            capacity_factor_hex = hex_net_generation / plant_capacities
            
            # Ensure capacity factor is within [0, 1]
            capacity_factor_hex = xr.where(capacity_factor_hex > 1, 1, capacity_factor_hex)
            capacity_factor_hex = xr.where(capacity_factor_hex < 0, 0, capacity_factor_hex)

            # Weighted average capacity factor for the hexagon
            weights = plant_capacities / plant_capacities.sum()
            weighted_avg_capacity_factor = (capacity_factor_hex * weights).sum(dim="plant")
            hydro_profile.loc[dict(hexagon=hex_index)] = weighted_avg_capacity_factor
    

    ###############################################################

    # pv_profile = cutout.pv(
    #     panel= 'CSi',
    #     orientation='latitude_optimal',
    #     layout = layout,
    #     shapes = hexagons,
    #     per_unit = True
    #     )
    # pv_profile = pv_profile.rename(dict(dim_0='hexagon'))
    pv_profile = xr.open_dataarray("Cutouts_atlite/Laos5AVG_pv.nc")

    # wind_profile = cutout.wind(
    #     # Changed turbine type - was Vestas_V80_2MW_gridstreamer in first run
    #     # Other option being explored: NREL_ReferenceTurbine_2020ATB_4MW, Enercon_E126_7500kW
    #     turbine = 'Vestas_V80_2MW_gridstreamer',
    #     layout = layout,
    #     shapes = hexagons,
    #     per_unit = True
    #     )
    # wind_profile = wind_profile.rename(dict(dim_0='hexagon'))
    wind_profile = xr.open_dataarray("Cutouts_atlite/Laos5AVG_wind.nc")


# wind_potential, pv_potential, hydro_potential, times, demand_profile, 
# wind_max_capacity, pv_max_capacity, hydro_max_capacity,
# country_series, water_limit=None

    for location in demand_centers:
        # Trucking optimization
        lcohs_trucking = np.zeros(len(pv_profile.hexagon))
        solar_capacities = np.zeros(len(pv_profile.hexagon))
        wind_capacities = np.zeros(len(pv_profile.hexagon))
        hydro_capacities = np.zeros(len(pv_profile.hexagon))
        electrolyzer_capacities = np.zeros(len(pv_profile.hexagon))
        battery_capacities = np.zeros(len(pv_profile.hexagon))
        h2_storages = np.zeros(len(pv_profile.hexagon))
        start = time.process_time()
        
        for hexagon in pv_profile.hexagon.data:
            hydrogen_demand_trucking, _ = demand_schedule(
                demand_parameters.loc[location,'Annual demand [kg/a]'],
                hexagons.loc[hexagon,f'{location} trucking state'],
                transport_excel_path,
                weather_excel_path)
            country_series = country_parameters.loc[hexagons.country[hexagon]]
            lcoh, wind_capacity, solar_capacity, hydro_capacity, electrolyzer_capacity, battery_capacity, h2_storage =\
                optimize_hydrogen_plant(wind_profile.sel(hexagon = hexagon),
                                    pv_profile.sel(hexagon = hexagon),
                                    hydro_profile.sel(hexagon = hexagon),
                                    wind_profile.time,
                                    hydrogen_demand_trucking,
                                    hexagons.loc[hexagon,'theo_turbines'],
                                    hexagons.loc[hexagon,'theo_pv'],
                                    hexagons.loc[hexagon,'hydro'],
                                    country_series,
                                    # water_limit = hexagons.loc[hexagon,'delta_water_m3']
                                    )
            lcohs_trucking[hexagon] = lcoh
            solar_capacities[hexagon] = solar_capacity
            wind_capacities[hexagon] = wind_capacity
            hydro_capacities[hexagon] = hydro_capacity
            electrolyzer_capacities[hexagon] = electrolyzer_capacity
            battery_capacities[hexagon] = battery_capacity
            h2_storages[hexagon] = h2_storage
        trucking_time = time.process_time()-start

        hexagons[f'{location} trucking solar capacity'] = solar_capacities
        hexagons[f'{location} trucking wind capacity'] = wind_capacities
        hexagons[f'{location} trucking hydro capacity'] = hydro_capacities
        hexagons[f'{location} trucking electrolyzer capacity'] = electrolyzer_capacities
        hexagons[f'{location} trucking battery capacity'] = battery_capacities
        hexagons[f'{location} trucking H2 storage capacity'] = h2_storages
        hexagons[f'{location} trucking production cost'] = lcohs_trucking

        print(f"Trucking optimization for {location} completed in {trucking_time} s")

        # Pipeline optimization
        lcohs_pipeline = np.zeros(len(pv_profile.hexagon))
        solar_capacities = np.zeros(len(pv_profile.hexagon))
        wind_capacities = np.zeros(len(pv_profile.hexagon))
        hydro_capacities = np.zeros(len(pv_profile.hexagon))
        electrolyzer_capacities = np.zeros(len(pv_profile.hexagon))
        battery_capacities = np.zeros(len(pv_profile.hexagon))
        h2_storages = np.zeros(len(pv_profile.hexagon))
        start = time.process_time()

        for hexagon in pv_profile.hexagon.data:
            _, hydrogen_demand_pipeline = demand_schedule(
                demand_parameters.loc[location,'Annual demand [kg/a]'],
                hexagons.loc[hexagon,f'{location} trucking state'],
                transport_excel_path,
                weather_excel_path)
            country_series = country_parameters.loc[hexagons.country[hexagon]]
            lcoh, wind_capacity, solar_capacity, hydro_capacity, electrolyzer_capacity, battery_capacity, h2_storage =\
                optimize_hydrogen_plant(wind_profile.sel(hexagon = hexagon),
                                    pv_profile.sel(hexagon = hexagon),
                                    hydro_profile.sel(hexagon = hexagon),
                                    wind_profile.time,
                                    hydrogen_demand_pipeline,
                                    hexagons.loc[hexagon,'theo_turbines'],
                                    hexagons.loc[hexagon,'theo_pv'],
                                    hexagons.loc[hexagon,'hydro'],
                                    country_series,
                                    # water_limit = hexagons.loc[hexagon,'delta_water_m3']
                                    )
            lcohs_pipeline[hexagon] = lcoh
            solar_capacities[hexagon] = solar_capacity
            wind_capacities[hexagon] = wind_capacity
            hydro_capacities[hexagon] = hydro_capacity
            electrolyzer_capacities[hexagon] = electrolyzer_capacity
            battery_capacities[hexagon] = battery_capacity
            h2_storages[hexagon] = h2_storage

        pipeline_time = time.process_time() - start

        hexagons[f'{location} pipeline solar capacity'] = solar_capacities
        hexagons[f'{location} pipeline wind capacity'] = wind_capacities
        hexagons[f'{location} pipeline hydro capacity'] = hydro_capacities
        hexagons[f'{location} pipeline electrolyzer capacity'] = electrolyzer_capacities
        hexagons[f'{location} pipeline battery capacity'] = battery_capacities
        hexagons[f'{location} pipeline H2 storage capacity'] = h2_storages
        hexagons[f'{location} pipeline production cost'] = lcohs_pipeline

        print(f"Pipeline optimization for {location} completed in {pipeline_time} s")

    hexagons.to_file(f'Resources/Scenario_atlite_{electrolyser_type}_{scenario_year}/hex_lcoh.geojson', driver='GeoJSON', encoding='utf-8')
    # hexagons.to_file('Resources/hex_lcoh_base_case.geojson', driver='GeoJSON', encoding='utf-8')
    
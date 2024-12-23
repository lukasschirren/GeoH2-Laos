#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Mar 26 16:52:59 2023

@author: Claire Halloran, University of Oxford
Contains code originally written by Leander MÃ¼ller, RWTH Aachen University

Calculates the cost-optimal hydrogen transportation strategy to the nearest demand center.

Calculate cost of pipeline transport and demand profile based on optimal size



"""

import geopandas as gpd
import numpy as np
import pandas as pd
from functions import CRF, cheapest_trucking_strategy, h2_conversion_stand, cheapest_pipeline_strategy
from shapely.geometry import Point
import shapely.geometry
import shapely.wkt
import geopy.distance
import os
import json

#%% Data Input

scenario_year = "25" # 25 30
electrolyser_type = "ALK" # ALK PEM

# Excel file with technology parameters
technology_parameters = "Parameters/technology_parameters.xlsx"
demand_parameters = f'Parameters_{electrolyser_type}_{scenario_year}/demand_parameters.xlsx'
country_excel_path = 'Parameters/country_parameters.xlsx'

#%% load data from technology parameters Excel file

infra_data = pd.read_excel(technology_parameters,
                           sheet_name='Infra',
                           index_col='Infrastructure')

global_data = pd.read_excel(technology_parameters,
                            sheet_name='Global',
                            index_col='Parameter'
                            ).squeeze("columns")

water_data = pd.read_excel(technology_parameters,
                            sheet_name='Water',
                            index_col='Parameter'
                            ).squeeze("columns")
demand_center_list = pd.read_excel(demand_parameters,
                                   sheet_name='Demand centers',
                                   index_col='Demand center',
                                   )
country_parameters = pd.read_excel(country_excel_path,
                                    index_col='Country')

pipeline_construction = global_data['Pipeline construction allowed']
road_construction = global_data['Road construction allowed']

road_capex_long = infra_data.at['Long road','CAPEX']            #â¬/km from John Hine, converted to Euro (Assumed earth to paved road)
road_capex_short = infra_data.at['Short road','CAPEX']         #â¬/km for raods < 10 km, from John Hine, converted to Euro (Assumed earth to paved road)
road_opex = infra_data.at['Short road','OPEX']                 #â¬/km/year from John Hine, converted to Euro (Assumed earth to paved road)

# Handle any hexagons at edges in the geojson which are labelled with a country we aren't analyzing

# Read the GeoJSON file
with open(f'Data_{scenario_year}/hexagons_with_country.geojson', 'r') as file:
    data = json.load(file)

# If the country of any hexagon is not in the country_parameters file, set the country to "Other" instead
for feature in data['features']:
    # Access and modify properties
    if not feature['properties']['country'] in list(country_parameters.index.values):
        feature['properties']['country'] = "Other"

# Write the modified GeoJSON back to the file
with open(f'Data_{scenario_year}/hexagons_with_country.geojson', 'w') as file:
    json.dump(data, file)

# Now, load the Hexagon file in geopandas
hexagon = gpd.read_file(f'Data_{scenario_year}/hexagons_with_country.geojson')

# Create Resources folder to save results if it doesn't already exist
if not os.path.exists('Resources'):
    os.makedirs('Resources')

#%% calculate cost of hydrogen state conversion and transportation for demand
# loop through all demand centers-- limit this on continential scale
for d in demand_center_list.index:
    demand_location = Point(demand_center_list.loc[d,'Lat [deg]'], demand_center_list.loc[d,'Lon [deg]'])
    distance_to_demand = np.empty(len(hexagon))
    hydrogen_quantity = demand_center_list.loc[d,'Annual demand [kg/a]']
    road_construction_costs = np.empty(len(hexagon))
    trucking_states = np.empty(len(hexagon),dtype='<U10')
    trucking_costs = np.empty(len(hexagon))
    pipeline_costs = np.empty(len(hexagon))
    demand_state = demand_center_list.loc[d,'Demand state']
    demand_fid = 0
    if demand_state not in ['500 bar','LH2','NH3']:
        raise NotImplementedError(f'{demand_state} demand not supported.')

# label demand location under consideration
    for i in range(len(hexagon)):
        if hexagon['geometry'][i].contains(demand_location) == True:
            demand_fid = i

    for i in range(len(hexagon)):
        # calculate distance to demand for each hexagon
        poly = shapely.wkt.loads(str(hexagon['geometry'][i]))
        center = poly.centroid
        demand_coords = (demand_center_list.loc[d,'Lat [deg]'], demand_center_list.loc[d,'Lon [deg]'])
        hexagon_coords = (center.y, center.x)
        dist = geopy.distance.geodesic(demand_coords, hexagon_coords).km
        
        distance_to_demand[i] = dist

        #!!! maybe this is the place to set a restriction based on distance to demand center-- for all hexagons with a distance below some cutoff point
        # label demand location under consideration
        if hexagon['geometry'][i].contains(demand_location) == True:
            # demand_fid = i
            # calculate cost of converting hydrogen to ammonia for local demand (i.e. no transport)
            if demand_state == 'NH3':
            # !!! where are the 0.03 values coming from? it's the cost of heat in unknown units
                local_conversion_cost = h2_conversion_stand(demand_state+'_load',
                                                            hydrogen_quantity,
                                                            country_parameters.loc['Electricity price (USD/kWh)',hexagon.country[i]],
                                                            country_parameters.loc['Heat price (USD/kWh)',hexagon.country[i]],
                                                            country_parameters.loc[hexagon['country'][i],'Plant interest rate']
                                                            )[2]/hydrogen_quantity
                
                trucking_costs.append(local_conversion_cost)
                pipeline_costs.append(local_conversion_cost)
            else:
                local_conversion_cost = h2_conversion_stand(demand_state,
                                     hydrogen_quantity,
                                     country_parameters.loc['Electricity price (USD/kWh)',hexagon.country[i]],
                                     country_parameters.loc['Heat price (USD/kWh)',hexagon.country[i]],
                                     country_parameters.loc[hexagon['country'][i],'Plant interest rate']
                                     )[2]/hydrogen_quantity
                trucking_costs.append(local_conversion_cost)
                pipeline_costs.append(local_conversion_cost)
        # determine elec_cost at demand to determine potential energy costs
        # elec_costs_at_demand = float(hexagon['cheapest_elec_cost'][demand_fid])/1000
        # calculate cost of constructing a road to each hexagon
        if road_construction == True:
            if hexagon['road_dist'][i]==0:
                road_construction_costs[i] = 0.
            elif hexagon['road_dist'][i]!=0 and hexagon['road_dist'][i]<10:
                road_construction_costs[i] = hexagon['road_dist'][i]\
                    *road_capex_short*CRF(
                        country_parameters.loc[hexagon['country'][i],'Infrastructure interest rate'],
                        country_parameters.loc[hexagon['country'][i],'Infrastructure lifetime (years)'])\
                    +hexagon['road_dist'][i]*road_opex
            else:
                road_construction_costs[i] = hexagon['road_dist'][i]*road_capex_long*CRF(
                    country_parameters.loc[hexagon['country'][i],'Infrastructure interest rate'],
                    country_parameters.loc[hexagon['country'][i],'Infrastructure lifetime (years)'])\
                +hexagon['road_dist'][i]*road_opex
                
            trucking_cost, trucking_state = cheapest_trucking_strategy(demand_state,
                                                                       hydrogen_quantity,
                                                                       distance_to_demand[i],
                                                                       country_parameters.loc[hexagon.country[i],'Electricity price (USD/kWh)'],
                                                                       country_parameters.loc[hexagon.country[i],'Heat price (USD/kWh)'],
                                                                       country_parameters.loc[hexagon['country'][i],'Infrastructure interest rate'],
                                                                       country_parameters.loc[hexagon.country[demand_fid],'Electricity price (USD/kWh)'],
                                                                       )
            trucking_costs[i] = trucking_cost
            trucking_states[i] = trucking_state

        elif hexagon['road_dist'][i]==0:
            trucking_cost, trucking_state = cheapest_trucking_strategy(demand_state,
                                                                       hydrogen_quantity,
                                                                       distance_to_demand[i],
                                                                       country_parameters.loc[hexagon.country[i],'Electricity price (USD/kWh)'],
                                                                       country_parameters.loc[hexagon.country[i],'Heat price (USD/kWh)'],
                                                                       country_parameters.loc[hexagon['country'][i],'Infrastructure interest rate'],
                                                                       country_parameters.loc[hexagon.country[demand_fid],'Electricity price (USD/kWh)'],
                                                                       )
            trucking_costs[i] = trucking_cost
            trucking_states[i] = trucking_state

        elif hexagon['road_dist'][i]>0: 
            trucking_costs[i] = np.nan
            trucking_states[i] = np.nan
        # pipeline costs
        if pipeline_construction== True:
        
            pipeline_cost, pipeline_type = cheapest_pipeline_strategy(demand_state,
                                                                      hydrogen_quantity,
                                                                      distance_to_demand[i],
                                                                    country_parameters.loc[hexagon.country[i],'Electricity price (USD/kWh)'],
                                                                    country_parameters.loc[hexagon.country[i],'Heat price (USD/kWh)'],
                                                                    country_parameters.loc[hexagon['country'][i],'Infrastructure interest rate'],
                                                                    country_parameters.loc[hexagon.country[demand_fid],'Electricity price (USD/kWh)'],
                                                                      )
            pipeline_costs[i] = pipeline_cost
        else:
            pipeline_costs[i] = np.nan

    # variables to save for each demand scenario
    hexagon[f'{d} road construction costs'] = road_construction_costs/hydrogen_quantity
    hexagon[f'{d} trucking transport and conversion costs'] = trucking_costs # cost of road construction, supply conversion, trucking transport, and demand conversion
    hexagon[f'{d} trucking state'] = trucking_states # cost of road construction, supply conversion, trucking transport, and demand conversion
    hexagon[f'{d} pipeline transport and conversion costs'] = pipeline_costs # cost of supply conversion, pipeline transport, and demand conversion

# Added force to UTF-8 encoding.
hexagon.to_file(f'Parameters_{electrolyser_type}_{scenario_year}/hex_transport.geojson', driver='GeoJSON', encoding='utf-8')


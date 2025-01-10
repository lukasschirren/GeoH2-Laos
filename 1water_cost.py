#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Apr  5 13:26:19 2023

@author: Claire Halloran, University of Oxford

Water costs for hydrogen production in each hexagon


"""

import geopandas as gpd
import pandas as pd
import numpy as np

hydro_year = "atlite" # wet dry atlite
scenario_year = "30" # 25 30
electrolyser_type = "ALK" # ALK PEM

hexagons = gpd.read_file(f'Resources/Scenario_{hydro_year}_{electrolyser_type}_{scenario_year}/hex_lcoh.geojson')
technology_parameters = "Parameters/technology_parameters.xlsx"
country_excel_path = 'Parameters/country_parameters.xlsx'

water_data = pd.read_excel(technology_parameters,
                            sheet_name='Water',
                            index_col='Parameter'
                            ).squeeze("columns")
country_parameters = pd.read_excel(country_excel_path,
                                    index_col='Country')

#%% water cost for each hexagon for each kg hydrogen produced

h2o_costs_dom_water_bodies = np.empty(len(hexagons))
h2o_costs_ocean = np.empty(len(hexagons))
h2o_costs = np.empty(len(hexagons))

electricity_demand_h2o_treatment = water_data['Freshwater treatment electricity demand (kWh/m3)']
# Remove ocen water costs (landlocked)
electricity_demand_h2o_ocean_treatment = water_data['Ocean water treatment electricity demand (kWh/m3)']
water_transport_costs = water_data['Water transport cost (USD/100 km/m3)']
water_spec_cost = water_data['Water specific cost (USD/m3)']
water_demand = water_data['Water demand  (L/kg H2)']

for i in range(len(hexagons)):
    h2o_costs_dom_water_bodies[i] =(water_spec_cost 
                                        + (water_transport_costs/100)*min(hexagons['waterbody_dist'][i],
                                                                          hexagons['waterway_dist'][i]) 
                                        + electricity_demand_h2o_treatment*\
                                            country_parameters.loc[hexagons.country[i],'Electricity price (USD/kWh)']
                                        )*water_demand/1000
    h2o_costs_ocean[i] =(water_spec_cost 
                             #+ (water_transport_costs/100)*hexagons['ocean_dist'][i] 
                             + electricity_demand_h2o_ocean_treatment*\
                                 country_parameters.loc[hexagons.country[i],'Electricity price (USD/kWh)']
                             )*water_demand/1000
    h2o_costs[i] = min(h2o_costs_dom_water_bodies[i],h2o_costs_ocean[i])

# Remove ocean water costs (landlocked)
hexagons['Ocean water costs'] = h2o_costs_ocean
hexagons['Freshwater costs'] = h2o_costs_dom_water_bodies
hexagons['Lowest water cost'] = h2o_costs

hexagons.to_file(f'Resources/Scenario_{hydro_year}_{electrolyser_type}_{scenario_year}/hex_water.geojson', driver='GeoJSON', encoding='utf-8')



# %%
from statistics import mode
from unicodedata import name
import numpy as np
from numpy import sort
import pandas as pd
import matplotlib.pyplot as plt
import altair as alt
from sqlalchemy import values
import datapane as dp
dp.login(token='fe7f5674e813c8a7739d1b5171c3c01e6299bf6f')
import datetime as dt


pd.set_option("display.precision", 2)

plant_2020=pd.read_csv('plant_gen_2020.csv',dtype={'Plant Code':str})
plant_history=pd.read_csv('plant_gen_history.csv',dtype={'Plant Code':str})

#%%Joining wind speed/NREL simulation data
nearest=pd.read_csv('nearest_sim.csv',dtype={'Plant Code':str})

plant_2020=plant_2020.merge(nearest,on='Plant Code',validate='1:1')
plant_history=plant_history.merge(nearest,on='Plant Code',validate='m:1')

#%%
plant_2020.drop(columns='Unnamed: 0',inplace=True)
plant_history.drop(columns='Unnamed: 0',inplace=True)

plant_2020=plant_2020.rename(columns={'Annual Net Gen':'2020 Net Generation (MWh)'})

plant_2020['Start of Operation']=pd.to_datetime(plant_2020['Start of Operation'],yearfirst=True)

plant_history['gen period']=pd.to_datetime(plant_history['gen period'],yearfirst=True)

plant_history=plant_history.rename(columns={'gen period':'Generation Period'})

#%% COMPUTING ANNUAL AND MONTHLY CAPACITY FACTORS


plant_2020['Annual Capacity Factor']=plant_2020['2020 Net Generation (MWh)']/(plant_2020['Nameplate Capacity (MW)']*8760)
plant_2020['Gen per Turbine']=plant_2020['2020 Net Generation (MWh)']/plant_2020['Number of Turbines']

plant_2020['Annual Capacity Factor']=np.where(plant_2020['Annual Capacity Factor']>1,np.nan,plant_2020['Annual Capacity Factor'])

plant_2020=plant_2020.sort_values(by=['State'])

plant_history['Monthly Capacity Factor']=plant_history['Net Gen']/(plant_history['Nameplate Capacity (MW)']*730)

plant_2020['Year']=plant_2020['Start of Operation'].dt.year

no_outliers=(plant_2020['Annual Capacity Factor']<.7)& (plant_2020['Annual Capacity Factor']>.05) & (plant_2020['Status']=='OP') & (plant_2020['Year']<2020)

plant_2020_trim=plant_2020[no_outliers]


# %% Grouping plants by state for monthly generation

plant_20_22_month=plant_history.query("year>=2020")
plant_20_22_month_state=plant_20_22_month.groupby('State',as_index=False)
plant_20_22_month_state=plant_20_22_month_state.agg({'Nameplate Capacity (MW)':sum,
                                                    'Number of Turbines':sum,
                                                    'Plant Code':'nunique',
                                                    'wind_speed':'median',
                                                    'Net Gen':sum,
                                                    'NERC Region':mode})
plant_20_22_month_state['Annual Capacity Factor']=plant_20_22_month_state['Net Gen']/(plant_20_22_month_state['Nameplate Capacity (MW)']*8760)

plant_20_22_month_state=plant_20_22_month_state.rename(columns={'NERC Region':'Predominant NERC Region','Plant Code':'Number of Plants'})


# %% Creating charts in Altair and uploading to Datapane
click = alt.selection_multi(fields=['State'])

alt_chart_plant = alt.Chart(plant_2020).mark_circle(size=60).encode(
    x='Nameplate Capacity (MW)',
    y='2020 Net Generation (MWh):Q',
    color='NERC Region',
    size='Number of Turbines',
    tooltip=['Plant Name:N','Utility Name:N','State','2020 Net Generation (MWh):Q','Number of Turbines','Predominant Turbine Manufacturer']
    ).properties(title='Plants by Generation and Capacity',
    width=1000,
    height=600
    ).transform_filter(click)

alt_chart_state = alt.Chart(plant_20_22_month_state).mark_bar().encode(
    x='Net Gen',
    y=alt.Y('State',sort='-x'),
    color=alt.condition(click,alt.value('steelblue'),alt.value('lightgray'))
    ).properties(title='States by Wind Generation',
    width=1000,
    height=600
    ).add_selection(click)

state_plant_chart=alt.vconcat(alt_chart_plant,alt_chart_state,data=plant_2020)


top10manuf = plant_2020['Predominant Turbine Manufacturer'].value_counts()[:5].index


plant_2020['Turbine Manufacturer']=plant_2020.loc[~plant_2020['Predominant Turbine Manufacturer'].isin(top10manuf),'Predominant Turbine Manufacturer'] = 'Other'


plants_by_manuf = alt.Chart(plant_2020).mark_bar().encode(
    alt.X('Start of Operation:T',timeUnit='year'),
    alt.Y('count(Plant Code)'),
    color='Predominant Turbine Manufacturer'
    ).properties(title='Number of Plants Built per Year and Turbine Manufacturer',
    width=1000,
    height=600
    )

cap_by_year=alt.Chart(plant_2020_trim).mark_circle().encode(
    alt.X('Start of Operation:T',timeUnit='year'),
    alt.Y('Annual Capacity Factor'),
    size='Nameplate Capacity (MW)',
    tooltip=['Plant Name:N','Utility Name:N','State','2020 Net Generation (MWh):Q','Number of Turbines','Predominant Turbine Manufacturer']
    ).properties(title='Plants by Age and 2020 Capacity Factor*',
    width=1000,
    height=600
    )

cap_by_year_line=alt.layer(
            cap_by_year,
            cap_by_year.transform_regression(on='Start of Operation',regression= 'Annual Capacity Factor').mark_line(
            )
)

cap_by_nerc=alt.Chart(plant_2020).mark_circle(
    opacity=.8,
    stroke='black',
    strokeWidth=1
).encode(
    alt.X('Annual Capacity Factor'),
    alt.Y('NERC Region'),
    alt.Size('Nameplate Capacity (MW)',
    scale=alt.Scale(range=[1,800])),
    alt.Color('NERC Region',legend=None)
).properties(title='Capacity Factor by NERC Region',
width=1000,
height=600
)

cap_by_BA=alt.Chart(plant_2020).mark_circle(
    opacity=.8,
    stroke='black',
    strokeWidth=1
).encode(
    alt.X('Annual Capacity Factor'),
    alt.Y('BA Code:N'),
    alt.Size('Nameplate Capacity (MW)',
    scale=alt.Scale(range=[1,800]))
).properties(title='Capacity Factor by NERC Region',
width=1000,
height=600
)

plant_history_ny=plant_history.query("State=='NY'")
plant_history_ny=plant_history_ny.query("year>=2010")

alt.data_transformers.disable_max_rows()

input_dropdown = alt.binding_select(options=plant_history_ny['Plant Name'].unique(), name='Plant Name')
selection = alt.selection_single(fields=['Plant Name'], bind=input_dropdown,name='Plant Name')

gen_by_year_plant=alt.Chart(plant_history_ny).mark_line().encode(
    alt.X('Generation Period',timeUnit='yearmonth'),
    alt.Y('Net Gen:Q')
    ).properties(title='Net Generation by New York Wind Farms 2015-2020',
    width=1000,
    height=600
    ).add_selection(
        selection
    ).transform_filter(
        selection
    )




wind_report=dp.Report(
    dp.Page(
        title='Overview',
        blocks=[state_plant_chart]
    ),
    dp.Page(
        title='Plants by Age and 2020 Capacity Factor*',
        blocks=[cap_by_year_line
        ,"*Only includes plants in operation with capacity factor between .05 and .7 that came online before 2020\n\n"]
    ),
    dp.Page(
        title='Plants by Manufacturer',
        blocks=[plants_by_manuf]
    ),
    dp.Page(title='Capacity Factor by NERC Region',
            blocks=[cap_by_nerc]
    ),
    dp.Page(title='Net Generation by New York Wind Farms 2010-2020',
            blocks=[gen_by_year_plant]
    ),        
    ).save(path='plant_gen_report.html',formatting=dp.ReportFormatting(width=dp.ReportWidth.FULL))

dp.Report(
    dp.Page(
        title='Overview',
        blocks=[state_plant_chart]
    ),
    dp.Page(
        title='Plants by Age and 2020 Capacity Factor*',
        blocks=[cap_by_year_line
        ,"*Only includes plants in operation with capacity factor between .05 and .7 that came online before 2020\n\n"]
    ),
    dp.Page(
        title='Plants by Manufacturer',
        blocks=[plants_by_manuf]
    ),
    dp.Page(title='Capacity Factor by NERC Region',
            blocks=[cap_by_nerc]
    ),
    dp.Page(title='Net Generation by New York Wind Farms 2010-2020',
            blocks=[gen_by_year_plant]
    ),        
    ).upload(name='Wind Power Generation Report')



#%%
plant_history_ny=plant_history.query("State=='NY'")
plant_history_ny=plant_history_ny.query("year>=2010")

alt.data_transformers.disable_max_rows()

input_dropdown = alt.binding_select(options=plant_history_ny['Plant Name'].unique(), name='Plant Name')
selection = alt.selection_single(fields=['Plant Name'], bind=input_dropdown,name='Plant Name')

gen_by_year_plant=alt.Chart(plant_history_ny).mark_line().encode(
    alt.X('Generation Period',timeUnit='yearmonth'),
    alt.Y('Net Gen:Q')
    ).properties(title='Net Generation by New York Wind Farms 2015-2020',
    width=1000,
    height=600
    ).add_selection(
        selection
    ).transform_filter(
        selection
    )

report=dp.Report(dp.Plot(gen_by_year_plant)).upload(name='test')


#%%
#%%  TEST:Creating GeoDataframe

import geopandas as gpd
from shapely import wkt

gdf=plant_2020[['Plant Name','Nameplate Capacity (MW)','Annual Capacity Factor','geometry']]

gdf['geometry']=gpd.GeoSeries.from_wkt(gdf['geometry'])

gdf=gpd.GeoDataFrame(gdf,geometry='geometry',crs="EPSG:5070")
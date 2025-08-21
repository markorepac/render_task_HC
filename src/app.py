import dash
from dash import dcc, html
from dash.dependencies import Input, Output, State
import geopandas as gpd
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np

# --- 1. Data Loading and Preparation ---
# This is done once when the app starts.
try:
    # Load the shapefile for roads, specifying the correct encoding.
    ROADS = gpd.read_file('ROADS.shp', encoding='cp1252')
    # Load the CSV for settlements.
    naselja = pd.read_csv('naselja.csv', delimiter=';')
    # Load the CSV for ports/marinas.
    m_luke = pd.read_csv('m_luke.csv', delimiter=';')

    # Convert the pandas DataFrames to GeoDataFrames.
    naselja_gdf = gpd.GeoDataFrame(
        naselja,
        geometry=gpd.points_from_xy(naselja.EASTING, naselja.NORTHING),
        crs=ROADS.crs
    )
    m_luke_gdf = gpd.GeoDataFrame(
        m_luke,
        geometry=gpd.points_from_xy(m_luke.EASTING, m_luke.NORTHING),
        crs=ROADS.crs
    )

    # Filter for the specific road types for the first analysis.
    AID = ROADS[(ROADS['KOD'] == 1) | (ROADS['KOD'] == 3)]
    # Filter for large settlements for the second analysis.
    large_settlements = naselja_gdf[naselja_gdf['BR_ST_01'] > 10000]


    # Reproject copies to WGS84 (EPSG:4326) for Plotly plotting.
    naselja_wgs84 = naselja_gdf.to_crs(epsg=4326)
    m_luke_wgs84 = m_luke_gdf.to_crs(epsg=4326)
    large_settlements_wgs84 = large_settlements.to_crs(epsg=4326)


    # Calculate the map's center for the initial view.
    map_center_lon = AID.to_crs(epsg=4326).union_all().centroid.x
    map_center_lat = AID.to_crs(epsg=4326).union_all().centroid.y

    DATA_LOADED_SUCCESSFULLY = True
except FileNotFoundError as e:
    DATA_LOADED_SUCCESSFULLY = False
    ERROR_MESSAGE = f"Error: Could not load data file '{e.filename}'. Make sure all data files are in the same directory."


# --- 2. Initialize the Dash App ---
app = dash.Dash(__name__)
server = app.server

# --- 3. Define the App Layout ---
app.layout = html.Div(style={'backgroundColor': '#1E1E1E', 'color': '#FFFFFF', 'fontFamily': 'Arial, sans-serif', 'padding': '20px'}, children=[
    
    # --- SECTION 1: Population near Roads ---
    html.Div([
        html.H1("Settlement Population Near Major Roads"),
        html.P("Use the slider to change the buffer distance (in meters) around the roads."),
        dcc.Slider(
            id='slider-roads', min=0, max=10000, step=100, value=500,
            marks={i: f'{i} m' for i in range(0, 20001, 5000)},
            tooltip={"placement": "bottom", "always_visible": True}
        ),
        html.H2(id='title-roads', style={'marginTop': '20px'}),
        html.Div(style={'display': 'flex', 'flexDirection': 'row'}, children=[
            dcc.Graph(id='map-roads', style={'height': '70vh', 'width': '70%'}, config={'scrollZoom': True}),
            dcc.Graph(id='barcharts-roads', style={'height': '70vh', 'width': '30%'})
        ])
    ]),

    html.Hr(style={'margin': '40px 0'}), # Separator line

    # --- SECTION 2: Ports near Large Settlements ---
    html.Div([
        html.H1("Ports Near Large Settlements"),
        html.P("Use the slider to change the buffer distance (in meters) from settlements with >10,000 inhabitants."),
        dcc.Slider(
            id='slider-ports', min=0, max=50000, step=1000, value=20000,
            marks={i: f'{i/1000} km' for i in range(0, 50001, 10000)},
            tooltip={"placement": "bottom", "always_visible": True}
        ),
        html.H2(id='title-ports', style={'marginTop': '20px'}),
        # UPDATED layout to include bar chart
        html.Div(style={'display': 'flex', 'flexDirection': 'row'}, children=[
            dcc.Graph(id='map-ports', style={'height': '70vh', 'width': '70%'}, config={'scrollZoom': True}),
            dcc.Graph(id='barchart-ports', style={'height': '70vh', 'width': '30%'})
        ])
    ])
])


# --- 4. Callback for SECTION 1 ---
@app.callback(
    [Output('map-roads', 'figure'),
     Output('title-roads', 'children'),
     Output('barcharts-roads', 'figure')],
    [Input('slider-roads', 'value')],
    [State('map-roads', 'relayoutData')]
)
def update_roads_section(buffer_distance, relayout_data):
    if not DATA_LOADED_SUCCESSFULLY:
        error_fig = go.Figure().update_layout(template="plotly_dark", title_text="Error")
        return error_fig, ERROR_MESSAGE, error_fig

    # Geospatial Analysis
    buffer_polygons = AID.buffer(buffer_distance)
    buffer_gdf = gpd.GeoDataFrame(geometry=buffer_polygons, crs=ROADS.crs)
    dissolved_buffer = buffer_gdf.union_all()
    dissolved_gdf = gpd.GeoDataFrame(geometry=[dissolved_buffer], crs=ROADS.crs)
    selected_naselja = gpd.sjoin(naselja_gdf, dissolved_gdf, how='inner', predicate='within')

    # Bar Chart Calculations
    pop_in_buffer = selected_naselja["BR_ST_01"].sum()
    pop_out_buffer = naselja_gdf["BR_ST_01"].sum() - pop_in_buffer
    count_in_buffer = len(selected_naselja)
    count_out_buffer = len(naselja_gdf) - count_in_buffer

    # Prepare Data for Plotting
    buffer_wgs84 = dissolved_gdf.to_crs(epsg=4326)
    selected_wgs84 = selected_naselja.to_crs(epsg=4326)

    # Create Map Figure
    map_fig = go.Figure()
    map_fig.add_trace(go.Choroplethmapbox(geojson=buffer_wgs84.__geo_interface__, locations=[0], z=[0], colorscale=[[0, 'rgba(0, 100, 255, 0.4)'], [1, 'rgba(0, 100, 255, 0.4)']], showscale=False, marker_line_width=1, marker_line_color='cyan', name='Buffer Zone'))
    map_fig.add_trace(go.Scattermapbox(lat=naselja_wgs84.geometry.y, lon=naselja_wgs84.geometry.x, mode='markers', marker=go.scattermapbox.Marker(size=5, color='#7f7f7f', opacity=0.7), name='All Settlements', hoverinfo='none'))
    map_fig.add_trace(go.Scattermapbox(lat=selected_wgs84.geometry.y, lon=selected_wgs84.geometry.x, mode='markers', marker=go.scattermapbox.Marker(size=8, color='yellow', opacity=0.9), text=selected_wgs84['NAZIV_NAS'], hoverinfo='text', name='Selected Settlements'))

    zoom, center = (6, {"lat": map_center_lat, "lon": map_center_lon})
    if relayout_data and 'mapbox.zoom' in relayout_data:
        zoom, center = relayout_data['mapbox.zoom'], relayout_data['mapbox.center']
    map_fig.update_layout(mapbox_style="carto-darkmatter", mapbox_zoom=zoom, mapbox_center=center, margin={"r":0,"t":0,"l":0,"b":0}, legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01, bgcolor='rgba(0,0,0,0.5)', font=dict(color='white')), template="plotly_dark")

    # Create Bar Chart Figure
    bar_fig = make_subplots(rows=2, cols=1, subplot_titles=("Population", "Number of Settlements"), vertical_spacing=0.15)
    bar_fig.add_trace(go.Bar(x=['Inside', 'Outside'], y=[pop_in_buffer, pop_out_buffer], marker_color=['#FFC300', '#581845'], name='Population'), row=1, col=1)
    bar_fig.add_trace(go.Bar(x=['Inside', 'Outside'], y=[count_in_buffer, count_out_buffer], marker_color=['#DAF7A6', '#900C3F'], name='Settlements'), row=2, col=1)
    bar_fig.update_layout(title_text="Data Summary", showlegend=False, template="plotly_dark", margin={"r":20,"t":40,"l":20,"b":20})

    title_string = f"Population within {buffer_distance} meters: {pop_in_buffer:,.0f}"
    return map_fig, title_string, bar_fig


# --- 5. Callback for SECTION 2 ---
@app.callback(
    [Output('map-ports', 'figure'),
     Output('title-ports', 'children'),
     Output('barchart-ports', 'figure')], # ADDED output for the new bar chart
    [Input('slider-ports', 'value')],
    [State('map-ports', 'relayoutData')]
)
def update_ports_section(buffer_distance, relayout_data):
    if not DATA_LOADED_SUCCESSFULLY:
        error_fig = go.Figure().update_layout(template="plotly_dark", title_text="Error")
        return error_fig, ERROR_MESSAGE, error_fig

    # Geospatial Analysis
    buffer_polygons = large_settlements.buffer(buffer_distance)
    buffer_gdf = gpd.GeoDataFrame(geometry=buffer_polygons, crs=ROADS.crs)
    dissolved_buffer = buffer_gdf.union_all()
    dissolved_gdf = gpd.GeoDataFrame(geometry=[dissolved_buffer], crs=ROADS.crs)
    selected_ports = gpd.sjoin(m_luke_gdf, dissolved_gdf, how='inner', predicate='within')
    
    selected_ports = selected_ports.drop_duplicates(subset=['NAZIV'])
    
    # Bar Chart Calculations
    count_in_buffer = len(selected_ports)
    count_out_buffer = len(m_luke_gdf) - count_in_buffer

    # Prepare Data for Plotting
    buffer_wgs84 = dissolved_gdf.to_crs(epsg=4326)
    selected_ports_wgs84 = selected_ports.to_crs(epsg=4326)

    # Create Map Figure
    map_fig = go.Figure()
    map_fig.add_trace(go.Choroplethmapbox(geojson=buffer_wgs84.__geo_interface__, locations=[0], z=[0], colorscale=[[0, 'rgba(255, 0, 100, 0.4)'], [1, 'rgba(255, 0, 100, 0.4)']], showscale=False, marker_line_width=1, marker_line_color='magenta', name='Buffer Zone'))
    map_fig.add_trace(go.Scattermapbox(lat=large_settlements_wgs84.geometry.y, lon=large_settlements_wgs84.geometry.x, mode='markers', marker=go.scattermapbox.Marker(size=10, color='cyan', symbol='star'), text=large_settlements_wgs84['NAZIV_NAS'], hoverinfo='text', name='Large Settlements (>10k)'))
    map_fig.add_trace(go.Scattermapbox(lat=m_luke_wgs84.geometry.y, lon=m_luke_wgs84.geometry.x, mode='markers', marker=go.scattermapbox.Marker(size=5, color='#7f7f7f', opacity=0.7), name='All Ports', hoverinfo='none'))
    map_fig.add_trace(go.Scattermapbox(lat=selected_ports_wgs84.geometry.y, lon=selected_ports_wgs84.geometry.x, mode='markers', marker=go.scattermapbox.Marker(size=8, color='lime', opacity=0.9), text=selected_ports_wgs84['NAZIV'], hoverinfo='text', name='Selected Ports'))

    zoom, center = (6, {"lat": map_center_lat, "lon": map_center_lon})
    if relayout_data and 'mapbox.zoom' in relayout_data:
        zoom, center = relayout_data['mapbox.zoom'], relayout_data['mapbox.center']
    map_fig.update_layout(mapbox_style="carto-darkmatter", mapbox_zoom=zoom, mapbox_center=center, margin={"r":0,"t":0,"l":0,"b":0}, legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01, bgcolor='rgba(0,0,0,0.5)', font=dict(color='white')), template="plotly_dark")

    # Create Bar Chart Figure for Ports
    bar_fig_ports = go.Figure()
    bar_fig_ports.add_trace(go.Bar(
        x=['Inside', 'Outside'], y=[count_in_buffer, count_out_buffer],
        marker_color=['#00CFE8', '#630C3F'], name='Ports'
    ))
    bar_fig_ports.update_layout(
        title_text="Ports Summary",
        showlegend=False,
        template="plotly_dark",
        margin={"r":20,"t":40,"l":20,"b":20}
    )

    title_string = f"Number of ports within {buffer_distance/1000:,.1f} km of large settlements: {count_in_buffer}"
    return map_fig, title_string, bar_fig_ports


# --- 6. Run the App ---
if __name__ == '__main__':
    app.run_server(debug=True)

# sales_value_matrix.py
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, dcc, html, Input, Output, State, no_update, callback_context
import dash_bootstrap_components as dbc
import base64
import io
import re
import chardet
import os
from collections import defaultdict

# Initialize app with professional theme
app = Dash(__name__, 
           external_stylesheets=[dbc.themes.LUX, dbc.icons.BOOTSTRAP],
           suppress_callback_exceptions=True,
           meta_tags=[{'name': 'viewport', 
                      'content': 'width=device-width, initial-scale=1.0'}])
server = app.server

# ======================================================================
# DATA PROCESSING FUNCTIONS (ENHANCED)
# ======================================================================

def detect_encoding(decoded_content):
    """Robust encoding detection with fallback"""
    result = chardet.detect(decoded_content)
    return result['encoding'] if result['confidence'] > 0.7 else 'utf-8'

def clean_column_names(df):
    """Standardize column names for internal processing"""
    df.columns = [col.strip().lower().replace(' ', '_') for col in df.columns]
    return df

def map_engagement_level(stage):
    """Robust engagement level mapping with fuzzy matching"""
    stage = str(stage).strip().lower()
    if 'untouch' in stage: return 0
    if 'free' in stage: return 1
    if 'direct' in stage or 'da-d' in stage: return 2
    if 'lite' in stage: return 3
    if 'full' in stage: return 4
    return 0  # Default to Untouched

def process_uploaded_data(contents, filename):
    """Enhanced file processing with error handling"""
    if not contents:
        return None, "No file uploaded"
    
    try:
        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)
        
        # Handle Excel files disguised as CSV
        if decoded.startswith(b'PK\x03\x04'):
            df = pd.read_excel(io.BytesIO(decoded))
        else:
            encoding = detect_encoding(decoded)
            df = pd.read_csv(io.BytesIO(decoded), encoding=encoding, engine='python', on_bad_lines='warn')
        
        # Preserve original column names for display
        original_columns = list(df.columns)
        df_clean = clean_column_names(df.copy())
        
        # Identify value columns (yes/no columns)
        value_columns = []
        for col in df_clean.columns:
            try:
                unique_vals = df_clean[col].dropna().astype(str).str.strip().str.lower().unique()
                if all(val in ['yes', 'no', 'y', 'n', '1', '0', 'true', 'false'] for val in unique_vals):
                    value_columns.append(col)
            except:
                continue
        
        return df_clean, value_columns, original_columns
    
    except Exception as e:
        return None, f"Error processing file: {str(e)}", []

def process_data(df, value_columns):
    """Enhanced data processing with quadrant logic"""
    # Clean and standardize data
    for col in value_columns:
        df[col] = df[col].astype(str).str.strip().str.lower()
        df[col] = df[col].apply(lambda x: 'Yes' if x in ['yes', 'y', '1', 'true'] else 'No')
    
    # Calculate value score
    df['value_score'] = df[value_columns].apply(lambda x: x.map({'Yes':1, 'No':0})).sum(axis=1)
    max_score = len(value_columns) or 1  # Prevent division by zero
    
    # Map engagement levels
    stage_col = next((col for col in df.columns if 'stage' in col or 'subscription' in col), None)
    if stage_col:
        df['engagement_level'] = df[stage_col].apply(map_engagement_level)
    else:
        df['engagement_level'] = 0
    
    # Quadrant classification
    value_threshold = max_score * 0.65
    engagement_threshold = 2.0
    
    conditions = [
        (df['value_score'] >= value_threshold) & (df['engagement_level'] >= engagement_threshold),
        (df['value_score'] < value_threshold) & (df['engagement_level'] >= engagement_threshold),
        (df['value_score'] >= value_threshold) & (df['engagement_level'] < engagement_threshold),
        (df['value_score'] < value_threshold) & (df['engagement_level'] < engagement_threshold)
    ]
    
    quadrants = [
        'Strategic Partners', 
        'Growth Opportunities', 
        'High Value Prospects', 
        'Basic Users'
    ]
    
    df['quadrant'] = np.select(conditions, quadrants, default='Unclassified')
    df['size'] = np.clip(df['value_score'] * 12 + 25, 20, 60)  # Constrained bubble sizing
    
    return df, max_score

# ======================================================================
# APP LAYOUT (ENHANCED UI)
# ======================================================================

app.layout = dbc.Container(fluid=True, className="py-0", children=[
    # Header with gradient - IMPROVED VISIBILITY
    dbc.Row(dbc.Col(className="header-section py-3 bg-primary text-white", children=[
        html.Div([
            html.H1("SALES VALUE MATRIX", 
                    className="title mb-1 display-4",
                    style={'font-weight': 'bold', 'color':'rgba(255,255,255,1)', 'text-shadow': '2px 2px 4px rgba(255,255,255,1)'}),
            html.P("Strategic Agency Value & Engagement Analysis", 
                  className="subtitle mb-0 lead")
        ], className="container text-center")
    ]), className="mb-4"),
    
    # Main content area
    html.Div(id='main-content', children=[
        # Upload section (initially visible)
        dbc.Row(dbc.Col(width=10, lg=8, className="mx-auto", children=[
            dbc.Card(className="shadow-lg border-0", children=[
                dbc.CardHeader("Upload Your CSV/Excel File", className="py-3 bg-light"),
                dbc.CardBody([
                    dcc.Upload(
                        id='upload-data',
                        children=html.Div([
                            html.I(className="bi bi-cloud-arrow-up-fill fs-1 text-primary mb-3"),
                            html.P("Drag & Drop or", className="mb-1 fs-5"),
                            html.P("Select File", className="font-weight-bold fs-4")
                        ], className="py-4"),
                        style={
                            'width': '100%', 
                            'borderWidth': '2px', 
                            'borderStyle': 'dashed', 
                            'borderRadius': '10px',
                            'textAlign': 'center',
                            'cursor': 'pointer'
                        },
                        multiple=False
                    ),
                    html.Div(id='upload-status', className="mt-3 text-center"),
                    dbc.Alert(
                        "Supports CSV/Excel files with agency, group, stage, and value columns",
                        color="secondary",
                        className="mt-3 p-2 text-center small"
                    )
                ])
            ])
        ]))
    ]),
    
    # Data stores
    dcc.Store(id='processed-data'),
    dcc.Store(id='value-columns'),
    dcc.Store(id='max-value-score'),
    dcc.Store(id='filename-store'),
    dcc.Store(id='original-columns')  # NEW: Store original column names
])

# ======================================================================
# CALLBACKS (OPTIMIZED & ERROR-FREE)
# ======================================================================

@app.callback(
    [Output('upload-status', 'children'),
     Output('main-content', 'children'),
     Output('processed-data', 'data'),
     Output('value-columns', 'data'),
     Output('max-value-score', 'data'),
     Output('filename-store', 'data'),
     Output('original-columns', 'data')],  # NEW: Store original columns
    [Input('upload-data', 'contents')],
    [State('upload-data', 'filename')]
)
def handle_upload(contents, filename):
    if not contents:
        return no_update, no_update, no_update, no_update, no_update, no_update, no_update
    
    df, value_columns, original_columns = process_uploaded_data(contents, filename)
    
    if df is None or df.empty:
        return dbc.Alert(f"Error: {value_columns}", color="danger"), no_update, no_update, no_update, no_update, no_update, no_update
    
    # Process data
    processed_df, max_score = process_data(df, value_columns)
    
    # Get physician groups and agencies
    group_col = next((col for col in processed_df.columns if 'group' in col), None)
    agency_col = next((col for col in processed_df.columns if 'agency' in col and 'name' in col), None)
    
    group_options = []
    agency_options = []
    
    if group_col:
        group_options = [{'label': group, 'value': group} 
                        for group in processed_df[group_col].unique()]
    
    if agency_col:
        agency_options = [{'label': agency, 'value': agency} 
                         for agency in processed_df[agency_col].unique()]
    
    # Create visualization layout with fixed areas
    visualization_layout = [
        # Filters and controls (top section)
        dbc.Row([
            dbc.Col(width=12, lg=3, className="mb-4", children=[
                dbc.Card(className="shadow-sm h-100", children=[
                    dbc.CardHeader([
                        html.Div([
                            html.H5("Filters & Controls", className="mb-0"),
                            dbc.Button(
                                html.I(className="bi bi-arrow-counterclockwise"),
                                id='reset-filters',
                                color="link",
                                className="float-end p-0"
                            )
                        ], className="d-flex justify-content-between align-items-center")
                    ], className="py-3"),
                    dbc.CardBody([
                        html.Div([
                            html.Small(f"File: {filename}", className="text-muted d-block mb-2 text-truncate"),
                            dbc.Badge("Data Loaded", color="success", className="mb-3")
                        ]),
                        
                        html.Label("Physician Groups", className="font-weight-bold mt-2"),
                        dcc.Dropdown(
                            id='group-filter',
                            options=group_options,
                            value=[opt['value'] for opt in group_options] if group_options else None,
                            multi=True,
                            placeholder="All Groups",
                            className="mb-3"
                        ),
                        
                        html.Label("Agencies", className="font-weight-bold"),
                        dcc.Dropdown(
                            id='agency-filter',
                            options=agency_options,
                            multi=True,
                            placeholder="All Agencies",
                            className="mb-3"
                        ),
                        
                        html.Label("View Mode", className="font-weight-bold mt-3"),
                        dbc.RadioItems(
                            id='view-mode',
                            options=[
                                {'label': ' Quadrant Analysis', 'value': 'quadrant'},
                                {'label': ' Feature Adoption', 'value': 'heatmap'}
                            ],
                            value='quadrant',
                            className="mb-3"
                        ),
                        
                        html.Label("Quadrant Display", className="font-weight-bold mt-3"),
                        dbc.Checklist(
                            id='quadrant-toggle',
                            options=[{'label': ' Show Quadrant Zones', 'value': 'show'}],
                            value=['show'],
                            switch=True,
                            className="mb-3"
                        ),
                        
                        dbc.Button("Reset View", 
                                  id='reset-view',
                                  color="outline-primary",
                                  className="w-100 mt-3",
                                  outline=True)
                    ])
                ])
            ]),
            
            # Visualization area (main content)
            dbc.Col(width=12, lg=9, children=[
                dbc.Card(className="shadow-sm h-100", children=[
                    dbc.CardBody(className="p-0", children=[
                        dcc.Graph(
                            id='main-visualization', 
                            className='h-100', 
                            config={
                                'displayModeBar': True, 
                                'displaylogo': False,
                                'modeBarButtonsToRemove': ['lasso2d', 'select2d']
                            },
                            style={'height': '65vh'}
                        )
                    ])
                ])
            ])
        ]),
        
        # Agency details area (fixed bottom section)
        dbc.Row([
            dbc.Col(width=12, children=[
                dbc.Collapse(
                    dbc.Card(className="shadow-sm mt-4", children=[
                        dbc.CardHeader("Agency Details", className="py-3 bg-light"),
                        dbc.CardBody(id='agency-details-landscape', style={'maxHeight': '300px', 'overflowY': 'auto'})
                    ]),
                    id='agency-details-collapse',
                    is_open=False
                )
            ])
        ])
    ]
    
    return [
        dbc.Alert(f"✅ Successfully processed: {filename} ({len(processed_df)} agencies)", color="success", className="mt-2"),
        visualization_layout,
        processed_df.to_json(date_format='iso', orient='split'),
        value_columns,
        max_score,
        filename,
        original_columns  # NEW: Return original column names
    ]

@app.callback(
    [Output('main-visualization', 'figure'),
     Output('agency-details-collapse', 'is_open'),
     Output('agency-details-landscape', 'children')],
    [Input('processed-data', 'data'),
     Input('value-columns', 'data'),
     Input('max-value-score', 'data'),
     Input('group-filter', 'value'),
     Input('agency-filter', 'value'),
     Input('view-mode', 'value'),
     Input('quadrant-toggle', 'value'),
     Input('reset-view', 'n_clicks'),
     Input('main-visualization', 'clickData'),
     Input('original-columns', 'data')],  # NEW: Original column names
    prevent_initial_call=True
)
def update_visualization(data_json, value_columns, max_score, selected_groups, 
                         selected_agencies, view_mode, show_quadrants, reset_click, 
                         click_data, original_columns):
    ctx = callback_context
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    # Reset view if reset button clicked
    if trigger_id == 'reset-view':
        return go.Figure(), False, no_update
    
    # Handle no data case
    if not data_json or not value_columns:
        return go.Figure(), False, no_update
    
    # Load data
    df = pd.read_json(data_json, orient='split')
    
    # Find relevant columns
    agency_col = next((col for col in df.columns if 'agency' in col and 'name' in col), 'agency_name')
    group_col = next((col for col in df.columns if 'group' in col), 'physician_group')
    
    # Apply filters
    if selected_groups and group_col in df.columns:
        df = df[df[group_col].isin(selected_groups)]
    
    if selected_agencies and agency_col in df.columns:
        df = df[df[agency_col].isin(selected_agencies)]
    
    # Create column mapping for display names
    display_names = {}
    if original_columns and len(original_columns) == len(df.columns):
        display_names = dict(zip(df.columns, original_columns))
    else:
        display_names = {col: col.replace('_', ' ').title() for col in df.columns}
    
    # Define colors
    quadrant_colors = {
        'Strategic Partners': '#4C72B0',
        'Growth Opportunities': '#55A868',
        'High Value Prospects': '#DD8452',
        'Basic Users': '#C44E52',
        'Unclassified': '#777777'
    }
    
    # Handle quadrant view
    if view_mode == 'quadrant':
        fig = go.Figure()
        
        # Add quadrant backgrounds if enabled
        if 'show' in show_quadrants and max_score and max_score > 0:
            value_threshold = max_score * 0.65
            engagement_threshold = 2.0
            
            # Add quadrant rectangles
            fig.add_shape(type="rect", 
                          x0=value_threshold, y0=engagement_threshold, 
                          x1=max_score, y1=4.5,
                          fillcolor=quadrant_colors['Strategic Partners'], 
                          opacity=0.08, layer='below', line_width=0)
            
            fig.add_shape(type="rect", 
                          x0=0, y0=engagement_threshold, 
                          x1=value_threshold, y1=4.5,
                          fillcolor=quadrant_colors['Growth Opportunities'], 
                          opacity=0.08, layer='below', line_width=0)
            
            fig.add_shape(type="rect", 
                          x0=value_threshold, y0=0, 
                          x1=max_score, y1=engagement_threshold,
                          fillcolor=quadrant_colors['High Value Prospects'], 
                          opacity=0.08, layer='below', line_width=0)
            
            fig.add_shape(type="rect", 
                          x0=0, y0=0, 
                          x1=value_threshold, y1=engagement_threshold,
                          fillcolor=quadrant_colors['Basic Users'], 
                          opacity=0.08, layer='below', line_width=0)
            
            # Add quadrant lines
            fig.add_shape(type="line", 
                          x0=value_threshold, y0=0, 
                          x1=value_threshold, y1=4.5,
                          line=dict(color="#555", width=1.5, dash='dash'))
            
            fig.add_shape(type="line", 
                          x0=0, y0=engagement_threshold, 
                          x1=max_score, y1=engagement_threshold,
                          line=dict(color="#555", width=1.5, dash='dash'))
            
            # Quadrant labels
            fig.add_annotation(
                x=value_threshold/2, 
                y=engagement_threshold/2, 
                text="Basic Users", 
                showarrow=False,
                font=dict(size=14, color=quadrant_colors['Basic Users'])
            )
            
            fig.add_annotation(
                x=value_threshold + (max_score - value_threshold)/2, 
                y=engagement_threshold/2, 
                text="High Value Prospects", 
                showarrow=False,
                font=dict(size=14, color=quadrant_colors['High Value Prospects'])
            )
            
            fig.add_annotation(
                x=value_threshold/2, 
                y=engagement_threshold + (4.5 - engagement_threshold)/2, 
                text="Growth Opportunities", 
                showarrow=False,
                font=dict(size=14, color=quadrant_colors['Growth Opportunities'])
            )
            
            fig.add_annotation(
                x=value_threshold + (max_score - value_threshold)/2, 
                y=engagement_threshold + (4.5 - engagement_threshold)/2, 
                text="Strategic Partners", 
                showarrow=False,
                font=dict(size=14, color=quadrant_colors['Strategic Partners'])
            )
        
        # Add bubbles with physician group differentiation
        if group_col in df.columns and not df.empty:
            for group in df[group_col].unique():
                group_df = df[df[group_col] == group]
                fig.add_trace(go.Scatter(
                    x=group_df['value_score'],
                    y=group_df['engagement_level'],
                    mode='markers',
                    marker=dict(
                        size=group_df['size'],
                        sizemode='diameter',
                        sizemin=5,
                        opacity=0.9,
                        line=dict(width=1, color='white')
                    ),
                    text=group_df[agency_col],
                    customdata=group_df[[agency_col, group_col, 'value_score', 'quadrant']],
                    hovertemplate=(
                        "<b>%{customdata[0]}</b><br>"
                        "Group: %{customdata[1]}<br>"
                        "Value Score: %{customdata[2]}/" + str(max_score) + "<br>"
                        "Quadrant: %{customdata[3]}<extra></extra>"
                    ),
                    name=group
                ))
        elif not df.empty:
            fig.add_trace(go.Scatter(
                x=df['value_score'],
                y=df['engagement_level'],
                mode='markers',
                marker=dict(
                    size=df['size'],
                    sizemode='diameter',
                    sizemin=5,
                    opacity=0.9,
                    line=dict(width=1, color='white'),
                    color=df['quadrant'],
                    colors=list(quadrant_colors.values())
                ),
                text=df[agency_col],
                customdata=df[[agency_col, 'value_score', 'quadrant']],
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "Value Score: %{customdata[1]}/" + str(max_score) + "<br>"
                    "Quadrant: %{customdata[2]}<extra></extra>"
                )
            ))
        
        # Layout configuration
        fig.update_layout(
            xaxis=dict(
                title='Value Adoption Score', 
                range=[-0.5, max_score + 0.5] if max_score > 0 else None,
                gridcolor='rgba(240, 242, 246, 0.8)',
                zeroline=False
            ),
            yaxis=dict(
                title='Engagement Level', 
                range=[-0.2, 4.7],
                tickvals=[0, 1, 2, 3, 4],
                ticktext=['Untouched', 'Freemium', 'DA-Direct', 'Orders 360 Lite', 'Orders 360 Full'],
                gridcolor='rgba(240, 242, 246, 0.8)',
                zeroline=False
            ),
            plot_bgcolor='rgba(255,255,255,0.95)',
            paper_bgcolor='rgba(248,249,250,1)',
            font=dict(family="Lato, sans-serif", color="#343a40"),
            margin=dict(l=50, r=50, t=30, b=50),
            hoverlabel=dict(bgcolor='white', font_size=12),
            showlegend=group_col in df.columns and len(df[group_col].unique()) > 1,
            legend_title_text="Physician Groups",
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=-0.25,
                xanchor="center",
                x=0.5
            ),
            transition={'duration': 300}
        )
    
    # Handle feature matrix view
    elif view_mode == 'heatmap' and not df.empty:
        # Prepare data for heatmap
        heat_df = df.sort_values(by='value_score', ascending=False)
        
        # Create annotated heatmap
        fig = go.Figure()
        
        # Create heatmap trace
        fig.add_trace(go.Heatmap(
            z=heat_df[value_columns].replace({'Yes': 1, 'No': 0}).T.values,
            x=heat_df[agency_col],
            y=[display_names.get(col, col) for col in value_columns],  # Use display names
            colorscale=[[0, '#f8f9fa'], [1, '#4C72B0']],
            showscale=False,
            hoverinfo='none'
        ))
        
        # Add annotations
        annotations = []
        for i, agency in enumerate(heat_df[agency_col]):
            for j, feature in enumerate(value_columns):
                value = heat_df[heat_df[agency_col] == agency][feature].values[0]
                annotations.append(dict(
                    x=agency,
                    y=display_names.get(feature, feature),  # Use display names
                    text="✓" if value == "Yes" else "✗",
                    showarrow=False,
                    font=dict(size=14, color="white" if value == "Yes" else "#6c757d"),
                    xref='x1',
                    yref='y1'
                ))
        
        fig.update_layout(
            annotations=annotations,
            xaxis_title="Agencies",
            yaxis_title="Features",
            plot_bgcolor='rgba(255,255,255,0.95)',
            paper_bgcolor='rgba(248,249,250,1)',
            font=dict(family="Lato, sans-serif", color="#343a40"),
            margin=dict(l=150, r=20, t=30, b=150),
            height=500 + len(value_columns)*15,
            xaxis=dict(
                tickangle=45, 
                tickfont=dict(size=10),
                automargin=True
            ),
            yaxis=dict(
                tickfont=dict(size=11),
                automargin=True
            )
        )
    
    # Handle agency selection
    agency_details = no_update
    details_open = False
    
    if click_data:
        try:
            # Get clicked agency name
            if view_mode == 'heatmap':
                agency_name = click_data['points'][0]['x']
            else:
                agency_name = click_data['points'][0]['text']
            
            agency_data = df[df[agency_col] == agency_name].iloc[0]
            
            # Create feature badges
            feature_badges = []
            for feature in value_columns:
                status = "success" if agency_data[feature] == 'Yes' else "secondary"
                feature_badges.append(
                    dbc.ListGroupItem([
                        dbc.Row([
                            dbc.Col(html.Span(display_names.get(feature, feature), className="text-truncate")), 
                            dbc.Col(
                                dbc.Badge("Adopted" if agency_data[feature] == 'Yes' else "Not Adopted", 
                                          color=status, 
                                          className="float-end"),
                                width="auto"
                            )
                        ], className="align-items-center g-2")
                    ], className="py-2 border-light")
                )
            
            # Create details card with original column names
            details_content = dbc.Container(fluid=True, children=[
                dbc.Row([
                    dbc.Col(md=6, children=[
                        dbc.Card(className="border-0 shadow-sm", children=[
                            dbc.CardHeader("Agency Information", className="py-2 bg-light"),
                            dbc.CardBody([
                                html.Div(className="mb-2", children=[
                                    html.Small(display_names.get(agency_col, "Agency Name"), className="text-muted d-block"),
                                    html.Strong(agency_name, className="d-block fs-5")
                                ]),
                                html.Div(className="mb-2", children=[
                                    html.Small(display_names.get(group_col, "Physician Group"), className="text-muted d-block"),
                                    html.Strong(agency_data.get(group_col, 'N/A'), className="d-block")
                                ]),
                                html.Div(className="mb-2", children=[
                                    html.Small("Value Score", className="text-muted d-block"),
                                    html.Strong(f"{agency_data['value_score']}/{max_score}", 
                                              className="d-block badge bg-primary fs-6 p-2")
                                ])
                            ])
                        ])
                    ]),
                    dbc.Col(md=6, children=[
                        dbc.Card(className="border-0 shadow-sm", children=[
                            dbc.CardHeader("Engagement Details", className="py-2 bg-light"),
                            dbc.CardBody([
                                html.Div(className="mb-2", children=[
                                    html.Small(display_names.get('sales_stage_(subscription)', "Sales Stage"), className="text-muted d-block"),
                                    html.Strong(agency_data.get('sales_stage_(subscription)', 'N/A'), 
                                              className="d-block")
                                ]),
                                html.Div(className="mb-2", children=[
                                    html.Small("Strategic Quadrant", className="text-muted d-block"),
                                    dbc.Badge(agency_data['quadrant'], 
                                              color="primary" if agency_data['quadrant'] == "Strategic Partners" else 
                                                    "success" if agency_data['quadrant'] == "Growth Opportunities" else
                                                    "warning" if agency_data['quadrant'] == "High Value Prospects" else "danger",
                                              className="mt-1 fs-6")
                                ]),
                                html.Div(className="mb-2", children=[
                                    html.Small(display_names.get('agency_type', "Agency Type"), className="text-muted d-block"),
                                    html.Strong(agency_data.get('agency_type', 'N/A'), className="d-block")
                                ])
                            ])
                        ])
                    ])
                ]),
                dbc.Row(className="mt-3", children=[
                    dbc.Col(children=[
                        dbc.Card(className="border-0 shadow-sm", children=[
                            dbc.CardHeader("Feature Adoption", className="py-2 bg-light"),
                            dbc.CardBody([
                                dbc.ListGroup(feature_badges, flush=True)
                            ])
                        ])
                    ])
                ])
            ])
            
            agency_details = details_content
            details_open = True
        except Exception as e:
            print(f"Error loading details: {e}")
            agency_details = dbc.Alert("Could not load agency details", color="danger")
            details_open = True
    
    return fig, details_open, agency_details

@app.callback(
    [Output('group-filter', 'value'),
     Output('agency-filter', 'value'),
     Output('view-mode', 'value'),
     Output('quadrant-toggle', 'value'),
     Output('main-visualization', 'clickData', allow_duplicate=True)],
    [Input('reset-filters', 'n_clicks')],
    prevent_initial_call=True
)
def reset_filters(n_clicks):
    if n_clicks:
        return [opt['value'] for opt in group_options] if group_options else None, None, 'quadrant', ['show'], None
    return no_update

# ======================================================================
# RUN APPLICATION
# ======================================================================
if __name__ == '__main__':
    app.run(debug=True, port=8050)
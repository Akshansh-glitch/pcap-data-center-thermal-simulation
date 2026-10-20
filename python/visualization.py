"""Plotly charts for actual model output, with display-only downsampling."""
from __future__ import annotations
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np

THERMAL = [[0.0,"#2258a5"],[0.25,"#29a9c7"],[0.5,"#e5d05b"],[0.75,"#e7883c"],[1.0,"#c33932"]]


def heatmap(temperature, max_display=120):
    stride = max(1, (max(temperature.shape) + max_display - 1) // max_display)
    view = temperature[::stride, ::stride]
    fig = go.Figure(go.Heatmap(z=view,
                                x=np.arange(0,temperature.shape[1],stride),
                                y=np.arange(0,temperature.shape[0],stride),
                                colorscale=THERMAL,
                                colorbar=dict(title="°C"),
                                hovertemplate="Row %{y}, col %{x}<br>%{z:.2f} °C<extra></extra>"))
    fig.update_layout(margin=dict(l=0,r=0,t=6,b=0), height=480,
                      xaxis_title="Column", yaxis_title="Row",
                      template="plotly_white")
    fig.update_yaxes(autorange="reversed", scaleanchor="x")
    return fig


def timeline(history):
    fig = go.Figure()
    if history:
        df = pd.DataFrame(history)
        for key, label, color in (("max","Peak","#c33932"),("mean","Mean","#2258a5"),("min","Minimum","#29a9c7")):
            fig.add_scatter(x=df["time_s"],y=df[key],mode="lines",name=label,line=dict(color=color))
    fig.update_layout(template="plotly_white",margin=dict(l=0,r=0,t=10,b=0),
                      height=260,xaxis_title="Simulation time (s)",yaxis_title="Temperature (°C)")
    return fig


def benchmark_chart(df, metric="compute_time_ms"):
    valid = df[df["success"] == True]
    if valid.empty: return go.Figure()
    fig = px.line(valid, x="grid_rows", y=metric, color="implementation", markers=True,
                  labels={"grid_rows":"Grid width (square)",metric:metric.replace("_"," ")},
                  color_discrete_sequence=["#2258a5","#29a9c7","#e7883c","#c33932"])
    fig.update_layout(template="plotly_white",margin=dict(l=0,r=0,t=10,b=0))
    return fig

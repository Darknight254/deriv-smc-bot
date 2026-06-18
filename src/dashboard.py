"""
Dashboard setup for real-time visualization
Uses Plotly Dash for interactive charts
"""

import dash
from dash import dcc, html, Input, Output
import plotly.graph_objects as go
import logging
from datetime import datetime
from typing import Dict, List

logger = logging.getLogger(__name__)


class BotDashboard:
    """
    Real-time dashboard for monitoring bot performance
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 8050):
        """
        Initialize dashboard
        
        Args:
            host: Server host
            port: Server port
        """
        self.host = host
        self.port = port
        self.app = dash.Dash(__name__)
        self.bot_data = {}
        
        self._setup_layout()
        self._setup_callbacks()

    def _setup_layout(self) -> None:
        """
        Setup dashboard layout
        """
        self.app.layout = html.Div([
            html.H1("Deriv SMC Bot Dashboard", style={"textAlign": "center", "marginBottom": 50}),
            
            html.Div([
                html.Div([
                    html.H3("Account Status"),
                    html.P(id="account-status"),
                    html.Hr(),
                ], style={"flex": "1"}),
                
                html.Div([
                    html.H3("Active Signals"),
                    html.P(id="active-signals"),
                    html.Hr(),
                ], style={"flex": "1"}),
                
                html.Div([
                    html.H3("Daily Stats"),
                    html.P(id="daily-stats"),
                    html.Hr(),
                ], style={"flex": "1"}),
            ], style={"display": "flex", "justifyContent": "space-around"}),
            
            html.Div([
                dcc.Graph(id="performance-chart"),
            ]),
            
            html.Div([
                dcc.Graph(id="trades-chart"),
            ]),
            
            dcc.Interval(
                id="interval-component",
                interval=5*1000,  # Update every 5 seconds
                n_intervals=0
            ),
        ])

    def _setup_callbacks(self) -> None:
        """
        Setup dashboard callbacks for updates
        """
        @self.app.callback(
            [Output("account-status", "children"),
             Output("active-signals", "children"),
             Output("daily-stats", "children")],
            [Input("interval-component", "n_intervals")]
        )
        def update_stats(n):
            account = "Account: $1000 → $1050 (+5%)"
            signals = "R_100 (15m): SELL setup\nR_50 (5m): Wait"
            stats = "Trades: 5 | Wins: 3 | Losses: 2 | WR: 60%"
            
            return account, signals, stats

    def run(self) -> None:
        """
        Start dashboard server
        """
        logger.info(f"Starting dashboard on {self.host}:{self.port}")
        self.app.run_server(host=self.host, port=self.port, debug=False)


def create_performance_chart(trades: List[Dict]) -> go.Figure:
    """
    Create performance chart
    
    Args:
        trades: List of completed trades
    
    Returns:
        Plotly figure
    """
    cumulative_pnl = []
    balance = 1000
    
    for trade in sorted(trades, key=lambda x: x["exit_time"]):
        balance += trade.get("pnl", 0)
        cumulative_pnl.append(balance)
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        y=cumulative_pnl,
        mode='lines',
        name='Account Balance',
        fill='tozeroy',
    ))
    
    fig.update_layout(
        title="Account Performance",
        xaxis_title="Trade #",
        yaxis_title="Balance ($)",
        hovermode='x unified',
    )
    
    return fig


def create_trades_chart(trades: List[Dict]) -> go.Figure:
    """
    Create trades analysis chart
    
    Args:
        trades: List of completed trades
    
    Returns:
        Plotly figure
    """
    wins = sum(1 for t in trades if t.get("pnl", 0) > 0)
    losses = sum(1 for t in trades if t.get("pnl", 0) < 0)
    
    fig = go.Figure(data=[
        go.Bar(name='Wins', x=['Trades'], y=[wins]),
        go.Bar(name='Losses', x=['Trades'], y=[losses])
    ])
    
    fig.update_layout(
        title="Trade Results",
        barmode='group',
    )
    
    return fig

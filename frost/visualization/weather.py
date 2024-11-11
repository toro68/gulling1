"""Visualization tools for weather data."""

import logging
from datetime import datetime, timedelta
from typing import List

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pytz
import streamlit as st
from plotly.subplots import make_subplots

from frost.config import FrostConfig  # Riktig import-sti
from frost.data.fetcher import FrostDataFetcher
from utils.gps_utils import get_last_gps_activity

logger = logging.getLogger(__name__)
config = FrostConfig()

class WeatherVisualizer:
    """Visualiserer værdata."""
    
    def __init__(self, df):
        self.df = df
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config = FrostConfig()
        self.plot_configs = {
            "Lufttemperatur": {
                "column": "air_temperature",
                "type": "scatter",
                "color": "darkred",
                "unit": "°C",
                "line_width": 0.5
            },
            "Snødybde": {
                "column": "surface_snow_thickness",
                "type": "scatter",
                "color": "cyan",
                "unit": "cm",
                "line_width": 0.5
            },
            "Vindstyrke": {
                "column": "wind_speed",
                "type": "scatter",
                "color": "green",
                "unit": "m/s",
                "line_width": 0.5
            },
            "Vindretning": {
                "column": "wind_from_direction",
                "type": "scatter",
                "color": "blue",
                "unit": "grader",
                "line_width": 0.5
            },
            "Luftfuktighet": {
                "column": "relative_humidity",
                "type": "scatter",
                "color": "purple",
                "unit": "%",
                "line_width": 0.5
            },
            "Duggpunkt": {
                "column": "dew_point_temperature",
                "type": "scatter",
                "color": "orange",
                "unit": "°C",
                "line_width": 0.5
            },
            "Vindkast": {
                "column": "max(wind_speed_of_gust PT1H)",
                "type": "scatter",
                "color": "red",
                "unit": "m/s",
                "line_width": 0.5
            }
        }

        # Legg til varselkonfigurasjon
        self.alert_configs = {
            "snow_drift": {
                "line_width": 2,
                "opacity": 1
            },
            "ice_warning": {
                "line_width": 2,
                "opacity": 1
            },
            "precipitation": {
                "bar_width": 3600000,  # 1 time i millisekunder
                "opacity": 1
            }
        }

    def create_improved_graph(self):
        """Oppretter en forbedret graf med valgfrie varsler og værdata."""
        try:
            if self.df is None or self.df.empty:
                return None
                
            self.logger.info("Starter create_improved_graph")
            
            # La brukeren velge hvilke grafer som skal vises
            st.sidebar.header("Velg grafer")
            
            # Varselgrafer
            st.sidebar.subheader("Varsler")
            show_snow_drift = st.sidebar.checkbox("⚠️ Snøfokk-varsel", value=True)
            show_ice_warning = st.sidebar.checkbox("🌡️ Glatte veier-varsel", value=True)
            show_precipitation = st.sidebar.checkbox("🌧️ Nedbørstype", value=True)
            
            # Værdata
            st.sidebar.subheader("Værdata")
            selected_plots = {}
            for name, config in self.plot_configs.items():
                if config['column'] in self.df.columns:
                    selected_plots[name] = st.sidebar.checkbox(
                        f"{name} ({config['unit']})",
                        value=name in ["Lufttemperatur", "Snødybde", "Vindstyrke"]  # Standard valg
                    )
            
            # Tell antall valgte grafer
            num_rows = (
                show_snow_drift + 
                show_ice_warning + 
                show_precipitation + 
                sum(selected_plots.values())
            )
            
            if num_rows == 0:
                st.warning("Velg minst én graf å vise")
                return None
            
            # Opprett subplot med valgte rader
            fig = make_subplots(
                rows=num_rows,
                cols=1,
                shared_xaxes=True,
                vertical_spacing=0.02,
                subplot_titles=self._get_subplot_titles(
                    show_snow_drift,
                    show_ice_warning,
                    show_precipitation,
                    selected_plots
                )
            )
            
            # Hold styr på gjeldende radnummer
            current_row = 1
            
            # Legg til varselgrafer
            if show_snow_drift:
                self._add_alert_graph(fig, row=current_row)
                current_row += 1
                
            if show_ice_warning:
                self._add_icy_roads_graph(fig, row=current_row)
                current_row += 1
                
            if show_precipitation:
                self._add_precipitation_type_graph(fig, row=current_row)
                current_row += 1
            
            # Legg til valgte værdata
            for name, show in selected_plots.items():
                if show and self.plot_configs[name]['column'] in self.df.columns:
                    trace = go.Scatter(
                        x=self.df.index,
                        y=self.df[self.plot_configs[name]['column']],
                        name=f"{name} ({self.plot_configs[name]['unit']})",
                        line=dict(
                            color=self.plot_configs[name]['color'],
                            width=self.plot_configs[name]['line_width']  # Bruk konfigurert linjetykkelse
                        ),
                        showlegend=True
                    )
                    fig.add_trace(trace, row=current_row, col=1)
                    fig.update_yaxes(
                        title_text=self.plot_configs[name]['unit'],
                        row=current_row,
                        col=1
                    )
                    current_row += 1
            
            # Oppdater layout
            fig.update_layout(
                height=300 * num_rows,  # Juster høyde basert på antall grafer
                showlegend=True,
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                )
            )
            
            return fig
            
        except Exception as e:
            self.logger.error(f"Feil ved oppretting av graf: {e}")
            self.logger.exception("Detaljert feilmelding:")
            return None

    def _get_subplot_titles(self, show_snow_drift, show_ice_warning, show_precipitation, selected_plots):
        """Genererer liste med titler for subplot basert på valgte grafer."""
        titles = []
        
        if show_snow_drift:
            titles.append("⚠️ Snøfokk-varsel")
        if show_ice_warning:
            titles.append("🌡️ Glatte veier-varsel")
        if show_precipitation:
            titles.append("🌧️ Nedbørstype")
            
        for name, show in selected_plots.items():
            if show:
                titles.append(name)
                
        return titles

    def _add_alert_graph(self, fig, row=1):
        """Legger til varselgraf med vertikale søyler for snøfokk."""
        try:
            if self.df is None or self.df.empty:
                return
                
            # Beregn risiko for hvert tidspunkt
            risk_series = pd.Series(index=self.df.index)
            for idx in self.df.index:
                risk_series[idx] = self._calculate_snow_drift_risk(idx)
            
            # Legg til søyler i grafen
            fig.add_trace(
                go.Bar(
                    x=risk_series.index,
                    y=risk_series * 100,
                    name="Snøfokk-risiko",
                    marker_color=risk_series.apply(
                        lambda x: f'rgba({int(255*x)},0,0,0.6)'
                    ),
                    hovertemplate=(
                        "Tidspunkt: %{x}<br>" +
                        "Risiko: %{y:.1f}%<br>" +
                        "<extra></extra>"
                    ),
                ),
                row=row, col=1
            )
            
            # Konfigurer akser og legg til risikonivåer
            self._configure_alert_graph(fig, row)
            
        except Exception as e:
            self.logger.error(f"Feil ved oppretting av varselgraf: {e}")

    def _calculate_snow_drift_risk(self, idx):
        """Beregner snøfokk-risiko basert på reelle værforhold."""
        try:
            # Hent verdier for gjeldende tidspunkt
            wind_speed = self.df.loc[idx, 'wind_speed']
            snow_depth = self.df.loc[idx, 'surface_snow_thickness']
            temp = self.df.loc[idx, 'air_temperature']
            humidity = self.df.loc[idx, 'relative_humidity']
            wind_gust = self.df.loc[idx, 'max(wind_speed_of_gust PT1H)']
            
            # Sjekk om vi har alle nødvendige verdier
            if pd.isna([wind_speed, snow_depth, temp, humidity, wind_gust]).any():
                return 0.0
                
            # 1. Grunnleggende vilkår må være oppfylt
            if (humidity < 85 or  # Minimum luftfuktighet
                temp > 0 or       # Må være minusgrader
                snow_depth < 1):  # Må være snø på bakken
                return 0.0
            
            # 2. Beregn delrisiko for hver parameter
            wind_risk = self._calculate_wind_risk(wind_speed, wind_gust)
            snow_risk = self._calculate_snow_risk(snow_depth)
            temp_risk = self._calculate_temp_risk(temp)
            
            # 3. Kombiner risikoer med vekting
            total_risk = self._combine_risks(wind_risk, snow_risk, temp_risk)
            
            # 4. Sjekk varighet (2-timers vindu)
            total_risk = self._apply_duration_filter(idx, total_risk)
            
            return total_risk
            
        except Exception as e:
            self.logger.error(f"Feil i risikoberegning: {e}")
            return 0.0

    def _calculate_wind_risk(self, wind_speed, wind_gust):
        """Beregner vindrisiko."""
        # Vindstyrke må være over moderat nivå for å være relevant
        if wind_speed < 9.5:
            return 0.0
            
        wind_base_risk = 0.0
        if wind_speed >= 13.0:
            wind_base_risk = 1.0
        elif wind_speed >= 9.5:
            wind_base_risk = (wind_speed - 9.5) / (13.0 - 9.5)
        
        # Legg til ekstra risiko for sterke vindkast
        gust_bonus = 0.0
        if wind_gust >= 16.0:
            gust_bonus = 0.2
        
        return min(wind_base_risk + gust_bonus, 1.0)

    def _calculate_snow_risk(self, snow_depth):
        """Beregner snørisiko."""
        if snow_depth < 1.0:  # Minimum snødybde
            return 0.0
            
        if snow_depth >= 4.0:
            return 1.0
        elif snow_depth >= 2.5:
            return 0.7
        else:
            return 0.3

    def _calculate_temp_risk(self, temp):
        """Beregner temperaturrisiko."""
        if temp > 0:  # Ingen risiko over frysepunktet
            return 0.0
            
        if temp <= -4.5:
            return 1.0
        elif temp <= -2.0:
            return 0.7
        else:
            return 0.4

    def _combine_risks(self, wind_risk, snow_risk, temp_risk):
        """Kombinerer delrisikoer til total risiko."""
        # Vekting av faktorer
        weights = {
            'wind': 0.5,    # Vind er viktigst
            'snow': 0.3,    # Snø er nest viktigst
            'temp': 0.2     # Temperatur minst viktig
        }
        
        # Beregn vektet sum
        total_risk = (wind_risk * weights['wind'] + 
                     snow_risk * weights['snow'] + 
                     temp_risk * weights['temp'])
        
        return total_risk

    def _apply_duration_filter(self, idx, risk):
        """Filtrerer risiko basert på varighet."""
        try:
            # Hent data for 2-timers vindu før gjeldende tidspunkt
            window_start = idx - pd.Timedelta(hours=2)
            window_data = self.df.loc[window_start:idx]
            
            # Sjekk om forholdene har vært konsistente
            consistent_conditions = all(
                self._basic_conditions_met(row)
                for _, row in window_data.iterrows()
            )
            
            return risk if consistent_conditions else risk * 0.5
            
        except Exception as e:
            self.logger.error(f"Feil i varighetsfilter: {e}")
            return risk

    def _basic_conditions_met(self, row):
        """Sjekker om grunnleggende vilkår er oppfylt."""
        return (
            row['relative_humidity'] >= 85 and
            row['air_temperature'] <= 0 and
            row['surface_snow_thickness'] >= 1.0 and
            row['wind_speed'] >= 9.5
        )

    def display_weather_data(self):
        try:
            if self.df is None or self.df.empty:
                st.error("Ingen værdata mottatt")
                return

            # Legg til periodevalg øverst
            start_date, end_date = self.select_time_period()
            
            # Sikre at DataFrame indeks har tidssone
            if self.df.index.tz is None:
                self.df.index = self.df.index.tz_localize('UTC')
            
            # Filtrer dataframe basert på valgt periode
            mask = (self.df.index >= start_date) & (self.df.index <= end_date)
            filtered_df = self.df[mask].copy()
            
            # Oppdater self.df midlertidig for visning
            original_df = self.df
            self.df = filtered_df
            
            # Resten av visningslogikken fortsetter som før
            selected_plots = st.multiselect(
                "Velg grafer som skal vises:",
                options=list(self.plot_configs.keys()),
                default=["Lufttemperatur", "Snødybde", "Vindstyrke", "Vindkast"]
            )
            
            # Filtrer plot_configs basert på valg
            filtered_configs = {
                name: config for name, config in self.plot_configs.items()
                if name in selected_plots
            }
            
            # Lagre original plot_configs
            original_configs = self.plot_configs.copy()
            self.plot_configs = filtered_configs

            tab1, tab2, tab3 = st.tabs(["🌡️ Hovedgraf", "📊 Andre værdata", "📈 Værstatistikk"])

            with tab1:
                st.subheader("Væroversikt")
                # Vis varsler først
                self.display_weather_alerts()
                # Deretter vis grafen
                fig = self.create_improved_graph()
                if fig:
                    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

            with tab2:
                st.subheader("Andre værdata")
                self.display_additional_data()

            with tab3:
                st.subheader("Værstatistikk")
                self.display_weather_statistics()
                
            # Gjenopprett original plot_configs
            self.plot_configs = original_configs

        except Exception as e:
            self.logger.error(f"Feil ved visning av værdata: {e}")
            st.error("Kunne ikke vise værdata")

    def display_weather_statistics(self):
        try:
            stats_data = {}
            for name, config in self.plot_configs.items():
                col = config["column"]
                if col in self.df.columns:
                    data = self.df[col]
                    valid_data = data.dropna()
                    if not valid_data.empty:
                        values = [
                            f"{valid_data.mean():.1f}",
                            f"{valid_data.median():.1f}",
                            f"{valid_data.min():.1f}",
                            f"{valid_data.max():.1f}",
                            f"{valid_data.sum():.1f}" if col in ["precipitation_amount"] else "N/A"
                        ]
                    else:
                        values = ["N/A", "N/A", "N/A", "N/A", "N/A"]
                    
                    stats_data[name] = values

            if stats_data:
                df_stats = pd.DataFrame(
                    stats_data,
                    index=["Gjennomsnitt", "Median", "Minimum", "Maksimum", "Sum"]
                )
                st.table(df_stats)
            else:
                st.warning("Ingen statistikk tilgjengelig")

        except Exception as e:
            self.logger.error(f"Feil ved generering av værstatistikk: {e}")
            st.error("Kunne ikke generere værstatistikk")

    def display_additional_data(self):
        """Viser tilleggsdata basert på tilgjengelige kolonner."""
        try:
            available_columns = set(self.df.columns)
            
            # Vindretningsanalyse
            if "wind_from_direction" in available_columns:
                with st.expander("🧭 Vindretningsanalyse", expanded=True):
                    wind_dir_data = self.df["wind_from_direction"].dropna()
                    if not wind_dir_data.empty:
                        percentages = self.analyze_wind_direction(wind_dir_data)
                        if percentages:
                            # Lag polar plot for vindretning
                            fig = go.Figure()
                            fig.add_trace(go.Scatterpolar(
                                r=list(percentages.values()),
                                theta=list(percentages.keys()),
                                fill='toself',
                                name='Vindretning'
                            ))
                            
                            fig.update_layout(
                                polar=dict(
                                    radialaxis=dict(
                                        visible=True,
                                        range=[0, max(percentages.values()) * 1.1],
                                        ticksuffix='%'
                                    )
                                ),
                                showlegend=False,
                                height=400,
                                title="Vindretningsfordeling"
                            )
                            
                            col1, col2 = st.columns([2, 1])
                            with col1:
                                st.plotly_chart(fig, use_container_width=True)
                            
                            with col2:
                                # Vis prosentvis fordeling
                                st.write("Fordeling:")
                                for dir_name, percent in percentages.items():
                                    st.metric(dir_name, f"{percent:.1f}%")
                                
                                # Vis dominerende vindretning
                                dominant_dir = max(percentages.items(), key=lambda x: x[1])
                                st.info(f"Dominerende vindretning: {dominant_dir[0]} ({dominant_dir[1]:.1f}%)")

            # Temperaturdata
            if "air_temperature" in available_columns:
                with st.expander("🌡️ Lufttemperatur"):
                    temp_fig = go.Figure()
                    temp_fig.add_trace(
                        go.Scatter(
                            x=self.df.index,
                            y=self.df["air_temperature"],
                            mode="lines",
                            name="Lufttemperatur",
                            line=dict(color="darkred")
                        )
                    )
                    temp_fig.update_layout(
                        height=400,
                        title="Temperaturutvikling",
                        xaxis_title="Tid",
                        yaxis_title="Temperatur (°C)"
                    )
                    st.plotly_chart(temp_fig, use_container_width=True)
                    
                    valid_data = self.df["air_temperature"].dropna()
                    if not valid_data.empty:
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Gjennomsnitt", f"{valid_data.mean():.1f}°C")
                        with col2:
                            st.metric("Minimum", f"{valid_data.min():.1f}°C")
                        with col3:
                            st.metric("Maksimum", f"{valid_data.max():.1f}°C")

            # Snødata
            if "surface_snow_thickness" in available_columns:
                with st.expander("❄️ Snødybde"):
                    snow_fig = go.Figure()
                    snow_fig.add_trace(
                        go.Scatter(
                            x=self.df.index,
                            y=self.df["surface_snow_thickness"],
                            mode="lines",
                            name="Snødybde",
                            line=dict(color="cyan")
                        )
                    )
                    snow_fig.update_layout(
                        height=400,
                        title="Snødybdeutvikling",
                        xaxis_title="Tid",
                        yaxis_title="Snødybde (cm)"
                    )
                    st.plotly_chart(snow_fig, use_container_width=True)
                    
                    valid_data = self.df["surface_snow_thickness"].dropna()
                    if not valid_data.empty:
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("Gjennomsnitt", f"{valid_data.mean():.1f} cm")
                        with col2:
                            st.metric("Maksimum", f"{valid_data.max():.1f} cm")

            # Vinddata
            if "max_wind_speed" in available_columns:
                with st.expander("🌪️ Vinddata"):
                    wind_fig = go.Figure()
                    wind_fig.add_trace(
                        go.Scatter(
                            x=self.df.index,
                            y=self.df["max_wind_speed"],
                            mode="lines",
                            name="Vindhastighet",
                            line=dict(color="green")
                        )
                    )
                    wind_fig.update_layout(
                        height=400,
                        title="Vindhastighetsprofil",
                        xaxis_title="Tid",
                        yaxis_title="Vindhastighet (m/s)"
                    )
                    st.plotly_chart(wind_fig, use_container_width=True)
                    
                    valid_data = self.df["max_wind_speed"].dropna()
                    if not valid_data.empty:
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Gjennomsnitt", f"{valid_data.mean():.1f} m/s")
                        with col2:
                            st.metric("Minimum", f"{valid_data.min():.1f} m/s")
                        with col3:
                            st.metric("Maksimum", f"{valid_data.max():.1f} m/s")

        except Exception as e:
            self.logger.error(f"Feil ved visning av tilleggsdata: {e}")
            st.error("Kunne ikke vise tilleggsdata")

    def analyze_wind_direction(self, wind_direction_data):
        """Analyserer vindretningsdata og returnerer prosentvis fordeling."""
        # Definer hovedretninger
        directions = {
            'N': (337.5, 22.5),
            'NØ': (22.5, 67.5),
            'Ø': (67.5, 112.5),
            'SØ': (112.5, 157.5),
            'S': (157.5, 202.5),
            'SV': (202.5, 247.5),
            'V': (247.5, 292.5),
            'NV': (292.5, 337.5)
        }
        
        # Initialiser teller for hver retning
        direction_counts = {dir_name: 0 for dir_name in directions.keys()}
        
        # Tell opp retninger
        for angle in wind_direction_data:
            if pd.isna(angle):
                continue
                
            angle = float(angle) % 360
            for dir_name, (start, end) in directions.items():
                if start > end:  # Håndter Nord-tilfellet
                    if angle >= start or angle < end:
                        direction_counts[dir_name] += 1
                        break
                elif start <= angle < end:
                    direction_counts[dir_name] += 1
                    break
        
        # Konverter til prosent
        total = sum(direction_counts.values())
        if total > 0:
            direction_percentages = {
                dir_name: (count / total) * 100 
                for dir_name, count in direction_counts.items()
            }
            return direction_percentages
        return None

    def display_weather_alerts(self):
        """Viser væradvarsler basert på analyser."""
        try:
            if self.df is None or self.df.empty:
                self.logger.warning("Ingen data tilgjengelig for varsler")
                return
                
            self.logger.info("Starter analyse av væradvarsler")
            
        except Exception as e:
            self.logger.error(f"Feil ved visning av væradvarsler: {str(e)}")
            st.error("Kunne ikke vise væradvarsler")

    def get_basic_alerts(self) -> List[str]:
        """Genererer grunnleggende værvarsler."""
        try:
            if self.df is None or self.df.empty:
                self.logger.warning("Ingen data tilgjengelig for varsler")
                return []
                
            alerts = []
            latest_data = self.df.iloc[-1]
            
            # Debug logging
            self.logger.info(f"Analyserer data fra: {latest_data.name}")
            self.logger.info(f"Tilgjengelige kolonner: {self.df.columns.tolist()}")
            
            # Snøfokk-analyse
            if 'wind_speed' in self.df.columns and 'surface_snow_thickness' in self.df.columns:
                wind_speed = latest_data['wind_speed']
                snow_depth = latest_data['surface_snow_thickness']
                self.logger.info(f"Vindstyrke: {wind_speed}, Snødybde: {snow_depth}")
                
                if wind_speed > 8 and snow_depth > 5:
                    alerts.append(f"⚠️ Fare for snøfokk (Vind: {wind_speed:.1f} m/s, Snø: {snow_depth:.1f} cm)")
            
            # Glatte veier-analyse
            if 'air_temperature' in self.df.columns:
                temp = latest_data['air_temperature']
                self.logger.info(f"Temperatur: {temp}")
                
                if -2 <= temp <= 2:
                    alerts.append(f"🌨️ Fare for glatte veier (Temp: {temp:.1f}°C)")
            
            # Nedbørsanalyse
            if 'sum(precipitation_amount PT1H)' in self.df.columns:
                precip = latest_data['sum(precipitation_amount PT1H)']
                self.logger.info(f"Nedbør: {precip}")
                
                if precip > 0:
                    temp = latest_data.get('air_temperature', 0)
                    if temp <= 0:
                        alerts.append(f"❄️ Snø ({precip:.1f} mm/t)")
                    elif temp <= 2:
                        alerts.append(f"🌨️ Sludd ({precip:.1f} mm/t)")
                    else:
                        alerts.append(f"🌧️ Regn ({precip:.1f} mm/t)")
            
            return alerts
            
        except Exception as e:
            self.logger.error(f"Feil ved generering av værvarsler: {e}")
            return []

    def select_time_period(self):
        """Lar brukeren velge tidsperiode for værdata."""
        # Bruk Oslo-tidssone for konsistent tidshåndtering
        oslo_tz = 'Europe/Oslo'
        now = pd.Timestamp.now(tz=oslo_tz)
        
        # Returner bare start og slutt basert på input fra app.py
        return now - pd.Timedelta(hours=24), now

    def _add_icy_roads_graph(self, fig, row=2):
        """Legger til varselgraf for glatte veier."""
        try:
            if self.df is None or self.df.empty:
                return
                
            # Beregn risiko for hvert tidspunkt
            risk_data = []
            for idx in self.df.index:
                # Hent nødvendige verdier
                temp = self.df.loc[idx, 'air_temperature']
                snow_depth = self.df.loc[idx, 'surface_snow_thickness']
                precip = self.df.loc[idx, 'sum(precipitation_amount PT1H)']
                
                # Beregn endring i snødybde
                snow_depth_change = snow_depth - self.df.loc[idx - pd.Timedelta(hours=1), 'surface_snow_thickness'] \
                    if idx - pd.Timedelta(hours=1) in self.df.index else 0
                
                # Beregn risiko
                risk = self._calculate_ice_risk_scenarios(
                    temp=temp,
                    precip=precip,
                    snow_depth=snow_depth,
                    snow_depth_change=snow_depth_change,
                    idx=idx
                )
                
                # Lag forklarende tekst
                conditions = []
                if temp > 0 and not pd.isna(precip) and precip > 0:
                    if snow_depth > 0:
                        conditions.append("Regn på snø/issåle")
                    else:
                        conditions.append("Regn som kan fryse")
                elif -1 < temp <= 2 and not pd.isna(precip) and precip > 0:
                    if snow_depth_change > 0.1:
                        conditions.append("Snø som kan bli glatt")
                    elif snow_depth_change < -0.1:
                        conditions.append("Smelting med fare for is")
                    else:
                        conditions.append("Sludd med isfare")
                
                # Legg til data for dette tidspunktet
                risk_data.append({
                    'timestamp': idx,
                    'risk': risk * 100,
                    'temp': temp,
                    'snow_depth': snow_depth,
                    'precip': precip if not pd.isna(precip) else 0,
                    'snow_change': snow_depth_change,
                    'conditions': ', '.join(conditions) if conditions else 'Ingen spesielle forhold'
                })
            
            # Konverter til DataFrame for enklere håndtering
            risk_df = pd.DataFrame(risk_data)
            
            # Legg til søyler i grafen med forbedret hover
            fig.add_trace(
                go.Bar(
                    x=risk_df['timestamp'],
                    y=risk_df['risk'],
                    name="Glatte veier",
                    marker=dict(
                        color=risk_df['risk'].apply(
                            lambda x: f'rgba({int(255*(x/100))},0,0,0.6)'
                        )
                    ),
                    width=3600000,  # 1 time i millisekunder
                    customdata=np.column_stack((
                        risk_df['temp'],
                        risk_df['snow_depth'],
                        risk_df['precip'],
                        risk_df['snow_change'],
                        risk_df['conditions']
                    )),
                    hovertemplate=(
                        "<b>Tidspunkt:</b> %{x|%Y-%m-%d %H:%M}<br>" +
                        "<b>Risiko:</b> %{y:.1f}%<br>" +
                        "<b>Temperatur:</b> %{customdata[0]:.1f}°C<br>" +
                        "<b>Snødybde:</b> %{customdata[1]:.1f}cm<br>" +
                        "<b>Nedbør:</b> %{customdata[2]:.1f}mm/t<br>" +
                        "<b>Snøendring:</b> %{customdata[3]:.1f}cm<br>" +
                        "<b>Forhold:</b> %{customdata[4]}<br>" +
                        "<extra></extra>"
                    )
                ),
                row=row, col=1
            )
            
        except Exception as e:
            self.logger.error(f"Feil ved oppretting av glatt vei-varsel: {e}")

    def _calculate_ice_risk_scenarios(self, temp, precip, snow_depth, snow_depth_change, idx):
        """
        Beregner risiko for glatte veier basert på vinterveifysikk.
        """
        try:
            # Hvis vi mangler kritiske data, returner ingen risiko
            if pd.isna([temp, snow_depth, precip]).any():
                return 0.0
                
            # Ingen risiko hvis:
            # - temperaturen er under 0
            # - snødybden øker
            # - ingen nedbør
            if temp <= 0 or snow_depth_change > 0 or precip <= 0:
                return 0.0
            
            # Beregn samlet snøsmelting over de siste 3 timene
            cumulative_melt = 0
            hours_to_check = 3
            for i in range(hours_to_check):
                prev_time = idx - pd.Timedelta(hours=i)
                if prev_time in self.df.index:
                    prev_snow = self.df.loc[prev_time, 'surface_snow_thickness']
                    if not pd.isna(prev_snow):
                        current_change = snow_depth - prev_snow
                        if current_change < 0:  # Bare tell med smelting
                            cumulative_melt += abs(current_change)
            
            # Beregn faktorer som brukes i flere scenarier
            melt_intensity = abs(snow_depth_change)  # Nåværende smeltehastighet
            rain_intensity = precip  # Nedbørintensitet
            
            # SCENARIO 1: Kombinert regn og snøsmelting
            if snow_depth_change <= -0.5 and 0 < temp <= 2:
                # Basisrisiko
                total_risk = 0.5
                
                # Øk risiko basert på kombinasjonen av regn og smelting
                current_melt_factor = min(1.0, melt_intensity / 0.5)  # 0.5cm/t gir maks
                cumulative_melt_factor = min(1.0, cumulative_melt / 1.5)  # 1.5cm over 3t gir maks
                rain_factor = min(1.0, rain_intensity / 2.0)  # 2mm/t gir maks
                
                # Kombiner faktorer med vekt på kumulativ smelting
                melt_combined = (current_melt_factor * 0.4 + cumulative_melt_factor * 0.6)
                
                # Synergy bonus når både regn og smelting er betydelig
                synergy_bonus = melt_combined * rain_factor * 0.4
                
                total_risk += melt_combined * 0.3 + synergy_bonus
                
                # Ekstra risiko ved vedvarende smelting
                if cumulative_melt >= 1.0:  # Betydelig samlet smelting
                    total_risk = min(1.0, total_risk + (cumulative_melt - 1.0) * 0.3)
            
            # SCENARIO 2: Regn på is/snøsåle
            elif snow_depth > 0:
                total_risk = 0.4
                rain_factor = min(0.3, rain_intensity * 0.15)
                cumulative_melt_factor = min(0.3, cumulative_melt * 0.4)
                total_risk += rain_factor + cumulative_melt_factor
            
            # SCENARIO 3: Temperaturfall mot null
            prev_hour = idx - pd.Timedelta(hours=1)
            if prev_hour in self.df.index:
                prev_temp = self.df.loc[prev_hour, 'air_temperature']
                if prev_temp > 2 and 0 < temp <= 2:
                    total_risk = max(total_risk, 0.5)
                    if cumulative_melt > 0:
                        total_risk += min(0.3, cumulative_melt * 0.4)
                    if rain_intensity > 0:
                        total_risk += min(0.2, rain_intensity * 0.1)
            
            return min(1.0, total_risk)
                
        except Exception as e:
            self.logger.error(f"Feil i risikoberegning: {e}")
            return 0.0

    def _configure_alert_graph(self, fig, row):
        """Konfigurerer utseendet på varselgrafen."""
        try:
            # Konfigurer y-aksen
            fig.update_yaxes(
                title_text="Risiko (%)",
                range=[0, 100],
                tickmode='array',
                ticktext=['0%', '20%', '40%', '60%', '80%', '100%'],
                tickvals=[0, 20, 40, 60, 80, 100],
                row=row, col=1
            )
            
            # Legg til horisontale linjer for risikonivåer med tynnere strek
            risk_levels = [
                (80, "Høy risiko", "red"),
                (60, "Moderat risiko", "orange"),
                (40, "Lav risiko", "yellow")
            ]
            
            for level, label, color in risk_levels:
                fig.add_hline(
                    y=level,
                    line_dash="dot",
                    line_width=0.5,  # Tynnere horisontal linje
                    line_color=color,
                    annotation_text=label,
                    annotation_position="right",
                    row=row, col=1
                )

            # Oppdater bredden på søylene for tydeligere vertikale linjer
            fig.update_traces(
                selector=dict(type='bar'),
                width=1000*3600*0.8,  # Juster bredden på søylene (80% av original)
                opacity=1,  # Øk opasiteten for tydeligere søyler
                row=row
            )
                
        except Exception as e:
            self.logger.error(f"Feil ved konfigurering av varselgraf: {e}")

    def _add_precipitation_type_graph(self, fig, row=3):
        """Legger til nedbørsgraf med type-kategorisering."""
        try:
            if self.df is None or self.df.empty:
                return
                
            # Hent relevante kolonner
            precip = self.df['sum(precipitation_amount PT1H)']
            temp = self.df['air_temperature']
            snow_depth = self.df['surface_snow_thickness']
            
            # Beregn endring i snødybde
            snow_depth_change = snow_depth.diff()
            
            # Definer masker for sikre soner
            definite_snow = (temp <= -1) & (precip > 0)  # Garantert snø når det er kaldt nok
            definite_rain = (temp > 2) & (precip > 0)    # Garantert regn når det er varmt nok
            
            # Overgangsone (-1°C til +2°C) - kategoriser basert på snødybdeendring
            transition_zone = (temp > -1) & (temp <= 2) & (precip > 0)
            snow_in_transition = transition_zone & (snow_depth_change > 0.1)  # Økende snødybde
            rain_in_transition = transition_zone & (snow_depth_change < -0.1) # Minkende snødybde
            mix_in_transition = transition_zone & (abs(snow_depth_change) <= 0.1)  # Stabil snødybde
            
            # Kombiner masker
            snow_mask = definite_snow | snow_in_transition
            rain_mask = definite_rain | rain_in_transition
            mix_mask = mix_in_transition
            
            # Legg til vertikale søyler for hver type
            fig.add_trace(
                go.Bar(
                    x=self.df[snow_mask].index,
                    y=precip[snow_mask],
                    name='Snø',
                    marker_color='rgba(0, 0, 255, 0.6)',
                    width=1000*3600,
                    hovertemplate=(
                        "Tidspunkt: %{x}<br>" +
                        "Mengde: %{y:.1f} mm/t<br>" +
                        "Type: Snø<br>" +
                        "Temp: %{customdata[0]:.1f}°C<br>" +
                        "Snøendring: %{customdata[1]:.1f} cm<br>" +
                        "<extra></extra>"
                    ),
                    customdata=self.df[snow_mask][['air_temperature', 'surface_snow_thickness']].diff()
                ),
                row=row, col=1
            )
            
            fig.add_trace(
                go.Bar(
                    x=self.df[mix_mask].index,
                    y=precip[mix_mask],
                    name='Sludd',
                    marker_color='rgba(128, 0, 128, 0.6)',
                    width=1000*3600,
                    hovertemplate=(
                        "Tidspunkt: %{x}<br>" +
                        "Mengde: %{y:.1f} mm/t<br>" +
                        "Type: Sludd<br>" +
                        "Temp: %{customdata[0]:.1f}°C<br>" +
                        "Snøendring: %{customdata[1]:.1f} cm<br>" +
                        "<extra></extra>"
                    ),
                    customdata=self.df[mix_mask][['air_temperature', 'surface_snow_thickness']].diff()
                ),
                row=row, col=1
            )
            
            fig.add_trace(
                go.Bar(
                    x=self.df[rain_mask].index,
                    y=precip[rain_mask],
                    name='Regn',
                    marker_color='rgba(255, 0, 0, 0.6)',
                    width=1000*3600,
                    hovertemplate=(
                        "Tidspunkt: %{x}<br>" +
                        "Mengde: %{y:.1f} mm/t<br>" +
                        "Type: Regn<br>" +
                        "Temp: %{customdata[0]:.1f}°C<br>" +
                        "Snøendring: %{customdata[1]:.1f} cm<br>" +
                        "<extra></extra>"
                    ),
                    customdata=self.df[rain_mask][['air_temperature', 'surface_snow_thickness']].diff()
                ),
                row=row, col=1
            )
            
            # Konfigurer y-aksen
            fig.update_yaxes(
                title_text="Nedbør (mm/t)",
                range=[0, max(precip) * 1.1],
                row=row, col=1
            )
            
        except Exception as e:
            self.logger.error(f"Feil ved oppretting av nedbørsgraf: {e}")

@st.cache_data(ttl=3600)
def get_cached_weather_data(start_date, end_date):
    """Henter og cacher værdata."""
    try:
        config = FrostConfig()
        fetcher = FrostDataFetcher(config)
        
        # Konverter datoer til Oslo tidssone hvis de ikke allerede er det
        oslo_tz = 'Europe/Oslo'
        
        # Håndter start_date
        if isinstance(start_date, pd.Timestamp):
            if start_date.tz is None:
                start_date = start_date.tz_localize(oslo_tz)
            else:
                start_date = start_date.tz_convert(oslo_tz)
        else:
            start_date = pd.Timestamp(start_date).tz_localize(oslo_tz)
        
        # Håndter end_date
        if isinstance(end_date, pd.Timestamp):
            if end_date.tz is None:
                end_date = end_date.tz_localize(oslo_tz)
            else:
                end_date = end_date.tz_convert(oslo_tz)
        else:
            end_date = pd.Timestamp(end_date).tz_localize(oslo_tz)
        
        # Formater datostrenger for API-kall
        start_str = start_date.strftime('%Y-%m-%dT%H:%M:%S')
        end_str = end_date.strftime('%Y-%m-%dT%H:%M:%S')
        
        df = fetcher._fetch_chunk(
            start_date=start_str,
            end_date=end_str
        )
        
        if df is not None and not df.empty:
            if 'timestamp' in df.columns:
                # Konverter timestamp-kolonne til Oslo tidssone
                df['timestamp'] = pd.to_datetime(df['timestamp']).tz_localize('UTC').tz_convert(oslo_tz)
                df.set_index('timestamp', inplace=True)
            return df
        return None
        
    except Exception as e:
        logger.error(f"Feil ved henting av værdata: {e}")
        return None
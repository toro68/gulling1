"""Visualization tools for weather data."""

import logging
from datetime import datetime, timedelta
from typing import List, Optional

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

def get_cached_weather_data(start_datetime, end_datetime):
    """
    Henter værdata fra cache eller API.
    
    Args:
        start_datetime: Starttidspunkt for datauthenting
        end_datetime: Sluttidspunkt for datauthenting
        
    Returns:
        DataFrame med værdata eller None hvis feil oppstår
    """
    try:
        fetcher = FrostDataFetcher(config=config)
        
        # Konverter datoer til streng hvis de er datetime objekter
        if isinstance(start_datetime, pd.Timestamp):
            start_datetime = start_datetime.strftime("%Y-%m-%dT%H:%M:%S")
        if isinstance(end_datetime, pd.Timestamp):
            end_datetime = end_datetime.strftime("%Y-%m-%dT%H:%M:%S")
            
        df = fetcher._fetch_chunk(start_datetime, end_datetime)
        if df is not None and not df.empty:
            return df
        return None
    except Exception as e:
        logger.error(f"Feil ved henting av værdata: {e}")
        return None

class WeatherVisualizer:
    """Visualiserer værdata."""
    
    def __init__(self, df: Optional[pd.DataFrame] = None):
        """
        Initialiser WeatherVisualizer.
        
        Args:
            df: DataFrame med værdata. Kan være None ved initialisering.
        """
        self.df = df
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config = FrostConfig()
        
        # Kolonnemapping for å håndtere forskjellige kolonnenavn fra API
        self.column_mapping = {
            'air_temperature': ['air_temperature', 'mean(air_temperature P1D)', 'max(air_temperature PT1H)'],
            'surface_snow_thickness': ['surface_snow_thickness'],
            'wind_speed': ['wind_speed', 'mean(wind_speed P1D)', 'max(wind_speed PT1H)'],
            'wind_from_direction': ['wind_from_direction'],
            'relative_humidity': ['relative_humidity'],
            'dew_point_temperature': ['dew_point_temperature'],
            'precipitation_amount': ['sum(precipitation_amount PT1H)'],
            'max_wind_speed': ['max(wind_speed_of_gust PT1H)', 'max(wind_speed PT1H)']
        }
        
        # Map kolonner hvis nødvendig
        if df is not None:
            self._map_columns()
        
        # Valider DataFrame hvis den er gitt
        if df is not None:
            if not isinstance(df, pd.DataFrame):
                raise TypeError("df må være en pandas DataFrame")
            if df.empty:
                self.logger.warning("Tom DataFrame mottatt")
        
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

    def display_user_guide(self):
        """Viser brukerveiledning for appen."""
        with st.expander("ℹ️ Om risiko for snøfokk og glatt", expanded=False):
            st.markdown("""
            ### ❄️ Risikovurdering for vinterføre
            
            *Kriteriene er utviklet gjennom analyse av værdata og faktiske hendelser siden 2018. Systemet er selvlærende og justeres løpende basert på tilbakemeldinger fra brukere og validering mot reelle situasjoner. Dette sikrer stadig mer presise varsler.*
            
            #### 🌨️ Snøfokk
            Varselet beregner risiko basert på flere faktorer:
            
            **Vindforhold:**
            - Moderat vind (>7.8 m/s): Økende risiko
            - Sterk vind (>10.6 m/s): Høy risiko
            - Kraftige vindkast (>17 m/s): Ekstra risiko
            
            **Temperatur:**
            - Mellom -2.2°C og 0°C: Gradvis økende risiko
            - Under -2.2°C: Høy risiko (tørr og lett snø)
            
            **Snødybde-endring:**
            - Under 0.8 cm: Lav risiko
            - Mellom 0.8 og 1.6 cm: Moderat risiko
            - Over 1.6 cm: Høy risiko
            
            **Luftfuktighet:**
            - Under 85%: Øker risiko (tørrere snø)
            
            *Risikoen vektes med 40% vind, 30% temperatur og 30% snødybde.*
            
            #### 🌡️ Glatte veier
            Varselet analyserer flere kritiske faktorer:
            
            **Temperatur:**
            - Mellom 0°C og +6°C: Ideelt for isdannelse
            - Høyest risiko rundt +2-3°C
            
            **Fuktighet og nedbør:**
            - Luftfuktighet over 80%
            - Minst 1.5mm nedbør siste 3 timer
            
            **Snøforhold:**
            - Snødybde over 10 cm
            - Minkende snødybde (aktiv smelting)
            
            *Risikoen er høyest når alle kriteriene er oppfylt samtidig.*
            
            #### ⚠️ Viktig å vite
            - Varslene er basert på værdata fra nærmeste målestasjon
            - Lokale forhold kan variere betydelig
            - Bruk varslene som veiledende informasjon
            - Følg alltid med på offisielle varsler
            - Oppdateres automatisk hver time
            - Varslingskriteriene valideres og forbedres kontinuerlig mot faktiske forhold
            
            #### 📊 Slik tolker du grafene
            - **Søyler**: Viser risiko fra 0-100%
            - **Farger**: 
              - 🔴 Rød (>75%): Høy risiko
              - 🟡 Gul (50-75%): Moderat risiko
              - 🟢 Grønn (<50%): Lav risiko
            - **Detaljer**: Hold musepekeren over søylene for mer informasjon
            """)

    def _map_columns(self):
        """Map kolonner fra API til standardiserte navn."""
        if self.df is None:
            return
            
        # For hver standardisert kolonne
        for std_col, api_cols in self.column_mapping.items():
            # Hvis kolonnen ikke allerede finnes
            if std_col not in self.df.columns:
                # Finn første matchende API-kolonne
                for api_col in api_cols:
                    if api_col in self.df.columns:
                        self.df[std_col] = self.df[api_col]
                        self.logger.info(f"Mapped {api_col} to {std_col}")
                        break

    def create_improved_graph(self):
        """Oppretter en forbedret graf med valgfrie varsler og værdata."""
        try:
            if self.df is None or self.df.empty:
                st.warning("Ingen data tilgjengelig")
                return False
            
            # La brukeren velge hvilke grafer som skal vises
            st.sidebar.header("Velg grafer")
            
            # Varselgrafer
            st.sidebar.subheader("Varsler")
            show_snow_drift = st.sidebar.checkbox("🌨️ Risiko for snøfokk", value=True)
            show_ice_warning = st.sidebar.checkbox("🌡️ Risiko for glatt", value=True)
            show_precipitation = st.sidebar.checkbox("🌧️ Nedbørstype", value=True)
            
            # Værdata
            st.sidebar.subheader("Værdata")
            selected_plots = {}
            for name, config in self.plot_configs.items():
                if config['column'] in self.df.columns:
                    selected_plots[name] = st.sidebar.checkbox(
                        f"{name} ({config['unit']})",
                        value=name in ["Lufttemperatur", "Snødybde", "Vindstyrke"]
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
                return False
            
            # Opprett subplot med faste størrelser
            fig = make_subplots(
                rows=num_rows,
                cols=1,
                shared_xaxes=True,
                vertical_spacing=0.05,
                subplot_titles=self._get_subplot_titles(
                    show_snow_drift,
                    show_ice_warning,
                    show_precipitation,
                    selected_plots
                ),
                row_heights=[0.25] * num_rows  # Lik høyde for alle subplot
            )
            
            # Behold bare denne ene layout-oppdateringen
            fig.update_layout(
                height=300 * num_rows,
                margin=dict(t=50, b=50, l=50, r=50),
                showlegend=False,  # Fjern legend
                plot_bgcolor='rgba(240,240,240,0.3)',
                paper_bgcolor='white',
                font=dict(
                    family="Arial, sans-serif",
                    size=12
                ),
                annotations=[{
                    'text': "Værdata fra Frost API",
                    'showarrow': False,
                    'x': 0.99,
                    'y': -0.1,
                    'xref': 'paper',
                    'yref': 'paper',
                    'font': dict(size=10, color='gray'),
                    'opacity': 0.7
                }],
                grid=dict(
                    rows=num_rows,
                    columns=1,
                    pattern='independent',
                    roworder='top to bottom'
                ),
                hoverlabel=dict(
                    bgcolor='white',
                    font_size=12,
                    font_family="Arial, sans-serif"
                )
            )
            
            # Hold styr på gjeldende radnummer
            current_row = 1
            
            # Legg til varselgrafer først
            if show_snow_drift and current_row <= num_rows:
                self._add_alert_graph(fig, row=current_row)
                current_row += 1
                
            if show_ice_warning and current_row <= num_rows:
                self._add_icy_roads_graph(fig, row=current_row)
                current_row += 1
                
            if show_precipitation and current_row <= num_rows:
                self._add_precipitation_type_graph(fig, row=current_row)
                current_row += 1
            
            # Legg til valgte værdata
            for name, show in selected_plots.items():
                if show and self.plot_configs[name]['column'] in self.df.columns:
                    if current_row > num_rows:  # Sjekk om vi har nådd maks antall rader
                        break
                        
                    if name == "Snødybde":
                        trace = go.Bar(
                            x=self.df.index,
                            y=self.df[self.plot_configs[name]['column']],
                            name=f"{name}",
                            marker_color='rgba(0, 191, 255, 0.7)',
                            showlegend=False,
                            hovertemplate=(
                                "Tidspunkt: %{x}<br>" +
                                "Snødybde: %{y:.1f} cm<br>" +
                                "<extra></extra>"
                            )
                        )
                        fig.add_trace(trace, row=current_row, col=1)
                        fig.update_yaxes(
                            title_text="Snødybde (cm)",
                            row=current_row, col=1
                        )
                    elif name == "Lufttemperatur":
                        trace = go.Scatter(
                            x=self.df.index,
                            y=self.df[self.plot_configs[name]['column']],
                            name=f"{name}",
                            line=dict(
                                color=self.plot_configs[name]['color'],
                                width=self.plot_configs[name]['line_width']
                            ),
                            showlegend=False
                        )
                        fig.add_trace(trace, row=current_row, col=1)
                        fig.update_yaxes(
                            title_text="Temperatur (°C)",
                            row=current_row, col=1
                        )
                    else:
                        trace = go.Scatter(
                            x=self.df.index,
                            y=self.df[self.plot_configs[name]['column']],
                            name=f"{name}",
                            line=dict(
                                color=self.plot_configs[name]['color'],
                                width=self.plot_configs[name]['line_width']
                            ),
                            showlegend=False
                        )
                        fig.add_trace(trace, row=current_row, col=1)
                        fig.update_yaxes(
                            title_text=f"{name} ({self.plot_configs[name]['unit']})",
                            row=current_row, col=1
                        )
                    current_row += 1
            
            # Forbedre x-akse format for alle subplots
            fig.update_xaxes(
                gridcolor='rgba(128,128,128,0.2)',
                tickformat='%H:%M\n%d.%m',
                tickangle=0,
                showgrid=True,
                zeroline=True,
                zerolinecolor='rgba(128,128,128,0.5)',
                showline=True,
                linewidth=1,
                linecolor='rgba(128,128,128,0.3)',
                mirror=True
            )

            # Forbedre y-akser for alle subplots
            fig.update_yaxes(
                gridcolor='rgba(128,128,128,0.2)',
                zeroline=True,
                zerolinecolor='rgba(128,128,128,0.5)',
                showgrid=True,
                showline=True,
                linewidth=1,
                linecolor='rgba(128,128,128,0.3)',
                mirror=True,
                ticksuffix=" "
            )

            # Vis grafen i Streamlit med config
            st.plotly_chart(
                fig,
                use_container_width=True,
                config={
                    'displayModeBar': False,  # Skjul modebar
                    'scrollZoom': False,      # Deaktiver scroll-zoom
                    'showTips': False         # Skjul tips
                }
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Feil ved oppretting av graf: {e}")
            st.error("En feil oppstod ved oppretting av grafen")
            return False

    def _add_alert_graph(self, fig, row):
        """Legger til graf som viser risiko for snøfokk."""
        try:
            # Sjekk om nødvendige data mangler
            missing_data = []
            if 'wind_speed' not in self.df.columns or self.df['wind_speed'].isnull().all():
                missing_data.append("vindstyrke")
            if 'air_temperature' not in self.df.columns or self.df['air_temperature'].isnull().all():
                missing_data.append("temperatur")
            if 'surface_snow_thickness' not in self.df.columns or self.df['surface_snow_thickness'].isnull().all():
                missing_data.append("snødybde")
            
            if missing_data:
                st.warning(f"⚠️ Værstasjonen mangler data for: {', '.join(missing_data)}")
                return
            
            # Beregn risiko for hvert tidspunkt
            risks = []
            
            # Hent nødvendige data fra DataFrame
            wind_speeds = self.df['wind_speed'].values
            temps = self.df['air_temperature'].values if 'air_temperature' in self.df.columns else None
            snow_depths = self.df['surface_snow_thickness'].values if 'surface_snow_thickness' in self.df.columns else None
            
            # Beregn risiko for hvert tidspunkt
            for i in range(len(wind_speeds)):
                risk = 0
                
                # Vindstyrke (40% vekt)
                if wind_speeds[i] > 10.6:
                    risk += 40
                elif wind_speeds[i] > 7.8:
                    risk += 20
                    
                # Temperatur (30% vekt)
                if temps is not None:
                    if temps[i] < -2.2:
                        risk += 30
                    elif temps[i] < 0:
                        risk += 15
                        
                # Snødybde (30% vekt)
                if snow_depths is not None:
                    if snow_depths[i] > 1.6:
                        risk += 30
                    elif snow_depths[i] > 0.8:
                        risk += 15
                        
                risks.append(min(risk, 100))
            
            # Opprett fargegradering basert på risikonivå
            colors = ['green' if r <= 50 else 'orange' if r <= 75 else 'red' for r in risks]
            
            # Samle risikofaktorer for hover
            hover_texts = []
            
            for i in range(len(wind_speeds)):
                factors = []
                if wind_speeds[i] > 10.6:
                    factors.append("Sterk vind (40%)")
                elif wind_speeds[i] > 7.8:
                    factors.append("Moderat vind (20%)")
                    
                if temps is not None:
                    if temps[i] < -2.2:
                        factors.append("Kald temperatur (30%)")
                    elif temps[i] < 0:
                        factors.append("Kjølig temperatur (15%)")
                        
                if snow_depths is not None:
                    if snow_depths[i] > 1.6:
                        factors.append("Mye løs snø (30%)")
                    elif snow_depths[i] > 0.8:
                        factors.append("Moderat løs snø (15%)")
                
                hover_text = (
                    f"Tidspunkt: {self.df.index[i]}<br>" +
                    f"Total risiko: {risks[i]}%<br>" +
                    (f"Faktorer:<br>- " + "<br>- ".join(factors) if factors else "Ingen risikofaktorer")
                )
                hover_texts.append(hover_text)
            
            # Legg til søylediagram med oppdatert hover
            trace = go.Bar(
                x=self.df.index,
                y=risks,
                name="Snøfokk-risiko",
                marker_color=colors,
                showlegend=False,
                hovertemplate="%{customdata}<extra></extra>",
                customdata=hover_texts,
                hoverinfo="text"
            )
            
            fig.add_trace(trace, row=row, col=1)
            
            # Oppdater y-akse
            fig.update_yaxes(
                title_text="Risiko for snøfokk (%)",
                range=[0, 100],
                ticksuffix="%",
                row=row,
                col=1
            )
            
        except Exception as e:
            self.logger.error(f"Feil ved plotting av snøfokk-risiko: {e}")
            st.error("Kunne ikke vise snøfokk-risiko")

    def _add_icy_roads_graph(self, fig, row):
        """Legger til graf som viser risiko for glatte veier."""
        try:
            # Sjekk om nødvendige data mangler
            missing_data = []
            if 'air_temperature' not in self.df.columns or self.df['air_temperature'].isnull().all():
                missing_data.append("temperatur")
            if 'relative_humidity' not in self.df.columns or self.df['relative_humidity'].isnull().all():
                missing_data.append("luftfuktighet")
            if 'sum(precipitation_amount PT1H)' not in self.df.columns:
                missing_data.append("nedbør")
            if 'surface_snow_thickness' not in self.df.columns:
                missing_data.append("snødybde")
            
            if missing_data:
                st.warning(f"⚠️ Værstasjonen mangler data for: {', '.join(missing_data)}")
                return
            
            # Beregn risiko for hvert tidspunkt
            risks = []
            hover_texts = []
            
            # Beregn snøendring
            snow_change = self.df['surface_snow_thickness'].diff()
            
            # Beregn 3-timers nedbør
            precip_3h = self.df['sum(precipitation_amount PT1H)'].rolling(window=3, min_periods=1).sum()
            
            for i in range(len(self.df)):
                risk = 0
                factors = []
                
                # Sjekk først om det er nok snø
                snow_depth = self.df['surface_snow_thickness'].iloc[i]
                if snow_depth < 10:  # Må ha minst 10 cm snø
                    risks.append(0)
                    hover_texts.append(
                        f"Tidspunkt: {self.df.index[i]}<br>" +
                        f"Total risiko: 0%<br>" +
                        f"Snødybde: {snow_depth:.1f} cm<br>" +
                        "Faktorer: For lite snø (<10 cm)"
                    )
                    continue
                
                # Temperatur (30% vekt)
                temp = self.df['air_temperature'].iloc[i]
                
                # Sjekk om det snør (temp under 0°C og nedbør)
                if temp <= 0 and i >= 2 and precip_3h.iloc[i] > 0:
                    risks.append(0)
                    hover_texts.append(
                        f"Tidspunkt: {self.df.index[i]}<br>" +
                        f"Total risiko: 0%<br>" +
                        f"Snødybde: {snow_depth:.1f} cm<br>" +
                        f"Temperatur: {temp:.1f}°C<br>" +
                        "Faktorer: Snøfall reduserer risiko"
                    )
                    continue
                
                if 0 <= temp <= 6:
                    risk += 30
                    factors.append("Temperatur 0-6°C (30%)")
                    if 2 <= temp <= 3:
                        risk += 10
                        factors.append("Ideell temperatur 2-3°C (+10%)")
                
                # Luftfuktighet (20% vekt)
                humidity = self.df['relative_humidity'].iloc[i]
                if humidity >= 80:
                    risk += 20
                    factors.append("Høy luftfuktighet >80% (20%)")
                
                # Nedbør siste 3 timer (20% vekt)
                if i >= 2:
                    if precip_3h.iloc[i] >= 1.5:
                        risk += 20
                        factors.append("Nedbør >1.5mm/3t (20%)")
                
                # Snøsmelting (20% vekt) - kun hvis temperaturen er over 0°C
                if temp > 0 and i > 0 and snow_change.iloc[i] < 0:
                    risk += 20
                    factors.append("Aktiv snøsmelting (20%)")
                
                risks.append(min(risk, 100))
                
                hover_text = (
                    f"Tidspunkt: {self.df.index[i]}<br>" +
                    f"Total risiko: {risk}%<br>" +
                    f"Snødybde: {snow_depth:.1f} cm<br>" +
                    f"Temperatur: {temp:.1f}°C<br>" +
                    (f"Faktorer:<br>- " + "<br>- ".join(factors) if factors else "Ingen risikofaktorer")
                )
                hover_texts.append(hover_text)
            
            # Opprett fargegradering basert på risikonivå
            colors = ['green' if r <= 50 else 'orange' if r <= 75 else 'red' for r in risks]
            
            # Legg til søylediagram
            trace = go.Bar(
                x=self.df.index,
                y=risks,
                name="Risiko for glatte veier",
                marker_color=colors,
                showlegend=False,
                hovertemplate="%{customdata}<extra></extra>",
                customdata=hover_texts,
                hoverinfo="text"
            )
            
            fig.add_trace(trace, row=row, col=1)
            
            # Oppdater y-akse
            fig.update_yaxes(
                title_text="Risiko for glatte veier (%)",
                range=[0, 100],
                ticksuffix="%",
                row=row,
                col=1
            )
            
        except Exception as e:
            self.logger.error(f"Feil ved plotting av isingsrisiko: {e}")
            st.error("Kunne ikke vise risiko for glatte veier")

    def _add_precipitation_type_graph(self, fig, row):
        """Legger til graf som viser nedbørstype."""
        try:
            # Sjekk om nødvendige data mangler
            missing_data = []
            required_columns = {
                "air_temperature": "temperatur",
                "sum(precipitation_amount PT1H)": "nedbør",
                "relative_humidity": "luftfuktighet"
            }
            
            for col, name in required_columns.items():
                if col not in self.df.columns or self.df[col].isnull().all():
                    missing_data.append(name)
            
            if missing_data:
                st.warning(f"⚠️ Værstasjonen mangler data for: {', '.join(missing_data)}")
                return
            
            # Definer terskelverdier
            temp_snow = -1.0  # Under denne er det snø
            temp_mix_low = -1.0  # Nedre grense for sludd
            temp_mix_high = 2.0  # Øvre grense for sludd
            
            # Klassifiser nedbørstype
            precip_types = []
            hover_texts = []
            
            for i in range(len(self.df)):
                temp = self.df['air_temperature'].iloc[i]
                precip = self.df['sum(precipitation_amount PT1H)'].iloc[i]
                
                if pd.isna(precip) or precip <= 0:
                    precip_type = 0  # Ingen nedbør
                    hover_text = "Ingen nedbør"
                elif temp <= temp_snow:
                    precip_type = 1  # Snø
                    hover_text = f"Snø ({precip:.1f} mm)"
                elif temp <= temp_mix_high:
                    precip_type = 2  # Sludd
                    hover_text = f"Sludd ({precip:.1f} mm)"
                else:
                    precip_type = 3  # Regn
                    hover_text = f"Regn ({precip:.1f} mm)"
                
                precip_types.append(precip_type)
                hover_texts.append(
                    f"Tidspunkt: {self.df.index[i]}<br>" +
                    f"Type: {hover_text}<br>" +
                    f"Temperatur: {temp:.1f}°C"
                )
            
            # Definer farger for hver type
            colors = ['lightgray', 'cyan', 'purple', 'blue']
            
            # Legg til søylediagram
            trace = go.Bar(
                x=self.df.index,
                y=precip_types,
                marker_color=[colors[t] for t in precip_types],
                showlegend=False,
                hovertemplate="%{customdata}<extra></extra>",
                customdata=hover_texts
            )
            
            fig.add_trace(trace, row=row, col=1)
            
            # Oppdater y-akse
            fig.update_yaxes(
                title_text="Nedbørstype",
                ticktext=['Ingen', 'Snø', 'Sludd', 'Regn'],
                tickvals=[0, 1, 2, 3],
                row=row,
                col=1
            )
            
        except Exception as e:
            self.logger.error(f"Feil ved plotting av nedbørstype: {e}")
            st.error("Kunne ikke vise nedbørstype")

    def _get_subplot_titles(self, show_snow_drift, show_ice_warning, show_precipitation, selected_plots):
        """Gets the subplot titles based on the selected graphs."""
        # Implementation of _get_subplot_titles method
        pass

    def display_weather_alerts(self):
        """Viser værvarsler og advarsler."""
        try:
            if self.df is None or self.df.empty:
                st.warning("Ingen værdata tilgjengelig for varsler")
                return
                
            st.subheader("🚨 Aktive værvarsler")
            
            # Sjekk snøfokk-risiko
            snow_drift_risk = self._calculate_snow_drift_risk()
            if snow_drift_risk >= 85:
                st.error("⚠️ Høy risiko for snøfokk")
            elif snow_drift_risk >= 65:
                st.error("⚠️ Moderat risiko for snøfokk")
            elif snow_drift_risk >= 45:
                st.warning("⚠️ Lav risiko for snøfokk")
                
            # Sjekk isingsrisiko
            ice_risk = self._calculate_ice_risk()
            if ice_risk > 75:
                st.error("⚠️ Høy risiko for glatte veier")
            elif ice_risk > 50:
                st.warning("⚠️ Moderat risiko for glatte veier")
                
            if snow_drift_risk < 45 and ice_risk <= 50:
                st.success("✅ Ingen aktive værvarsler")
                
        except Exception as e:
            self.logger.error(f"Feil ved visning av værvarsler: {e}")
            st.error("Kunne ikke vise værvarsler")

    def _calculate_snow_drift_risk(self):
        """Beregner risiko for snøfokk basert på værdata."""
        try:
            if 'wind_speed' not in self.df.columns or self.df['wind_speed'].empty:
                return 0
                
            # Hent siste værmålinger
            latest = self.df.iloc[-1]
            
            # Vekting av faktorer
            risk = 0
            
            # Vindstyrke (40% vekt)
            wind_speed = latest['wind_speed']
            if wind_speed > 10.6:  # Sterk vind
                risk += 40
            elif wind_speed > 7.8:  # Moderat vind
                risk += 20
                
            # Temperatur (30% vekt)
            if 'air_temperature' in self.df.columns:
                temp = latest['air_temperature']
                if temp < -2.2:
                    risk += 30
                elif temp < 0:
                    risk += 15
                    
            # Snødybde (30% vekt)
            if 'surface_snow_thickness' in self.df.columns:
                snow = latest['surface_snow_thickness']
                if snow > 1.6:
                    risk += 30
                elif snow > 0.8:
                    risk += 15
                    
            return min(risk, 100)  # Maksimalt 100% risiko
            
        except Exception as e:
            self.logger.error(f"Feil ved beregning av snøfokk-risiko: {e}")
            return 0
            
    def _calculate_ice_risk(self):
        """Beregner risiko for glatte veier basert på værdata."""
        try:
            if 'air_temperature' not in self.df.columns or self.df['air_temperature'].empty:
                return 0
                
            # Hent siste værmålinger
            latest = self.df.iloc[-1]
            
            # Vekting av faktorer
            risk = 0
            
            # Temperatur (40% vekt)
            temp = latest['air_temperature']
            if 0 <= temp <= 6:
                risk += 40
                if 2 <= temp <= 3:  # Ekstra risiko ved ideell temperatur
                    risk += 10
                    
            # Luftfuktighet (30% vekt)
            if 'relative_humidity' in self.df.columns:
                humidity = latest['relative_humidity']
                if humidity > 80:
                    risk += 30
                    
            # Nedbør (30% vekt)
            if 'sum(precipitation_amount PT1H)' in self.df.columns:
                precip = self.df['sum(precipitation_amount PT1H)'].tail(3).sum()
                if precip > 1.5:  # Mer enn 1.5mm siste 3 timer
                    risk += 30
                    
            return min(risk, 100)  # Maksimalt 100% risiko
            
        except Exception as e:
            self.logger.error(f"Feil ved beregning av isingsrisiko: {e}")
            return 0


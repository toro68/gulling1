import streamlit as st
from datetime import datetime
import pandas as pd
from frost.visualization.weather import WeatherVisualizer, get_cached_weather_data
from frost.config import FrostConfig
from utils.gps_utils import get_last_gps_activity
import logging

logger = logging.getLogger(__name__)

def main():
    st.title("Værdata fra Gullingen")
    
    col1, col2 = st.columns(2)
    with col1:
        period_type = st.selectbox(
            "Velg periode:",
            options=[
                "Siste 24 timer",
                "Siste 48 timer",
                "Siste 7 dager",
                "Egendefinert periode",
                "Været siden sist brøyting"
            ],
            key="period_selector"
        )
    
    try:
        now = pd.Timestamp.now(tz='Europe/Oslo')
        
        if period_type == "Været siden sist brøyting":
            try:
                last_gps_time = get_last_gps_activity()
                if last_gps_time:
                    start_datetime = last_gps_time
                    end_datetime = now
                    st.info(f"Siste brøyting: {last_gps_time.strftime('%Y-%m-%d %H:%M')}")
                else:
                    st.warning("GPS-data ikke tilgjengelig - viser siste 24 timer")
                    start_datetime = now - pd.Timedelta(hours=24)
                    end_datetime = now
            except Exception as e:
                logger.error(f"Feil ved henting av GPS-data: {e}")
                st.warning("Kunne ikke hente GPS-data - viser siste 24 timer")
                start_datetime = now - pd.Timedelta(hours=24)
                end_datetime = now
        elif period_type == "Egendefinert periode":
            col_start, col_end = st.columns(2)
            with col_start:
                start_date = st.date_input(
                    "Velg startdato:",
                    value=(now - pd.Timedelta(days=1)).date(),
                    key="start_date"
                )
            with col_end:
                end_date = st.date_input(
                    "Velg sluttdato:",
                    value=now.date(),
                    key="end_date"
                )
            start_datetime = pd.Timestamp(start_date, tz='Europe/Oslo')
            end_datetime = pd.Timestamp(end_date, tz='Europe/Oslo').replace(hour=23, minute=59)
        else:
            if period_type == "Siste 24 timer":
                start_datetime = now - pd.Timedelta(hours=24)
            elif period_type == "Siste 48 timer":
                start_datetime = now - pd.Timedelta(hours=48)
            else:  # Siste 7 dager
                start_datetime = now - pd.Timedelta(days=7)
            end_datetime = now
        
        if start_datetime and end_datetime:
            df = get_cached_weather_data(start_datetime, end_datetime)
            
            if df is not None and not df.empty:
                visualizer = WeatherVisualizer(None)
                visualizer.df = df
                
                # Vis væradvarsler først
                visualizer.display_weather_alerts()
                
                # Deretter vis grafer
                try:
                    fig = visualizer.create_improved_graph()
                    if fig is not None:
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.warning("Kunne ikke opprette graf")
                except Exception as e:
                    st.error(f"Feil ved visning av graf: {str(e)}")
                    logger.exception("Graf-feil:")
            else:
                st.error("Ingen data tilgjengelig for valgt periode")
    
    except Exception as e:
        st.error(f"En feil oppstod: {str(e)}")
        logger.exception("Hovedfeil:")

if __name__ == "__main__":
    main()

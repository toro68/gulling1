import streamlit as st
import pandas as pd
from frost.visualization.weather import (
    WeatherVisualizer,
    get_cached_weather_data
)
from utils.gps_utils import get_last_gps_activity
import logging

logger = logging.getLogger(__name__)

def main():
    # Sett opp sidekonfigurasjon
    st.set_page_config(
        page_title="Vinterføre",
        page_icon="❄️",
        layout="wide"
    )
    
    # Vis header
    st.title("❄️ Vinterføre")
    
    col1, _ = st.columns(2)
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
                # Kjør script for å hente siste brøytetidspunkt
                import subprocess
                import os
                
                # Få absolutt sti til scriptet
                script_path = os.path.join(os.path.dirname(__file__), 'scripts/check_last_plowing.py')
                logger.info(f"Prøver å kjøre script: {script_path}")
                
                result = subprocess.run(
                    ['python3', script_path], 
                    capture_output=True, 
                    text=True
                )
                
                # Logg resultatet
                logger.info(f"Script returnerte kode: {result.returncode}")
                logger.info(f"Script stdout: {result.stdout}")
                if result.stderr:
                    logger.error(f"Script stderr: {result.stderr}")
                
                if result.returncode == 0 and "Siste brøyting:" in result.stdout:
                    # Parse output for å finne tidspunktet
                    import re
                    match = re.search(r'Siste brøyting: (\d{2}\.\d{2}\.\d{4}) kl\. (\d{2}:\d{2})', result.stdout)
                    if match:
                        date_str = match.group(1)
                        time_str = match.group(2)
                        last_plow_time = pd.Timestamp(f"{date_str} {time_str}", tz='Europe/Oslo')
                        start_datetime = last_plow_time
                        end_datetime = now
                        st.info(
                            f"Siste brøyting: {last_plow_time.strftime('%Y-%m-%d %H:%M')}"
                        )
                    else:
                        st.warning("Kunne ikke tolke brøytetidspunkt - viser siste 24 timer")
                        start_datetime = now - pd.Timedelta(hours=24)
                        end_datetime = now
                else:
                    st.warning("Kunne ikke hente brøytedata - viser siste 24 timer")
                    start_datetime = now - pd.Timedelta(hours=24)
                    end_datetime = now
            except Exception as e:
                logger.error(f"Feil ved henting av brøytedata: {e}")
                st.warning("Kunne ikke hente brøytedata - viser siste 24 timer")
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
            end_datetime = pd.Timestamp(end_date, tz='Europe/Oslo').replace(
                hour=23,
                minute=59
            )
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
                visualizer = WeatherVisualizer(df)
                
                # Vis væradvarsler først
                visualizer.display_weather_alerts()
                
                # Vis graf og håndter resultatet
                if visualizer.create_improved_graph():
                    # Graf ble opprettet vellykket - ikke vis feilmelding
                    pass
                else:
                    # Graf kunne ikke opprettes - feilmelding er allerede vist av WeatherVisualizer
                    pass
            else:
                st.error("Ingen data tilgjengelig for valgt periode")
    
    except Exception as e:
        st.error("En feil oppstod i applikasjonen. Vennligst prøv igjen senere.")
        logger.exception("Uventet feil i hovedapplikasjonen:")

if __name__ == "__main__":
    main()

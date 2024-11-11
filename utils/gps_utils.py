import requests
from datetime import datetime
import logging
import streamlit as st
import pandas as pd
import pytz
from frost.config import FrostConfig

# Konfigurer logging
logger = logging.getLogger(__name__)
config = FrostConfig()

def fetch_gps_data():
    """Henter GPS-data fra API."""
    try:
        response = requests.get(config.GPS_URL)
        response.raise_for_status()
        
        gps_data = response.json()
        all_eq_dicts = gps_data.get('features', [])
        
        gps_entries = []
        oslo_tz = pytz.timezone('Europe/Oslo')
        
        for eq_dict in all_eq_dicts:
            date_str = eq_dict['properties'].get('Date')
            if date_str:
                try:
                    date = datetime.strptime(date_str, config.GPS_CONFIG["FORMAT"])
                    date = oslo_tz.localize(date)
                    gps_entry = {
                        'BILNR': eq_dict['properties'].get('BILNR'),
                        'Date': date
                    }
                    gps_entries.append(gps_entry)
                except ValueError as e:
                    logger.error(f"Feil ved parsing av dato: {e}")
        
        return gps_entries
        
    except requests.RequestException as e:
        logger.error(f"Feil ved henting av GPS-data: {e}")
        return []
    except Exception as e:
        logger.error(f"Uventet feil i fetch_gps_data: {e}")
        return []

def get_last_gps_activity():
    """Henter tidspunkt for siste GPS-aktivitet."""
    try:
        gps_entries = fetch_gps_data()
        if gps_entries:
            # Konverter til DataFrame for enklere håndtering
            df = pd.DataFrame(gps_entries)
            
            # Finn siste aktivitet
            last_activity = df['Date'].max()
            
            return last_activity
        else:
            logger.warning("Ingen GPS-data funnet")
            return None
            
    except Exception as e:
        logger.error(f"Feil ved henting av siste GPS-aktivitet: {e}")
        return None

def display_gps_data(start_date, end_date):
    """Viser GPS-data for valgt periode."""
    gps_entries = fetch_gps_data()

    with st.expander("Siste GPS aktivitet"):
        if gps_entries:
            df = pd.DataFrame(gps_entries)
            
            # Filtrer for valgt periode
            mask = (df['Date'] >= start_date) & (df['Date'] <= end_date)
            df = df[mask]
            
            if not df.empty:
                # Vis siste aktivitet per bil
                latest_activities = df.sort_values('Date').groupby('BILNR').last()
                
                # Formater dato for visning
                latest_activities['Formatted Date'] = latest_activities['Date'].dt.strftime('%Y-%m-%d %H:%M:%S')
                
                st.dataframe(
                    latest_activities[['Formatted Date']],
                    column_config={'Formatted Date': 'Sist aktiv'}
                )
                
                st.write(f"Antall aktive kjøretøy: {len(latest_activities)}")
            else:
                st.write("Ingen GPS-aktivitet i valgt periode")
        else:
            st.write("Ingen GPS-data tilgjengelig")
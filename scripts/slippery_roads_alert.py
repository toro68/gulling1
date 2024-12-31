import pandas as pd
import numpy as np
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import logging
import json
from pathlib import Path

# Sett opp logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/slippery_roads_alert.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def load_config():
    """Laster konfigurasjon fra config.json."""
    try:
        with open('config/alert_config.json', 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Kunne ikke laste konfigurasjon: {str(e)}")
        raise


def get_weather_data(config):
    """Henter værdata fra API."""
    try:
        # Hent data fra API (erstatt med faktisk API-kall)
        response = requests.get(config['weather_api_url'])
        response.raise_for_status()
        data = response.json()
        
        # Konverter til DataFrame
        df = pd.DataFrame([{
            'timestamp': datetime.now(),
            'air_temperature': data['temperature'],
            'surface_snow_thickness': data['snow_depth'],
            'precipitation_amount': data['precipitation_1h'],
            'relative_humidity': data['humidity']
        }])
        
        # Last tidligere data for å beregne endringer
        history_file = Path('data/temp/weather_history.csv')
        if history_file.exists():
            history = pd.read_csv(history_file)
            history['timestamp'] = pd.to_datetime(history['timestamp'])
            
            # Behold bare de siste 24 timene
            cutoff = datetime.now() - timedelta(hours=24)
            history = history[history['timestamp'] > cutoff]
            
            # Legg til ny data
            df = pd.concat([history, df], ignore_index=True)
        
        # Lagre oppdatert historikk
        df.to_csv(history_file, index=False)
        
        # Beregn endringer
        df['snow_change'] = df['surface_snow_thickness'].diff()
        df['precip_3h'] = df['precipitation_amount'].rolling(
            window=3, min_periods=1).sum()
        
        return df.iloc[-1]  # Returner siste rad
        
    except Exception as e:
        logger.error(f"Feil ved henting av værdata: {str(e)}")
        raise


def assess_slippery_conditions(weather_data, config):
    """
    Vurderer om forholdene tilsier glatte veier basert på:
    - Temperatur mellom 0°C og +6°C (smelteforhold)
    - Høy luftfuktighet
    - Minst 1.5mm nedbør siste 3 timer
    - Minst 10 cm snødybde
    - Minkende snødybde (smelting)
    """
    try:
        conditions = {
            'temp_ok': 0 <= weather_data['air_temperature'] <= 6,
            'humidity_ok': weather_data['relative_humidity'] >= 80,
            'precip_ok': weather_data['precip_3h'] >= 1.5,
            'snow_ok': weather_data['surface_snow_thickness'] >= 10,
            'melting_ok': weather_data['snow_change'] < 0
        }
        
        risk_present = all(conditions.values())
        
        return {
            'risk_present': risk_present,
            'conditions': conditions,
            'weather_data': weather_data.to_dict()
        }
        
    except Exception as e:
        logger.error(f"Feil ved risikovurdering: {str(e)}")
        raise


def send_alert_email(assessment, config):
    """Sender varsel på e-post hvis det er risiko for glatte veier."""
    if not assessment['risk_present']:
        return
    
    try:
        msg = MIMEMultipart()
        msg['From'] = config['email']['sender']
        msg['To'] = config['email']['recipient']
        msg['Subject'] = 'VARSEL: Risiko for glatte veier'
        
        # Lag e-postinnhold
        body = f"""
        VARSEL OM RISIKO FOR GLATTE VEIER
        
        Tidspunkt: {datetime.now().strftime('%Y-%m-%d %H:%M')}
        
        Værforhold:
        - Temperatur: {assessment['weather_data']['air_temperature']:.1f}°C
        - Luftfuktighet: {assessment['weather_data']['relative_humidity']:.1f}%
        - Snødybde: {assessment['weather_data']['surface_snow_thickness']:.1f} cm
        - Endring i snødybde: {assessment['weather_data']['snow_change']:.1f} cm
        - Nedbør siste 3 timer: {assessment['weather_data']['precip_3h']:.1f} mm
        
        Alle kriterier for glatte veier er oppfylt:
        - Temperatur mellom 0°C og +6°C: {assessment['conditions']['temp_ok']}
        - Høy luftfuktighet (>80%): {assessment['conditions']['humidity_ok']}
        - Tilstrekkelig nedbør (>1.5mm/3t): {assessment['conditions']['precip_ok']}
        - Nok snø på bakken (>10cm): {assessment['conditions']['snow_ok']}
        - Minkende snødybde: {assessment['conditions']['melting_ok']}
        
        Vær forsiktig!
        """
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Send e-post
        with smtplib.SMTP(config['email']['smtp_server']) as server:
            server.starttls()
            server.login(
                config['email']['username'],
                config['email']['password']
            )
            server.send_message(msg)
            
        logger.info("Varsel sendt på e-post")
        
    except Exception as e:
        logger.error(f"Feil ved sending av e-post: {str(e)}")
        raise


def main():
    try:
        # Last konfigurasjon
        config = load_config()
        
        # Hent værdata
        weather_data = get_weather_data(config)
        
        # Vurder forhold
        assessment = assess_slippery_conditions(weather_data, config)
        
        # Send varsel hvis nødvendig
        if assessment['risk_present']:
            send_alert_email(assessment, config)
            logger.info("Varsel sendt - risiko for glatte veier")
        else:
            logger.info("Ingen risiko for glatte veier")
        
    except Exception as e:
        logger.error(f"Feil i hovedprogrammet: {str(e)}")
        raise


if __name__ == "__main__":
    main() 
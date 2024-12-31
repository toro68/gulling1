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
        logging.FileHandler('logs/snowdrift_alert.log'),
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
    """Henter ferske værdata fra Frost API."""
    try:
        # Frost API endepunkt
        endpoint = 'https://frost.met.no/observations/v0.jsonld'
        
        # Parametere for API-kall
        now = datetime.now()
        params = {
            'sources': config['weather_station'],
            'elements': ','.join([
                'air_temperature',
                'wind_speed',
                'relative_humidity',
                'surface_snow_thickness',
                'max_wind_speed_3h',
                'wind_from_direction'
            ]),
            'referencetime': f"{now - timedelta(hours=3)}/{now}"
        }
        
        # Utfør API-kall
        response = requests.get(
            endpoint,
            params=params,
            auth=(config['frost_client_id'], '')
        )
        
        if response.status_code == 200:
            data = response.json()
            return pd.json_normalize(
                data['data'],
                ['observations'],
                ['referenceTime']
            )
        else:
            logger.error(f"API-feil: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"Feil ved henting av værdata: {str(e)}")
        return None

def assess_snowdrift_risk(weather_data, config):
    """Vurderer risiko for snøfokk basert på værdata."""
    try:
        # Grunnleggende kriterier
        wind_ok = weather_data['wind_speed'].max() >= config['wind_threshold']
        temp_ok = weather_data['air_temperature'].mean() <= config['temp_threshold']
        snow_ok = weather_data['surface_snow_thickness'].max() >= config['snow_depth_threshold']
        humidity_ok = weather_data['relative_humidity'].mean() <= config['humidity_threshold']
        
        # Beregn risikoscore
        risk_score = 0
        if wind_ok and temp_ok and snow_ok and humidity_ok:
            wind_factor = min(weather_data['wind_speed'].max() / 15.0, 1.0)
            temp_factor = min(abs(weather_data['air_temperature'].mean()) / 10.0, 1.0)
            snow_factor = min(weather_data['surface_snow_thickness'].max() / 50.0, 1.0)
            
            risk_score = (wind_factor * 0.4 + 
                         temp_factor * 0.3 + 
                         snow_factor * 0.3)
            
        return {
            'risk_score': risk_score,
            'conditions': {
                'wind_speed': weather_data['wind_speed'].max(),
                'temperature': weather_data['air_temperature'].mean(),
                'snow_depth': weather_data['surface_snow_thickness'].max(),
                'humidity': weather_data['relative_humidity'].mean()
            }
        }
        
    except Exception as e:
        logger.error(f"Feil ved risikovurdering: {str(e)}")
        return None

def send_alert_email(risk_assessment, config):
    """Sender e-postvarsel ved høy risiko for snøfokk."""
    try:
        if risk_assessment['risk_score'] >= config['risk_threshold']:
            # Opprett e-post
            msg = MIMEMultipart()
            msg['From'] = config['email_from']
            msg['To'] = config['email_to']
            msg['Subject'] = 'VARSEL: Høy risiko for snøfokk'
            
            # E-postinnhold
            body = f"""
            VARSEL OM HØY RISIKO FOR SNØFOKK
            
            Tidspunkt: {datetime.now().strftime('%Y-%m-%d %H:%M')}
            Risikoscore: {risk_assessment['risk_score']:.2f}
            
            Værforhold:
            - Vindstyrke: {risk_assessment['conditions']['wind_speed']:.1f} m/s
            - Temperatur: {risk_assessment['conditions']['temperature']:.1f}°C
            - Snødybde: {risk_assessment['conditions']['snow_depth']:.1f} cm
            - Luftfuktighet: {risk_assessment['conditions']['humidity']:.1f}%
            
            Dette er et automatisk varsel. Følg med på lokale værforhold.
            """
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Send e-post
            with smtplib.SMTP(config['smtp_server'], config['smtp_port']) as server:
                server.starttls()
                server.login(config['smtp_username'], config['smtp_password'])
                server.send_message(msg)
                
            logger.info("Varsel sendt på e-post")
            return True
            
    except Exception as e:
        logger.error(f"Feil ved sending av e-post: {str(e)}")
        return False

def main():
    """Hovedfunksjon for snøfokk-varsling."""
    try:
        # Opprett nødvendige mapper
        Path('logs').mkdir(exist_ok=True)
        Path('config').mkdir(exist_ok=True)
        
        # Last konfigurasjon
        config = load_config()
        
        # Hent værdata
        weather_data = get_weather_data(config)
        if weather_data is None:
            return
            
        # Vurder risiko
        risk_assessment = assess_snowdrift_risk(weather_data, config)
        if risk_assessment is None:
            return
            
        # Send varsel hvis høy risiko
        if risk_assessment['risk_score'] >= config['risk_threshold']:
            send_alert_email(risk_assessment, config)
            
    except Exception as e:
        logger.error(f"En feil oppstod i hovedfunksjonen: {str(e)}")

if __name__ == '__main__':
    main() 
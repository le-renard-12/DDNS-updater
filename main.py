import requests
import yaml
from cloudflare import Cloudflare
import json
import pprint
import os
from typing import *
import logging
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ddns_updater.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def retrieve_current_public_ip()-> str :
    """Gets your current public IP.

    Returns:
        str:(ip) Your public IP value
    """
    try:
        response = requests.get("https://ipinfo.io/ip")

        status = response.status_code
        ip = response.text
        
        if status == 200:
            return ip
        else:
            return None
    
    except Exception as e:
        logger.error(f"Error retrieving public IP: {e}")
        return None

def read_secrets(file_path)-> dict:
    
    with open(file=file_path, mode="r", encoding="utf-8") as f:
        secrets = yaml.safe_load(f)
    
    return secrets

def get_record_id(api_email: str, api_key: str, zone_id: str, record_name: str) -> Optional[str]:
    """Get the record ID for a given record name.
    
    Args:
        api_email (str): Cloudflare API email
        api_key (str): Cloudflare API key
        zone_id (str): Zone ID of the domain
        record_name (str): Name of the A record to find
    
    Returns:
        Optional[str]: Record ID if found, None otherwise
    """
    try:
        client = Cloudflare(api_email=api_email, api_key=api_key)
        record = client.dns.records.list(
            zone_id=zone_id,
            name=record_name,
        )
        
        if record:
            record_id = record.result[0].id
            logger.info(f"Found record ID for {record_name}: {record_id}")
            return record_id
        
        return None
    except Exception as e:
        logger.error(f"Error getting record ID: {e}")
        return None

def update_dns_record(api_email: str, api_key: str, zone_id: str, record_id: str, new_ip: str) -> bool:
    """Updates a DNS A record with the new IP address.

    Args:
        api_email (str): Cloudflare API email
        api_key (str): Cloudflare API key
        zone_id (str): Zone ID of the domain
        record_id (str): DNS record ID to update
        new_ip (str): New IP address to set

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        client = Cloudflare(api_email=api_email, api_key=api_key)
        
        response = client.dns.records.edit(
            zone_id=zone_id,
            dns_record_id=record_id,
            content=new_ip            
        )
        
        if response:
            logger.info(f"DNS record updated to {new_ip}")
            return True
        
        return False
    except Exception as e:
        logger.error(f"Error updating DNS record: {e}")
        return False

def run_updater():
    logger.info("Starting DDNS update process")
    
    # Read configuration
    secrets = read_secrets('secrets.yaml')
    
    # Get current public IP
    current_ip = retrieve_current_public_ip()
    if not current_ip:
        logger.error("Failed to retrieve public IP")
        return
    
    logger.info(f"Current public IP: {current_ip}")
    
    # Update each record in the list
    for record_name in secrets['cloudflare']['record_names']:
        logger.info(f"Processing record: {record_name}")
        
        # Get record ID from record name
        record_id = get_record_id(
            api_email=secrets['cloudflare']['email'],
            api_key=secrets['cloudflare']['api_key'],
            zone_id=secrets['cloudflare']['zone_id'],
            record_name=record_name
        )
        
        if not record_id:
            logger.warning(f"Failed to find record ID for {record_name}")
            continue
        
        # Update DNS record
        success = update_dns_record(
            api_email=secrets['cloudflare']['email'],
            api_key=secrets['cloudflare']['api_key'],
            zone_id=secrets['cloudflare']['zone_id'],
            record_id=record_id,
            new_ip=current_ip
        )
        
        if success:
            logger.info(f"Successfully updated DNS record {record_name} to {current_ip}")
        else:
            logger.error(f"Failed to update DNS record {record_name}")
    
    logger.info("DDNS update process completed")

def main():
    secrets = read_secrets('secrets.yaml')
    scheduler = BlockingScheduler()
    
    # Add the job with cron schedule from config
    scheduler.add_job(
        run_updater,
        CronTrigger.from_crontab(secrets['schedule']['cron'])
    )
    
    logger.info(f"Starting scheduler with cron: {secrets['schedule']['cron']}")
    scheduler.start()

if __name__ == "__main__":
    main()


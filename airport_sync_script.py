#!/usr/bin/env python3
"""
Airport & Country Data Synchronization Script
============================================

Downloads and synchronizes airport and country data from OurAirports.com
to Supabase database every 6 months for continent/region analysis.

Data Sources:
- https://davidmegginson.github.io/ourairports-data/airports.csv
- https://davidmegginson.github.io/ourairports-data/countries.csv

Author: FlightRadar Scraper Team
Last Updated: September 14, 2025
"""

import os
import sys
import requests
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv
import logging
from datetime import datetime, timedelta
import json

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('airport_sync.log'),
        logging.StreamHandler()
    ]
)

# Load environment variables
load_dotenv()

# Database configuration
DB_CONFIG = {
    'dbname': os.getenv("DB_NAME"),
    'user': os.getenv("DB_USER"),
    'password': os.getenv("DB_PASSWORD"),
    'host': os.getenv("DB_HOST"),
    'port': os.getenv("DB_PORT")
}

# Data source URLs
AIRPORTS_CSV_URL = "https://davidmegginson.github.io/ourairports-data/airports.csv"
COUNTRIES_CSV_URL = "https://davidmegginson.github.io/ourairports-data/countries.csv"

# File paths for local storage
DATA_DIR = "airport_data"
AIRPORTS_FILE = os.path.join(DATA_DIR, "airports.csv")
COUNTRIES_FILE = os.path.join(DATA_DIR, "countries.csv")
MERGED_FILE = os.path.join(DATA_DIR, "airports_geography.csv")
SYNC_LOG_FILE = os.path.join(DATA_DIR, "sync_log.json")

class AirportDataSyncer:
    """Handles downloading, processing, and syncing airport/country data."""
    
    def __init__(self):
        self.ensure_data_directory()
        self.connection = None
        
    def ensure_data_directory(self):
        """Create data directory if it doesn't exist."""
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)
            logging.info(f"Created data directory: {DATA_DIR}")
    
    def connect_to_database(self):
        """Establish connection to Supabase PostgreSQL database."""
        try:
            self.connection = psycopg2.connect(**DB_CONFIG)
            logging.info("Successfully connected to Supabase database")
            return True
        except Exception as e:
            logging.error(f"Failed to connect to database: {e}")
            return False
    
    def disconnect_from_database(self):
        """Close database connection."""
        if self.connection:
            self.connection.close()
            logging.info("Database connection closed")
    
    def should_sync(self):
        """Check if 6 months have passed since last sync."""
        if not os.path.exists(SYNC_LOG_FILE):
            logging.info("No previous sync found - proceeding with initial sync")
            return True
            
        try:
            with open(SYNC_LOG_FILE, 'r') as f:
                sync_log = json.load(f)
                
            last_sync = datetime.fromisoformat(sync_log.get('last_sync', '2000-01-01'))
            six_months_ago = datetime.now() - timedelta(days=180)
            
            if last_sync < six_months_ago:
                logging.info(f"Last sync was {last_sync.strftime('%Y-%m-%d')} - sync needed")
                return True
            else:
                logging.info(f"Last sync was {last_sync.strftime('%Y-%m-%d')} - sync not needed yet")
                return False
                
        except Exception as e:
            logging.warning(f"Error reading sync log: {e} - proceeding with sync")
            return True
    
    def download_csv_file(self, url, local_path):
        """Download CSV file from URL to local path."""
        try:
            logging.info(f"Downloading {url}")
            response = requests.get(url, timeout=60)
            response.raise_for_status()
            
            with open(local_path, 'wb') as f:
                f.write(response.content)
                
            logging.info(f"Successfully downloaded to {local_path}")
            return True
            
        except Exception as e:
            logging.error(f"Failed to download {url}: {e}")
            return False
    
    def download_source_data(self):
        """Download both airports.csv and countries.csv files."""
        logging.info("Starting data download process...")
        
        success = True
        success &= self.download_csv_file(AIRPORTS_CSV_URL, AIRPORTS_FILE)
        success &= self.download_csv_file(COUNTRIES_CSV_URL, COUNTRIES_FILE)
        
        if success:
            logging.info("All source files downloaded successfully")
        else:
            logging.error("Failed to download some source files")
            
        return success
    
    def merge_airport_country_data(self):
        """Process airports and countries data, focusing on IATA airports."""
        try:
            logging.info("Loading and processing CSV files...")
            
            # Load datasets
            airports_df = pd.read_csv(AIRPORTS_FILE)
            countries_df = pd.read_csv(COUNTRIES_FILE)
            
            logging.info(f"Loaded {len(airports_df)} airports and {len(countries_df)} countries")
            
            # Filter airports with IATA codes (our primary focus)
            airports_with_iata = airports_df[
                (airports_df['iata_code'].notna()) & 
                (airports_df['iata_code'] != '') &
                (airports_df['type'].isin(['large_airport', 'medium_airport', 'small_airport']))
            ].copy()
            
            logging.info(f"Found {len(airports_with_iata)} airports with IATA codes")
            
            # Merge with countries data to get country names
            merged_df = airports_with_iata.merge(
                countries_df[['code', 'name']],
                left_on='iso_country',
                right_on='code',
                how='left'
            )
            
            # Select and rename columns for our geography table
            geography_df = merged_df[[
                'iata_code',
                'name_x',  # airport name
                'iso_country',
                'name_y',  # country name
                'continent',  # from airports CSV
                'latitude_deg',
                'longitude_deg',
                'elevation_ft',
                'municipality'
            ]].copy()
            
            # Rename columns for clarity
            geography_df.columns = [
                'iata_code',
                'airport_name',
                'country_code',
                'country_name',
                'continent',
                'latitude',
                'longitude',
                'elevation_ft',
                'city'
            ]
            
            # Fix missing continent data for North American countries
            north_american_countries = [
                'US', 'CA', 'MX', 'GT', 'BZ', 'SV', 'HN', 'NI', 'CR', 'PA', 
                'CU', 'JM', 'HT', 'DO', 'BS', 'BB', 'TT', 'GD', 'LC', 'VC',
                'AG', 'DM', 'KN', 'AI', 'VG', 'VI', 'PR', 'GP', 'MQ', 'BL',
                'MF', 'SX', 'CW', 'AW', 'BQ', 'TC', 'KY', 'BM', 'GL'
            ]
            
            # Assign NA continent to North American countries where continent is null
            # Use both .isnull() and .isna() to catch all null variations
            na_mask = (
                (geography_df['country_code'].isin(north_american_countries)) & 
                (geography_df['continent'].isnull() | geography_df['continent'].isna())
            )
            geography_df.loc[na_mask, 'continent'] = 'NA'
            
            logging.info(f"Assigned NA continent to {na_mask.sum()} North American airports")
            
            # Clean up data - only drop records where iata_code is null
            # Don't drop continent nulls yet since we just assigned NA values
            geography_df = geography_df.dropna(subset=['iata_code'])
            
            # Now check for any remaining null continents and log them
            remaining_nulls = geography_df['continent'].isnull().sum()
            if remaining_nulls > 0:
                logging.warning(f"Still have {remaining_nulls} airports with null continents after NA assignment")
                # Drop remaining null continents
                geography_df = geography_df.dropna(subset=['continent'])
            
            geography_df['airport_name'] = geography_df['airport_name'].str.strip()
            geography_df['continent'] = geography_df['continent'].str.strip()
            
            # Fill missing country names with country code if needed
            geography_df['country_name'] = geography_df['country_name'].fillna(geography_df['country_code'])
            geography_df['country_name'] = geography_df['country_name'].str.strip()
            
            # Save merged data
            geography_df.to_csv(MERGED_FILE, index=False)
            logging.info(f"Processed data saved to {MERGED_FILE} with {len(geography_df)} records")
            
            return geography_df
            
        except Exception as e:
            logging.error(f"Failed to process airport/country data: {e}")
            return None
    
    def create_geography_table(self):
        """Create the airports_geography table in Supabase if it doesn't exist."""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS airports_geography (
            id SERIAL PRIMARY KEY,
            iata_code VARCHAR(3) UNIQUE NOT NULL,
            airport_name VARCHAR(255) NOT NULL,
            country_code VARCHAR(5),
            country_name VARCHAR(100),
            continent VARCHAR(50) NOT NULL,
            latitude DECIMAL(10, 6),
            longitude DECIMAL(10, 6),
            elevation_ft INTEGER,
            city VARCHAR(100),
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Create indexes for better query performance (only if they don't exist)
        CREATE INDEX IF NOT EXISTS idx_airports_geography_iata ON airports_geography(iata_code);
        CREATE INDEX IF NOT EXISTS idx_airports_geography_country ON airports_geography(country_code);
        CREATE INDEX IF NOT EXISTS idx_airports_geography_continent ON airports_geography(continent);
        """
        
        try:
            cursor = self.connection.cursor()
            logging.info("Creating airports_geography table if it doesn't exist...")
            cursor.execute(create_table_sql)
            self.connection.commit()
            cursor.close()
            logging.info("Successfully created/verified airports_geography table")
            return True
            
        except Exception as e:
            logging.error(f"Failed to create airports_geography table: {e}")
            if self.connection:
                self.connection.rollback()
            return False
    
    def sync_to_database(self, geography_df):
        """Sync the merged geography data to Supabase."""
        if geography_df is None or len(geography_df) == 0:
            logging.error("No geography data to sync")
            return False
        
        try:
            # Create table if needed
            if not self.create_geography_table():
                return False
            
            # Prepare data for insertion
            data_tuples = [
                (
                    row['iata_code'],
                    row['airport_name'],
                    row['country_code'],
                    row['country_name'],
                    row['continent'],
                    row['latitude'] if pd.notna(row['latitude']) else None,
                    row['longitude'] if pd.notna(row['longitude']) else None,
                    int(row['elevation_ft']) if pd.notna(row['elevation_ft']) else None,
                    row['city'] if pd.notna(row['city']) else None
                )
                for _, row in geography_df.iterrows()
            ]
            
            # Use UPSERT logic like scraper_final_v5 - INSERT ... ON CONFLICT ... UPDATE
            cursor = self.connection.cursor()
            
            logging.info(f"Upserting {len(data_tuples)} geography records...")
            upsert_sql = """
                INSERT INTO airports_geography (
                    iata_code, airport_name, country_code, country_name, continent,
                    latitude, longitude, elevation_ft, city
                ) VALUES %s
                ON CONFLICT (iata_code) DO UPDATE SET
                    airport_name = EXCLUDED.airport_name,
                    country_code = EXCLUDED.country_code,
                    country_name = EXCLUDED.country_name,
                    continent = EXCLUDED.continent,
                    latitude = EXCLUDED.latitude,
                    longitude = EXCLUDED.longitude,
                    elevation_ft = EXCLUDED.elevation_ft,
                    city = EXCLUDED.city,
                    last_updated = CURRENT_TIMESTAMP
            """
            
            execute_values(cursor, upsert_sql, data_tuples, page_size=1000)
            self.connection.commit()
            
            # Get counts of inserted vs updated
            cursor.execute("SELECT COUNT(*) FROM airports_geography;")
            total_count = cursor.fetchone()[0]
            cursor.close()
            
            logging.info(f"Successfully synced {len(data_tuples)} airport geography records")
            logging.info(f"Total airports in database: {total_count}")
            return True
            
        except Exception as e:
            logging.error(f"Failed to sync data to database: {e}")
            if self.connection:
                self.connection.rollback()
            return False
    
    def update_sync_log(self):
        """Update the sync log with current timestamp."""
        sync_log = {
            'last_sync': datetime.now().isoformat(),
            'records_synced': 0,  # Will be updated by caller
            'status': 'success'
        }
        
        try:
            with open(SYNC_LOG_FILE, 'w') as f:
                json.dump(sync_log, f, indent=2)
            logging.info("Sync log updated successfully")
            
        except Exception as e:
            logging.warning(f"Failed to update sync log: {e}")
    
    def run_sync(self, force=False):
        """Run the complete synchronization process."""
        logging.info("=" * 60)
        logging.info("AIRPORT GEOGRAPHY DATA SYNC - STARTING")
        logging.info("=" * 60)
        
        # Check if sync is needed (skip check if force=True for manual runs)
        if not force and not self.should_sync():
            logging.info("Sync not needed at this time - use --force to sync anyway")
            return True
        
        # Connect to database
        if not self.connect_to_database():
            return False
        
        try:
            # Download source data
            if not self.download_source_data():
                return False
            
            # Merge and process data
            geography_df = self.merge_airport_country_data()
            if geography_df is None:
                return False
            
            # Sync to database
            if not self.sync_to_database(geography_df):
                return False
            
            # Update sync log
            self.update_sync_log()
            
            logging.info("=" * 60)
            logging.info("AIRPORT GEOGRAPHY DATA SYNC - COMPLETED SUCCESSFULLY")
            logging.info(f"Synced {len(geography_df)} airport records")
            logging.info("=" * 60)
            
            return True
            
        except Exception as e:
            logging.error(f"Sync process failed: {e}")
            return False
            
        finally:
            self.disconnect_from_database()

def main():
    """Main function to run the sync process."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Sync airport geography data')
    parser.add_argument('--force', action='store_true', 
                       help='Force sync even if 6 months have not passed')
    parser.add_argument('--test', action='store_true',
                       help='Test mode - download and process but do not sync to database')
    
    args = parser.parse_args()
    
    syncer = AirportDataSyncer()
    
    if args.test:
        logging.info("Running in TEST mode - no database sync")
        syncer.download_source_data()
        geography_df = syncer.merge_airport_country_data()
        if geography_df is not None:
            logging.info(f"Test successful - would sync {len(geography_df)} records")
        return
    
    success = syncer.run_sync(force=args.force)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()

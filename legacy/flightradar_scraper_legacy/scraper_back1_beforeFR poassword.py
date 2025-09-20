# scraper.py
import os
import psycopg2
from dotenv import load_dotenv
import logging
import requests
from bs4 import BeautifulSoup
import time # For adding delays
from psycopg2.extras import execute_values # Import the helper

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables from .env file
load_dotenv()

# Database connection details from environment variables
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")

# --- Database Functions ---
def get_db_connection():
    """Establishes a connection to the PostgreSQL database using pooler details."""
    conn = None
    # (Error checking for missing vars omitted for brevity - was added before)
    try:
        logging.info(f"Attempting to connect to database '{DB_NAME}' via pooler {DB_HOST}:{DB_PORT}...")
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        logging.info("Database connection successful!")
        return conn
    except psycopg2.OperationalError as e:
        logging.error(f"Database connection failed: {e}")
        return None
    except Exception as e:
        logging.error(f"An unexpected error occurred during connection: {e}")
        return None

# --- Web Scraping Functions ---
HEADERS = { # (Headers defined as before)
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://www.google.com/'
}

def get_aircraft_list_page(aircraft_type_code):
    """Fetches the HTML content for the aircraft type list page."""
    url = f"https://www.flightradar24.com/data/aircraft/{aircraft_type_code.lower()}"
    logging.info(f"Fetching aircraft list page: {url}")
    try:
        response = requests.get(url, headers=HEADERS, timeout=20)
        response.raise_for_status()
        logging.info(f"Successfully fetched page. Status code: {response.status_code}")
        return response.text
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to fetch page {url}: {e}")
        return None

def extract_registrations(html_content, aircraft_type_code):
    """Parses HTML to find aircraft registration links."""
    registrations = set()
    if not html_content:
        return list(registrations)

    soup = BeautifulSoup(html_content, 'html.parser')
    table_rows = soup.find_all('tr') # Assuming this selector still works
    link_pattern = f"/data/aircraft/"

    for row in table_rows:
        links = row.find_all('a', href=True)
        for link in links:
            href = link['href']
            if href.startswith(link_pattern) and not href.endswith(f"/{aircraft_type_code.lower()}"):
                 registration = href.split('/')[-1].upper()
                 if registration and len(registration) > 2 and not registration.isdigit():
                     registrations.add(registration)

    if not registrations:
        logging.warning("Could not extract any registrations. The HTML structure or selectors might have changed.")
    else:
        logging.info(f"Extracted {len(registrations)} unique potential registrations.")

    return list(registrations)

# --- Database Interaction Function (Using Batch Inserts) ---
def save_registrations_to_db(conn, registrations, aircraft_type_code):
    """Saves a list of registrations to the aircraft table using batch inserts."""
    if not registrations:
        logging.warning("No registrations provided to save.")
        return 0

    if conn is None:
        logging.error("Cannot save registrations, database connection is invalid.")
        return 0

    # Prepare data as a list of tuples: [(reg1, type), (reg2, type), ...]
    data_tuples = [(reg, aircraft_type_code) for reg in registrations]

    # SQL uses %s placeholders for execute_values
    sql = """
        INSERT INTO aircraft (registration, type)
        VALUES %s
        ON CONFLICT (registration) DO NOTHING;
    """

    logging.info(f"Attempting batch insert of {len(data_tuples)} registrations for type {aircraft_type_code}...")

    cursor = None
    try:
        cursor = conn.cursor()
        logging.debug("Database cursor created.")

        # Execute the batch insert
        # execute_values efficiently inserts multiple rows
        # page_size can be adjusted, 100 is a reasonable default
        execute_values(cursor, sql, data_tuples, page_size=100)

        inserted_count = cursor.rowcount # For INSERT ... DO NOTHING, rowcount reflects affected rows (might be 0 if all existed)
                                        # It's harder to get exact new vs skipped count with execute_values this way
                                        # but we know the operation completed if no error occurred.

        logging.info(f"Batch insert command executed. Committing transaction...")
        conn.commit()
        logging.info(f"Commit successful. Processed approximately {len(data_tuples)} registrations (new or existing).")
        # We return the number of tuples processed as a proxy for success
        # A more complex approach would be needed to count exact inserts vs skips
        return len(data_tuples) # Return total processed instead of just inserted

    except psycopg2.Error as e:
        logging.error(f"DATABASE ERROR during batch insert: {e}")
        if conn and not conn.closed:
             logging.info("Attempting to rollback transaction due to DB error.")
             conn.rollback()
        return 0 # Indicate failure
    except Exception as e:
        logging.error(f"UNEXPECTED ERROR during batch database operation: {e}")
        if conn and not conn.closed:
             logging.info("Attempting to rollback transaction due to unexpected error.")
             conn.rollback()
        return 0
    finally:
        if cursor:
            cursor.close()
            logging.debug("Database cursor closed.")

    # This part is unlikely to be reached now but kept for structure
    return 0 # Should have returned earlier


# --- Main Execution Block ---
if __name__ == "__main__":
    connection = None
    # List of aircraft types to process
    AIRCRAFT_TYPES_TO_SCRAPE = ["A330", "B747", "B757", "B767", "B777", "IL76"]
    # Delay between fetching pages for different aircraft types (in seconds)
    FETCH_DELAY_SECONDS = 5

    total_new_registrations = 0

    try:
        # 1. Establish DB Connection
        logging.info("--- Script Start ---")
        connection = get_db_connection()
        if not connection:
             logging.error("Database connection failed. Exiting.")
             exit() # Stop if we can't connect

        # 2. Loop through each aircraft type
        for target_aircraft_type in AIRCRAFT_TYPES_TO_SCRAPE:
            logging.info(f"--- Processing Aircraft Type: {target_aircraft_type} ---")

            # 2a. Fetch the list page
            html = get_aircraft_list_page(target_aircraft_type)

            if html:
                # 2b. Extract registrations
                regs = extract_registrations(html, target_aircraft_type)

                # 2c. Save registrations to Database
                if regs:
                     inserted = save_registrations_to_db(connection, regs, target_aircraft_type)
                     if inserted > 0: # Keep track of total new ones across all types
                         total_new_registrations += inserted
                     logging.info(f"Processed {target_aircraft_type}. Result count (new or existing): {inserted}")
                else:
                    logging.warning(f"No registrations found for {target_aircraft_type}.")
            else:
                logging.error(f"Could not retrieve page for {target_aircraft_type}.")

            # 2d. Wait before fetching the next type to avoid rate limiting
            logging.info(f"Waiting {FETCH_DELAY_SECONDS} seconds before next aircraft type...")
            time.sleep(FETCH_DELAY_SECONDS)

        logging.info(f"--- Finished processing all aircraft types. Total new registrations added: {total_new_registrations} ---")

        # --- Placeholder for future steps ---
        # TODO: Fetch flight movements for each registration
        # TODO: Implement monthly update logic

    except Exception as main_exception:
        logging.error(f"An error occurred in the main execution block: {main_exception}", exc_info=True) # Log stack trace

    finally:
        # Ensure the connection is closed if it was successfully opened
        if connection:
            connection.close()
            logging.info("Database connection closed.")
        logging.info("--- Script End ---")

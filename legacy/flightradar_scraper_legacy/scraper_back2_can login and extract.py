# scraper.py (Backup before testing login/history fetch)
import os
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv
import logging
import requests
from bs4 import BeautifulSoup
import time
import datetime
import re # Import regex for parsing

# --- Setup ---
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
load_dotenv()

# Database details
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")

# Flightradar24 Credentials
FR24_USERNAME = os.getenv("FR24_USERNAME")
FR24_PASSWORD = os.getenv("FR24_PASSWORD")

# Basic check for FR24 credentials
if not FR24_USERNAME or not FR24_PASSWORD:
    logging.warning("Flightradar24 username or password missing in .env file. Cannot log in for extended history.")

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://www.google.com/'
}

# --- Database Functions ---
def get_db_connection():
    """Establishes a connection to the PostgreSQL database using pooler details."""
    conn = None
    try:
        logging.info(f"Attempting to connect to database '{DB_NAME}' via pooler {DB_HOST}:{DB_PORT}...")
        conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT)
        logging.info("Database connection successful!")
        return conn
    except psycopg2.OperationalError as e: logging.error(f"Database connection failed: {e}"); return None
    except Exception as e: logging.error(f"An unexpected error occurred during connection: {e}"); return None

def save_registrations_to_db(conn, registrations, aircraft_type_code):
    """Saves a list of registrations to the aircraft table using batch inserts."""
    if not registrations: logging.warning("No registrations provided to save."); return 0
    if conn is None: logging.error("Cannot save registrations, database connection is invalid."); return 0
    data_tuples = [(reg, aircraft_type_code) for reg in registrations]
    sql = "INSERT INTO aircraft (registration, type) VALUES %s ON CONFLICT (registration) DO NOTHING;"
    logging.info(f"Attempting batch insert of {len(data_tuples)} registrations for type {aircraft_type_code}...")
    cursor = None
    try:
        cursor = conn.cursor()
        execute_values(cursor, sql, data_tuples, page_size=100)
        logging.info(f"Batch insert command executed. Committing transaction...")
        conn.commit()
        logging.info(f"Commit successful. Processed approximately {len(data_tuples)} registrations (new or existing).")
        return len(data_tuples)
    except psycopg2.Error as e: logging.error(f"DATABASE ERROR during batch insert: {e}"); conn.rollback(); return 0
    except Exception as e: logging.error(f"UNEXPECTED ERROR during batch database operation: {e}"); conn.rollback(); return 0
    finally:
        if cursor: cursor.close()
    return 0

# --- Web Scraping Functions ---

# --- Flightradar24 Login Function (Attempt 3 - Pre-fetch + Headers) ---
def fr24_login(session):
    """Logs into Flightradar24 - fetches page first and adds more headers."""
    if not FR24_USERNAME or not FR24_PASSWORD:
        logging.error("Login credentials not found in environment variables.")
        return False

    login_url = "https://www.flightradar24.com/user/login"
    # A page to fetch first to establish session/cookies
    initial_page_url = "https://www.flightradar24.com/" # Try main page

    payload = {
        'email': FR24_USERNAME, 'password': FR24_PASSWORD,
        'remember': 'true', 'returnUrl': 'undefined', 'type': 'web'
    }

    # --- Update Headers - Mimic browser more closely ---
    login_headers = {
        'User-Agent': HEADERS['User-Agent'], # Keep base User-Agent
        'Accept': '*/*', # More generic Accept seen in browser fetch
        'Accept-Language': HEADERS['Accept-Language'],
        'Origin': 'https://www.flightradar24.com', # Often required for POST
        'Referer': initial_page_url, # Referer should be the page containing the form
        # 'Content-Type': 'application/x-www-form-urlencoded', # Let requests set this based on 'data'
        'Sec-Ch-Ua': '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"', # From browser
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"macOS"',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        # Add X-Requested-With if commonly used by FR24's JS, otherwise omit
        # 'X-Requested-With': 'XMLHttpRequest'
    }


    try:
        # --- Step 1: GET initial page to establish session/cookies ---
        logging.info(f"Fetching initial page {initial_page_url} to prepare session...")
        initial_response = session.get(initial_page_url, headers=HEADERS, timeout=20)
        initial_response.raise_for_status()
        logging.debug(f"Initial page fetch status: {initial_response.status_code}")
        # We don't necessarily need to parse this page, just let the session store cookies

        # --- Step 2: POST login data ---
        logging.info(f"Attempting login POST to {login_url} as {FR24_USERNAME}...")
        response = session.post(login_url, headers=login_headers, data=payload, timeout=25)
        response.raise_for_status() # Check for HTTP errors (like 520 again?)

        # --- Check for successful login (JSON check) ---
        final_url = response.url; content_type = response.headers.get('content-type', '').lower()
        logging.debug(f"Login POST finished. Status: {response.status_code}, Final URL: {final_url}, Content-Type: {content_type}")

        is_json_response = 'application/json' in content_type
        if is_json_response:
             # (JSON parsing and checking logic as before)
             try:
                json_response = response.json()
                logging.debug(f"Login response JSON: {json_response}")
                if json_response.get("success") is True or json_response.get("status") == "success":
                    logging.info("Flightradar24 login successful (based on JSON response).")
                    features = json_response.get("features", {}); history_days = features.get("history.aircraft.days", 0)
                    logging.info(f"Detected history access: {history_days} days.")
                    return True
                else:
                    error_message = json_response.get("message", "Unknown error in JSON")
                    logging.warning(f"Flightradar24 login failed (JSON response): {error_message}")
                    return False
             except ValueError:
                logging.warning("Could not parse JSON response despite content type."); logging.debug(f"Login response text: {response.text[:1000]}"); return False
        else:
             # (Fallback HTML keyword check as before)
             logging.warning(f"Login response was not JSON (Content-Type: {content_type}). Attempting keyword check...")
             # ... (rest of keyword check logic) ...
             logging.warning("Flightradar24 login check failed (HTML response or keywords not found)."); return False


    except requests.exceptions.HTTPError as http_err:
        # Log specific HTTP errors like the 520
        logging.error(f"HTTP error during Flightradar24 login: {http_err}")
        # Log response body if available, might contain clues for 5xx errors
        if http_err.response is not None:
             logging.error(f"Response Body Snippet: {http_err.response.text[:1000]}")
        return False
    except requests.exceptions.RequestException as e:
        logging.error(f"Network error during Flightradar24 login request: {e}")
        return False
    except Exception as e:
        logging.error(f"Unexpected error during login: {e}", exc_info=True)
        return False

# --- Modified Web Scraping Functions to use Session ---

def get_aircraft_list_page(session, aircraft_type_code):
    """Fetches the HTML content for the aircraft type list page using a session."""
    url = f"https://www.flightradar24.com/data/aircraft/{aircraft_type_code.lower()}"
    logging.info(f"Fetching aircraft list page: {url}")
    try:
        response = session.get(url, headers=HEADERS, timeout=20)
        response.raise_for_status()
        logging.info(f"Successfully fetched page. Status code: {response.status_code}")
        return response.text
    except requests.exceptions.RequestException as e: logging.error(f"Failed to fetch page {url}: {e}"); return None

def extract_registrations(html_content, aircraft_type_code):
    """Parses HTML to find aircraft registration links."""
    # (Assuming this function works as is from previous step)
    registrations = set(); soup = BeautifulSoup(html_content, 'html.parser'); table_rows = soup.find_all('tr'); link_pattern = f"/data/aircraft/"
    for row in table_rows:
        links = row.find_all('a', href=True)
        for link in links:
            href = link['href'];
            if href.startswith(link_pattern) and not href.endswith(f"/{aircraft_type_code.lower()}"):
                 registration = href.split('/')[-1].upper();
                 if registration and len(registration) > 2 and not registration.isdigit(): registrations.add(registration)
    if not registrations: logging.warning("Could not extract any registrations.")
    else: logging.info(f"Extracted {len(registrations)} unique potential registrations.")
    return list(registrations)


def get_flight_history_page(session, registration):
    """Fetches the HTML content for a specific aircraft's flight history page using a session."""
    url = f"https://www.flightradar24.com/data/aircraft/{registration.lower()}"
    logging.info(f"Fetching flight history page for {registration}: {url}")
    try:
        response = session.get(url, headers=HEADERS, timeout=20)
        response.raise_for_status()
        logging.info(f"Successfully fetched history page. Status code: {response.status_code}")
        return response.text
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to fetch history page {url}: {e}")
        return None

# --- NEW: Parsing Helper Functions ---
def parse_fr24_datetime(date_str, time_str, current_year):
    """Combines date and time strings from FR24 into a datetime object (assuming UTC)."""
    if not date_str or not time_str or time_str == '—':
        return None
    try:
        # Handle dates like "05 Apr" - assume current year
        if len(date_str.split()) == 2:
            date_str = f"{date_str} {current_year}"

        # Combine date and time
        full_datetime_str = f"{date_str} {time_str}"
        # Specify format including year
        dt = datetime.datetime.strptime(full_datetime_str, '%d %b %Y %H:%M')
        # Assume FR24 uses UTC - add timezone info
        return dt.replace(tzinfo=datetime.timezone.utc)
    except ValueError as e:
        logging.warning(f"Could not parse datetime: '{date_str} {time_str}'. Error: {e}")
        return None

def parse_flight_time(time_str):
    """Converts flight time string like '3:00' to timedelta or None."""
    if not time_str or time_str == '—':
        return None
    try:
        hours, minutes = map(int, time_str.split(':'))
        return datetime.timedelta(hours=hours, minutes=minutes)
    except ValueError:
        logging.warning(f"Could not parse flight time: '{time_str}'")
        return None

# --- Updated extract_flight_history to include basic parsing ---
def extract_flight_history(html_content, registration):
    """Parses HTML to extract and parse flight history data."""
    flights = []
    if not html_content: return flights

    # (Optional) Save HTML
    # try: ... with open(...) ... except ...

    soup = BeautifulSoup(html_content, 'html.parser')
    table = soup.find('table', id='tbl-datatable')

    if not table:
        logging.warning(f"Could not find flight history table using id='tbl-datatable' for {registration}.")
        # (Check for subscription msg) ...
        return flights
    else:
        logging.debug(f"Found table with id='tbl-datatable'.") # Changed to debug

    table_body = table.find('tbody')
    data_rows = table_body.find_all('tr') if table_body else table.find_all('tr')
    logging.debug(f"Found {len(data_rows)} total <tr> rows for {registration}.") # Changed to debug

    if not data_rows: logging.warning(f"No <tr> rows found for {registration}."); return flights

    current_year = datetime.datetime.now().year # Get current year for date parsing

    for row_index, row in enumerate(data_rows):
        cells = row.find_all('td')
        expected_min_cells = 12
        if len(cells) < expected_min_cells: continue

        try:
            date_str = cells[2].text.strip()
            from_airport_raw = cells[3].text.strip()
            to_airport_raw = cells[4].text.strip()
            flight_num_tag = cells[5].find('a')
            flight_num = flight_num_tag.text.strip() if flight_num_tag else cells[5].text.strip()
            flight_time_str = cells[6].text.strip()
            std_str = cells[7].text.strip()
            atd_str = cells[8].text.strip()
            sta_str = cells[9].text.strip()
            status_or_ata_str = cells[11].text.strip()

            origin_code = from_airport_raw.split('(')[-1].replace(')', '').strip() if '(' in from_airport_raw else from_airport_raw
            destination_code = to_airport_raw.split('(')[-1].replace(')', '').strip() if '(' in to_airport_raw else to_airport_raw
            origin_name = from_airport_raw.split('(')[0].strip() if '(' in from_airport_raw else ""
            destination_name = to_airport_raw.split('(')[0].strip() if '(' in to_airport_raw else ""

            # --- PARSE DATES/TIMES ---
            # Note: Assumes UTC timezone from FR24
            std_dt = parse_fr24_datetime(date_str, std_str, current_year)
            atd_dt = parse_fr24_datetime(date_str, atd_str, current_year)
            sta_dt = parse_fr24_datetime(date_str, sta_str, current_year) # Need arrival date logic
            # TODO: Improve sta_dt - it might be on the next day! Requires comparing STD/Flight Time

            # Parse ATA from status string (e.g., "Landed 03:32")
            ata_dt = None
            if status_or_ata_str.startswith("Landed"):
                ata_time_str = status_or_ata_str.replace("Landed", "").strip()
                # TODO: Determine arrival date correctly for ATA (could be next day)
                ata_dt = parse_fr24_datetime(date_str, ata_time_str, current_year)

            # Parse flight time
            flight_time_delta = parse_flight_time(flight_time_str)

            # We need ATD for the unique key, skip if unavailable
            if not atd_dt:
                 logging.debug(f"Skipping row {row_index+1} for {registration} due to missing ATD.")
                 continue

            flight_data = {
                "registration": registration,
                "flight_number": flight_num,
                "origin_code": origin_code,
                "origin_name": origin_name,
                "destination_code": destination_code,
                "destination_name": destination_name,
                "scheduled_departure": std_dt,
                "actual_departure": atd_dt, # Used in unique constraint
                "scheduled_arrival": sta_dt,
                "actual_arrival": ata_dt,
                "flight_time": flight_time_delta,
                # 'scrape_date' is added by DB default
            }
            flights.append(flight_data)

        # (Error handling except blocks as before) ...
        except IndexError: logging.warning(f"Skipping row {row_index+1} due to IndexError...")
        except AttributeError: logging.warning(f"Skipping row {row_index+1} due to AttributeError...")
        except Exception as e: logging.error(f"Error parsing row {row_index+1} for {registration}: {e}", exc_info=True)

    logging.info(f"Successfully parsed {len(flights)} flight records for {registration}.")
    return flights

# --- NEW: Function to Save Flight History ---
def save_flight_history_to_db(conn, flight_records):
    """Saves a list of parsed flight records to the movements table using batch inserts."""
    if not flight_records:
        logging.warning("No flight records provided to save.")
        return 0
    if conn is None:
        logging.error("Cannot save flight records, database connection is invalid.")
        return 0

    # Prepare data tuples in the correct order for the movements table columns
    # registration, flight_number, origin_code, origin_name, destination_code, destination_name,
    # scheduled_departure, actual_departure, scheduled_arrival, actual_arrival, flight_time
    data_tuples = [
        (
            rec.get("registration"), rec.get("flight_number"),
            rec.get("origin_code"), rec.get("origin_name"),
            rec.get("destination_code"), rec.get("destination_name"),
            rec.get("scheduled_departure"), rec.get("actual_departure"),
            rec.get("scheduled_arrival"), rec.get("actual_arrival"),
            rec.get("flight_time")
        ) for rec in flight_records
    ]

    sql = """
        INSERT INTO movements (
            registration, flight_number, origin_code, origin_name, destination_code, destination_name,
            scheduled_departure, actual_departure, scheduled_arrival, actual_arrival, flight_time
        ) VALUES %s
        ON CONFLICT (registration, flight_number, actual_departure) DO NOTHING;
    """
    # Assumes unique constraint is on (registration, flight_number, actual_departure)

    logging.info(f"Attempting batch insert of {len(data_tuples)} flight movements...")
    cursor = None
    try:
        cursor = conn.cursor()
        execute_values(cursor, sql, data_tuples, page_size=100)
        processed_count = cursor.rowcount # Might not be accurate for new vs skipped
        logging.info(f"Movement batch insert command executed. Approx affected/processed rows: {processed_count}. Committing...")
        conn.commit()
        logging.info(f"Commit successful.")
        return len(data_tuples) # Return total processed

    except psycopg2.Error as e:
        logging.error(f"DATABASE ERROR during movement batch insert: {e}")
        if conn and not conn.closed: conn.rollback()
        return 0 # Indicate failure
    except Exception as e:
        logging.error(f"UNEXPECTED ERROR during movement batch database operation: {e}")
        if conn and not conn.closed: conn.rollback()
        return 0
    finally:
        if cursor: cursor.close()

    return 0

# --- Main Execution Block ---
if __name__ == "__main__":
    connection = None
    web_session = requests.Session()
    web_session.headers.update(HEADERS) # Set default headers

    # --- List of all aircraft types you want to track ---
    AIRCRAFT_TYPES_TO_SCRAPE = ["A330", "B747", "B757", "B767", "B777", "IL76"]
    FETCH_DELAY_SECONDS = 3 # Delay between requests to be polite

    total_new_registrations_overall = 0 # Track across all types
    total_movements_processed_overall = 0 # Track across all types

    try:
        logging.info("--- Script Start ---")

        # 1. Login (Crucial for consistent access)
        logged_in = False
        if FR24_USERNAME and FR24_PASSWORD:
            logged_in = fr24_login(web_session)
            if logged_in:
                logging.info("Login successful, proceeding.")
                time.sleep(FETCH_DELAY_SECONDS) # Wait after login
            else:
                logging.warning("Login failed. History data might be incomplete or blocked. Proceeding anyway...")
                # Consider exiting if login is absolutely required:
                # exit("Exiting due to login failure.")
        else:
            logging.info("No FR24 credentials found, proceeding without login.")

        # 2. DB Connection
        connection = get_db_connection()
        if not connection:
            logging.error("Database connection failed. Exiting.")
            exit() # Cannot proceed without DB

        # --- Combined Loop: Process Each Type and its History ---
        for target_aircraft_type in AIRCRAFT_TYPES_TO_SCRAPE:
            logging.info(f"========== Processing Aircraft Type: {target_aircraft_type} ==========")
            current_registrations = []

            # --- Part 1: Get Registrations for this type ---
            logging.info(f"--- Fetching registrations for {target_aircraft_type} ---")
            html = get_aircraft_list_page(web_session, target_aircraft_type)
            if html:
                regs = extract_registrations(html, target_aircraft_type)
                if regs:
                    inserted_count = save_registrations_to_db(connection, regs, target_aircraft_type)
                    logging.info(f"Saved/Processed {inserted_count} registrations for {target_aircraft_type}.")
                    # Store regs found for history fetching, even if already in DB
                    current_registrations = regs
                else:
                    logging.warning(f"No registrations extracted for {target_aircraft_type}.")
            else:
                logging.error(f"Could not retrieve registration list page for {target_aircraft_type}.")

            logging.info(f"Waiting {FETCH_DELAY_SECONDS} seconds before fetching history...")
            time.sleep(FETCH_DELAY_SECONDS)

            # --- Part 2: Fetch History for ALL found registrations for this type ---
            if not current_registrations:
                logging.warning(f"Skipping history fetch for {target_aircraft_type} as no registrations were found/extracted.")
                continue # Move to the next aircraft type

            logging.info(f"--- Fetching history for {len(current_registrations)} registrations of type {target_aircraft_type} ---")
            for i, reg_to_fetch in enumerate(current_registrations):
                logging.info(f"--- Processing History for {target_aircraft_type} registration {i+1}/{len(current_registrations)}: {reg_to_fetch} ---")
                history_html = get_flight_history_page(web_session, reg_to_fetch)

                if history_html:
                    # Check for "no data" message before parsing table
                    if "could not find data for specified flight" in history_html.lower():
                        logging.info(f"History page for {reg_to_fetch} indicates no data available. Skipping.")
                    else:
                        # Parse data (HTML method)
                        flight_records = extract_flight_history(history_html, reg_to_fetch)

                        if flight_records:
                            # Save extracted records to DB
                            processed = save_flight_history_to_db(connection, flight_records)
                            if processed >= 0: # execute_values might return 0 if all were skipped
                                total_movements_processed_overall += len(flight_records) # Count attempts
                                logging.info(f"Attempted to save {len(flight_records)} movement records for {reg_to_fetch} (ON CONFLICT skips existing).")
                            else:
                                logging.warning(f"Database save function indicated an error for {reg_to_fetch}.")
                        else:
                             # extract_flight_history already logs warnings if table/rows not found
                             logging.warning(f"No flight records were parsed from the page for {reg_to_fetch} (may be expected if table structure changed or was empty).")
                else:
                     logging.error(f"Could not retrieve history page for {reg_to_fetch}.")

                # Delay between each history page request
                logging.debug(f"Waiting {FETCH_DELAY_SECONDS} seconds before next registration...")
                time.sleep(FETCH_DELAY_SECONDS)

            logging.info(f"--- Finished processing history for type {target_aircraft_type} ---")
            # Optional longer delay between aircraft types
            # logging.info(f"Waiting a bit longer before starting next aircraft type...")
            # time.sleep(FETCH_DELAY_SECONDS * 2)


        logging.info("========== Script Finished Processing All Types ==========")
        logging.info(f"Total movement records processed/attempted to save across all types: {total_movements_processed_overall}")

    except Exception as main_exception:
        logging.error(f"An unhandled error occurred in the main execution block: {main_exception}", exc_info=True)
    finally:
        if connection:
            connection.close()
            logging.info("Database connection closed.")
        logging.info("--- Script End ---")

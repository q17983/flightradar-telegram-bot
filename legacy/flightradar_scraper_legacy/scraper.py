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

# --- Progress File ---
PROGRESS_FILE = "scraper_progress.txt"

def read_progress():
    """Reads the last processed item from the progress file."""
    try:
        if os.path.exists(PROGRESS_FILE):
            with open(PROGRESS_FILE, 'r') as f:
                line = f.readline().strip()
                if line and ':' in line:
                    last_type, last_reg = line.split(':', 1)
                    logging.info(f"Resuming after Type: {last_type}, Registration: {last_reg}")
                    return last_type, last_reg
    except Exception as e:
        logging.error(f"Error reading progress file {PROGRESS_FILE}: {e}")
    logging.info("No valid progress file found, starting from beginning.")
    return None, None

def write_progress(aircraft_type, registration):
    """Writes the last successfully processed item to the progress file."""
    try:
        with open(PROGRESS_FILE, 'w') as f:
            f.write(f"{aircraft_type}:{registration}\n")
        logging.debug(f"Progress saved: {aircraft_type}:{registration}")
    except Exception as e:
        logging.error(f"Error writing progress file {PROGRESS_FILE}: {e}")

def clear_progress():
    """Removes the progress file on successful completion."""
    try:
        if os.path.exists(PROGRESS_FILE):
            os.remove(PROGRESS_FILE)
            logging.info(f"Progress file {PROGRESS_FILE} removed.")
    except Exception as e:
        logging.error(f"Error removing progress file {PROGRESS_FILE}: {e}")

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

def save_registrations_to_db(conn, aircraft_list):
    """Saves aircraft data (reg, specific_type, operator) using INSERT ... ON CONFLICT ... UPDATE."""
    if not aircraft_list:
        logging.warning("No aircraft data provided to save.")
        return 0
    if conn is None or conn.closed:
        logging.error("Cannot save aircraft data, database connection is invalid.")
        return 0

    # Prepare list of tuples: (registration, specific_type, operator)
    # Ensure specific_type is not None before adding
    data_tuples = [(reg, specific_type, airline) for reg, specific_type, airline in aircraft_list if specific_type]

    if not data_tuples:
        logging.warning("No valid aircraft data tuples (with specific type) to save.")
        return 0

    # Use ON CONFLICT to insert new, or update existing type/operator if changed
    sql = """
        INSERT INTO aircraft (registration, type, operator)
        VALUES %s
        ON CONFLICT (registration) DO UPDATE SET
            type = EXCLUDED.type, -- Update type from the scraped specific value
            operator = CASE
                           WHEN aircraft.operator IS NULL AND EXCLUDED.operator IS NOT NULL THEN EXCLUDED.operator
                           ELSE aircraft.operator
                       END
        WHERE aircraft.type IS DISTINCT FROM EXCLUDED.type -- Update if type is different
           OR (aircraft.operator IS NULL AND EXCLUDED.operator IS NOT NULL); -- Update if operator was NULL and is now known
        """

    logging.info(f"Attempting batch insert/update of {len(data_tuples)} aircraft records...")
    cursor = None
    try:
        cursor = conn.cursor()
        execute_values(cursor, sql, data_tuples, page_size=100)
        logging.info(f"Aircraft batch insert/update command executed. Committing...")
        conn.commit()
        logging.info(f"Commit successful.")
        return len(data_tuples)
    except psycopg2.Error as e:
        logging.error(f"DATABASE ERROR during aircraft batch insert/update: {e}")
        if conn and not conn.closed: conn.rollback()
        return 0
    except Exception as e:
        logging.error(f"UNEXPECTED ERROR during aircraft batch database operation: {e}")
        if conn and not conn.closed: conn.rollback()
        return 0
    finally:
        if cursor: cursor.close()

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

# --- MODIFIED AGAIN: Extract Specific Type, Registration, AND Airline ---
def extract_registrations(html_content):
    """Parses the main aircraft type list HTML to find specific type, registration, and airline."""
    aircraft_data = {} # Dict stores {registration: (specific_type, airline_name)}
    if not html_content: return []

    soup = BeautifulSoup(html_content, 'html.parser')

    # --- Find table (logic as before) ---
    list_container = soup.find('div', id='cnt-list-aircraft')
    if not list_container:
        table = soup.find('table', class_='data-table')
        if not table: table = soup.find('table')
    else:
        table = list_container.find('table', class_='data-table')
        if not table: table = list_container.find('table')

    if not table:
        logging.warning(f"Could not find main aircraft list table.") # Removed type code from log
        return []

    table_body = table.find('tbody')
    rows = table_body.find_all('tr') if table_body else table.find_all('tr')

    logging.debug(f"Found {len(rows)} total <tr> rows in list table.")
    if not rows:
        logging.warning(f"No <tr> rows found in list table.")
        return []

    processed_count = 0
    skipped_rows = 0
    start_index = 1 if len(rows) > 1 and rows[0].find('th') else 0
    logging.debug(f"Starting row parsing from index {start_index}.")

    for row_index, row in enumerate(rows[start_index:], start=start_index):
        cells = row.find_all('td')

        # Need cells for MSN, Type, Reg, Airline (at least 4)
        if len(cells) >= 4:
            try:
                # --- Indices based on recent logs/screenshots ---
                # cells[0]: MSN
                # cells[1]: Specific Type Code <<-- NEW
                # cells[2]: Registration
                # cells[3]: Airline
                # ---

                # Extract Specific Type
                specific_type = cells[1].text.strip().upper()
                if not specific_type or specific_type == '-': # Handle empty/placeholder type
                    # logging.debug(f"DEBUG ROW {row_index}: SKIPPING - Specific type is empty in cell 1.")
                    skipped_rows+=1
                    continue

                # Extract Registration
                reg_cell = cells[2]
                reg_link = reg_cell.find('a', href=True)
                registration = reg_link.text.strip().upper() if reg_link else None
                if not registration:
                    # logging.debug(f"DEBUG ROW {row_index}: SKIPPING - Reg text is None/empty in cell 2.")
                    skipped_rows+=1
                    continue

                # Extract Airline
                airline_cell = cells[3]
                airline_link = airline_cell.find('a', href=True)
                airline_name = airline_link.text.strip() if airline_link else airline_cell.text.strip()
                if not airline_name or airline_name == '-' or airline_name == '':
                    airline_name = None

                # Store data: {registration: (specific_type, airline_name)}
                aircraft_data[registration] = (specific_type, airline_name)
                processed_count += 1

            except IndexError:
                skipped_rows+=1
            except Exception as e:
                logging.error(f"Error parsing row {row_index}: {e}", exc_info=False)
                skipped_rows+=1
        else:
            skipped_rows+=1

    if skipped_rows > 0:
         logging.debug(f"Total skipped rows during parsing: {skipped_rows}")

    if not aircraft_data:
        logging.warning(f"Could not extract any valid (type, reg, airline) tuples.")
    else:
        logging.info(f"Extracted {len(aircraft_data)} unique aircraft data tuples (Type, Reg, Airline).")

    # Return list of tuples: [(registration, specific_type, airline_name), ...]
    return [(reg, data[0], data[1]) for reg, data in aircraft_data.items()]


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
def extract_flight_history(html_content, registration, latest_known_departure_ts=None):
    """Parses HTML, applying filter based on latest known departure timestamp."""
    flights = []
    if not html_content: return flights

    # (Optional) Save HTML
    # try: ... with open(...) ... except ...

    soup = BeautifulSoup(html_content, 'html.parser')
    table = soup.find('table', id='tbl-datatable')

    if not table:
        logging.warning(f"Could not find flight history table for {registration}."); return flights
    else:
        logging.debug(f"Found table with id='tbl-datatable'.")

    table_body = table.find('tbody')
    data_rows = table_body.find_all('tr') if table_body else table.find_all('tr')
    logging.debug(f"Found {len(data_rows)} total <tr> rows for {registration}.")

    if not data_rows: logging.warning(f"No <tr> rows found for {registration}."); return flights

    current_year = datetime.datetime.now().year
    new_flights_found_count = 0

    for row_index, row in enumerate(data_rows):
        cells = row.find_all('td')
        expected_min_cells = 12
        if len(cells) < expected_min_cells: continue

        try:
            # --- Extract data (indices as determined before) ---
            date_str = cells[2].text.strip()
            atd_str = cells[8].text.strip() # Get ATD early for timestamp check

            # --- PARSE ATD FIRST for comparison ---
            atd_dt = parse_fr24_datetime(date_str, atd_str, current_year)

            # --- Check if flight is newer than latest known ---
            if latest_known_departure_ts and atd_dt and atd_dt <= latest_known_departure_ts:
                # logging.debug(f"Skipping row {row_index+1} for {registration}: ATD {atd_dt} is not newer than known {latest_known_departure_ts}")
                continue # Skip this flight, it's not new

            # --- If we reach here, the flight is potentially new, proceed with full parsing ---
            from_airport_raw = cells[3].text.strip(); to_airport_raw = cells[4].text.strip()
            flight_num_tag = cells[5].find('a'); flight_num = flight_num_tag.text.strip() if flight_num_tag else cells[5].text.strip()
            flight_time_str = cells[6].text.strip(); std_str = cells[7].text.strip(); sta_str = cells[9].text.strip()
            status_or_ata_str = cells[11].text.strip()

            origin_code = from_airport_raw.split('(')[-1].replace(')', '').strip() if '(' in from_airport_raw else from_airport_raw
            destination_code = to_airport_raw.split('(')[-1].replace(')', '').strip() if '(' in to_airport_raw else to_airport_raw
            origin_name = from_airport_raw.split('(')[0].strip() if '(' in from_airport_raw else ""
            destination_name = to_airport_raw.split('(')[0].strip() if '(' in to_airport_raw else ""

            # Parse remaining dates/times
            std_dt = parse_fr24_datetime(date_str, std_str, current_year)
            sta_dt = parse_fr24_datetime(date_str, sta_str, current_year) # Still needs arrival day logic
            ata_dt = None
            if status_or_ata_str.startswith("Landed"):
                ata_time_str = status_or_ata_str.replace("Landed", "").strip()
                ata_dt = parse_fr24_datetime(date_str, ata_time_str, current_year) # Still needs arrival day logic

            flight_time_delta = parse_flight_time(flight_time_str)

            # Require ATD for saving (part of key)
            if not atd_dt:
                logging.debug(f"Skipping row {row_index+1} for {registration}: Missing ATD after passing time check.")
                continue

            flight_data = {
                "registration": registration, "flight_number": flight_num,
                "origin_code": origin_code, "origin_name": origin_name,
                "destination_code": destination_code, "destination_name": destination_name,
                "scheduled_departure": std_dt, "actual_departure": atd_dt,
                "scheduled_arrival": sta_dt, "actual_arrival": ata_dt,
                "flight_time": flight_time_delta,
            }
            flights.append(flight_data)
            new_flights_found_count += 1

        # (Error handling except blocks as before) ...
        except IndexError: logging.warning(f"Skipping row {row_index+1} due to IndexError...")
        except AttributeError: logging.warning(f"Skipping row {row_index+1} due to AttributeError...")
        except Exception as e: logging.error(f"Error parsing row {row_index+1} for {registration}: {e}", exc_info=True)

    # Log count of flights *after* timestamp filtering
    logging.info(f"Parsed {new_flights_found_count} potentially new flight records for {registration} (after timestamp check).")
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

def get_latest_movement_timestamp(conn, registration):
    """Queries the DB for the most recent actual_departure timestamp for a registration."""
    if conn is None or conn.closed:
        logging.error(f"Cannot get latest timestamp for {registration}, DB connection invalid.")
        return None

    sql = "SELECT MAX(actual_departure) FROM movements WHERE registration = %s;"
    cursor = None
    latest_timestamp = None
    try:
        cursor = conn.cursor()
        cursor.execute(sql, (registration,))
        result = cursor.fetchone()
        if result and result[0]:
            latest_timestamp = result[0]
            # Ensure it's timezone-aware (assuming DB stores TIMESTAMPTZ)
            if latest_timestamp.tzinfo is None:
                 # If DB didn't store TZ, assume UTC based on our parsing
                 latest_timestamp = latest_timestamp.replace(tzinfo=datetime.timezone.utc)
            logging.debug(f"Latest known departure for {registration} in DB: {latest_timestamp}")
        else:
            logging.debug(f"No previous movements found in DB for {registration}.")
    except psycopg2.Error as e:
        logging.error(f"DATABASE ERROR fetching latest timestamp for {registration}: {e}")
    except Exception as e:
        logging.error(f"UNEXPECTED ERROR fetching latest timestamp for {registration}: {e}")
    finally:
        if cursor: cursor.close()
    return latest_timestamp

def parse_codes(code_str):
    """ Parses 'XX / XXX', 'XXX', or 'XX-XXX' into IATA, ICAO codes """
    iata = None
    icao = None
    if not code_str:
        return iata, icao

    code_str = code_str.strip()
    # Explicitly return None if it's just a hyphen
    if code_str == '-':
         logging.info("Code field contains only '-', indicating codes are not listed.")
         return iata, icao

    parts = []
    if ' / ' in code_str:
        parts = [p.strip() for p in code_str.split('/')]
    elif '-' in code_str and len(code_str) > 1: # Avoid splitting just '-'
        parts = [p.strip() for p in code_str.split('-')]
    else: # Handle single code (could be IATA or ICAO) or unexpected format
        parts = [code_str]

    if len(parts) == 2:
        # Assume format is IATA / ICAO or IATA-ICAO
        part1 = parts[0].upper()
        part2 = parts[1].upper()

        # Simple assignment based on length assumption
        if len(part1) <= 2 and len(part2) == 3: # Common case XX / XXX
            iata = part1
            icao = part2
        elif len(part1) == 3 and len(part2) <= 2: # Less common XXX / XX
            icao = part1
            iata = part2
        elif len(part1) <= 2: # If first is IATA-like, assign it
             iata = part1
        elif len(part1) == 3: # If first is ICAO-like, assign it
             icao = part1
        # Assign second part if the other wasn't assigned yet and length matches
        if not icao and len(part2) == 3:
            icao = part2
        elif not iata and len(part2) <= 2:
            iata = part2

    elif len(parts) == 1:
        # Assume it's ICAO if 3 chars, otherwise maybe IATA
        candidate = parts[0].upper()
        if len(candidate) == 3:
            icao = candidate
            logging.debug(f"Parsed single code '{candidate}' as ICAO.")
        elif len(candidate) <= 2 and candidate: # Check it's not empty
            iata = candidate # Less common case
            logging.debug(f"Parsed single code '{candidate}' as IATA.")
        else:
             logging.warning(f"Single code part '{candidate}' doesn't fit IATA/ICAO pattern.")


    # Final validation based on expected lengths
    if iata and not (1 <= len(iata) <= 2):
        logging.warning(f"Parsed IATA '{iata}' has unexpected length, discarding.")
        iata = None
    if icao and len(icao) != 3:
        logging.warning(f"Parsed ICAO '{icao}' has unexpected length, discarding.")
        icao = None

    return iata, icao

def extract_aircraft_details_from_history(html_content):
    """
    Parses the aircraft history page HTML for details, and the IATA/ICAO codes
    from the FIRST 'Code' label found.
    """
    details = {}
    if not html_content: return None

    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        # --- Try finding a reasonably specific container first ---
        info_container = soup.find('div', id='cnt-aircraft-info')
        if not info_container:
            # Fallback selectors based on observed structures
            info_container = soup.find('div', class_='col-md-6')
            if not info_container:
                 # Look for the div containing the code labels specifically
                 potential_containers = soup.find_all('div', class_='col-sm-5')
                 for pc in potential_containers:
                      if pc.find('label', string=re.compile(r'^Code$', re.IGNORECASE)):
                           info_container = pc
                           logging.debug("Found potential info container based on 'Code' label presence.")
                           break
                 if not info_container: # Ultimate fallback
                    info_container = soup
                    logging.debug("Could not find specific info container, searching whole page.")

        # --- Extract Aircraft Details ---
        details_value = None
        # Search within the determined container, or globally if needed
        search_area = info_container if info_container != soup else soup
        aircraft_label = search_area.find('label', string=re.compile(r'AIRCRAFT', re.IGNORECASE))
        if aircraft_label:
            details_span = aircraft_label.find_next('span', class_='details')
            if details_span: details_value = details_span.text.strip()
        details['details'] = details_value
        logging.debug(f"Extracted Aircraft Details: {details_value if details_value else 'Not Found'}")

        # --- Extract Codes using the FIRST "Code" Label Found ---
        iata_code = None
        icao_code = None
        # Find ALL 'Code' labels within the container
        code_labels = info_container.find_all('label', string=re.compile(r'^Code$', re.IGNORECASE))

        if code_labels:
            # --- Focus ONLY on the first label found ---
            first_code_label = code_labels[0]
            logging.debug("Found at least one 'Code' label. Processing the first one.")
            code_span = first_code_label.find_next('span', class_='details')
            if code_span:
                code_text = code_span.text.strip()
                logging.debug(f"Found text next to FIRST 'Code' label: '{code_text}'")
                # Parse codes using the helper function (which now handles '-')
                iata_code, icao_code = parse_codes(code_text)
                if iata_code or icao_code:
                     logging.info(f"Extracted Codes from FIRST 'Code' text '{code_text}': IATA={iata_code}, ICAO={icao_code}")
                elif code_text != '-': # Only warn if it wasn't the expected hyphen
                     logging.warning(f"Could not parse IATA/ICAO from FIRST 'Code' text: '{code_text}' (and it wasn't '-')")
            else:
                logging.warning("Found first 'Code' label but no adjacent 'details' span.")
        else:
            logging.warning("Could not find any '<label>Code</label>' tag.")

        details['iata'] = iata_code
        details['icao'] = icao_code

        # Return details if we found the aircraft detail string OR the ICAO code
        if details['details'] or details['icao']:
            return details
        else:
            logging.warning("Failed to extract essential details (Aircraft Detail or ICAO code). Returning None.")
            return None

    except Exception as e:
        logging.error(f"Error occurred during detail/code extraction: {e}", exc_info=True)
        return None

# --- NEW: Function to Update Aircraft Details and Last Scraped ---
def update_aircraft_details(conn, registration, details, iata, icao):
    """Updates aircraft_details, codes, and last_scraped time in the aircraft table."""
    if not registration or (not details and not iata and not icao):
        logging.debug(f"Skipping detail update for {registration}: No new data provided.")
        return False
    if conn is None or conn.closed:
        logging.error(f"Cannot update details for {registration}, DB connection invalid.")
        return False

    # Build the SET part dynamically based on what data we have
    set_clauses = []
    params = []
    if details:
        set_clauses.append("aircraft_details = %s")
        params.append(details)
    if iata:
        set_clauses.append("operator_iata_code = %s")
        params.append(iata)
    if icao:
        set_clauses.append("operator_icao_code = %s")
        params.append(icao)

    # Always update last_scraped if we are updating anything else
    set_clauses.append("last_scraped = NOW()")

    if not params: # Should not happen if initial check passed, but good safety
        return False

    params.append(registration) # Add registration for the WHERE clause

    sql = f"""
        UPDATE aircraft
        SET {', '.join(set_clauses)}
        WHERE registration = %s;
        """
    # Note: This overwrites existing data for these columns.
    # Could add AND column IS NULL checks to WHERE if only want to fill blanks.

    cursor = None
    try:
        cursor = conn.cursor()
        logging.debug(f"Executing detail update for {registration}: SQL={cursor.mogrify(sql, params).decode('utf-8')}")
        cursor.execute(sql, tuple(params)) # Ensure params is a tuple
        updated_count = cursor.rowcount
        conn.commit()
        if updated_count > 0:
            logging.info(f"Successfully updated details/codes/timestamp for {registration}.")
        else:
            logging.debug(f"Details/codes update for {registration} affected 0 rows (registration not found or data unchanged?).")
        return True
    except psycopg2.Error as e:
        logging.error(f"DATABASE ERROR during detail update for {registration}: {e}")
        if conn and not conn.closed: conn.rollback()
        return False
    except Exception as e:
        logging.error(f"UNEXPECTED ERROR during detail update for {registration}: {e}")
        if conn and not conn.closed: conn.rollback()
        return False
    finally:
        if cursor: cursor.close()

# --- Main Execution Block (Integrated Detail/Code Updates) ---
if __name__ == "__main__":
    connection = None
    web_session = requests.Session()
    web_session.headers.update(HEADERS)

    AIRCRAFT_TYPES_TO_SCRAPE = ["A330", "B747", "B757", "B767", "B777", "IL76"]
    FETCH_DELAY_SECONDS = 3
    total_movements_processed_overall = 0

    # --- Read Progress ---
    PROGRESS_FILE = "scraper_progress.txt" # Ensure PROGRESS_FILE is defined here or globally
    start_after_type, start_after_reg = read_progress()
    found_start_type = (start_after_type is None)
    found_start_reg = (start_after_reg is None)

    try:
        logging.info("--- Script Start ---")

        # 1. Login
        logged_in = False
        if FR24_USERNAME and FR24_PASSWORD:
            logged_in = fr24_login(web_session)
            if logged_in:
                logging.info("Login successful.")
                time.sleep(FETCH_DELAY_SECONDS)
            else:
                logging.warning("Login failed. Proceeding anyway...")
        else:
            logging.info("No FR24 credentials found.")

        # 2. Initial DB Connection
        connection = get_db_connection()

        # --- Main Loop ---
        for type_index, target_aircraft_type in enumerate(AIRCRAFT_TYPES_TO_SCRAPE):

            # --- Progress Skipping Logic for Type ---
            if not found_start_type:
                if target_aircraft_type == start_after_type:
                    found_start_type = True
                    found_start_reg = (start_after_reg is None) # Reset reg check for this type
                else:
                    logging.info(f"Skipping type {target_aircraft_type} based on progress file.")
                    continue # Move to next type

            logging.info(f"========== Processing Aircraft Type: {target_aircraft_type} ==========")
            aircraft_tuples_found = []

            # --- Check/Reconnect DB ---
            if connection is None or connection.closed:
                logging.warning("DB connection lost. Reconnecting...")
                connection = get_db_connection()
                if connection is None or connection.closed:
                    logging.error("Reconnect failed. Skipping type.")
                    continue # Skip this type

            # --- Part 1: Get Specific Types, Registrations, AND Airlines ---
            logging.info(f"--- Fetching data for {target_aircraft_type} list page ---")
            html = get_aircraft_list_page(web_session, target_aircraft_type)
            if html:
                extracted_aircraft = extract_registrations(html)
                if extracted_aircraft:
                    processed_count = save_registrations_to_db(connection, extracted_aircraft)
                    logging.info(f"Attempted save/update for {processed_count} aircraft records fetched from {target_aircraft_type} page.")
                    aircraft_tuples_found = extracted_aircraft
                else:
                    logging.warning(f"No aircraft data tuples extracted from {target_aircraft_type} page.")
            else:
                logging.error(f"Could not retrieve list page for {target_aircraft_type}.")
            time.sleep(FETCH_DELAY_SECONDS)

            # --- Part 2: Fetch History AND Details/Codes ---
            if not aircraft_tuples_found:
                logging.warning(f"Skipping history for {target_aircraft_type} as no registrations were extracted.")
                continue

            logging.info(f"--- Fetching history & details for {len(aircraft_tuples_found)} regs from {target_aircraft_type} list ---")
            for i, (reg_to_fetch, specific_type, _) in enumerate(aircraft_tuples_found):

                # --- Progress Skipping Logic for Registration ---
                if not found_start_reg:
                    if reg_to_fetch == start_after_reg:
                        found_start_reg = True
                        logging.info(f"Resumed at registration {reg_to_fetch}. Processing...")
                    else:
                        logging.debug(f"Skipping registration {reg_to_fetch} based on progress file.")
                        continue # Move to next registration

                # --- Check/Reconnect DB ---
                if connection is None or connection.closed:
                    logging.warning("DB connection lost during history loop. Reconnecting...")
                    connection = get_db_connection()
                    if connection is None or connection.closed:
                        logging.error("Reconnect failed. Breaking history loop for this type.")
                        break # Stop processing history for this type

                # --- Get Latest Timestamp ---
                latest_ts = get_latest_movement_timestamp(connection, reg_to_fetch)

                logging.info(f"--- Processing History/Details for {specific_type} reg {i+1}/{len(aircraft_tuples_found)}: {reg_to_fetch} ---")
                history_html = get_flight_history_page(web_session, reg_to_fetch)

                if history_html:
                    # --- >>> NEW: Extract and Update Details/Codes <<< ---
                    parsed_details = extract_aircraft_details_from_history(history_html)
                    if parsed_details:
                        update_aircraft_details(
                            conn=connection,
                            registration=reg_to_fetch,
                            details=parsed_details.get('details'),
                            iata=parsed_details.get('iata'),
                            icao=parsed_details.get('icao')
                        )
                    # --- >>> End of New Detail Update Section <<< ---

                    # Check for "no data" page
                    if "could not find data for specified flight" in history_html.lower():
                        logging.info(f"History page for {reg_to_fetch} indicates no data available. Skipping movement processing.")
                        write_progress(target_aircraft_type, reg_to_fetch)
                    else:
                        # Parse Movements (pass latest_ts)
                        flight_records = extract_flight_history(history_html, reg_to_fetch, latest_ts)
                        if flight_records:
                            # Save Movements
                            processed = save_flight_history_to_db(connection, flight_records)
                            if processed >= 0:
                                total_movements_processed_overall += len(flight_records)
                                logging.info(f"Attempted save for {len(flight_records)} new movement records for {reg_to_fetch}.")
                                write_progress(target_aircraft_type, reg_to_fetch)
                            else:
                                logging.warning(f"Movement DB save error for {reg_to_fetch}. Progress not saved.")
                        else:
                            logging.info(f"No *new* flight movements parsed for {reg_to_fetch}.") # Changed from warning
                            write_progress(target_aircraft_type, reg_to_fetch)
                else:
                     logging.error(f"Could not retrieve history page for {reg_to_fetch}. Progress not saved.")

                logging.debug(f"Waiting {FETCH_DELAY_SECONDS} seconds...")
                time.sleep(FETCH_DELAY_SECONDS)
            # End of loop for registrations within a type
            logging.info(f"--- Finished processing aircraft from {target_aircraft_type} list ---")
        # End of loop for aircraft types

        logging.info("========== Script Finished Processing All Types ==========")
        logging.info(f"Total movement records processed/attempted to save: {total_movements_processed_overall}")
        # Clear Progress on Successful Full Run
        clear_progress()

    except KeyboardInterrupt:
        logging.warning("Script interrupted by user. Progress file *not* cleared.")
    except Exception as main_exception:
        logging.error(f"An unhandled error occurred: {main_exception}", exc_info=True)
    finally:
        if connection and not connection.closed:
            connection.close()
            logging.info("Database connection closed.")
        elif connection:
             logging.warning("Database connection was already closed before finally block.")
        else:
             logging.info("Database connection was not established.")
        logging.info("--- Script End ---")

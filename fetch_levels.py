#!/usr/bin/env python3

"""
Futures Custom Notes Generator

Fetches futures data and creates a combined CSV file with price level notes for:
1. Regular Trading Hours (RTH): Current day's High and Low (if within RTH) or previous day's High and Low
2. Extended Trading Hours (ETH): Overnight High, Low
3. Previous Day's High and Low
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import pytz
import logging
import os
import argparse

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def fetch_futures_data(symbol):
    """
    Fetch futures data using yfinance
    Returns regular hours and extended hours data
    """
    logging.info(f"Fetching data for {symbol}...")

    # Get data for the last 5 days to ensure we have previous day's data
    end_date = datetime.now()
    start_date = end_date - timedelta(days=5)

    # Fetch data with 1-minute intervals to capture extended hours
    futures = yf.Ticker(symbol)
    df = futures.history(start=start_date, end=end_date, interval="1m", prepost=True)

    if df.empty:
        raise ValueError(f"No data retrieved for symbol: {symbol}. Please check the ticker symbol and internet connection.")

    logging.info(f"Retrieved {len(df)} data points")
    logging.info(f"DataFrame head:\n{df.head()}")
    logging.info(f"DataFrame tail:\n{df.tail()}")
    return df

def get_rth_data(df, date):
    """
    Extract Regular Trading Hours data for a given date
    """
    # Convert to Eastern Time
    df_et = df.copy()
    df_et.index = df_et.index.tz_convert('America/New_York')

    # Filter for the specified date during RTH hours
    rth_data = df_et[
        (df_et.index.date == date) &
        (df_et.index.time >= pd.Timestamp('09:30').time()) &
        (df_et.index.time <= pd.Timestamp('16:00').time())
    ]

    if rth_data.empty:
        raise ValueError(f"Could not find RTH session data for {date}")

    high_price = rth_data['High'].max()
    low_price = rth_data['Low'].min()

    logging.info(f"\nRTH Data ({date}):")
    logging.info(f"  High: {high_price:.2f}")
    logging.info(f"  Low: {low_price:.2f}")

    return {
        'DHI': high_price,
        'DLO': low_price
    }

def get_previous_rth_data(df, date):
    """
    Extract Regular Trading Hours data for the previous day
    """
    # Convert to Eastern Time
    df_et = df.copy()
    df_et.index = df_et.index.tz_convert('America/New_York')

    # Filter for the specified date during RTH hours
    rth_data = df_et[
        (df_et.index.date == date) &
        (df_et.index.time >= pd.Timestamp('09:30').time()) &
        (df_et.index.time <= pd.Timestamp('16:00').time())
    ]

    if rth_data.empty:
        logging.warning(f"Could not find RTH session data for {date}")
        return {
            'PDH': None,
            'PDL': None
        }

    high_price = rth_data['High'].max()
    low_price = rth_data['Low'].min()

    logging.info(f"\nPrevious RTH Data ({date}):")
    logging.info(f"  High: {high_price:.2f}")
    logging.info(f"  Low: {low_price:.2f}")

    return {
        'PDH': high_price,
        'PDL': low_price
    }

def get_most_recent_rth_data(df):
    """
    Get the most recent available RTH data
    """
    # Convert to Eastern Time
    df_et = df.copy()
    df_et.index = df_et.index.tz_convert('America/New_York')

    # Get the current trading day and time
    current_date = datetime.now(pytz.timezone('America/New_York')).date()

    # Check for the most recent available RTH data
    for days_back in range(1, 6):
        check_date = current_date - timedelta(days=days_back)
        rth_data = df_et[
            (df_et.index.date == check_date) &
            (df_et.index.time >= pd.Timestamp('09:30').time()) &
            (df_et.index.time <= pd.Timestamp('16:00').time())
        ]

        if not rth_data.empty:
            high_price = rth_data['High'].max()
            low_price = rth_data['Low'].min()

            logging.info(f"\nMost Recent RTH Data ({check_date}):")
            logging.info(f"  High: {high_price:.2f}")
            logging.info(f"  Low: {low_price:.2f}")

            return {
                'PDH': high_price,
                'PDL': low_price
            }

    raise ValueError("Could not find any recent RTH session data")

def get_current_rth_data(df):
    """
    Extract current day's Regular Trading Hours data if within RTH, otherwise previous day's data
    """
    # Get the current trading day and time
    current_date = datetime.now(pytz.timezone('America/New_York')).date()
    current_time = datetime.now(pytz.timezone('America/New_York')).time()

    # Log the current date and time
    logging.info(f"Current date: {current_date}")
    logging.info(f"Current time: {current_time}")

    # Check if the current time is within RTH
    if pd.Timestamp('09:30').time() <= current_time <= pd.Timestamp('16:00').time():
        # Within RTH, get current day's data
        logging.info("Within RTH, fetching current day's data")
        return get_rth_data(df, current_date)
    else:
        # Outside RTH, get the most recent available RTH data
        logging.info("Outside RTH, fetching most recent available RTH data")
        return get_most_recent_rth_data(df)

def get_overnight_data(df):
    """
    Extract overnight (extended hours) data
    Overnight typically runs from 6:00 PM ET to 9:30 AM ET next day
    """
    df_et = df.copy()
    df_et.index = df_et.index.tz_convert('America/New_York')

    current_time = datetime.now(pytz.timezone('America/New_York'))
    current_date = current_time.date()

    # Define overnight session
    if current_time.time() < pd.Timestamp('09:30').time():
        # Currently in overnight session
        start_date = current_date - timedelta(days=1)
        overnight_data = df_et[
            ((df_et.index.date == start_date) & (df_et.index.time >= pd.Timestamp('18:00').time())) |
            ((df_et.index.date == current_date) & (df_et.index.time <= current_time.time()))
        ]
    else:
        # Regular trading hours, look at completed overnight session
        start_date = current_date - timedelta(days=1)
        overnight_data = df_et[
            ((df_et.index.date == start_date) & (df_et.index.time >= pd.Timestamp('18:00').time())) |
            ((df_et.index.date == current_date) & (df_et.index.time <= pd.Timestamp('09:30').time()))
        ]

    # If no overnight data found, look for most recent extended hours session
    if overnight_data.empty:
        for days_back in range(1, 5):
            check_date = current_date - timedelta(days=days_back)
            start_date = check_date - timedelta(days=1)

            overnight_data = df_et[
                ((df_et.index.date == start_date) & (df_et.index.time >= pd.Timestamp('18:00').time())) |
                ((df_et.index.date == check_date) & (df_et.index.time <= pd.Timestamp('09:30').time()))
            ]

            if not overnight_data.empty:
                break

    if overnight_data.empty:
        raise ValueError("Could not find overnight session data")

    ONH = overnight_data['High'].max()
    ONL = overnight_data['Low'].min()

    logging.info(f"\nOvernight Session Data:")
    logging.info(f"  High (ONH): {ONH:.2f}")
    logging.info(f"  Low (ONL): {ONL:.2f}")

    return {
        'ONH': ONH,
        'ONL': ONL
    }

def create_combined_csv(rth_data, overnight_data, previous_rth_data, filename='combined.csv', symbol='ESH6.CME@BMD'):
    """
    Create a combined CSV file for both RTH and overnight notes
    """
    # Define distinct colors
    colors = {
        'DHI': "#047A04",       # Green
        'DLO': "#FF0000",       # Red
        'PDH': "#047A04",       # Green
        'PDL': "#FF0000",       # Red
        'ONH': "#5151F1",       # Blue
        'ONL': "#0000FF"        # Blue
    }

    rows = []

    # Add RTH data
    for label, price in rth_data.items():
        if price is not None:
            row = {
                'Symbol': symbol,
                'Price Level': f'{price:.2f}',
                'Note': f'{label.upper()}',
                'Foreground Color': "#FFFFFF",
                'Background color': colors[label],
                'Text Alignment': 'left',
                'Draw Note Price Horizontal Line': 'TRUE'
            }
            rows.append(row)

    # Add overnight data
    for label, price in overnight_data.items():
        row = {
            'Symbol': symbol,
            'Price Level': f'{price:.2f}',
            'Note': f'{label.upper()}',
            'Foreground Color': "#FFFFFF",  # White
            'Background color': colors[label],
            'Text Alignment': 'left',
            'Draw Note Price Horizontal Line': 'TRUE'
        }
        rows.append(row)

    # Add previous RTH data
    for label, price in previous_rth_data.items():
        if price is not None:
            row = {
                'Symbol': symbol,
                'Price Level': f'{price:.2f}',
                'Note': f'{label.upper()}',
                'Foreground Color': "#FFFFFF",
                'Background color': colors[label],
                'Text Alignment': 'left',
                'Draw Note Price Horizontal Line': 'TRUE'
            }
            rows.append(row)

    df = pd.DataFrame(rows)
    df.to_csv(filename, index=False)
    logging.info(f"\n✓ Created {filename}")
    return filename

def main():
    """
    Main function to orchestrate data fetching and CSV creation
    """
    parser = argparse.ArgumentParser(description="Futures Custom Notes Generator")
    parser.add_argument("--symbol", type=str, default="ES=F", help="Futures symbol to fetch data for")
    parser.add_argument("--bm_symbol", type=str, default="ESH6.CME@BMD", help="Bookmap symbol name")
    parser.add_argument("--combined_filename", type=str, default="combined.csv", help="Filename for combined notes CSV")

    args = parser.parse_args()

    try:
        # Fetch futures data
        df = fetch_futures_data(args.symbol)

        # Get the current trading day and time
        current_date = datetime.now(pytz.timezone('America/New_York')).date()
        current_time = datetime.now(pytz.timezone('America/New_York')).time()

        # Log the current date and time
        logging.info(f"Current date: {current_date}")
        logging.info(f"Current time: {current_time}")

        # Check if the current time is within RTH
        if pd.Timestamp('09:30').time() <= current_time <= pd.Timestamp('16:00').time():
            # Within RTH, fetch current day's data
            logging.info("Within RTH, fetching current day's data")
            try:
                rth_data = get_rth_data(df, current_date)
            except ValueError as e:
                logging.error(f"Error fetching current day's RTH data: {e}")
                logging.info("Falling back to most recent available RTH data")
                rth_data = get_most_recent_rth_data(df)
        else:
            # Outside RTH, fetch most recent available RTH data
            logging.info("Outside RTH, fetching most recent available RTH data")
            rth_data = get_most_recent_rth_data(df)

        # Extract overnight data
        overnight_data = get_overnight_data(df)

        # Extract previous day's RTH data
        previous_date = datetime.now(pytz.timezone('America/New_York')).date() - timedelta(days=1)
        previous_rth_data = get_previous_rth_data(df, previous_date)

        # Create combined CSV file
        combined_file = create_combined_csv(rth_data, overnight_data, previous_rth_data, filename=args.combined_filename, symbol=args.bm_symbol)

        logging.info("\n" + "=" * 60)
        logging.info("SUCCESS! CSV file created:")
        logging.info(f"  {combined_file}")
        logging.info("=" * 60)
        logging.info("8=>")

    except Exception as e:
        logging.error(f"\n❌ Error: {e}")
        logging.error("\nTroubleshooting:")
        logging.error("  - Ensure you have internet connection")
        logging.error("  - Install required packages: pip install yfinance pandas pytz")
        logging.error("  - The ticker symbol may need adjustment based on contract month")
        logging.error("  - Ensure the script is run during RTH (9:30 AM to 4:00 PM ET) or check data availability for the previous day")
        return 1

    return 0

if __name__ == "__main__":
    exit(main())
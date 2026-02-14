import json
import time
import logging
from web3 import Web3
from the_graphe_handler import backfill_db_block_range
from db_operations.internal._db_operations import _get_last_indexed_block, _get_pg_connection
from db_operations import fill_db_history
from event_handlers.get_and_decode_event_yam import get_raw_logs_yam, decode_raw_logs_yam
from event_handlers import store_event_in_queue
from db_operations import add_events_to_db
from app_logging.logging_config import setup_logging
from app_logging.send_telegram_alert import send_telegram_alert
from app_logging import shutdown
from config import(
    BLOCK_TO_RETRIEVE,
    COUNT_BEFORE_RESYNC,
    BLOCK_BUFFER,
    TIME_TO_WAIT_BEFORE_RETRY,        
    MAX_RETRIES_PER_BLOCK_RANGE,
    COUNT_PERIODIC_BACKFILL_THEGRAPH,
    EXPORT_EVENTS_TO_EVENT_QUEUE
)


import os
from dotenv import load_dotenv
load_dotenv()

# Load secrests and config
w3_urls = os.environ["YAM_INDEXING_W3_URLS"].split(",")
subgraph_url = os.environ["YAM_INDEXING_SUBGRAPH_URL"]
the_graph_api_key = os.environ["YAM_INDEXING_THE_GRAPH_API_KEY"]

POSTGRES_HOST = os.getenv("POSTGRES_HOST")
POSTGRES_PORT = os.getenv("POSTGRES_PORT")
POSTGRES_DB   = os.getenv("POSTGRES_DB")
POSTGRES_WRITER_USER = "yam-indexing-writer"
POSTGRES_WRITER_USER_PASSWORD = os.getenv("POSTGRES_WRITER_USER_PASSWORD")

POSTGRES_DATA = [POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_WRITER_USER, POSTGRES_WRITER_USER_PASSWORD]


def main_indexing():

    # Set up signals to catch when the process is stopped (via ctrl-c, docker stop, ...)
    shutdown.setup_signal_handlers()

    #### LOAD DATA ####

    with open('ressources/blockchain_contracts.json', 'r') as f:
        yam_contract_address = json.load(f)['contracts']['yamv1']['address']

    #### INITIALIZATION ####

    w3_indice = 0
    w3_indice_backup = 1 
    w3 = Web3(Web3.HTTPProvider(w3_urls[w3_indice]))
    w3_backup = Web3(Web3.HTTPProvider(w3_urls[w3_indice_backup])) # a backup is set up to ensure no logs is missed (for some unknown reasons, sometime a RPC might miss a log)

    try:
        conn = _get_pg_connection(*POSTGRES_DATA)
        last_block_indexed = _get_last_indexed_block(conn)
    finally:
        conn.close()
    try:
        latest_block_number = w3.eth.block_number
    except Exception as e:
        msg = (
            "Fetch of initial latest block didn't work\n"
            f"{e}\n"
            "Please correct your RPC and restart the yam indexing"
        )
        logger.error(msg)
        send_telegram_alert(f"Application yam indexing: {msg}")
        raise SystemExit(msg)

    # backfill DB from the last indexed block in DB to the latest available block in the blockchain
    conn = _get_pg_connection(*POSTGRES_DATA)
    backfill_db_block_range(conn, subgraph_url, the_graph_api_key, last_block_indexed, latest_block_number)


    from_block = latest_block_number - BLOCK_BUFFER - BLOCK_TO_RETRIEVE + 1
    to_block = latest_block_number - BLOCK_BUFFER
    sync_counter = 0
    backfill_thegraph_count = 0

    logger.info("Application has started")
    send_telegram_alert("Application yam indexing has started")
    print('indexing module running...')

    #### INDEXING LOGIC ####

    consecutive_global_failures = 0

    try:
        while True:
        
            start_time = time.time()

            success = False

            if shutdown.shutdown_requested:
                logger.info(
                    "Shutdown requested (%s). Stopping after last completed cycle.",
                    shutdown.shutdown_reason
                )
                send_telegram_alert(
                    f"Application yam indexing : shutdown requested ({shutdown.shutdown_reason})"
                )
                break
        
            for attempt in range(MAX_RETRIES_PER_BLOCK_RANGE):
            
                try:
                    raw_logs = get_raw_logs_yam(w3, yam_contract_address, from_block, to_block)
                    success = True
                    consecutive_global_failures = 0
                    try: # a backup is set up to ensure no logs is missed (for some unknown reasons, sometime a RPC might miss a log)
                        raw_logs_backup = get_raw_logs_yam(w3_backup, yam_contract_address, from_block, to_block)
                        for log in raw_logs_backup:
                            if log not in raw_logs:
                                raw_logs.append(log)
                    except:
                        pass
                    break # leave the for loop if success
                
                except Exception as e:
                    
                    if attempt < MAX_RETRIES_PER_BLOCK_RANGE - 1:
                        logger.info(f"Blocks retrieval failed for {w3.provider.endpoint_uri.split('//')[1].rsplit('/', 1)[0]}. Retrying in {TIME_TO_WAIT_BEFORE_RETRY} seconds...")
                        time.sleep(TIME_TO_WAIT_BEFORE_RETRY)
                    
                    else:
                        # if the request has fails severals time, change RPC
                        old_indice = w3_indice
                        w3_indice = (w3_indice + 1) % len(w3_urls) # This will give you the sequence: 0 → 1 → 2 → ... → n → 0 → 1 → 2 → ... → n → 0 ...
                        w3_indice_backup = (w3_indice_backup + 1) % len(w3_urls)
                        w3 = Web3(Web3.HTTPProvider(w3_urls[w3_indice]))
                        w3_backup = Web3(Web3.HTTPProvider(w3_urls[w3_indice_backup]))
                        logger.info(f"Blocks retrieval failed too many times. Changing from w3 RPC n°{old_indice + 1} to w3 RPC n°{w3_indice + 1} [{w3.provider.endpoint_uri.split('//')[1].rsplit('/', 1)[0]}]")
                        
                        # check if all RPC have failed consecutively
                        consecutive_global_failures += 1
                        if consecutive_global_failures >= len(w3_urls):
                            logger.error("ALL RPCs failed consecutively in a full cycle")
                            send_telegram_alert("Application yam indexing: All RPCs failed consecutively in a full cycle. You might need to add new valid RPCs")
                            consecutive_global_failures = 0  # reset so we can detect future full cycles
                            time.sleep(180)

                if shutdown.shutdown_requested:
                    break
            
            if not success:
                continue
            
            decoded_logs = decode_raw_logs_yam(raw_logs)

            ### export offerAccepted event to event_queue ###
            if EXPORT_EVENTS_TO_EVENT_QUEUE:
                if any(log.get("topic") == "OfferAccepted" for log in decoded_logs):
                    conn = _get_pg_connection(*POSTGRES_DATA)
                    try:
                        for log in decoded_logs:
                            if log.get("topic") == "OfferAccepted": #store in DB
                                store_event_in_queue(conn, log)
                    finally:
                        conn.close()

        
            ### Add logs to the DB
            conn = _get_pg_connection(*POSTGRES_DATA)
            add_events_to_db(conn, from_block, to_block, decoded_logs)
            logger.info(f"{len(decoded_logs)} YAM log(s) retrieved from block {from_block} to {to_block}")
        
            from_block = to_block + 1
            to_block += BLOCK_TO_RETRIEVE
        
            sync_counter += 1
            backfill_thegraph_count += 1
        
            if sync_counter > COUNT_BEFORE_RESYNC:
                sync_counter = 0
                latest_block_number = w3.eth.block_number
                # we resynchronize the 'to_block' to the latest block without touching the 'from_block'
                to_block = latest_block_number - BLOCK_BUFFER
                
                # We calcul the deviation and we move back the 'from_block' if it is ahead of what it should do
                deviation = to_block - from_block - BLOCK_TO_RETRIEVE + 1
                if deviation < 0:
                    from_block = latest_block_number - BLOCK_BUFFER - BLOCK_TO_RETRIEVE + 1
                logger.info(f"resync on newest block - deviation was {deviation} block(s)")

            if backfill_thegraph_count > COUNT_PERIODIC_BACKFILL_THEGRAPH:
                backfill_thegraph_count = 0
                # backfill DB from the last indexed block in DB to the latest available block in the blockchain
                from_block_backfill = to_block - 17280 # 17280 blocks = 1 day
                conn = _get_pg_connection(*POSTGRES_DATA)
                backfill_db_block_range(conn, subgraph_url, the_graph_api_key, from_block_backfill, to_block)
            
            # Adjust sleep time accordingly - we don't want to deviate so we take the execution time into account
            execution_time = time.time() - start_time
            time_to_sleep = max(0, BLOCK_TO_RETRIEVE * 5.4 - execution_time) # 5.4 because it seems to go too fast with 5 and it ends up fetching block that doesn't exist yet
            
            
            # Sleep for the adjusted time
            time.sleep(time_to_sleep)

    except Exception as e:
        logger.error(f"Indexing loop failed with error: {str(e)}", exc_info=True)
        print(f"Indexing loop failed with error: {str(e)}")
        send_telegram_alert(f"Application yam indexing: Indexing loop failed with error: {str(e)}")

if __name__ == "__main__":
    # Set up logging
    setup_logging()
    logger = logging.getLogger("main")

    ### fill complete history if the DB is empty ###
    conn = _get_pg_connection(*POSTGRES_DATA)
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1 FROM public.indexing_state LIMIT 1")
            if cursor.fetchone() is None:
                fill_db_history()
            else:
                logger.info("history already exists: skipping history filling")
    finally:
        conn.close()


    ### strat main indexing loop ###
    while True:
        try:
            main_indexing()
            if shutdown.shutdown_requested:
                logger.info("Application yam indexing stopped")
                break
        except SystemExit:
            logger.critical("Application stopped due to fatal configuration error")
            break
        except Exception as e:
            logger.exception(f"Fatal error in main_indexing. Restarting in 5 minutes...\n{e}")
            send_telegram_alert(f"Application yam indexing: Fatal error in main_indexing. Restarting in 5 minutes...\n{e}")
            time.sleep(300)
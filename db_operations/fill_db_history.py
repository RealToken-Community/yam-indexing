from db_operations import add_events_to_db
from db_operations.add_events_to_db import get_number_of_incorrect_the_graph_logindex
from db_operations.internal._db_operations import _get_pg_connection
from the_graphe_handler.internals import fetch_all_offer_created, fetch_all_offer_deleted, fetch_all_offer_updated, fetch_all_offer_accepted, fetch_offer_created_from_block_range
from event_handlers.get_and_decode_event_yam import get_raw_logs_yam_by_topic, decode_raw_logs_yam
from app_logging.send_telegram_alert import send_telegram_alert
from concurrent.futures import ThreadPoolExecutor
from web3 import Web3
from web3.exceptions import Web3RPCError
from requests.exceptions import HTTPError, Timeout, ConnectionError
from urllib.parse import urlparse
import json
import time

import logging
logger = logging.getLogger(__name__)

import os
from dotenv import load_dotenv
load_dotenv()

POSTGRES_WRITER_USER = "yam-indexing-writer"

START_BLOCK = 25530394 # block creation for the yam v1 contract
BTACH_SIZE_BLOCK = 7500  # number of block to retrieve each request

# Dictionary of YAM event topic hashes for efficient lookup
TOPIC_YAM = {
    'OfferCreated': '9fa2d733a579251ad3a2286bebb5db74c062332de37e4904aa156729c4b38a65',
    'OfferDeleted': '88686b85d6f2c3ab9a04e4f15a22fcfa025ffd97226dcf0a67cdf682def55676',
    'OfferAccepted': '0fe687b89794caf9729d642df21576cbddc748b0c8c7a5e1ec39f3a46bd00410',
    'OfferUpdated': 'c26a0a1f023ef119f120b3d9843d9e77dc8f66bbc0ea91d48d6dd39b8e351178'
}

# Load secrests and config
w3_urls = os.environ["YAM_INDEXING_W3_URLS"].split(",")
POSTGRES_HOST = os.getenv("POSTGRES_HOST")
POSTGRES_PORT = os.getenv("POSTGRES_PORT")
POSTGRES_DB   = os.getenv("POSTGRES_DB")
POSTGRES_WRITER_USER_PASSWORD = os.getenv("POSTGRES_WRITER_USER_PASSWORD")

SUBGRAPH_URL = os.getenv("YAM_INDEXING_SUBGRAPH_URL")
API_KEY = os.getenv("YAM_INDEXING_THE_GRAPH_API_KEY")

with open('ressources/blockchain_contracts.json', 'r') as f:
    yam_contract_address = json.load(f)['contracts']['yamv1']['address']

def fill_db_history():

    def is_rpc_timeout(exc: Exception) -> bool:
        # Web3 JSON-RPC error
        if isinstance(exc, Web3RPCError):
            return "timeout" in str(exc).lower()
    
        # HTTP-level errors (gateway, provider, rate limit)
        if isinstance(exc, HTTPError):
            return exc.response is not None and exc.response.status_code in {408, 429, 502, 503, 504}
    
        # Network-level timeouts
        if isinstance(exc, (Timeout, ConnectionError)):
            return True
    
        return False

    logger.info('start filling DB history')

    # initialize DB connection
    pg_conn = _get_pg_connection(POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_WRITER_USER, POSTGRES_WRITER_USER_PASSWORD)

    # w3
    w3_1 = Web3(Web3.HTTPProvider(w3_urls[0], request_kwargs={"timeout": 120}))
    w3_2 = Web3(Web3.HTTPProvider(w3_urls[1], request_kwargs={"timeout": 120}))
    try:
        latest_block_number = w3_1.eth.block_number
    except Exception as e:
        msg = (
            "Fetch of initial latest block didn't work\n"
            f"{e}\n"
            "Please correct your RPC and restart the yam indexing"
        )
        logger.error(msg)
        send_telegram_alert(f"Application yam indexing: {msg}")
        raise SystemExit(msg)

    try:
        # Fetch from w3 RPC all offerCreated and add them to the DB
        logger.info("step 1/4 : fetching offer created from w3 RPC")
        print("\nofferCreated with w3 RPC:")
        created_offers_w3 = []
        seen = set()
        
        with ThreadPoolExecutor(max_workers=2) as pool:
            last_logged_step = 0
            for from_block in range(START_BLOCK, latest_block_number + 1, BTACH_SIZE_BLOCK):
                to_block = min(from_block + BTACH_SIZE_BLOCK - 1, latest_block_number)
        
                f1 = pool.submit(
                    get_raw_logs_yam_by_topic,
                    w3_1, yam_contract_address, TOPIC_YAM["OfferCreated"], from_block, to_block
                )
                f2 = pool.submit(
                    get_raw_logs_yam_by_topic,
                    w3_2, yam_contract_address, TOPIC_YAM["OfferCreated"], from_block, to_block
                )
        
                raw_logs_1 = []
                raw_logs_2 = []
        
                try:
                    raw_logs_1 = f1.result()
                except Exception as e:
                    if is_rpc_timeout(e):
                        logger.info(f"{urlparse(w3_1.provider.endpoint_uri).netloc} time out. Request was from block {from_block} to {to_block}. Splitting this batch into more batches")
                        time.sleep(10)
                        for i in range(10):
                            batch_from = from_block + i * ((to_block - from_block + 1) // 10)
                            batch_to   = to_block if i == 9 else batch_from + ((to_block - from_block + 1) // 10) - 1
                            try:
                                raw_logs = get_raw_logs_yam_by_topic(w3_1, yam_contract_address, TOPIC_YAM["OfferCreated"], batch_from, batch_to)
                                raw_logs_1.extend(raw_logs)
                                time.sleep(0.2)
                            except Exception as e:
                                if is_rpc_timeout(e):
                                    logger.warning(f"{urlparse(w3_1.provider.endpoint_uri).netloc} time out. Request was from block {batch_from} to {batch_to}.")
                                    send_telegram_alert(f"yam-indexing initialization: {urlparse(w3_1.provider.endpoint_uri).netloc} time out. Request was from block {batch_from} to {batch_to}.")
                    else:
                        raise
        
                try:
                    raw_logs_2 = f2.result()
                except Exception as e:
                    if is_rpc_timeout(e):
                        logger.info(f"{urlparse(w3_2.provider.endpoint_uri).netloc} time out. Request was from block {from_block} to {to_block}. Splitting this batch into more batches")
                        time.sleep(10)
                        for i in range(10):
                            batch_from = from_block + i * ((to_block - from_block + 1) // 10)
                            batch_to   = to_block if i == 9 else batch_from + ((to_block - from_block + 1) // 10) - 1
                            try:
                                raw_logs = get_raw_logs_yam_by_topic(w3_2, yam_contract_address, TOPIC_YAM["OfferCreated"], batch_from, batch_to)
                                raw_logs_2.extend(raw_logs)
                                time.sleep(0.2)
                            except Exception as e:
                                if is_rpc_timeout(e):
                                    logger.warning(f"{urlparse(w3_2.provider.endpoint_uri).netloc} time out. Request was from block {batch_from} to {batch_to}.")
                                    send_telegram_alert(f"yam-indexing initialization: {urlparse(w3_1.provider.endpoint_uri).netloc} time out. Request was from block {batch_from} to {batch_to}.")
                    else:
                        raise
        
                decoded_logs_1 = decode_raw_logs_yam(raw_logs_1) if raw_logs_1 else []
                decoded_logs_2 = decode_raw_logs_yam(raw_logs_2) if raw_logs_2 else []
        
                for log in decoded_logs_1 + decoded_logs_2:
                    key = (log["transactionHash"], log["logIndex"])
                    if key not in seen:
                        seen.add(key)
                        created_offers_w3.append(log)
        
                time.sleep(0.05)

                progress = (from_block - START_BLOCK) / (latest_block_number - START_BLOCK) * 100
                print(
                    f"offer created retrieved from {START_BLOCK} to {to_block} "
                    f"[{progress:.1f}%]",
                    end="\r",
                    flush=True
                )
                
                current_step = int(progress // 5) * 5
                if current_step > last_logged_step:
                    logger.info(
                        f"offer created retrieved from {START_BLOCK} to {to_block} "
                        f"[{current_step}%]"
                    )
                    last_logged_step = current_step

        add_events_to_db(pg_conn=pg_conn, from_block=None, to_block=None, decoded_logs=created_offers_w3, initialisation_mode=True, close_connection=False)
        pg_conn.commit()

        # Fetch from TheGraph all offerCreated and add them to the DB
        logger.info("step 2/4 : fetching offer created from The Graph")
        print("\nofferCreated with TheGraph:")
        created_offers_the_graph = []
        created_offers_the_graph = fetch_all_offer_created(API_KEY, SUBGRAPH_URL)
        add_events_to_db(pg_conn=pg_conn, from_block=None, to_block=None, decoded_logs=created_offers_the_graph, initialisation_mode=True, close_connection=False)
        pg_conn.commit()

        # check the number of offer_id in the table to make sure there are no missing created offer
        cur = pg_conn.cursor()
        cur.execute("""
            SELECT
                MAX(offer_id) AS max_offer_id,
                COUNT(*)      AS row_count
            FROM offers
        """)
        max_offer_id, row_count = cur.fetchone()
        
        if max_offer_id + 1 == row_count:
            logger.info(f"{row_count} created offers stored to the DB")
        else:
            msg = "Some created offers are missing. Please start again the initialization. You might need to wait for TheGraph or change your RPC"
            logger.error(msg)
            send_telegram_alert(f"Application yam indexing: {msg}")
            raise RuntimeError("Offers table integrity check failed")
        
        logger.info(f"Number of TheGraph event not added because of a incorrect logIndex: {get_number_of_incorrect_the_graph_logindex()}")
        
        # Fetch from w3 RPC all offerCreated and add them to the DB
        logger.info("step 3/4 : fetching offerAccepted, offerUpdated and offerDeleted from w3 RPC")
        print("\nofferAccepted, offerUpdated and offerDeleted with w3 RPC:")
        accepted_updated_deleted_offers_w3 = []
        seen = set()
        

        with ThreadPoolExecutor(max_workers=2) as pool:
            last_logged_step = 0
            for from_block in range(START_BLOCK, latest_block_number + 1, BTACH_SIZE_BLOCK):
                to_block = min(from_block + BTACH_SIZE_BLOCK - 1, latest_block_number)
        
                f1 = pool.submit(
                    get_raw_logs_yam_by_topic,
                    w3_1, yam_contract_address, [TOPIC_YAM["OfferAccepted"], TOPIC_YAM["OfferUpdated"], TOPIC_YAM["OfferDeleted"]], from_block, to_block
                )
                f2 = pool.submit(
                    get_raw_logs_yam_by_topic,
                    w3_2, yam_contract_address, [TOPIC_YAM["OfferAccepted"], TOPIC_YAM["OfferUpdated"], TOPIC_YAM["OfferDeleted"]], from_block, to_block
                )
        
                raw_logs_1 = []
                raw_logs_2 = []
        
                try:
                    raw_logs_1 = f1.result()
                except Exception as e:
                    if is_rpc_timeout(e):
                        logger.info(f"{urlparse(w3_1.provider.endpoint_uri).netloc} time out. Request was from block {from_block} to {to_block}. Splitting this batch into more batches")
                        time.sleep(10)
                        for i in range(10):
                            batch_from = from_block + i * ((to_block - from_block + 1) // 10)
                            batch_to   = to_block if i == 9 else batch_from + ((to_block - from_block + 1) // 10) - 1
                            try:
                                raw_logs = get_raw_logs_yam_by_topic(w3_1, yam_contract_address, [TOPIC_YAM["OfferAccepted"], TOPIC_YAM["OfferUpdated"], TOPIC_YAM["OfferDeleted"]], batch_from, batch_to)
                                raw_logs_1.extend(raw_logs)
                                time.sleep(0.2)
                            except Exception as e:
                                if is_rpc_timeout(e):
                                    logger.warning(f"{urlparse(w3_1.provider.endpoint_uri).netloc} time out. Request was from block {batch_from} to {batch_to}.")
                                    send_telegram_alert(f"yam-indexing initialization: {urlparse(w3_1.provider.endpoint_uri).netloc} time out. Request was from block {batch_from} to {batch_to}.")
                    else:
                        raise
        
                try:
                    raw_logs_2 = f2.result()
                except Exception as e:
                    if is_rpc_timeout(e):
                        logger.info(f"{urlparse(w3_2.provider.endpoint_uri).netloc} time out. Request was from block {from_block} to {to_block}. Splitting this batch into more batches")
                        time.sleep(10)
                        for i in range(10):
                            batch_from = from_block + i * ((to_block - from_block + 1) // 10)
                            batch_to   = to_block if i == 9 else batch_from + ((to_block - from_block + 1) // 10) - 1
                            try:
                                raw_logs = get_raw_logs_yam_by_topic(w3_2, yam_contract_address, [TOPIC_YAM["OfferAccepted"], TOPIC_YAM["OfferUpdated"], TOPIC_YAM["OfferDeleted"]], batch_from, batch_to)
                                raw_logs_2.extend(raw_logs)
                                time.sleep(0.2)
                            except Exception as e:
                                if is_rpc_timeout(e):
                                    logger.warning(f"{urlparse(w3_2.provider.endpoint_uri).netloc} time out. Request was from block {batch_from} to {batch_to}.")
                                    send_telegram_alert(f"yam-indexing initialization: {urlparse(w3_1.provider.endpoint_uri).netloc} time out. Request was from block {batch_from} to {batch_to}.")
                    else:
                        raise
        
                decoded_logs_1 = decode_raw_logs_yam(raw_logs_1) if raw_logs_1 else []
                decoded_logs_2 = decode_raw_logs_yam(raw_logs_2) if raw_logs_2 else []
        
                for log in decoded_logs_1 + decoded_logs_2:
                    key = (log["transactionHash"], log["logIndex"])
                    if key not in seen:
                        seen.add(key)
                        created_offers_w3.append(log)
        
                time.sleep(0.05)

                progress = (from_block - START_BLOCK) / (latest_block_number - START_BLOCK) * 100
                print(
                    f"offerAccepted, offerUpdated and offerDeleted retrieved from {START_BLOCK} to {to_block} "
                    f"[{progress:.1f}%]",
                    end="\r",
                    flush=True
                )
                
                current_step = int(progress // 5) * 5
                if current_step > last_logged_step:
                    logger.info(
                        f"offerAccepted, offerUpdated and offerDeleted retrieved from {START_BLOCK} to {to_block} "
                        f"[{current_step}%]"
                    )
                    last_logged_step = current_step
        
        add_events_to_db(pg_conn=pg_conn, from_block=None, to_block=None, decoded_logs=accepted_updated_deleted_offers_w3, initialisation_mode=True, close_connection=False)
        pg_conn.commit()

        # fetch new offers with w3 RPC that might have been created after the start of this script
        # we do it just before all offerAccepted/offerDeleted/offerUpdated from the graph: if TheGraph fetches a event that belongs to an offer id not yet retrieve in the first iteration, it cause cause conflict with the primary key
        
        highest_block_number = max(
            int(created_offers_w3[-1]['blockNumber']),
            int(created_offers_the_graph[-1]['blockNumber'])
        )
        
        latest_block_number = w3_1.eth.block_number
        created_offers_w3_second_iteration = []

        for from_block in range(highest_block_number, latest_block_number + 1, BTACH_SIZE_BLOCK):
            to_block = min(from_block + BTACH_SIZE_BLOCK - 1, latest_block_number)
            raw_logs = get_raw_logs_yam_by_topic(w3_1, yam_contract_address, TOPIC_YAM['OfferCreated'], from_block, to_block)
            decoded_logs = decode_raw_logs_yam(raw_logs)
            created_offers_w3_second_iteration.extend(decoded_logs)
            time.sleep(0.05)
        add_events_to_db(pg_conn=pg_conn, from_block=None, to_block=None, decoded_logs=created_offers_w3_second_iteration, initialisation_mode=False, close_connection=False)
        pg_conn.commit()


        # Fetch from TheGraph all offerAccepted/offerDeleted/offerUpdated and add them to the DB
        logger.info("step 4/4 : fetching offerAccepted, offerUpdated and offerDeleted from TheGraph")
        print("\nofferAccepted, offerUpdated and offerDeleted with TheGrpah:")
        accepted_offers_the_graph = fetch_all_offer_accepted(API_KEY, SUBGRAPH_URL)
        updated_offers_the_graph = fetch_all_offer_updated(API_KEY, SUBGRAPH_URL)
        deleted_offers_the_graph = fetch_all_offer_deleted(API_KEY, SUBGRAPH_URL)
        latest_block_number = w3_1.eth.block_number
        created_offers_the_graph = fetch_offer_created_from_block_range(SUBGRAPH_URL, API_KEY, highest_block_number, latest_block_number)
        all_events_the_graph = created_offers_the_graph + accepted_offers_the_graph + updated_offers_the_graph + deleted_offers_the_graph
        all_events_sorted_the_graph = sorted(all_events_the_graph, key=lambda x: x['timestamp'])
        add_events_to_db(pg_conn=pg_conn, from_block=None, to_block=None, decoded_logs=all_events_sorted_the_graph, initialisation_mode=True, close_connection=False)
        pg_conn.commit()


        highest_block_number = max(
            int(created_offers_w3[-1]['blockNumber']),
            int(created_offers_the_graph[-1]['blockNumber']),
            int(created_offers_w3_second_iteration[-1]['blockNumber']),
            int(all_events_sorted_the_graph[-1]['blockNumber'])
        )

        # Add indexing state record
        cursor = pg_conn.cursor()
        cursor.execute(
            """
            INSERT INTO indexing_state (from_block, to_block)
            VALUES (%s, %s)
            """,
            (25530394, highest_block_number),
        )
        pg_conn.commit()
        
        logger.info(f"Total number of TheGraph event not added because of a incorrect logIndex: {get_number_of_incorrect_the_graph_logindex()}")
        logger.info(f'Filling DB history completed ! DB indexed up to block {highest_block_number}')

    finally:
        pg_conn.close()
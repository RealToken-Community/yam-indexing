BLOCK_TO_RETRIEVE = 3                   # Number of block to retrieve from the W3 RPC by HTTP request 
COUNT_BEFORE_RESYNC = 80                # Number of retrieve before resynchronizing to the latest block
BLOCK_BUFFER = 7                        # Gap between the latest block available and what is actually retrieve
TIME_TO_WAIT_BEFORE_RETRY = 2           # time to wait before retry when RPC is not available
MAX_RETRIES_PER_BLOCK_RANGE = 7         # Number of time the request will be retried when it has failed before changing the RPC
COUNT_PERIODIC_BACKFILL_THEGRAPH = 960  # Number of iteration before backfilling the blocks into the DB the blocks of the last few hours (with TheGraph)
EXPORT_EVENTS_TO_EVENT_QUEUE = False     # Export events to event_queue table (True or False)
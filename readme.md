# YAM Indexing Module

## Table of Contents

- [Overview](#overview)
- [System Requirements](#system-requirements)
- [Configuration](#configuration)
  - [Configure Environment Variables](#configure-environment-variables)
- [Installation & Execution](#installation--execution)
  - [Option A — Docker (Recommended)](#option-a--docker-recommended)
  - [Option B — Manual Installation (Without Docker)](#option-b--manual-installation-without-docker)
- [Configurable Application Parameters](#configurable-application-parameters)
- [Optional Export of OfferAccepted Events](#optional-export-of-offeraccepted-events)
- [Database Structure](#database-structure)
- [Design Considerations](#design-considerations)
- [Subgraph Requirements](#subgraph-requirements)

## Overview

This project is a standalone Python module dedicated to indexing all **YAM v1** on-chain events on the **Gnosis blockchain**, storing them locally in a SQLite database for fast and reliable access.

It performs:
- Continuous live indexing using multiple RPC endpoints.
- Automatic recovery and RPC rotation on failure.
- Full historical backfill during initialization using _The Graph_ and 2 RPCs.
- Periodic integrity checks through short backfills using _The Graph_.
- Optional export of OfferAccepted events to the `event_queue` table to enable real-time detection by other applications.

The local postgre database and the OfferAccepted event export are used by other projects, such as the [yam-transactions-report-generator](https://github.com/RealToken-Community/yam-transactions-report-generator) and the [yam-sale-notify-bot](https://github.com/LoganSulpizio/yam-sale-notify-bot).

---

## System Requirements

- Python 3.11+
- Docker & Docker Compose (optional but recommended)

---

## Configuration

### Configure Environment Variables

An example configuration file is provided: `.env.example`.  
Copy it to `.env` and update the values with your own secrets.

```env
# Web3 RPC URLs (comma-separated)
YAM_INDEXING_W3_URLS=https://rpc.ankr.com/gnosis/...,https://gnosis.api.onfinality.io/rpc?apikey=...,https://lb.nodies.app/v1/...

# The Graph API key
YAM_INDEXING_THE_GRAPH_API_KEY=

# Subgraph endpoint with the API key injected into the URL
YAM_INDEXING_SUBGRAPH_URL=https://gateway.thegraph.com/api/[api-key]/subgraphs/id/7xsjkvdDtLJuVkwCigMaBqGqunBvhYjUSPFhpnGL1rvu

# Postgres DB
POSTGRES_USER=postgres
POSTGRES_PASSWORD=
POSTGRES_DB=yam_events
POSTGRES_HOST=yam-indexing-postgres
POSTGRES_PORT=5432
POSTGRES_PORT_HOST=5432
POSTGRES_READER_USER_PASSWORD=
POSTGRES_WRITER_USER_PASSWORD=
POSTGRES_EVENT_QUEUE_USER_PASSWORD=

# Telegram alerts (used to receive error notifications)
TELEGRAM_ALERT_BOT_TOKEN=
TELEGRAM_ALERT_GROUP_ID=
```

> **Note:**  
> RPC URLs must be provided as a comma-separated string on a single line, without spaces.  
> For alerts, you can configure a Telegram bot and a Telegram group: the bot (using `TELEGRAM_ALERT_BOT_TOKEN`) must be added to the telegram chat group (`TELEGRAM_ALERT_GROUP_ID`) to receive automatic notifications about critical events such as failures or application stops.

---

## Installation & Execution

### Option A — Docker (Recommended)

The project includes a **ready-to-use Docker integration**.

From the **project root directory** (where `docker-compose.yml` is located), build
(or rebuild) and start the service with:

```bash
docker compose up --build -d
```

This single command:
- Rebuilds the image if the source code changed
- Recreates the existing containers without duplication
- Starts the service from a clean state



To stop the service:

```bash
docker compose stop
```

> **Note on database persistence**  
> The postgres database is stored in a Docker volume and is therefore persistent across container restarts, rebuilds, and upgrades.  
> On first startup, if no database is found, the container automatically runs the initialization process, creates the database, and backfills the full on-chain history (this may take some time). Once completed, the service seamlessly switches to the live indexing loop.  
> On subsequent starts, if the database already exists, the initialization step is skipped and the live indexing service starts immediately.
> For detailed information about initialization and runtime behavior, see the sections below.

---

### Option B — Manual Installation (Without Docker)

#### 1. Create and Activate a Python Virtual Environment

```bash
# Optional but recommended: create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate
```

#### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

#### 3. Initialization

- Create the postgres databass using the `init_postgres\00-init.sql` file
- Set a password for the postgres users created at `init_postgres\00-init.sql` (see other files in `init_postgres\`)


#### 4. Running the Indexing Service

Start the continuous indexing loop (on first run, the script performs a full historical backfill of all YAM events first):

```bash
python3 -m main
```

The indexing loop service performs:

##### A. Startup Synchronization
Checks for missing blocks since last shutdown and fills any gaps using _The Graph_.

##### B. Live Indexing Loop
- Pulls raw logs directly from RPCs  
- Decodes events  
- Stores them in Postgres  
- Rotates RPCs automatically on repeated failures  

##### C. Periodic Backfill
Ensures data consistency using _The Graph_.


> With Docker, all of those above commands are handled internally by the container.
---

## Configurable Application Parameters

The module exposes several **application parameters** that can be tuned inside `config.py`:

| Parameter | Description |
|----------|-------------|
| `BLOCK_TO_RETRIEVE` | Number of blocks retrieved per RPC HTTP request. |
| `COUNT_BEFORE_RESYNC` | Number of iterations before resynchronizing to the latest block. |
| `BLOCK_BUFFER` | Safety gap between the latest known block and the one actually requested. |
| `TIME_TO_WAIT_BEFORE_RETRY` | Seconds to wait before retrying an unavailable RPC. |
| `MAX_RETRIES_PER_BLOCK_RANGE` | Maximum retries before switching to another RPC provider. |
| `COUNT_PERIODIC_BACKFILL_THEGRAPH` | Number of iterations before triggering the periodic TheGraph backfill. |
| `EXPORT_EVENTS_TO_EVENT_QUEUE` | Export events to event_queue table (set to True or False) |

---

## Optional Export of OfferAccepted Events

The module can optionally export OfferAccepted events to a dedicated PostgreSQL table named `event_queue`, allowing other applications (such as notification or monitoring services) to consume these events in near real time. To enable it, see the `config.py` file

```python
EXPORT_EVENTS_TO_EVENT_QUEUE = True
```

---

## Database Structure

The database is designed to persist all YAM offers, their full event history, and the indexing state, while optionally exposing selected events to other applications via an event queue.

### `offers`

Stores the **state of every offer** ever created on the YAM contract.  
Each row represents **one unique offer**, identified by its on-chain `offer_id`.

**Purpose**
- Maintain the latest known state of each offer
- Provide a fast lookup table for current offer status and metadata

**Columns**
- `offer_id` (`BIGINT`, PK)  
  Unique on-chain identifier of the offer
- `seller_address` (`TEXT`)  
  Address of the offer creator
- `initial_amount` (`TEXT`)  
  Initial amount of tokens offered (raw on-chain value)
- `price_per_unit` (`TEXT`)  
  Price per token unit at creation
- `offer_token` (`TEXT`)  
  Address of the token being sold
- `buyer_token` (`TEXT`)  
  Address of the token used to buy
- `status` (`TEXT`)  
  Current offer status (`InProgress`, `SoldOut`, `Deleted`)
- `block_number` (`BIGINT`)  
  Block number at which the offer was created
- `transaction_hash` (`TEXT`)  
  Transaction hash of the creation event
- `log_index` (`INT`)  
  Log index of the creation event within the transaction
- `creation_timestamp` (`TIMESTAMPTZ`)  
  Timestamp derived from the block in which the offer was created


### `offer_events`

Stores **the full lifecycle of every offer**, including all state changes.  
Each row corresponds to **one on-chain event** related to an offer.

**Purpose**
- Keep an immutable event history
- Allow precise reconstruction of offer state over time
- Enable analytics, reporting and full history.

**Columns**
- `unique_id` (`TEXT`, PK)  
  Unique identifier derived from `(transaction_hash + log_index)`
- `offer_id` (`BIGINT`, FK → `offers.offer_id`)  
  Offer concerned by the event
- `event_type` (`TEXT`)  
  Event type (`OfferCreated`, `OfferUpdated`, `OfferAccepted`, `OfferDeleted`)
- `amount` (`TEXT`, nullable)  
  Amount involved in the event (if applicable)
- `price` (`TEXT`, nullable)  
  Price defined or updated by the event
- `buyer_address` (`TEXT`, nullable)  
  Buyer address for `OfferAccepted` events
- `amount_bought` (`TEXT`, nullable)  
  Amount purchased in a buy event
- `price_bought` (`TEXT`, nullable)  
  Price paid during purchase
- `block_number` (`BIGINT`)  
  Block number of the event
- `transaction_hash` (`TEXT`)  
  Transaction hash of the event
- `log_index` (`INT`)  
  Log index of the event
- `event_timestamp` (`TIMESTAMPTZ`)  
  Timestamp derived from the event block


### `indexing_state`

Tracks the **progress of the blockchain indexing process**.

**Purpose**
- Ensure the indexer can safely resume after a restart
- Avoid reprocessing already indexed block ranges

**Columns**
- `indexing_id` (`BIGSERIAL`, PK)  
  Internal indexing run identifier
- `from_block` (`BIGINT`)  
  First block number processed in this batch
- `to_block` (`BIGINT`)  
  Last block number processed in this batch

### `event_queue`

Optional table used to **expose selected events to external applications**.

**Purpose**
- Act as a lightweight event queue
- Enable other services (bots, alerts, analytics) to consume events without re-indexing the blockchain

**Columns**
- `id` (`BIGSERIAL`, PK)  
  Internal event identifier
- `created_at` (`TIMESTAMPTZ`)  
  Insertion timestamp
- `payload` (`JSONB`)  
  Serialized event data (e.g. `OfferAccepted`)

**Notes**
- This table is populated **only if** `EXPORT_EVENT_TO_EVENT_QUEUE = True`
- Writes are append-only
- Consumption is handled by downstream applications

---

## Database Query Examples

This section provides **practical SQL query examples** to help you explore and use the database once it has been populated by the indexer.  
All examples below assume **read-only access** using the `yam-indexing-reader` PostgreSQL user.

### List all active offers (not sold out or not deleted)

Retrieve the IDs of all offers that are still available (not sold out or deleted):

```sql
SELECT offer_id
FROM public.offers
WHERE status = 'InProgress'
ORDER BY offer_id;
```

### List all active offers of a specific user (not sold out or not deleted)

Retrieve all the IDs offers of a seller address that are still available (not sold out or deleted):

```sql
SELECT offer_id
FROM public.offers
WHERE status = 'InProgress'
ORDER BY offer_id;
```

### Retrieve the full event history of an offer

Fetch all events associated with a specific `offer_id`, ordered chronologically:

```sql
SELECT
  event_type,
  block_number,
  transaction_hash,
  log_index,
  event_timestamp,
  amount,
  price,
  buyer_address,
  amount_bought,
  price_bought,
  unique_id
FROM public.offer_events
WHERE offer_id = 220191
ORDER BY block_number ASC, log_index ASC;
```

### Retrieve all events linked to an address (seller or buyer) for a given offer token

Useful to reconstruct the full activity of a given address:

```sql
SELECT
  e.offer_id,
  o.seller_address,
  e.buyer_address,
  e.event_type,
  e.event_timestamp,
  e.amount,
  e.price,
  e.amount_bought,
  e.price_bought,
  e.transaction_hash,
  e.log_index
FROM public.offer_events e
JOIN public.offers o ON o.offer_id = e.offer_id
WHERE (
        o.seller_address = '0xADDRESS'
     OR e.buyer_address  = '0xADDRESS'
      )
  AND o.offer_token = '0xTOKEN_ADDRESS'
ORDER BY e.block_number ASC, e.log_index ASC;

```


These examples are intended as a starting point. They can easily be adapted for analytics, monitoring dashboards, bots, or reporting tools consuming the indexed YAM data.

---

## Design Considerations

### Data Reliability
- Uses multiple RPCs with automatic failover  
- Subgraph-based backfilling avoids missing historical events  
- Local SQLite DB ensures zero dependency on external services at runtime  

### Scalability
The indexer performs a fixed number of queries regardless of the number of users.  
All applications query the local DB.

### Resilience
Even if _The Graph_ becomes temporarily unavailable, the module continues indexing live events from RPCs.

---

## Subgraph Requirements

You need access to **a subgraph that exposes YAM offer-related events as entities**:

- **OfferCreated**
- **OfferUpdated**
- **OfferAccepted**
- **OfferDeleted**

These entities must exist in the subgraph schema and be queryable.

The complete `subgraph.yaml` file is provided in the project, but below is an example of the **relevant parts** illustrating the minimum expected configuration:

```yaml
entities:
  - OfferAccepted
  - OfferCreated
  - OfferDeleted
  - OfferUpdated

eventHandlers:
  - event: OfferAccepted(...)
    handler: handleOfferAccepted
  - event: OfferCreated(...)
    handler: handleOfferCreated
  - event: OfferDeleted(...)
    handler: handleOfferDeleted
  - event: OfferUpdated(...)
    handler: handleOfferUpdated
```
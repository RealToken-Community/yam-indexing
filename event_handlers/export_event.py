import json
from pathlib import Path

def export_event_to_json(decoded_logs: list, export_path: str = "./transactions_queue"):
    path = Path(export_path)
    path.mkdir(parents=True, exist_ok=True)

    for log in decoded_logs:
        if log.get("topic") == "OfferAccepted":
            file_path = path / f"{log['transactionHash']}_{log['logIndex']}.json"
            with file_path.open("w", encoding="utf-8") as f:
                json.dump(log, f, indent=4)
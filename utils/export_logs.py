import os
import json
import datetime

def export_api_logs(logs, out_dir="reports", fmt="json"):
    os.makedirs(out_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    if fmt == "json":
        out_path = os.path.join(out_dir, f"api_logs_{timestamp}.json")
        with open(out_path, "w") as f:
            json.dump(logs, f, indent=2)
        return out_path
    elif fmt == "csv":
        import csv
        out_path = os.path.join(out_dir, f"api_logs_{timestamp}.csv")
        with open(out_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=logs[0].keys())
            writer.writeheader()
            writer.writerows(logs)
        return out_path
    else:
        raise ValueError("Unsupported format")

# Example usage:
# logs = [{"endpoint": "/code", "status": 200, ...}, ...]
# export_api_logs(logs, fmt="json")

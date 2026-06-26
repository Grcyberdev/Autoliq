
import json
import os

DATA_FILE = "stock_data_checkpoint.json"

def main():
    if not os.path.exists(DATA_FILE):
        print("No checkpoint file found.")
        return

    with open(DATA_FILE, "r") as f:
        data = json.load(f)

    if "IMFL_BOR" in data:
        imfl_data = data["IMFL_BOR"]
        dates_to_remove = []
        for date, items in imfl_data.items():
            if not items: # Empty dict
                dates_to_remove.append(date)
        
        print(f"Found {len(dates_to_remove)} empty dates for IMFL_BOR.")
        for d in dates_to_remove:
            del imfl_data[d]
        
        print(f"Removed empty dates. {len(imfl_data)} valid dates remain for IMFL_BOR.")
        
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)
        print("Checkpoint updated.")

if __name__ == "__main__":
    main()

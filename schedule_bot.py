import schedule
import time
import subprocess
import sys
from datetime import datetime

def run_pipeline():
    print(f"\n=======================================================")
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Kicking off scheduled pipeline...")
    print(f"=======================================================\n")
    
    # Run the main pipeline
    # We use subprocess to ensure a completely fresh environment/memory for each run
    subprocess.run([sys.executable, "-u", "main.py", "--profile", "mythology"])
    
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Scheduled pipeline complete.\n")

# Schedule times
schedule.every().day.at("09:00").do(run_pipeline)
schedule.every().day.at("21:00").do(run_pipeline)

if __name__ == "__main__":
    print("=======================================================")
    print("  YOUTUBE BOT SCHEDULER ACTIVE")
    print("  - Running automatically at 09:00 and 21:00 every day.")
    print("  - Make sure to leave this terminal window OPEN.")
    print("=======================================================")

    while True:
        schedule.run_pending()
        time.sleep(30)  # Check schedule every 30 seconds

# Liquor Bond Automation - System Walkthrough

This document provides a detailed breakdown of the internal mechanics, algorithmic decisions, data schemas, and reliability features implemented across the Liquor Bond Automation Suite.

---

## 🔄 1. Automation Execution Workflow

Each execution run follows a synchronous pipeline to ensure clean execution state:

```
[Start] ──> [Init Web Driver] ──> [Login & Solve Captcha] ──> [Navigate & Scrape] 
              │                                                │
[Finish] <── [Send Telegram Alert] <── [Update Google Sheet] <── [Process Duplicates]
```

### Step 1: Web Driver Initialization
- Launches a Selenium WebDriver instance with specific Chrome flags:
  - `--headless=new` (Runs in a virtual display framework when executed via launchd/Xvfb).
  - `--no-sandbox` and `--disable-dev-shm-usage` (Enables resource containment).
  - Merges standard output and standard error outputs into log files.

### Step 2: Login & Verification Loop
1. Navigates to the portal URL defined in the configuration.
2. Un-hides the password inputs by removing `readonly` DOM attributes dynamically using JavaScript injection.
3. Targets the Captcha element, captures its screenshot, and crops it to the exact bounding box coordinates of the captcha image.
4. Feeds the pre-processed image bytes into Tesseract OCR (and/or `ddddocr`) to extract alphanumeric text.
5. Fills in credentials, inputs the solved captcha, and clicks submit.
6. Validates if login succeeded. If login fails, the scraper retries the process (up to a designated threshold).

### Step 3: Navigation and Web Scraping
- Directs the browser to the Stock Dispatch or Pass Endorsements URLs.
- Simulates date selectors via JavaScript injections to target selected date ranges (e.g. current day or yesterday's date).
- Extracts dynamic tables from the Excise Portal DOM, checking row by row to collect Date of Endorsement, Supplier Name, Truck Number, Liquor Type, and Quantities.

### Step 4: Duplicate Analysis & State Management
- Reads local state from checkpoint files (`incoming_stock_checkpoint.json` and `stock_data_checkpoint.json`).
- Compares scraped records against existing local checkpoints.
- Flags and filters out already processed transactions. Only newly scraped rows are passed to the next stage.

### Step 5: Google Sheets Synchronization
- Establishes connection using Google Authentication libraries via a GCP Service Account Key.
- Appends newly discovered entries to worksheets (e.g., `Truck Endorsements`, `Country Spirit Endorsements`).
- Applies standard format rules (e.g., bold headers, locked rows/columns).

### Step 6: Messaging Alerts
- Formulates a WhatsApp-style markdown report of processed entries (consolidating quantities per supplier).
- Dispatches the alerts to target chats via Telegram Bot API calls.

---

## 🧩 2. Captcha OCR Solving Strategy

The portal uses distorted numeric and alphanumeric captchas. To solve these reliably, the suite implements a multi-step pre-processing pipeline in Pillow before sending to Tesseract:

```
[Raw Bounding Box Image]
       │
       ▼
[Grayscale conversion (RGB -> L)]
       │
       ▼
[Upscaling (LANCZOS 4x/5x)] ──> Thicken/Restore anti-aliased edges
       │
       ▼
[Auto-Contrast Stretching] ──> Maximizes dynamic range
       │
       ▼
[Binarization Thresholding] ──> Pixels binarized to pure Black (0) / White (255)
       │
       ▼
[Pixel Density Inversion] ──> Ensures text is Black on a White background
       │
       ▼
[Morphological Thickening] ──> MinFilter/MaxFilter to clean line cuts
       │
       ▼
[Tesseract OCR Engine] ──> Whitelisted character configs (--psm 7)
```

1. **Upscaling:** Captchas are scaled up 4x to 5x using LANCZOS interpolation to avoid edge pixelation.
2. **Thresholding:** Converts the grayscale pixels to binary states based on target luminescence thresholds (ranging from 120 to 160).
3. **Inversion:** Counts white vs. black pixels to ensure the output image features black text on a clean white background.
4. **Morphological Filters:** Applies `MinFilter` (erosion) to thicken lines and repair broken characters, enhancing OCR engine accuracy.

---

## 📊 3. Google Sheets Schema & Layout

The Google Sheet **"Liqour Stock Data"** uses a specific schema layout to allow automated tracking and stock subtraction:

### A. Truck Endorsements Sheet
Contains data for IMFL trucks.
Columns:
- `DateofEndorsement` (YYYY-MM-DD format)
- `Supplier`
- `TruckNumber`
- `LiqourTypes`
- `TotalQuantity`
- `Status` (e.g., "Arrived", "Not Arrived")
- `DateArrived`
- `DateCompleted`

### B. Country Spirit Endorsements Sheet
Contains data for CS trucks. Has a similar structure to Truck Endorsements.

### C. Stock_Management Sheet
Handles stock math.
Columns:
- **Col A:** `Liquor Name`
- **Col B:** `Current Stock` — Contains a dynamic Google Sheets formula pointing to the opening stock minus dispatches:
  `=C{row}-SUM(D{row}:ZZ{row})`
- **Col C:** `Opening Stock` — Initial baseline value.
- **Col D onwards:** Daily dispatches added chronologically.

---

## 🛡️ 4. Fault Tolerance & Reliability Features

To guarantee 24/7 autonomous stability, several safeguards are active:

### 1. Directory Lock Concurrency Guard
- Before starting, the wrapper `run_automation.sh` attempts to create `/tmp/liquor_automation.lock.d`.
- If creation fails, it checks the PID file inside. If the PID is still running, the run terminates immediately to prevent duplicate runs.
- If the PID is dead, it cleans up the stale directory and starts.
- Ensures a `trap` clears the lock directory on exit.

### 2. Sandbox OS Browser Cleanup
- Web browsers can leak memory if crashes occur. The wrapper script runs cleanup logic after every script run:
  - **macOS:** Safely kills `chromedriver` to avoid closing user-opened Google Chrome browsers.
  - **Linux:** Aggressively terminates all active Chrome and Chromium subprocesses.

### 3. Dynamic Service Account Failover
- In local runtime, the script attempts to load credentials from `keys/` or root files.
- In CI (GitHub Actions), the key is created dynamically from secrets using base64 decoding.
- Incorporates API call retries to absorb minor Google API network timeouts.

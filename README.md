# Smart Service: Dynamic Tire Rental Pricing

This project was developed as part of the **"Smart Services" specialization module** at [IU International University of Applied Sciences](https://www.iu.org/) in March 2020.  
It demonstrates how **smart service business models** can be implemented through **dynamic pricing of tire rentals**, based on real-world **road quality data**.

📄 The full project documentation is available in **[README_project_report_german.pdf](README_project_report_german.pdf)**.

---

## 🚀 Project Overview

The project integrates **road quality data** (from [SmartRoadSense](http://smartroadsense.uniurb.it/)) with a **dynamic pricing engine** for tire rentals:

- **Data source:** crowdsourced smartphone accelerometer data about road conditions  
- **Core idea:** Tires wear out faster on poor roads → rental fees should reflect actual usage conditions  
- **Implementation:**  
  - CSV-based data ingestion  
  - Road quality evaluation  
  - Dynamic pricing calculation  
  - Simple user interface for interaction  

---

## 📂 Repository Structure

```
.
├── main.py                        # Entry point for running the service
├── process_with_csv.py            # Batch processing of road data from CSV
├── process_with_user_interface.py # Interactive CLI for user input
├── config.template.py             # Example config (copy to config.py and adjust if needed)
├── userfiles/
│   ├── to_process.csv             # Example road quality input file
│   ├── wheel_data.csv             # Example tire data for pricing
├── internal/
│   └── smartroadsense_backup.zip  # Backup of SmartRoadSense database (for reproducibility)
└── README_project_report_german.pdf # Full project report (German)
```

---

## ⚙️ Installation

Clone the repository:

```bash
git clone https://github.com/your-username/smart-tire-pricing.git
cd smart-tire-pricing
```

(Optional) create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate   # Linux/Mac
.venv\Scripts\activate      # Windows
```

Install dependencies (if any are listed in requirements.txt):

```bash
pip install -r requirements.txt
```

---

## ▶️ Usage

### 1. Run with CSV input

Process a sample dataset from `userfiles/to_process.csv`:

```bash
python process_with_csv.py
```

Results will be written to `userfiles/_processed_csv.csv`.

### 2. Run with interactive CLI

Start an interactive prompt for entering road/tire parameters:

```bash
python process_with_user_interface.py
```

### 3. Main entry point

Run the integrated flow (uses config):

```bash
python main.py
```

---

## 🗄 Data & Backups

- Example CSVs in `userfiles/`  
- SmartRoadSense backup database in `internal/` (for reproducibility in case the original service is offline)

---

## 🛡️ Security & Privacy Notes

- No API keys or secrets are included in this repository.  
- Configuration values (e.g., API endpoints) should be set in a local `config.py`, based on the provided `config.template.py`.  
- Generated outputs (e.g., processed CSVs) are ignored via `.gitignore` and should not be committed.  

---

## 📖 Documentation

For detailed methodology, business model considerations, and evaluation results, see:  
📄 [README_project_report_german.pdf](README_project_report_german.pdf)

---

## ✨ Credits

- Developed by Philipp von Lovenberg as part of the Smart Services module.  
- Data provided by SmartRoadSense.  
- Academic supervision: IU International University of Applied Sciences (2020).
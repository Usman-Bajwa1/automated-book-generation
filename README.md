# Automated Book Generation System

An intelligent, modular system that automatically generates complete books using AI.  
The system can create outlines, generate chapters, summarize progress, and send automated email updates — all while allowing human-in-the-loop feedback at key stages.

---

## Features
- **AI-Powered Writing:** Uses large language models (LLMs) to generate outlines, chapters, and summaries.
- **Chat Memory:** Uses `langgraph` in built memory to remember chat conversation per session 
- **Excel Feedback Loop:** Human feedback on outlines and chapters is read directly from Excel.  
- **Automated Emails:** Sends email updates with generated content attachments.  
- **Stateful Workflow:** Built using `langgraph` for modular and resumable generation.  
- **Secure Configuration:** Environment variables for email credentials and API keys.
- **History Storage:** Stores each chapter summary in the database for future review.

---

## Requirements
- Python 3.12  
- Conda (recommended)  
- A Google Account with an **App Password** for SMTP email (if using Gmail)  
- A valid `.env` file with your credentials and configuration values

---

## Installation

Clone the repository and set up the environment:

```bash
# Clone the repository
git clone https://github.com/Usman-Bajwa1/automated-book-generation.git
cd automated-book-generation

# Create and activate a new Conda environment
conda create -n book-gen python=3.12 -y
conda activate book-gen

# Install dependencies
pip install -r requirements.txt
# Fill the .env file as done in the example and then run 
# Update the 'excel_fp' in async main of bookgeneration.py to give your own excel file
python -m app.models.bookgeneration
```
## Important
The **instruction** and **update lines** in the terminal will guide you completely on how to make changes in excel.
  



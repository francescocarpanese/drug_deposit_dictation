# Drug Deposit Dictation

Voice-based CLI application for managing hospital drug inventory in Angola. Workers can record drug information and movements verbally, which are then transcribed, processed by AI, and imported into a database.

## Overview

This application solves the problem of data entry difficulties for local hospital workers by allowing them to:
1. Record drug information and movements by voice
2. Automatically transcribe audio to text using Whisper
3. Extract structured data using a local LLM (Llama 3.1)
4. Import data into a SQLite database for the main dashapp

## Features

- 🎤 **Voice Recording**: Record drug definitions and movements verbally
- 📝 **Transcription**: Uses OpenAI Whisper for accurate Portuguese transcription
- 🤖 **AI Processing**: Llama 3.1 extracts structured data from transcriptions
- 💾 **Database**: SQLite database with drugs and movements tables
- 🔄 **Complete Workflow**: Single command to process audio → database
- 📊 **Inspection**: CSV files for easy data review before import

## Installation

### Prerequisites

- Python 3.13+
- [uv](https://github.com/astral-sh/uv) package manager
- [FFmpeg](https://ffmpeg.org/) - required for audio processing
- [Ollama](https://ollama.ai/) with Llama 3.1 model installed

### Setup

1. **Install FFmpeg:**
   ```bash
   # On macOS:
   brew install ffmpeg
   
   # On Ubuntu/Debian:
   sudo apt update && sudo apt install ffmpeg
   
   # On Windows:
   # Download from https://ffmpeg.org/download.html
   ```

2. **Install Ollama and pull Llama 3.1:**
   ```bash
   # Install Ollama from https://ollama.ai/
   # Then pull the model:
   ollama pull llama3.1
   ```

3. **Install the application:**
   ```bash
   # Clone or navigate to the project directory
   cd drug_deposit_dictation
   
   # Install with uv
   uv sync
   
   # Or install dependencies
   uv pip install -e .
   ```

4. **Initialize the database:**
   ```bash
   uv run drug-dictation init-db
   ```

## Usage

### Quick Start: Full Pipeline

Process an audio recording through the complete workflow:

```bash
uv run drug-dictation process-audio audio/Voice_251023_112500.m4a
```

This will:
1. Transcribe the audio to text
2. Process the text with LLM to extract structured data
3. Show you the extracted data for review
4. Import to the database (if you confirm)

### Individual Commands

#### 1. Transcribe Audio

Convert audio to text and save as JSON:

```bash
uv run drug-dictation transcribe audio/Voice_251023_112500.m4a
```

Options:
- `--model, -m`: Whisper model size (tiny, base, small, medium, large) - default: base
- `--output-dir, -o`: Output directory - default: output/transcriptions
- `--language, -l`: Language code - default: pt (Portuguese)

#### 2. Process Transcription

Extract structured data from transcription JSON:

```bash
uv run drug-dictation process output/transcriptions/Voice_251023_112500_transcription.json
```

Options:
- `--model, -m`: Ollama model name - default: llama3.1
- `--output-dir, -o`: Output directory - default: output/processed

#### 3. Import to Database

Import CSV data to the database:

```bash
uv run drug-dictation import-data output/processed/Voice_251023_112500_transcription_data.csv
```

Options:
- `--db, -d`: Database path - default: data/drug_inventory.db
- `--review/--no-review`: Review before importing - default: review

#### 4. Batch Processing

Process all audio files in a directory:

```bash
uv run drug-dictation batch-process audio/
```

Options:
- `--whisper-model`: Whisper model size - default: base
- `--llm-model`: Ollama model - default: llama3.1
- `--language, -l`: Language code - default: pt

### Database Queries

#### List all drugs:

```bash
uv run drug-dictation list-drugs
```

#### View drug movement history:

```bash
uv run drug-dictation drug-history 1
```

## Database Schema

### Drugs Table

```sql
CREATE TABLE drugs (
    id INTEGER PRIMARY KEY,
    name TEXT,
    dose TEXT,
    units TEXT,
    expiration DATE,
    pieces_per_box INTEGER,
    type TEXT,
    lote TEXT,
    current_stock INTEGER DEFAULT 0,
    last_inventory_date DATE DEFAULT '1990-01-01'
)
```

### Movements Table

```sql
CREATE TABLE movements (
    id INTEGER PRIMARY KEY,
    date_movement DATE,
    destination_origin TEXT,
    pieces_moved INTEGER,
    movement_type TEXT CHECK(movement_type IN ('entry', 'exit', 'inventory')),
    signature TEXT,
    entry_datetime TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    drug_id INTEGER,
    FOREIGN KEY (drug_id) REFERENCES drugs(id)
)
```

## Workflow Details

### 1. Recording Voice Input

Workers should speak clearly in Portuguese, including:

**For new drugs:**
- Drug name
- Dose (e.g., "500mg", "10ml")
- Units (mg, ml, tablets, etc.)
- Expiration date
- Type (antibiotic, analgesic, etc.)
- Lot number
- Pieces per box

**For movements:**
- Drug name and dose
- Movement type: "entrada" (entry), "saída" (exit), or "inventário" (inventory)
- Number of pieces
- Destination (for exit) or origin (for entry)
- Date (if different from today)
- Person responsible

### 2. Transcription

Whisper transcribes the audio to Portuguese text and saves it as JSON with:
- Original audio file path
- Transcribed text
- Timestamp
- Individual segments with timings

### 3. LLM Processing

Llama 3.1 analyzes the transcription and extracts:
- Drug information (for new drugs)
- Movement information (for entries/exits/inventory)

Results are saved as:
- Processed JSON (for record keeping)
- CSV file (for easy inspection)

### 4. Database Import

The CSV is imported to the SQLite database:
- New drugs are added to the `drugs` table
- Movements are added to the `movements` table
- Stock levels are automatically updated based on movement type

## Tips

1. **Model Selection:**
   - Use `tiny` or `base` Whisper models for faster processing
   - Use `small` or `medium` for better accuracy
   - `large` is most accurate but slowest

2. **Audio Quality:**
   - Record in a quiet environment
   - Speak clearly and at a moderate pace
   - M4A, MP3, and WAV formats are all supported

3. **Review Before Import:**
   - Always review CSV files before importing to catch any errors
   - The `--review` option (default) shows data before importing
   - Use `--no-review` to auto-import when you're confident

4. **Batch Processing:**
   - Process multiple recordings at once with `batch-process`
   - Useful for end-of-day batch imports

## Project Structure

```
drug_deposit_dictation/
├── src/drug_deposit_dictation/
│   ├── __init__.py
│   ├── main.py           # CLI interface
│   ├── transcribe.py     # Whisper transcription
│   ├── process_llm.py    # LLM processing
│   ├── import_data.py    # Database import
│   └── database.py       # Database operations
├── audio/                # Audio recordings
├── output/
│   ├── transcriptions/   # JSON transcriptions
│   └── processed/        # Processed CSV files
├── data/                 # SQLite database
├── pyproject.toml
└── README.md
```

## Troubleshooting

### Ollama Connection Issues

Make sure Ollama is running:
```bash
ollama serve
```

### Whisper Installation Issues

If you encounter issues with PyTorch/Whisper:
```bash
uv pip install --upgrade openai-whisper torch
```

### Database Locked

If you get "database is locked" errors, make sure no other process is accessing the database.

## License

MIT

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

This progress is aims to improve the UX for the drug deposit program in [here](https://github.com/francescocarpanese/stock_management) used in Chiulo Hospital (Angola).

One of the main issue in operating the program was found the difficulties for the local worker to use a computare and insert the data with the application.

This folder develops a dictation system. The local worker in the deposit will only need to record a voice data where they describe they mention: 
- Drug name (ex. Aciclovar)
- Dose of the drug (ex. 50g)
- Expiration date.
- Pieces per box.
- type of drug: (comprimidos, ampulla, xerope, ..)
- type of movement. entry/exit/inventario. Inventario means you are updating the stock information.
- pieces moved: Number of pieces moved ( ex. 5 comprimodos)
- entire boxes moved: Number of entire boxes moved ( ex. 5 caixina). Number of boxes an single pieces will be added in the end
- destination/origin: The origin (supplier) or destination of the drug.
- date of movemet

This packages then provide utils to: 
- The recorded voice is then transcribed into text with Whisper.
- An LLm is then used to convert the transcription into a formatted JSON with the previous information.
- The JSON is then process to match a list of expected drugs available in the deposit.
- The formatted file is finally inserted into the database for the application. 

# Quick Start Guide

## Initial Setup

1. **Install FFmpeg (required for audio processing):**
```bash
# On macOS with Homebrew:
brew install ffmpeg
```

2. **Install Ollama and Llama 3.1:**
```bash
# Install Ollama from https://ollama.ai/
# Then pull the model:
ollama pull llama3.1
```

3. **Install Python dependencies:**
```bash
uv sync
```


4. **Transcribe autio file**
To transcribe a single file 

```bash
uv run drug-dictation transcribe <file_path>
```

To transcribe a batch of file in a folder 
```bash
uv run drug-dictation batch-transcribe <folder_path>
```

5. **Process the transcritpion to json with LLM.**
```bash
uv run drug-dictation process-transcription <file_path_json>
```

Or to process a batch of files
```bash
uv run drug-dictation batch-process-transcription <folder_path>
```

6. **Post-process json and adhere to standard for drug name and dose**

ONGOING

7. **Write to database**
ONGOING


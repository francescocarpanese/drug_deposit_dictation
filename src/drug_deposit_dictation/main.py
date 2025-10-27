#!/usr/bin/env python3
"""CLI for drug deposit dictation system."""

import click
from pathlib import Path
from typing import Optional

from drug_deposit_dictation.transcribe import AudioTranscriber
from drug_deposit_dictation.process_llm import TranscriptionProcessor
from drug_deposit_dictation.import_data import DataImporter
from drug_deposit_dictation.database import DatabaseManager


@click.group()
@click.version_option()
def cli():
    """Drug Deposit Dictation - Voice-based inventory management for hospitals."""
    pass


@cli.command()
@click.argument('audio_file', type=click.Path(exists=True))
@click.option('--output-dir', '-o', default='output/transcriptions',
              help='Output directory for transcription JSON')
@click.option('--model', '-m', default='large',
              type=click.Choice(['tiny', 'base', 'small', 'medium', 'large']),
              help='Whisper model size')
@click.option('--language', '-l', default='pt',
              help='Language code (default: pt for Portuguese)')
def transcribe(audio_file: str, output_dir: str, model: str, language: str):
    """Transcribe an audio file to text using Whisper."""
    click.echo(f"Transcribing: {audio_file}")
    
    transcriber = AudioTranscriber(model_name=model)
    json_path = transcriber.save_transcription(audio_file, output_dir, language)
    
    click.echo(f"✓ Transcription complete: {json_path}")


@cli.command()
@click.argument('directory', type=click.Path(exists=True))
@click.option('--output-dir', '-o', default='output/transcriptions', help='Output directory for transcription JSONs')
@click.option('--model', '-m', default='large', type=click.Choice(['tiny', 'base', 'small', 'medium', 'large']), help='Whisper model size')
@click.option('--language', '-l', default='pt', help='Language code')
def batch_transcribe(directory: str, output_dir: str, model: str, language: str):
    """Transcribe all audio files in a directory to JSON."""
    audio_dir = Path(directory)
    audio_files = []
    for ext in ['*.mp3', '*.wav', '*.m4a', '*.ogg', '*.flac']:
        audio_files.extend(audio_dir.glob(ext))
    if not audio_files:
        click.echo("No audio files found in directory.")
        return
    click.echo(f"Found {len(audio_files)} audio files")
    transcriber = AudioTranscriber(model_name=model)
    for i, audio_file in enumerate(audio_files, 1):
        click.echo(f"\n{'='*60}")
        click.echo(f"Transcribing {i}/{len(audio_files)}: {audio_file.name}")
        click.echo('='*60)
        try:
            json_path = transcriber.save_transcription(
                str(audio_file),
                output_dir=output_dir,
                language=language
            )
            click.echo(f"✓ Saved: {json_path}")
        except Exception as e:
            click.echo(f"✗ Error: {e}", err=True)

@cli.command()
@click.argument('json_file', type=click.Path(exists=True))
@click.option('--output-dir', '-o', default='output/processed',
              help='Output directory for processed CSV')
@click.option('--model', '-m', default='llama3.1',
              help='Ollama model name')
def process_transcription(json_file: str, output_dir: str, model: str):
    """Process transcription JSON with LLM to extract structured data."""
    click.echo(f"Processing: {json_file}")
    
    processor = TranscriptionProcessor(model_name=model)
    csv_path = processor.process_json_to_csv(json_file, output_dir)
    
    click.echo(f"✓ Processing complete: {csv_path}")


@cli.command()
@click.argument('csv_file', type=click.Path(exists=True))
@click.option('--db', '-d', default='data/drug_inventory.db',
              help='Database path')
@click.option('--review/--no-review', default=True,
              help='Review data before importing')
@click.option('--auto-create/--no-auto-create', default=True,
              help='Automatically create new drugs when no match found')
def import_data(csv_file: str, db: str, review: bool, auto_create: bool):
    """Import CSV data into the database."""
    click.echo(f"Importing: {csv_file}")
    
    importer = DataImporter(db_path=db)
    
    if review:
        result = importer.import_with_review(csv_file, auto_create_drugs=auto_create)
    else:
        result = importer.import_csv(csv_file, auto_create_drugs=auto_create)
    
    if result['success']:
        click.echo(f"\n✓ Import successful!")
        click.echo(f"  - Movements processed: {result['movements_processed']}")
        click.echo(f"  - New drugs created: {result['drugs_created']}")
        click.echo(f"  - Existing drugs matched: {result['drugs_matched']}")
    else:
        click.echo(f"\n✗ Import failed!")
        click.echo(f"  - Movements failed: {result['movements_failed']}")
        if result.get('details'):
            for detail in result['details']:
                if not detail.get('success'):
                    click.echo(f"  - Error: {detail.get('error')}", err=True)


@cli.command()
@click.argument('audio_file', type=click.Path(exists=True))
@click.option('--db', '-d', default='data/drug_inventory.db',
              help='Database path')
@click.option('--whisper-model', default='base',
              type=click.Choice(['tiny', 'base', 'small', 'medium', 'large']),
              help='Whisper model size')
@click.option('--llm-model', default='llama3.1',
              help='Ollama model name')
@click.option('--language', '-l', default='pt',
              help='Language code')
@click.option('--review/--no-review', default=True,
              help='Review data before importing')
def process_audio(audio_file: str, db: str, whisper_model: str,
                  llm_model: str, language: str, review: bool):
    """Complete workflow: transcribe audio, process with LLM, and import to database."""
    click.echo("="*60)
    click.echo("DRUG DEPOSIT DICTATION - Full Pipeline")
    click.echo("="*60)
    
    # Step 1: Transcribe
    click.echo("\n[1/3] Transcribing audio...")
    transcriber = AudioTranscriber(model_name=whisper_model)
    json_path = transcriber.save_transcription(
        audio_file,
        output_dir='output/transcriptions',
        language=language
    )
    click.echo(f"✓ Transcription saved: {json_path}")
    
    # Step 2: Process with LLM
    click.echo("\n[2/3] Processing with LLM...")
    processor = TranscriptionProcessor(model_name=llm_model)
    csv_path = processor.process_json_to_csv(
        json_path,
        output_dir='output/processed'
    )
    click.echo(f"✓ CSV saved: {csv_path}")
    
    # Step 3: Import to database
    click.echo("\n[3/3] Importing to database...")
    importer = DataImporter(db_path=db)
    
    if review:
        result = importer.import_with_review(csv_path, auto_create_drugs=True)
    else:
        result = importer.import_csv(csv_path, auto_create_drugs=True)
    
    if result['success']:
        click.echo(f"\n✓ Import successful!")
        click.echo(f"  - Movements processed: {result['movements_processed']}")
        click.echo(f"  - New drugs created: {result['drugs_created']}")
        click.echo(f"  - Existing drugs matched: {result['drugs_matched']}")
        click.echo("\n" + "="*60)
        click.echo("COMPLETE!")
        click.echo("="*60)
    else:
        click.echo(f"\n✗ Import failed!")
        click.echo(f"  - Movements failed: {result['movements_failed']}")
        for detail in result.get('details', []):
            if not detail.get('success'):
                click.echo(f"  - Error: {detail.get('error')}", err=True)


@cli.command()
@click.option('--db', '-d', default='data/drug_inventory.db',
              help='Database path')
@click.option('--limit', '-n', default=20, help='Number of drugs to show')
def list_drugs(db: str, limit: int):
    """List drugs in the database."""
    db_manager = DatabaseManager(db_path=db)
    drugs = db_manager.list_drugs()
    
    if not drugs:
        click.echo("No drugs in database.")
        return
    
    click.echo(f"\nTotal drugs: {len(drugs)}")
    click.echo("\n" + "="*80)
    
    for i, drug in enumerate(drugs[:limit], 1):
        click.echo(f"[{drug['id']}] {drug['name']}")
        if drug['dose']:
            click.echo(f"    Dose: {drug['dose']} {drug['units']}")
        if drug['type']:
            click.echo(f"    Type: {drug['type']}")
        if drug['lote']:
            click.echo(f"    Lot: {drug['lote']}")
        click.echo(f"    Stock: {drug['current_stock']} | Expiration: {drug['expiration']}")
        click.echo("    " + "-"*76)
    
    if len(drugs) > limit:
        click.echo(f"... and {len(drugs) - limit} more drugs")


@cli.command()
@click.argument('drug_id', type=int)
@click.option('--db', '-d', default='data/drug_inventory.db',
              help='Database path')
def drug_history(drug_id: int, db: str):
    """Show movement history for a drug."""
    db_manager = DatabaseManager(db_path=db)
    
    # Get drug info
    drugs = db_manager.list_drugs()
    drug = next((d for d in drugs if d['id'] == drug_id), None)
    
    if not drug:
        click.echo(f"Drug ID {drug_id} not found.", err=True)
        return
    
    movements = db_manager.get_movements_for_drug(drug_id)
    
    click.echo("\n" + "="*80)
    click.echo(f"Drug: {drug['name']} (ID: {drug_id})")
    click.echo(f"Current Stock: {drug['current_stock']}")
    click.echo("="*80)
    
    if not movements:
        click.echo("No movements recorded.")
        return
    
    click.echo(f"\nMovements ({len(movements)}):")
    for mov in movements:
        click.echo(f"\n[{mov['id']}] {mov['movement_type'].upper()}")
        click.echo(f"    Date: {mov['date_movement']}")
        click.echo(f"    Pieces: {mov['pieces_moved']}")
        if mov['destination_origin']:
            click.echo(f"    Dest/Origin: {mov['destination_origin']}")
        if mov['signature']:
            click.echo(f"    Signature: {mov['signature']}")
        click.echo(f"    Recorded: {mov['entry_datetime']}")


@cli.command()
@click.option('--db', '-d', default='data/drug_inventory.db',
              help='Database path')
def init_db(db: str):
    """Initialize the database."""
    click.echo(f"Initializing database: {db}")
    
    from drug_deposit_dictation.database import create_all_tables
    create_all_tables(db)
    
    click.echo("✓ Database initialized successfully!")



@cli.command()
@click.argument('directory', type=click.Path(exists=True))
@click.option('--output-dir', '-o', default='output/processed', help='Output directory for processed CSVs')
@click.option('--model', '-m', default='llama3.1', help='Ollama model name')
def batch_process_transcription(directory: str, output_dir: str, model: str):
    """Process all transcription JSON files in a directory with LLM."""
    json_dir = Path(directory)
    json_files = list(json_dir.glob('*.json'))
    if not json_files:
        click.echo("No JSON files found in directory.")
        return
    click.echo(f"Found {len(json_files)} JSON files")
    processor = TranscriptionProcessor(model_name=model)
    for i, json_file in enumerate(json_files, 1):
        click.echo(f"\n{'='*60}")
        click.echo(f"Processing {i}/{len(json_files)}: {json_file.name}")
        click.echo('='*60)
        try:
            csv_path = processor.process_json_to_csv(
                str(json_file),
                output_dir=output_dir
            )
            click.echo(f"✓ Saved: {csv_path}")
        except Exception as e:
            click.echo(f"✗ Error: {e}", err=True)


if __name__ == '__main__':
    cli()

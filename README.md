# ICUVRapp

Python desktop application for running the **RPH ICU VR-Stroop** research study.
It walks a participant through consent, a Polar Bluetooth heart-rate baseline, a
VR (or control) intervention, and a cognitive Stroop task, then exports the data
as an AES-256 encrypted ZIP.

## Features

- Guided GUI (CustomTkinter) covering consent → sensor pairing → baseline →
  intervention → Stroop → secure export.
- Automatic participant ID and balanced group assignment (VR / Non-VR Control).
- Polar heart-rate sensor discovery over Bluetooth LE (`bleak`).
- Stroop task with reaction-time, accuracy, and congruency tracking.
- Per-participant Excel log + summary (average HR/PPI, RMSSD, Stroop metrics).
- PDF consent form and encrypted ZIP archive written to `Study_Backup/`.

## Requirements

- Python **>= 3.14**
- [`uv`](https://docs.astral.sh/uv/) for environment and dependency management
- Bluetooth LE adapter (for the Polar sensor pairing screen)

## Installation

```powershell
uv sync
```

## Configuration

The application requires a password used to encrypt the exported ZIP archives.
Copy `sample.env` to `.env` and set a strong value:

```powershell
Copy-Item sample.env .env
```

Then edit `.env`:

```env
STUDY_FILE_PASSWORD=your-secure-password
```

The `.env` file is loaded at startup and its values override any pre-existing
shell environment variables.

## Running

```powershell
uv run icuvrapp
```

This launches the study GUI. On first run a `data/` directory and a
`Participant_Registry.csv` file are created at the repository root.

## Outputs

For each participant, the app writes the following into `data/`:

- `SECURE_<ID>_<timestamp>.zip` — AES-256 encrypted archive containing:
  - `Consent_<ID>.pdf` — signed consent form
  - `Data_<ID>.xlsx` — per-second log plus a summary row (HR, PPI, RMSSD,
    Stroop mean RT, interference, accuracy, errors)
  - `Participant_Registry.csv` — running roster

The intermediate PDF and XLSX are deleted after the ZIP is written; only the
encrypted archive and the registry remain on disk.

## Project structure

```
pyproject.toml
sample.env
data/               # created at runtime; holds registry + encrypted exports
src/icuvrapp/
  main.py           # entry point; loads .env and calls run_app()
  ICUVRstudy.py     # GUI, study flow, data capture, export
```

## Development

`uv sync` installs the `dev` dependency group by default (which includes
`ruff` and `prek`).

### Pre-commit hooks with prek

This repo uses [`prek`](https://prek.j178.dev/) (a fast, drop-in replacement
for `pre-commit`) to run lint/format and hygiene checks before each commit.
Hooks are configured in [prek.toml](prek.toml) and include trailing-whitespace,
end-of-file-fixer, large-file / merge-conflict / private-key checks, JSON /
TOML / YAML validation, and `ruff` lint + format.

`prek` is included in the `dev` dependency group, so `uv sync` already
installs it. Enable the git hook in this repo once:

```powershell
uv run prek install
```

Run all hooks manually against every tracked file:

```powershell
uv run prek run --all-files
```

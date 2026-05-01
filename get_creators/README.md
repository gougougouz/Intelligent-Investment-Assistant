# get24_video

## Purpose
Fetch download URLs for videos published within the last 24 hours by a Douyin creator `sec_id`.

## Requirements
- Python 3.8+
- requests
- python-dotenv

## Setup
1. Create `get_creators/.env` and set `DOUYIN_AUTH_TOKEN` (or `TIKHUB_API_TOKEN`).
2. Open `get_creators/get24_video.py` and fill in `SEC_ID`.

## Usage
```bash
python get_creators/get24_video.py
```

## Output
The script writes results to a local file. You can change `OUTPUT_FORMAT` and
`OUTPUT_PATH` in the script to use JSON or CSV.

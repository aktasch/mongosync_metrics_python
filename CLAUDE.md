# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Flask web application that analyzes MongoDB mongosync JSON logs and generates interactive Plotly visualizations of replication metrics. The application accepts log files via an upload form, extracts specific message types, and creates time-series charts showing replication progress, lag time, and operation duration statistics.

**Key dependencies**: Flask 3.0.0 (web framework), Plotly 5.18.0 (visualization), Jinja2 3.1.2 (templating)

## Core Architecture

**Single-file application**: `mongosync_plotly_multiple.py` contains the entire Flask app with two routes:

1. `GET /` — Returns an HTML form for file upload
2. `POST /upload` — Processes the uploaded mongosync log file:
   - Validates all lines as valid JSON (returns 400 if invalid)
   - Extracts 5 message types: `"Replication progress."`, `"Version info"`, `"Mongosync Options"`, `"Recent operation duration stats."`, `"Sent response."`
   - Parses nested JSON fields (e.g., `response['body']` is a JSON string that needs re-parsing)
   - Extracts metrics: `totalEventsApplied`, `lagTimeSeconds`, operation duration averages/maximums/counts for Collection Copy and CEA operations
   - Builds a 7-row subplot figure with 6 scatter plots (metrics) and 1 table (mongosync options)
   - Returns rendered HTML with embedded Plotly visualization

**Data flow**: JSON log file → Line-by-line validation → Message filtering → Metric extraction → Plotly figure generation → HTML render

## Common Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the Flask app locally (listens on port 3030)
python mongosync_plotly_multiple.py

# Docker build and run
docker build -t mongosync-metrics .
docker run -it --rm -p 3030:3030 mongosync-metrics

# Test with sample log file
curl -X POST -F "file=@test_mongosync.log" http://localhost:3030/upload
```

Once running, access the app at `http://localhost:3030`.

## Recent Improvements (Latest Implementation)

The app has been refactored with the following major improvements:

### Architecture & Performance

- **Single-pass log parsing**: All message types are extracted in one pass through the file, eliminating redundant `json.loads()` calls
- **Jinja2 templates**: HTML moved to `templates/` directory (`index.html`, `plot.html`) for better maintainability
- **Logging instead of print**: Uses Python's `logging` module with configurable levels instead of print statements

### Bug Fixes

- **Fixed estimated bytes**: Corrected bug where `estimated_total_bytes` was unconditionally reset to 0
- **Fixed undefined variable**: `mongosync_sent_response_body` is now safely initialized before use
- **Fixed X-axis alignment**: Operation stats now use their own timestamps (`ops_times`) instead of replication progress times
- **Removed message type mismatches**: Corrected filters from `"sent response"` → `"Sent response."` and `"Operation duration stats."` → `"Recent operation duration stats."`
- **Removed duplicate code**: `times` list is now extracted once, not twice

### Error Handling & UX

- **User-visible error messages**: Errors (invalid file, bad JSON, file type) are displayed on the form with clear explanations
- **File validation**: Checks file extension and size (50MB limit) before processing
- **Graceful error handling**: Invalid JSON on specific lines is reported with line numbers
- **No silent failures**: All error conditions now provide user feedback

### Code Quality

- **Removed dead code**: Deleted unused `/plot` route that never worked
- **Removed unused variables**: Cleaned up unused `mongosync_opts_text` variable
- **Better version info**: Uses first version entry; improved annotation formatting
- **Flattened table structure**: `hiddenFlags` nested dict is properly flattened in options table

## Key Implementation Details

- **Message types extracted** (single-pass):
  - `"Replication progress."` → replication metrics (events, lag time)
  - `"Version info"` → version, OS, architecture
  - `"Mongosync Options"` → configuration table
  - `"Recent operation duration stats."` → operation timing metrics
  - `"Sent response."` → estimated copy progress (bytes)

- **Metrics visualization**: 7 subplots with different line styles (solid, dashed, dotted) for different metric types

- **Time parsing**: RFC3339 format, first 26 characters: `"%Y-%m-%dT%H:%M:%S.%f"`

- **Bytes calculation**: Extracts from the last valid `"Sent response."` message body

## Templates

HTML is organized in `templates/` directory (requires Jinja2):

- **`index.html`**: File upload form with error display. Centered flexbox layout with gradient background. Accepts .json, .log, .txt files.
- **`plot.html`**: Results page displaying Plotly visualization. Embeds JSON plot object. Includes window resize handler for responsive plots.

## UI/UX Improvements

- **Centered layouts**: Both upload and results pages are centered with responsive design

- **Professional styling**: Gradient background on upload form, card-based design with shadows
- **Mobile responsive**: Plots adapt to viewport width with Plotly's responsive mode
- **Better visual hierarchy**: Clear spacing between sections, improved typography
- **Drag-and-drop ready**: File input accepts .json, .log, and .txt files
- **Window resize handling**: Plots automatically redraw on browser resize

## Testing

A `test_mongosync.log` sample file is included with realistic mongosync metrics for testing. The app successfully:

- Parses 22 log lines with all message types
- Generates interactive plots with Plotly (7 subplots with 18+ metrics)
- Displays version info, replication progress, and operation statistics
- Shows mongosync configuration in a formatted table

Test with: `curl -X POST -F "file=@test_mongosync.log" http://localhost:3030/upload`

## Gotchas & Common Mistakes

- **Message type strings are exact**: `"Sent response."` ≠ `"sent response"`. Case and punctuation matter. Check actual log file strings before changing filters.
- **Nested JSON in response body**: The `sent_response['body']` field is a JSON **string** that must be parsed again with `json.loads()`, not used directly as a dict.
- **Operation stats use separate timestamps**: Don't use `replication_progress` times for operation duration plots. Extract and use `ops_times` separately to avoid X-axis misalignment.
- **Estimated bytes from last message**: Always use the **last valid** `"Sent response."` message (search reversed); earlier messages contain stale data. Current implementation correctly uses reversed iteration.
- **Hidden flags flattening**: The `hiddenFlags` nested dict in mongosync options must be flattened with prefix `"hiddenFlags."` for the table display, or it renders as a malformed cell.

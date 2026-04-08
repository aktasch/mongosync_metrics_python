import plotly.graph_objects as go
from plotly.subplots import make_subplots
from plotly.utils import PlotlyJSONEncoder
from flask import Flask, request, render_template
import json
from datetime import datetime
import logging
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
ALLOWED_EXTENSIONS = {'json', 'log', 'txt'}

# Create Flask app
app = Flask(__name__, template_folder='templates')
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE


def allowed_file(filename):
    """Check if file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def parse_log_lines(lines):
    """
    Single-pass log parsing to extract all message types.
    Returns dict with lists of parsed JSON for each message type.
    """
    parsed_data = {
        'replication_progress': [],
        'version_info': [],
        'mongosync_options': [],
        'operation_stats': [],
        'sent_response': []
    }

    for line_idx, line in enumerate(lines):
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON on line {line_idx + 1}: {line[:100]}")
            raise ValueError(f"Invalid JSON on line {line_idx + 1}")

        message = parsed.get('message', '')

        if message == 'Replication progress.':
            parsed_data['replication_progress'].append(parsed)
        elif message == 'Version info':
            parsed_data['version_info'].append(parsed)
        elif message == 'Mongosync Options':
            parsed_data['mongosync_options'].append(parsed)
        elif message == 'Recent operation duration stats.':
            parsed_data['operation_stats'].append(parsed)
        elif message == 'Sent response.':
            parsed_data['sent_response'].append(parsed)

    return parsed_data


def extract_metrics(data):
    """Extract and organize all metrics from parsed data."""
    metrics = {
        'times': [],
        'totalEventsApplied': [],
        'lagTimeSeconds': [],
        'estimated_total_bytes': 0,
        'estimated_copied_bytes': 0,
        'ops_times': [],
        'CollectionCopySourceRead': [],
        'CollectionCopySourceRead_maximum': [],
        'CollectionCopySourceRead_numOperations': [],
        'CollectionCopyDestinationWrite': [],
        'CollectionCopyDestinationWrite_maximum': [],
        'CollectionCopyDestinationWrite_numOperations': [],
        'CEASourceRead': [],
        'CEASourceRead_maximum': [],
        'CEASourceRead_numOperations': [],
        'CEADestinationWrite': [],
        'CEADestinationWrite_maximum': [],
        'CEADestinationWrite_numOperations': [],
    }

    # Extract replication progress metrics
    for item in data['replication_progress']:
        if 'time' in item:
            try:
                time = datetime.strptime(item['time'][:26], "%Y-%m-%dT%H:%M:%S.%f")
                metrics['times'].append(time)
                if 'totalEventsApplied' in item:
                    metrics['totalEventsApplied'].append(item['totalEventsApplied'])
                if 'lagTimeSeconds' in item:
                    metrics['lagTimeSeconds'].append(item['lagTimeSeconds'])
            except ValueError as e:
                logger.warning(f"Failed to parse time {item.get('time')}: {e}")

    # Extract operation stats metrics with their own timestamps
    ops_times = []
    for item in data['operation_stats']:
        if 'time' in item:
            try:
                time = datetime.strptime(item['time'][:26], "%Y-%m-%dT%H:%M:%S.%f")
                ops_times.append(time)
            except ValueError:
                pass

    metrics['ops_times'] = ops_times

    # Extract operation duration stats
    for item in data['operation_stats']:
        if 'CollectionCopySourceRead' in item:
            cc_src = item['CollectionCopySourceRead']
            if 'averageDurationMs' in cc_src:
                metrics['CollectionCopySourceRead'].append(float(cc_src['averageDurationMs']))
            if 'maximumDurationMs' in cc_src:
                metrics['CollectionCopySourceRead_maximum'].append(float(cc_src['maximumDurationMs']))
            if 'numOperations' in cc_src:
                metrics['CollectionCopySourceRead_numOperations'].append(float(cc_src['numOperations']))

        if 'CollectionCopyDestinationWrite' in item:
            cc_dst = item['CollectionCopyDestinationWrite']
            if 'averageDurationMs' in cc_dst:
                metrics['CollectionCopyDestinationWrite'].append(float(cc_dst['averageDurationMs']))
            if 'maximumDurationMs' in cc_dst:
                metrics['CollectionCopyDestinationWrite_maximum'].append(float(cc_dst['maximumDurationMs']))
            if 'numOperations' in cc_dst:
                metrics['CollectionCopyDestinationWrite_numOperations'].append(float(cc_dst['numOperations']))

        if 'CEASourceRead' in item:
            cea_src = item['CEASourceRead']
            if 'averageDurationMs' in cea_src:
                metrics['CEASourceRead'].append(float(cea_src['averageDurationMs']))
            if 'maximumDurationMs' in cea_src:
                metrics['CEASourceRead_maximum'].append(float(cea_src['maximumDurationMs']))
            if 'numOperations' in cea_src:
                metrics['CEASourceRead_numOperations'].append(float(cea_src['numOperations']))

        if 'CEADestinationWrite' in item:
            cea_dst = item['CEADestinationWrite']
            if 'averageDurationMs' in cea_dst:
                metrics['CEADestinationWrite'].append(float(cea_dst['averageDurationMs']))
            if 'maximumDurationMs' in cea_dst:
                metrics['CEADestinationWrite_maximum'].append(float(cea_dst['maximumDurationMs']))
            if 'numOperations' in cea_dst:
                metrics['CEADestinationWrite_numOperations'].append(float(cea_dst['numOperations']))

    # Extract bytes from sent response (use the last response body if multiple exist)
    if data['sent_response']:
        for response in reversed(data['sent_response']):
            if 'body' in response:
                try:
                    body = json.loads(response['body'])
                    if 'progress' in body and 'collectionCopy' in body['progress']:
                        cc = body['progress']['collectionCopy']
                        if 'estimatedTotalBytes' in cc:
                            metrics['estimated_total_bytes'] = cc['estimatedTotalBytes']
                        if 'estimatedCopiedBytes' in cc:
                            metrics['estimated_copied_bytes'] = cc['estimatedCopiedBytes']
                        break  # Use the last valid response
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"Failed to parse sent response body: {e}")

    return metrics


def build_figure(metrics, options_table, version_info):
    """Build Plotly figure with all subplots."""
    fig = make_subplots(
        rows=7, cols=1,
        subplot_titles=(
            "Estimated Copied Bytes",
            "Total Events Applied",
            "Collection Copy Source Read",
            "Collection Copy Destination Write",
            "CEA Source Read",
            "CEA Destination Write",
            "MongoSync Options"
        ),
        specs=[[{}], [{}], [{}], [{}], [{}], [{}], [{"type": "table"}]]
    )

    # Add version info annotation
    if version_info:
        fig.add_annotation(
            x=0.5, y=1.05, xref="paper", yref="paper",
            text=version_info, showarrow=False,
            font=dict(size=12)
        )

    # Row 1: Estimated bytes bar chart
    fig.add_trace(
        go.Bar(
            name='Estimated Total Bytes',
            x=['Bytes'],
            y=[metrics['estimated_total_bytes']],
            marker=dict(color='#1f77b4')
        ),
        row=1, col=1
    )
    fig.add_trace(
        go.Bar(
            name='Estimated Copied Bytes',
            x=['Bytes'],
            y=[metrics['estimated_copied_bytes']],
            marker=dict(color='#ff7f0e')
        ),
        row=1, col=1
    )

    # Row 2: Replication progress
    fig.add_trace(
        go.Scatter(
            x=metrics['times'],
            y=metrics['totalEventsApplied'],
            mode='lines',
            name='Total Events Applied',
            line=dict(color='#2ca02c')
        ),
        row=2, col=1
    )
    fig.add_trace(
        go.Scatter(
            x=metrics['times'],
            y=metrics['lagTimeSeconds'],
            mode='lines',
            name='Lag Time Seconds',
            line=dict(color='#d62728')
        ),
        row=2, col=1
    )

    # Row 3: Collection Copy Source Read
    fig.add_trace(
        go.Scatter(x=metrics['ops_times'], y=metrics['CollectionCopySourceRead'],
                   mode='lines', name='CC Source Read Avg', line=dict(color='#9467bd')),
        row=3, col=1
    )
    fig.add_trace(
        go.Scatter(x=metrics['ops_times'], y=metrics['CollectionCopySourceRead_maximum'],
                   mode='lines', name='CC Source Read Max', line=dict(color='#8c564b', dash='dash')),
        row=3, col=1
    )
    fig.add_trace(
        go.Scatter(x=metrics['ops_times'], y=metrics['CollectionCopySourceRead_numOperations'],
                   mode='lines', name='CC Source Read Ops', line=dict(color='#e377c2', dash='dot')),
        row=3, col=1
    )

    # Row 4: Collection Copy Destination Write
    fig.add_trace(
        go.Scatter(x=metrics['ops_times'], y=metrics['CollectionCopyDestinationWrite'],
                   mode='lines', name='CC Dest Write Avg', line=dict(color='#7f7f7f')),
        row=4, col=1
    )
    fig.add_trace(
        go.Scatter(x=metrics['ops_times'], y=metrics['CollectionCopyDestinationWrite_maximum'],
                   mode='lines', name='CC Dest Write Max', line=dict(color='#bcbd22', dash='dash')),
        row=4, col=1
    )
    fig.add_trace(
        go.Scatter(x=metrics['ops_times'], y=metrics['CollectionCopyDestinationWrite_numOperations'],
                   mode='lines', name='CC Dest Write Ops', line=dict(color='#17becf', dash='dot')),
        row=4, col=1
    )

    # Row 5: CEA Source Read
    fig.add_trace(
        go.Scatter(x=metrics['ops_times'], y=metrics['CEASourceRead'],
                   mode='lines', name='CEA Source Read Avg', line=dict(color='#ff9896')),
        row=5, col=1
    )
    fig.add_trace(
        go.Scatter(x=metrics['ops_times'], y=metrics['CEASourceRead_maximum'],
                   mode='lines', name='CEA Source Read Max', line=dict(color='#98df8a', dash='dash')),
        row=5, col=1
    )
    fig.add_trace(
        go.Scatter(x=metrics['ops_times'], y=metrics['CEASourceRead_numOperations'],
                   mode='lines', name='CEA Source Read Ops', line=dict(color='#c5b0d5', dash='dot')),
        row=5, col=1
    )

    # Row 6: CEA Destination Write
    fig.add_trace(
        go.Scatter(x=metrics['ops_times'], y=metrics['CEADestinationWrite'],
                   mode='lines', name='CEA Dest Write Avg', line=dict(color='#c49c94')),
        row=6, col=1
    )
    fig.add_trace(
        go.Scatter(x=metrics['ops_times'], y=metrics['CEADestinationWrite_maximum'],
                   mode='lines', name='CEA Dest Write Max', line=dict(color='#f7b6d2', dash='dash')),
        row=6, col=1
    )
    fig.add_trace(
        go.Scatter(x=metrics['ops_times'], y=metrics['CEADestinationWrite_numOperations'],
                   mode='lines', name='CEA Dest Write Ops', line=dict(color='#c7c7c7', dash='dot')),
        row=6, col=1
    )

    # Row 7: Options table
    fig.add_trace(options_table, row=7, col=1)

    # Update layout with responsive sizing
    fig.update_layout(
        height=1800,
        title_text="Mongosync Replication Metrics",
        showlegend=True,
        hovermode='x unified',
        autosize=True,
        margin=dict(l=50, r=50, t=80, b=50)
    )

    return fig


def build_options_table(mongosync_options):
    """Build table trace from mongosync options."""
    if not mongosync_options:
        return go.Table(
            header=dict(values=['Mongosync Options']),
            cells=dict(values=[['No options found in log file']])
        )

    options = mongosync_options[0]
    keys = list(options.keys())
    values = [[options.get(k, '') for k in keys]]

    # Flatten hiddenFlags if present
    flattened_keys = []
    flattened_values = []
    for k, v in zip(keys, values[0]):
        if k == 'hiddenFlags' and isinstance(v, dict):
            for hk, hv in v.items():
                flattened_keys.append(f"hiddenFlags.{hk}")
                flattened_values.append(hv)
        else:
            flattened_keys.append(k)
            flattened_values.append(v)

    return go.Table(
        header=dict(values=['Key', 'Value'], font=dict(size=12, color='black')),
        cells=dict(values=[flattened_keys, flattened_values], font=dict(size=10, color='darkblue')),
        columnwidth=[0.75, 2.5]
    )


def format_version_info(version_info_list):
    """Format version info for display."""
    if not version_info_list:
        return ""

    # Use the first version info entry
    info = version_info_list[0]
    return (f"MongoSync Version: {info.get('version', 'N/A')}, "
            f"OS: {info.get('os', 'N/A')}, "
            f"Arch: {info.get('arch', 'N/A')}")


@app.route('/')
def upload_form():
    """Render file upload form."""
    error = request.args.get('error')
    return render_template('index.html', error=error)


@app.route('/upload', methods=['POST'])
def upload_file():
    """Process uploaded log file and generate plots."""
    if 'file' not in request.files:
        return render_template('index.html', error='No file selected')

    file = request.files['file']

    if file.filename == '':
        return render_template('index.html', error='No file selected')

    if not allowed_file(file.filename):
        return render_template(
            'index.html',
            error=f'Invalid file type. Allowed: {", ".join(ALLOWED_EXTENSIONS)}'
        )

    try:
        # Read file lines (bytes from Flask file object)
        lines = [line.decode('utf-8', errors='ignore') for line in file]

        if not lines:
            return render_template('index.html', error='Log file is empty')

        logger.info(f"Parsing {len(lines)} log lines from {file.filename}")

        # Single-pass parsing
        data = parse_log_lines(lines)

        # Check if we have any relevant data
        if not data['replication_progress'] and not data['operation_stats']:
            logger.warning('No replication progress or operation stats found in log')
            return render_template(
                'index.html',
                error='No mongosync metrics found in log file'
            )

        # Extract metrics
        metrics = extract_metrics(data)

        # Build table and version info
        options_table = build_options_table(data['mongosync_options'])
        version_info = format_version_info(data['version_info'])

        # Build figure
        fig = build_figure(metrics, options_table, version_info)

        # Convert to JSON
        plot_json = json.dumps(fig, cls=PlotlyJSONEncoder)

        logger.info(f"Successfully processed {file.filename}")

        return render_template('plot.html', plot_json=plot_json, version_info=version_info)

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        return render_template('index.html', error=f'Invalid log format: {str(e)}')
    except Exception as e:
        logger.error(f"Error processing file: {e}", exc_info=True)
        return render_template('index.html', error=f'Error processing file: {str(e)}')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3030, debug=False)

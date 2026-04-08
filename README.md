# mongosync_metrics_python

A Flask web application that analyzes MongoDB mongosync JSON logs and generates interactive Plotly visualizations of replication metrics on port **3030**.

The application accepts log files via a web form, validates all JSON lines, extracts specific message types, and creates time-series charts showing replication progress, lag time, and operation duration statistics. It includes a Dockerfile for containerization and comprehensive error handling.

![Alt text for image 1](static/centered_home.png)

## How It Works

The Flask application (`mongosync_plotly_multiple.py`) provides two routes:

1. **Upload Form** (`GET /`) — Web interface for uploading mongosync log files (.json, .log, or .txt)
2. **Processing** (`POST /upload`) — Processes uploaded logs and returns interactive visualizations:
   - Validates JSON format (50MB max file size)
   - Extracts 5 message types in a single pass: `"Replication progress."`, `"Version info"`, `"Mongosync Options"`, `"Recent operation duration stats."`, `"Sent response."`
   - Parses metrics: total events applied, lag time, operation duration stats (average/maximum/count) for Collection Copy and CEA operations
   - Generates 7-subplot Plotly figure (6 time-series charts + 1 options table)
   - Displays with responsive, centered layout using Jinja2 templates

The application uses Python's `logging` module for configurable output and provides clear error messages for invalid files or malformed JSON.

## Dockerfile

The Dockerfile is used to create a Docker image of the application. The Docker image includes the Python environment with all the necessary dependencies installed, as well as the Python script itself.

To build the Docker image, navigate to the directory containing the Dockerfile and run the following command:

```bash
docker build -t my-python-app .
```

To run the Docker container, use the following command:

```bash
docker run -it --rm --name my-running-app my-python-app
```

## requirements.txt

The `requirements.txt` file lists the Python packages that the script depends on. The packages are specified with their version numbers to ensure compatibility.

To install the dependencies, use the following command:

```bash
pip install -r requirements.txt
```

This command should be run in the Python environment where you want to run the script. If you're using a virtual environment, make sure to activate it first.

## Getting Started

1. Clone the repository to your local machine.
2. Navigate to the directory containing the Python script and the `requirements.txt` file.
3. Install the dependencies with `pip install -r requirements.txt`.
4. Run the Python script with `mongosync_plotly_multiple.py`.

Please note that you need to have Python and pip installed on your machine to run the script and install the dependencies. If you want to use Docker, you also need to have Docker installed.

## Accessing the Application and Viewing Plots

Once the application is running, you can access it by opening a web browser and navigating to `http://localhost:3030`. This assumes that the application is running on the same machine where you're opening the browser, and that it's configured to listen on port 3030.

![Alt text for image 2](static/centered_results.png)

## Uploading the mongosync Log File

The method for uploading the `mongosync` log file depends on how the application is designed. The application provides a user interface for uploading files, you can use that. Typically, this involves clicking a "Browse" or "Upload" button, selecting the file from your file system, and then clicking an "Open" or "Upload" button.

## Viewing the Plot Information

Once the `mongosync` log file is uploaded, the application processes the data and generates the plots. You can view these plots by navigating to the appropriate page in the application. The exact method depends on how the application is designed, but typically, you would click on a link or button, or navigate to a specific URL.

If the plots aren't immediately visible after uploading the file, you may need to refresh the page. If the plots still aren't visible, check for any error messages or notifications from the application.

## ToDo

- Test with multiple mongosync versions, only tested with 1.6.1.
- Certified the time lines.
- Create more metrics with "TRACE" debug level
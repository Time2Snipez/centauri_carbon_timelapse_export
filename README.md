# Centauri Carbon Timelapse Export

A Python script that makes exporting timelapse videos from your Centauri Carbon 3D printer easy. This tool can automatically discover the latest timelapse, trigger the export process, and download the resulting MP4 file to your local machine.

## Features

- **Automatic Discovery**: Find the latest timelapse video using `--latest` flag
- **Manual Export**: Export specific timelapse files by providing the path
- **WebSocket Integration**: Uses WebSocket communication for real-time export status
- **Robust Download**: Includes retry logic and error handling for reliable downloads
- **Flexible Configuration**: Customizable host, timeout, and output directory settings

## Installation

1. Clone this repository:
```bash
git clone <repository-url>
cd centauri_carbon_timelapse_export
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Basic Usage

Export the latest timelapse video:
```bash
python export.py 192.168.178.100 --latest
```

Export a specific timelapse file:
```bash
python export.py 192.168.178.100 my_print_2024-01-15.mp4
```

### All Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `host` | string | **Required** | Printer IP address or hostname |
| `file` | string | - | MP4 filename (e.g., `ECC_0.4_Grampo_PLA0.24_11m59s-3518651.mp4`) |
| `--latest` | flag | - | Automatically discover and export the latest timelapse |
| `--list-path` | string | `/local/aic_tlp/` | Directory path to search for timelapses (used with `--latest`) |
| `--out-dir` | string | `.` | Directory to save the downloaded MP4 file |
| `--check` | flag | - | Perform HTTP check after WebSocket confirmation |
| `--timeout` | integer | `180` | Maximum seconds to wait for export completion |
| `--verbose` | flag | - | Enable detailed logging for WebSocket and download operations |

### Examples

#### Export Latest Timelapse
```bash
# Export the most recent timelapse to current directory
python export.py 192.168.178.100 --latest

# Export latest timelapse with verbose output
python export.py 192.168.178.100 --latest --verbose

# Export latest timelapse to specific directory
python export.py 192.168.178.100 --latest --out-dir ./timelapses/
```

#### Export Specific File
```bash
# Export a specific timelapse file
python export.py 192.168.178.100 my_print_2024-01-15.mp4

# Export with custom timeout
python export.py 192.168.178.100 my_print_2024-01-15.mp4 --timeout 300
```

#### Advanced Usage
```bash
# Export latest with custom list path and output directory
python export.py 192.168.178.100 --latest --list-path /local/aic_tlp/ --out-dir ./exports/ --verbose

# Export with HTTP verification and extended timeout
python export.py 192.168.178.100 --latest --check --timeout 300 --verbose

# Export specific file with custom settings
python export.py 192.168.178.100 special_print.mp4 --out-dir ./videos/ --check
```

## How It Works

1. **Discovery** (when using `--latest`): The script fetches the directory listing from your printer to find the most recent timelapse file
2. **Export Trigger**: Sends a WebSocket command to your printer to start the export process
3. **Status Monitoring**: Waits for WebSocket confirmation that the export is ready
4. **Download**: Downloads the completed MP4 file to your specified directory
5. **Verification**: Optionally performs HTTP checks to ensure the file is accessible

## Requirements

- Python 3.7+
- Network access to your Centauri Carbon printer
- WebSocket support (included in Python 3.7+)

## Troubleshooting

### Common Issues

**Connection Timeout**: Increase the `--timeout` value if your printer takes longer to process the export.

**File Not Found**: Ensure the file path is correct and matches what you see in the printer's web interface.

**Download Fails**: The script includes automatic retry logic, but if downloads consistently fail, check your network connection and printer status.

**WebSocket Errors**: Try using the `--check` flag to enable HTTP fallback verification.

### Debug Mode

Use the `--verbose` flag to see detailed information about:
- WebSocket communication
- File discovery process
- Download progress and retries
- Export status updates

## License

See [LICENSE](LICENSE) file for details.

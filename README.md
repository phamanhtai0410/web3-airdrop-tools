# Multi-Account Manager for Blockchain Airdrops

A comprehensive tool for managing multiple accounts across various platforms to participate in blockchain airdrops.

## Features

- **Account Management**: Create and manage multiple user accounts
- **Proxy Rotation**: Built-in proxy rotation system to avoid IP detection
- **Containerized Browser**: Run browser automation in isolated Docker containers
- **Multi-Platform Support**: Register and automate actions on Twitter, Telegram, Discord, and more
- **Airdrop Automation**: Participate in airdrops with configurable actions

## Project Structure

```
project_root/
├── account_manager.py           # Core account management functionality
├── proxy_manager.py             # Proxy rotation system
├── main.py                      # Main orchestrator for account management
├── Dockerfile                   # Container configuration for browser automation
├── docker-compose.yml           # Multi-container Docker setup
├── requirements.txt             # Python dependencies
├── data/                        # Persistent data storage
│   ├── accounts.json            # Account information storage
│   └── proxies.json             # Proxy list storage
├── logs/                        # Log files directory
│   └── ...                      # Log files generated during runtime
└── browser_automation/          # Browser automation implementation
    ├── __init__.py
    ├── google_automation.py     # Google account registration
    ├── twitter_automation.py    # Twitter registration and actions
    ├── telegram_automation.py   # Telegram registration and actions
    └── discord_automation.py    # Discord registration and actions
```

## Installation

### Prerequisites

- Docker and Docker Compose
- Python 3.8+

### Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/airdrop-tool.git
cd airdrop-tool
```

2. Build the Docker image:
```bash
docker build -t airdrop-bot .
```

3. Create the data directories:
```bash
mkdir -p data logs
```

4. Add your proxies to `data/proxies.json` (or use the built-in tool to add them later)

## Usage

### Basic Commands

```bash
# Create 5 new accounts
docker run -v $(pwd)/data:/app/data -v $(pwd)/logs:/app/logs airdrop-bot --create 5

# Register accounts on platforms
docker run -v $(pwd)/data:/app/data -v $(pwd)/logs:/app/logs airdrop-bot --register --platforms twitter,telegram

# Participate in an airdrop
docker run -v $(pwd)/data:/app/data -v $(pwd)/logs:/app/logs airdrop-bot --airdrop "ProjectX"
```

### Command Line Options

- `--headless`: Run browsers in headless mode (no visible UI)
- `--no-proxy`: Disable proxy usage
- `--create N`: Create N new accounts
- `--register`: Register accounts on platforms
- `--platforms PLATFORMS`: Comma-separated list of platforms to register on
- `--airdrop NAME`: Participate in the specified airdrop

### Using Docker Compose

For more complex setups, use Docker Compose:

```bash
docker-compose up -d
```

## Local Development

For development or running the application without Docker, follow these steps:

### 1. Set up a virtual environment

```bash
# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# On Windows
venv\Scripts\activate
# On macOS/Linux
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Set up Redis for local development

You'll need Redis for the task queue. You can:

- Install Redis locally: [Redis installation guide](https://redis.io/docs/getting-started/installation/)
- Use a Redis Docker container:
```bash
docker run --name redis -p 6379:6379 -d redis:alpine
```

### 4. Configure environment variables

Create a `.env` file in the project root:

```
REDIS_HOST=localhost
REDIS_PORT=6379
HEADLESS=false
LOG_LEVEL=INFO
DATA_DIR=./data
```

### 5. Run the application components

```bash
# Run the main orchestrator
python main.py

# Run a worker in a separate terminal
python worker.py

# Run the proxy checker in a separate terminal
python proxy_checker.py
```

### 6. Development Tips

- **Debug Mode**: Add `--debug` to any command to enable verbose logging
- **Testing Components**: You can test individual modules separately:
  ```bash
  python -m account_manager
  python -m proxy_manager
  ```
- **Mocking Browser Automation**: During development, you can use `--mock-browser` to simulate browser actions without actually launching browsers

### 7. Linting and Testing

```bash
# Run linting
pip install flake8
flake8 .

# Run tests
pip install pytest
pytest
```

## Proxy Configuration

Add proxies in one of these formats:

1. Simple format (IP:PORT):
```
203.24.108.171:80
45.77.177.53:8888
```

2. With authentication (IP:PORT:USERNAME:PASSWORD):
```
51.79.145.53:3128:user1:pass123
34.142.51.21:443:user2:pass456
```

## Implementing Browser Automation

The project includes stubs for browser automation. To implement them:

1. Add your Selenium/Playwright code to the appropriate files in the `browser_automation` directory
2. Update the main.py file to use your implemented automation classes
3. Test with a single account before scaling up

## Security Notes

- Store your account passwords securely
- Use dedicated email addresses for this purpose
- Rotate proxies frequently to avoid detection
- Consider using residential proxies for better success rates

## Disclaimer

This tool is for educational purposes only. Always adhere to the Terms of Service of any platform you interact with. The creators of this tool are not responsible for any misuse or violations of terms.

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
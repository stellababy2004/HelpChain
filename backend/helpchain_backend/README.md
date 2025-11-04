# HelpChain Project

HelpChain is a Flask-based web application designed to provide a seamless experience for users needing assistance. This project includes various components such as API routes, controllers, services, and utilities to facilitate the core functionalities.

## Project Structure

```
helpchain-backend
├── src
│   ├── app.py                  # Main entry point for the application
│   ├── config.py               # Configuration settings for the application
│   ├── routes
│   │   └── api.py              # API routes definition
│   ├── controllers
│   │   └── helpchain_controller.py # Logic for handling help chain requests
│   ├── services
│   │   └── ngrok_service.py     # Logic for ngrok tunnel management
│   ├── utils
│   │   └── qr_generator.py      # QR code generation utilities
│   └── __init__.py             # Package initialization
├── scripts
│   └── start_helpchain.py       # Script to start the Flask app and ngrok tunnel
├── tests
│   └── test_app.py              # Tests for the application functionality
├── requirements.txt              # List of project dependencies
├── .env                          # Environment variables and sensitive settings
├── .gitignore                    # Files and directories to ignore in version control
└── README.md                     # Project documentation
```

## Installation

1. Clone the repository:

   ```
   git clone <repository-url>
   cd helpchain-backend
   ```

2. Create a virtual environment:

   ```
   python -m venv venv
   ```

3. Activate the virtual environment:

   - On Windows:
     ```
     venv\Scripts\activate
     ```
   - On macOS/Linux:
     ```
     source venv/bin/activate
     ```

4. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage

To start the application, run the following command:

```
python scripts/start_helpchain.py
```

This will launch the Flask server and ngrok tunnel, providing you with a public URL to access the application.

## Testing

To run the tests, execute:

```
pytest tests/test_app.py
```

## Contributing

Contributions are welcome! Please open an issue or submit a pull request for any enhancements or bug fixes.

## License

This project is licensed under the MIT License. See the LICENSE file for more details.

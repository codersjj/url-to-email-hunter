# URL to Email Hunter

A powerful full-stack application designed to crawl websites and extract email addresses efficiently. Built with Next.js for the frontend and FastAPI with Playwright for the backend.

## Features

- **URL Crawling**: Automatically crawls provided URLs to find contact pages.
- **Email Extraction**: Uses intelligent patterns to extract email addresses from web pages.
- **Real-time Logs**: View extraction progress and logs in real-time on the dashboard.
- **Data Export**: Export extracted emails and failed URLs to Excel files.
- **Proxy Support**: Integrated proxy management for reliable crawling.
- **Parallel Processing**: Supports parallel extraction for faster results.

## Tech Stack

- **Frontend**: [Next.js](https://nextjs.org/), React, Tailwind CSS, Lucide React
- **Backend**: [FastAPI](https://fastapi.tiangolo.com/), Python
- **Scraping**: [Playwright](https://playwright.dev/python/)
- **Utilities**: Pandas, OpenPyXL

## Prerequisites

Before you begin, ensure you have the following installed:

- [Node.js](https://nodejs.org/) (v18 or higher)
- [Python](https://www.python.org/) (v3.8 or higher)

## Getting Started

### 1. Clone the Repository

```bash
git clone <repository-url>
cd url-to-email-hunter
```

### 2. Frontend Setup

Install the frontend dependencies:

```bash
npm install
# or
yarn install
# or
pnpm install
```

Start the frontend development server:

```bash
npm run dev
```

The frontend will be available at [http://localhost:3000](http://localhost:3000).

### 3. Backend Setup

The project includes a convenient script to set up and run the backend automatically.

Run the following command from the project root:

```bash
npm run backend
```

This command will:
1.  Install the required Python dependencies from `backend/requirements.txt`.
2.  Start the FastAPI backend server.

Alternatively, you can set it up manually:

```bash
# Install dependencies
pip install -r backend/requirements.txt

# Run the backend
python backend/main.py
```

The backend API will be available at `http://localhost:8000` (or the port configured in `main.py`).

## Usage

1.  Open the application in your browser at [http://localhost:3000](http://localhost:3000).
2.  Enter the URLs you want to scan in the input area (one per line).
3.  Click the "Start Extraction" button.
4.  Monitor the progress in the "Real-time Logs" section.
5.  Once completed, you can export the results using the "Export" buttons.

## Project Structure

- `app/`: Next.js frontend application code.
- `backend/`: Python FastAPI backend code.
    - `main.py`: Entry point for the backend API.
    - `email_extractor.py`: Core logic for email extraction.
    - `requirements.txt`: Python dependencies.
- `public/`: Static assets.

## License

[MIT](LICENSE)

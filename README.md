# Multi-Identity Dating & Bulletin Board Telegram Bot

A high-performance, asynchronous Telegram Bot and companion WebApp built with **FastAPI**, **Aiogram 3**, and **MongoDB**. Designed using Clean Architecture (Domain-Driven Design principles), the application serves as an interactive bulletin board where users can find others based on shared interests (hobbies, networking, or dating) using multi-profile identities, advanced tagging, and customizable matching rules.

---

## Key Features

- **Multi-Identity Profiles**: Users can maintain up to 100 distinct profiles (listings), allowing them to project different identities for different interests (e.g., networking vs. gaming). Only one profile can be marked as "Active" in search pools at any time.
- **Advanced Matchmaking Loop**: 
  * Semi-random profile selection combined with dynamic tag filtering (`require_tags`, `exclude_tags`, `any_tags`).
  * Automatic profile exclusion: ensures users do not see their own profiles or profiles they have already viewed.
  * Smart Reset: automatically resets seen profile logs when the matching candidate pool is fully exhausted.
- **Dynamic Contact Exchange Mechanics**:
  * **One-Way Share**: Instantly sends your active profile with optional public/private contacts directly to the target user.
  * **Mutual Exchange Handshake**: Holds private contact details until the recipient agrees to accept the exchange. When accepted, both users simultaneously unlock and receive each other's chosen private details.
- **Integrated Telegram WebApp (HTML5 Hub)**:
  * Sleek UI facilitating tag management, advanced search filter definitions, and a centralized "Pending Requests" inbox.
  * Secure WebApp initialization data parsing, utilizing SHA256 HMAC verification to prevent unauthorized state manipulation.
  * "Send to Chat" button inside the WebApp allowing users to render other profiles' cards directly inside their personal bot DM.
- **Robust Media & Album Buffering**: Handlers capture media groups (albums up to 10 files) and use an asynchronous timeout buffer to compile multiple photos/videos into a single unified profile media array.
- **Rate-Limiting & High-Throughput Logging**:
  * Anti-spam throttling middleware utilizing custom data and keyboard interaction speed limits.
  * Non-blocking, thread-safe asynchronous queue-based batch database logger. Writes log batches to MongoDB every 2 seconds to eliminate database write bottlenecks during peak activity.

---

## Directory Layout (Clean Architecture)

The repository strictly isolates business rules from external frameworks:

```text
├── application/               # Application Layer (Orchestration & Use Cases)
│   └── services.py            # Interfaces with domain repositories to execute workflows
├── bot/                       # Telegram Bot Presentation Layer (Aiogram 3)
│   ├── handlers/              # Command, message, and callback handlers
│   │   ├── base.py            # Fallbacks, start command, main menu UI, cancel states
│   │   ├── browse.py          # Matchmaking loops, alert modals, request triggers
│   │   ├── contacts.py        # Custom offline contact validator and privacy toggles
│   │   └── profile.py         # Multi-profile lifecycle controls and album buffering
│   ├── bot_setup.py           # Bot instantiation and asynchronous commands setup
│   ├── helpers.py             # Rich media message-rendering helpers (InputMedia groups)
│   ├── keyboards.py           # Telegram Reply, Inline, and WebApp keyboard templates
│   ├── middlewares.py         # Anti-spam throttling and language mapping middleware
│   └── states.py              # Aiogram Finite State Machine (FSM) structures
├── domain/                    # Enterprise Domain Layer
│   └── interfaces.py          # Abstract Base Classes (ABCs) enforcing repository patterns
├── infrastructure/            # Data Access & External Framework Adapters
│   ├── bot/
│   │   └── storage.py         # Custom Aiogram FSM State Storage powered by MongoDB
│   ├── config.py              # Centralized environment variable management
│   ├── database/
│   │   └── mongo_repository.py# Concrete Motor (Async MongoDB) repository implementations
│   ├── locales.py             # Trilingual localization maps (EN, RU, PT)
│   └── security.py            # Telegram WebApp signature/hash verifier
├── webapp/                    # WebApp Backend Presentation Layer (FastAPI)
│   ├── api.py                 # REST Endpoints for tag management, requests inbox, and actions
│   └── static/
│       └── index.html         # Rich-client Single Page WebApp (Vanilla JS + WebApp SDK)
├── main.py                    # Main Entrypoint (FastAPI + Webhook Lifecycle Management)
└── .env                       # Environment configuration secrets (git-ignored)
```

---

## Tech Stack

- **Frameworks**: [FastAPI](https://fastapi.tiangolo.com/) (Web Server & API API), [Aiogram 3.x](https://docs.aiogram.dev/) (Asynchronous Bot Framework)
- **Database**: [MongoDB](https://www.mongodb.com/) via [Motor](https://motor.readthedocs.io/) (Asynchronous Driver)
- **Validation**: [Pydantic v2](https://docs.pydantic.dev/) (API Payload schemas)
- **Frontend**: Single Page Application using vanilla JS and official Telegram WebApp SDK
- **Utilities**: `phonenumbers` (international contact parsing)

---

## Local Setup & Installation

### 1. Prerequisites
- Python 3.10 or higher installed.
- Access to a running MongoDB instance (locally or on Mongo Atlas).
- A valid Telegram Bot Token from [@BotFather](https://t.me/BotFather).
- An SSL-capable tunnel for local webhook testing (e.g., [ngrok](https://ngrok.com/)).

### 2. Clone and Setup Environment
Clone the repository and install the required dependencies:
```bash
git clone https://github.com/yourusername/day_dating_bot.git
cd day_dating_bot

python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

*(Note: Create a `requirements.txt` file containing dependencies like `fastapi`, `uvicorn`, `aiogram`, `motor`, `pydantic`, `phonenumbers`, `python-dotenv` if not already present.)*

### 3. Configure Variables
Create a `.env` file in the root directory:
```env
TOKEN="YOUR_TELEGRAM_BOT_TOKEN"
MONGODB_URI="mongodb+srv://user:pass@cluster.mongodb.net/database?retryWrites=true&w=majority"
WEBHOOK_URL="https://your-ngrok-subdomain.ngrok-free.app"
WEBHOOK_SECRET="dating_bot_secure_path_abc123"
```

### 4. Running the Application
Launch the unified FastAPI server. On startup, the `lifespan` handler automatically initializes MongoDB collections, indexes, handles outstanding migrations, launches the background queue logging task, and registers the webhook URL with Telegram.

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

---

## Environment Variables Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `TOKEN` | Telegram Bot Token issued by `@BotFather`. | *Required* |
| `MONGODB_URI` | Standard MongoDB connection string. | `mongodb://localhost:27017` |
| `WEBHOOK_URL` | Base public HTTPS URL pointing to your application. | *Required* |
| `WEBHOOK_SECRET` | Secret path suffix protecting the webhook endpoint from discovery. | `dating_bot_secure_path_abc123` |
| `DATA_SPEED_LIMIT` | Throttling timeout (seconds) applied to standard text messages. | `0.8` |
| `KEYBOARD_SPEED_LIMIT`| Throttling timeout (seconds) applied to inline keyboard presses. | `0.1` |

---

## Matchmaking Algorithm Details

When a user initiates search via the **Browse** loop:
1. The application parses the active profile's dynamic search parameters (the intersection of required tags, non-excluded tags, and union matching tags).
2. It generates a random float index (`random_index`) and attempts to locate one matching profile with a `random_index >= current_random_float`.
3. If no profile matches the forward direction, the search direction is reversed (`random_index < current_random_float`).
4. If still empty, it sweeps the database, ignoring the user's "seen" profile cache. If a match is found under this condition, the user's seen profile cache is purged, allowing a soft recycling of candidate pools.

---

## Deployment Guidelines (Production)

For standard production setups, run the application behind a reverse proxy (like **Nginx**) configured to serve HTTPS traffic.

### Example Nginx Config:
```nginx
server {
    listen 443 ssl http2;
    server_name bot.example.com;

    ssl_certificate /etc/letsencrypt/live/bot.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/bot.example.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded-for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Ensure Python dependencies are kept up-to-date and run the server using process managers like **systemd** or **PM2**.
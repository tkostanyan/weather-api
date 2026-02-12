# Weather API Service

A robust FastAPI weather service that fetches data from OpenWeatherMap with configurable backends for caching, storage, and event logging.

## Architecture

The service uses an **Abstract Factory pattern** with dependency injection to support multiple environments:

| Component | Test | Local (Development) | Production (AWS) |
|-----------|------|---------------------|------------------|
| **Cache** | In-Memory | Redis | ElastiCache |
| **Storage** | Local Files | Local Files | S3 |
| **Database** | In-Memory | MongoDB | DynamoDB |

Set `ENVIRONMENT=test`, `ENVIRONMENT=local`, or `ENVIRONMENT=prod` to switch between implementations.

## Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose (optional, but recommended)
- OpenWeatherMap API key (free tier available at [openweathermap.org](https://openweathermap.org/api))

### Development Workflow

**Option 1: Docker (Recommended)**

```bash
# 1. Set your API key
cp .env.example .env # Edit .env and add your WEATHER_API_KEY

# 2. Run tests
docker-compose run --rm weather-api-test

# 3. Start the application
docker-compose up -d

# 4. Access the API
curl "http://localhost:8001/weather?city=London"

# 5. View API docs
open http://localhost:8001/docs
```

**Option 2: Local Python Environment**

1. **Clone and setup:**
   ```bash
   cd weather-api
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env and add your WEATHER_API_KEY
   ```

3. **Run tests:**
   ```bash
   pytest -v
   ```

4. **Run the application:**
   ```bash
   uvicorn app.main:app --reload
   ```

5. **Access the API:**
   - API: http://localhost:8000
   - Swagger Docs: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc

### Docker

The project includes three Docker Compose services:

1. **weather-api** - Main application with hot reload (port 8001)
2. **redis** - Redis cache for local development
3. **mongodb** - MongoDB database for event logging
4. **weather-api-test** - Isolated test runner (test environment)

**Start all services:**

```bash
# Set your API key
export WEATHER_API_KEY=your_api_key_here

# Start Redis, MongoDB, and the API
docker-compose up -d
```

**Run tests in Docker:**

```bash
# Run the isolated test service
docker-compose run --rm weather-api-test

# No Redis or MongoDB needed - uses in-memory implementations!
```

**View logs:**

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f weather-api
```

**Stop all services:**

```bash
docker-compose down

# Remove volumes too
docker-compose down -v
```

## API Endpoints

### Weather

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/weather?city={city}` | Get current weather for a city |
| GET | `/weather/forecast?city={city}&days={1-5}` | Get weather forecast |
| GET | `/weather/multi?cities={city1,city2,...}` | Get weather for multiple cities |

### Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | API information |
| GET | `/health` | Health check |
| GET | `/stats` | Usage statistics |

## Examples

### Get Current Weather

```bash
curl "http://localhost:8000/weather?city=London"
```

**Response:**
```json
{
  "city": "London",
  "country": "GB",
  "temperature": 15.2,
  "feels_like": 14.8,
  "humidity": 72,
  "weather_condition": "Clouds",
  "weather_description": "scattered clouds",
  "cached": false
}
```

### Get Weather Forecast

```bash
curl "http://localhost:8000/weather/forecast?city=Paris&days=3"
```

### Get Multiple Cities

```bash
curl "http://localhost:8000/weather/multi?cities=London,Paris,Berlin"
```

## Project Structure

```
weather-api/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── config.py            # Configuration management
│   ├── dependencies.py      # FastAPI dependency injection
│   ├── rate_limiter.py      # Rate limiting configuration
│   ├── exceptions/
│   │   ├── service_exceptions.py        # Internal service errors
│   │   └── weather_service_exceptions.py # Weather API errors
│   ├── models/
│   │   ├── weather.py       # Weather data models
│   │   └── events.py        # Event type constants
│   ├── routers/
│   │   └── weather.py       # Weather API routes
│   └── services/
│       ├── base.py          # Abstract base classes (ABC)
│       ├── factory.py       # Service factory (environment-based)
│       ├── weather_client.py   # Async OpenWeatherMap client
│       ├── weather_service.py  # Business logic layer
│       ├── cache/
│       │   ├── __init__.py
│       │   ├── memory_cache.py    # In-memory (test)
│       │   ├── redis_cache.py     # Redis (local)
│       │   └── elasticache_client.py # ElastiCache (prod)
│       ├── storage/
│       │   ├── __init__.py
│       │   ├── local_storage.py   # Local files (local)
│       │   └── s3_storage.py      # S3 (prod)
│       └── database/
│           ├── __init__.py
│           ├── memory_logger.py   # In-memory (test)
│           ├── mongodb_logger.py  # MongoDB (local)
│           └── dynamodb_logger.py # DynamoDB (prod)
├── tests/
│   ├── __init__.py
│   ├── conftest.py          # Test fixtures
│   ├── test_services.py     # Unit tests
│   └── test_weather_api.py  # Integration tests
├── data/                    # Local storage directory
│   └── weather/             # Weather JSON files
├── .env.example             # Environment template
├── Dockerfile
├── docker-compose.yml       # Includes MongoDB & Redis
├── requirements.txt
└── README.md
```

## Configuration

Configuration is managed via environment variables:

### Core Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `ENVIRONMENT` | `local` | Environment: `local`, `prod`, or `test` |
| `WEATHER_API_KEY` | required | OpenWeatherMap API key |
| `WEATHER_API_BASE_URL` | `https://api.openweathermap.org/data/2.5` | API base URL |
| `CACHE_TTL_SECONDS` | `300` | Cache TTL (5 minutes) |
| `RATE_LIMIT_PER_MINUTE` | `100` | Rate limit per client IP |
| `DEBUG` | `false` | Enable debug mode |
| `LOG_LEVEL` | `INFO` | Logging level |

### Local Development

| Variable | Default | Description |
|----------|---------|-------------|
| `DATA_DIR` | `./data` | Local file storage directory |
| `REDIS_HOST` | `localhost` | Redis host |
| `REDIS_PORT` | `6379` | Redis port |
| `MONGODB_CONNECTION_STRING` | `mongodb://localhost:27017` | MongoDB connection |
| `MONGODB_DATABASE_NAME` | `weather_api` | MongoDB database name |

### Production (AWS)

| Variable | Default | Description |
|----------|---------|-------------|
| `AWS_REGION` | `us-east-1` | AWS region |
| `AWS_ACCESS_KEY_ID` | - | AWS access key |
| `AWS_SECRET_ACCESS_KEY` | - | AWS secret key |
| `S3_BUCKET_NAME` | - | S3 bucket for storage |
| `DYNAMODB_TABLE_NAME` | `weather-events` | DynamoDB table |
| `ELASTICACHE_HOST` | - | ElastiCache endpoint |
| `ELASTICACHE_PORT` | `6379` | ElastiCache port |

## Running Tests

### Local Testing (with venv)

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_services.py -v

# Run specific test class
pytest tests/test_weather_api.py::TestWeatherEndpoint -v
```

### Docker Compose Testing

The project includes a dedicated test service in `docker-compose.yml`:

**Test Service Configuration:**
- **Environment:** `ENVIRONMENT=test` (uses in-memory implementations)
- **Isolation:** Runs independently without Redis/MongoDB dependencies
- **Speed:** Fast execution with no external service overhead
- **Entry Point:** Runs pytest with verbose output

**Run tests with Docker Compose:**

```bash
# Run the test service
docker-compose run --rm weather-api-test

# Run specific test file
docker-compose run --rm weather-api-test pytest tests/test_services.py -v

# Run with coverage
docker-compose run --rm weather-api-test pytest --cov=app --cov-report=term-missing

# Run specific test class
docker-compose run --rm weather-api-test pytest tests/test_weather_api.py::TestWeatherEndpoint -v
```

**Benefits of Docker testing:**
- ✅ Consistent environment across all machines
- ✅ No local Python setup required
- ✅ Clean state on every run
- ✅ CI/CD ready configuration

## Architecture Notes

### Abstract Factory Pattern

All services inherit from abstract base classes in `app/services/base.py`:

```python
# Base classes define the interface
class BaseStorage(ABC):
    async def save(self, data, key) -> str: ...
    async def load(self, key) -> dict: ...

class BaseCache(ABC):
    async def get(self, key) -> T: ...
    async def set(self, key, value) -> None: ...

class BaseEventLogger(ABC):
    async def log(self, event_type, ...) -> str: ...
```

### Dependency Injection

Routes use FastAPI's dependency injection for clean code:

```python
from app.dependencies import WeatherServiceDep

@router.get("/weather")
async def get_weather(
    city: str,
    weather_service: WeatherServiceDep,  # Injected with all dependencies
):
    summary, response_time = await weather_service.get_weather(city, client_ip)
    return summary
```

The `WeatherService` internally uses the appropriate cache, storage, and event logger based on the `ENVIRONMENT` setting.

### Switching Environments

```bash
# Test environment (In-Memory for all services)
ENVIRONMENT=test pytest tests/

# Local development (MongoDB, Local Files, Redis)
ENVIRONMENT=local uvicorn app.main:app --reload

# Production (DynamoDB, S3, ElastiCache)
ENVIRONMENT=prod uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Error Handling

The API returns consistent error responses:

```json
{
  "error": "CityNotFound",
  "message": "City 'InvalidCity' not found",
  "detail": "Please check the city name and try again"
}
```

| Status Code | Error Type | Description |
|-------------|------------|-------------|
| 404 | CityNotFound | City not found |
| 429 | RateLimitExceeded | Too many requests |
| 500 | ConfigurationError | API key issues |
| 502 | ExternalAPIError | Weather API failure |

## License

MIT License


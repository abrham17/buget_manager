# 🤖 Merchant Financial Agent (MFA)

**A Context-Aware AI Proposal Leveraging Model Context Protocol and Function Calling for SMB Financial Automation**

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![Django](https://img.shields.io/badge/Django-5.0+-green.svg)](https://djangoproject.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-Passing-brightgreen.svg)](tests/)

## 🚀 Overview

The Merchant Financial Agent (MFA) is an autonomous, context-aware AI solution designed specifically for Small and Medium Business (SMB) financial automation. Built on the Model Context Protocol (MCP) and advanced Function Calling capabilities, it provides intelligent financial management through natural language interaction.

### ✨ Key Features

- **🧠 Conversational AI Interface**: Natural language processing for financial queries and commands
- **📊 Advanced Financial Analytics**: Comprehensive reporting with trend analysis and forecasting
- **💰 Multi-Currency Support**: Real-time exchange rates and currency conversion
- **📅 Google Calendar Integration**: OAuth 2.0 integration for event management
- **🔒 Enterprise Security**: Audit trails, data encryption, and secure API handling
- **⚡ High Performance**: Optimized for speed with caching and async processing
- **🧪 Comprehensive Testing**: 80%+ code coverage with automated testing

## 🏗️ Architecture

### Core Components

1. **Model Context Protocol (MCP)**: Standardized execution and orchestration layer
2. **Function Calling (FC)**: High-fidelity intent generation and structured JSON commands
3. **LLM Integration**: Multi-provider support (OpenAI, Anthropic) with conversation management
4. **MCP Servers**: Specialized servers for financial data, calendar, and currency services
5. **Advanced Reporting Engine**: Query-based aggregation with comprehensive analytics
6. **Security Framework**: Rate limiting, request validation, and audit logging

### Technology Stack

- **Backend**: Django 5.0+ with async support
- **Database**: PostgreSQL (production) / SQLite (development)
- **AI/ML**: OpenAI GPT-4, Anthropic Claude, LangChain
- **APIs**: Google Calendar API, Exchange Rate API
- **Security**: OAuth 2.0, JWT, CORS, Rate Limiting
- **Testing**: pytest, pytest-django, coverage
- **Frontend**: Modern HTML5, CSS3, JavaScript (ES6+)

## 📦 Installation

### Prerequisites

- Python 3.11 or higher
- PostgreSQL 13+ (for production)
- Node.js 18+ (for frontend assets)
- Git

### Quick Start

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/merchant-financial-agent.git
   cd merchant-financial-agent
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Run migrations**
   ```bash
   python manage.py migrate
   ```

6. **Create superuser**
   ```bash
   python manage.py createsuperuser
   ```

7. **Start development server**
   ```bash
   python manage.py runserver
   ```

8. **Access the application**
   - Web Interface: http://localhost:8000
   - Admin Panel: http://localhost:8000/admin
   - API Documentation: http://localhost:8000/api/

## 🔧 Configuration

### Environment Variables

Create a `.env` file in the project root with the following variables:

```env
# Django Settings
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/mfa_db

# AI Provider Keys
OPENAI_API_KEY=your-openai-api-key
ANTHROPIC_API_KEY=your-anthropic-api-key

# Google Calendar Integration
GOOGLE_CLIENT_SECRETS_FILE=path/to/client_secrets.json

# Exchange Rate API
EXCHANGE_RATE_API_KEY=your-exchange-rate-api-key

# Security
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
CSRF_TRUSTED_ORIGINS=https://localhost,https://127.0.0.1
```

### Google Calendar Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable Google Calendar API
4. Create OAuth 2.0 credentials
5. Download the client secrets JSON file
6. Set `GOOGLE_CLIENT_SECRETS_FILE` in your `.env`

## 🚀 Usage

### Web Interface

1. **Register/Login**: Create your merchant account
2. **Dashboard**: Overview of financial health and key metrics
3. **Transactions**: Manage income and expense transactions
4. **Events**: Schedule and manage business events
5. **Reports**: Generate comprehensive financial reports
6. **AI Agent**: Chat with your financial assistant
7. **Currency**: Convert currencies with real-time rates

### AI Agent Commands

The AI agent understands natural language commands:

```
"Show me my financial summary for this month"
"Convert 1000 USD to EUR"
"Schedule a meeting with my accountant next Tuesday"
"What were my top expenses last quarter?"
"Create a forecast for next month's revenue"
"Generate a comprehensive financial report"
```

### API Usage

#### Chat API
```bash
curl -X POST http://localhost:8000/api/chat/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-token" \
  -d '{"message": "Show me my financial summary"}'
```

#### Function Call API
```bash
curl -X POST http://localhost:8000/api/function-call/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-token" \
  -d '{
    "function_name": "financial_db_adapter.generate_summary",
    "function_args": {
      "merchant_id": 1,
      "timeframe": "month"
    }
  }'
```

#### Reports API
```bash
curl -X POST http://localhost:8000/api/reports/generate/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-token" \
  -d '{
    "start_date": "2024-01-01",
    "end_date": "2024-01-31",
    "include_forecasts": true,
    "include_trends": true
  }'
```

## 🧪 Testing

### Run All Tests
```bash
python run_tests.py
```

### Run Specific Test Suites
```bash
# Performance tests
python run_tests.py performance

# Security tests
python run_tests.py security

# Coverage report
python run_tests.py coverage

# Specific test module
python run_tests.py specific tests.test_function_calling
```

### Using pytest directly
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test file
pytest tests/test_integration.py

# Run with verbose output
pytest -v
```

## 📊 API Documentation

### Core Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/chat/` | POST | Chat with AI agent |
| `/api/function-call/` | POST | Direct function calls |
| `/api/reports/generate/` | POST | Generate comprehensive reports |
| `/api/reports/quick/` | POST | Quick report generation |
| `/api/reports/query/` | POST | Custom financial queries |
| `/api/health/` | GET | Health check |

### MCP Server Functions

#### Financial DB Adapter
- `financial_db_adapter.generate_summary`
- `financial_db_adapter.get_income`
- `financial_db_adapter.get_expenses`
- `financial_db_adapter.get_net_income`
- `financial_db_adapter.add_transaction`
- `financial_db_adapter.update_transaction_status`

#### Google Calendar Server
- `google_calendar_server.calendar_create_event`
- `google_calendar_server.calendar_find_events`
- `google_calendar_server.calendar_update_event`
- `google_calendar_server.calendar_delete_event`
- `google_calendar_server.calendar_check_availability`

#### Currency Service
- `currency_service.get_live_fx_rate`
- `currency_service.convert_currency`

## 🔒 Security Features

- **Authentication**: Django's built-in authentication system
- **Authorization**: Role-based access control
- **Rate Limiting**: Configurable rate limits for API endpoints
- **Input Validation**: Comprehensive input sanitization
- **Audit Logging**: Complete audit trail for all financial actions
- **CORS Protection**: Configurable CORS settings
- **XSS Protection**: Built-in XSS protection
- **CSRF Protection**: CSRF tokens for all forms

## 📈 Performance

- **Async Support**: Django async views for high concurrency
- **Database Optimization**: Efficient queries with proper indexing
- **Caching**: Redis-based caching for frequently accessed data
- **Connection Pooling**: Database connection pooling
- **Rate Limiting**: Prevents abuse and ensures fair usage

## 🚀 Deployment

### Production Deployment

1. **Set production environment variables**
2. **Configure PostgreSQL database**
3. **Set up Redis for caching**
4. **Configure reverse proxy (Nginx)**
5. **Set up SSL certificates**
6. **Configure monitoring and logging**

### Docker Deployment

```bash
# Build Docker image
docker build -t mfa-app .

# Run with docker-compose
docker-compose up -d
```

### Environment-Specific Settings

The application supports different configurations for development, staging, and production environments through environment variables and Django settings.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines

- Follow PEP 8 style guidelines
- Write comprehensive tests for new features
- Update documentation for API changes
- Ensure all tests pass before submitting PR
- Use meaningful commit messages

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- OpenAI for GPT-4 API
- Anthropic for Claude API
- Google for Calendar API
- Django community for the excellent framework
- All contributors and users

## 📞 Support

- **Documentation**: [Wiki](https://github.com/yourusername/merchant-financial-agent/wiki)
- **Issues**: [GitHub Issues](https://github.com/yourusername/merchant-financial-agent/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/merchant-financial-agent/discussions)
- **Email**: support@merchant-financial-agent.com

## 🗺️ Roadmap

- [ ] Mobile app (React Native)
- [ ] Advanced machine learning models
- [ ] Integration with more accounting software
- [ ] Real-time notifications
- [ ] Advanced security features
- [ ] Multi-language support
- [ ] API versioning
- [ ] GraphQL support

---

**Built with ❤️ for Small and Medium Businesses**

*Empowering SMBs with intelligent financial automation through cutting-edge AI technology.*# buget_manager

# Merchant Financial Agent

## Overview

The Merchant Financial Agent (MFA) is a fully-implemented Django-based web application designed to help small-to-medium business (SMB) merchants manage their financial operations. The platform provides comprehensive financial tracking, event management, reporting capabilities, and real-time currency conversion tools. Built with Django 5.0 and styled with Tailwind CSS, the application offers an intuitive, modern interface for managing transactions, tracking important business deadlines, and generating financial insights.

**Status**: Fully functional and ready for use. All core features implemented as of October 2025.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Framework & Technology Stack

**Problem**: Need for a robust, secure web framework suitable for financial data management.

**Solution**: Django 5.0 with Python as the core framework.

**Rationale**: Django provides built-in security features (CSRF protection, user authentication), ORM for database abstraction, and admin interface for data management. Its "batteries-included" philosophy reduces development overhead for financial applications requiring audit trails and secure transaction handling.

**Pros**:
- Built-in authentication and authorization
- Excellent security defaults for handling sensitive financial data
- Powerful ORM for database operations
- Admin interface for easy data management

**Cons**:
- Monolithic architecture may limit scalability for very large deployments
- Server-side rendering approach may require additional work for highly interactive features

### Frontend Architecture

**Problem**: Need for responsive, modern UI without complex build processes.

**Solution**: Server-side template rendering with Tailwind CSS via CDN.

**Rationale**: Uses Django's template engine with Tailwind CSS for styling. Templates extend from a base layout (`base.html`) providing consistent navigation and messaging across pages.

**Pros**:
- No build step required for styling
- Consistent design system through Tailwind
- Simple deployment without JavaScript bundling

**Cons**:
- Limited interactivity compared to SPA frameworks
- CDN dependency for Tailwind CSS

### Data Model Architecture

**Problem**: Need for reliable financial record-keeping with categorization and audit capabilities.

**Solution**: Immutable ledger pattern for transactions with supporting models for categories, events, forecasts, and currency rates.

**Core Models**:

1. **Transaction**: Immutable financial ledger entries with fields for amount, type (income/expense), category, payment method, and timestamps
2. **Category**: Classification system for transactions (income vs. expense types)
3. **Event**: Business deadline and event tracking (tax payments, invoices, meetings, reminders)
4. **Forecast**: Financial forecasting capabilities for revenue/expense projections
5. **CurrencyRate**: Foreign exchange rate storage for multi-currency support

**Rationale**: The immutable transaction model ensures financial data integrity and provides complete audit trails. Django's built-in User model handles merchant authentication.

**Pros**:
- Clear separation of concerns across models
- Immutable transactions prevent data tampering
- Foreign key relationships maintain data integrity

**Cons**:
- No soft-delete mechanism currently implemented
- Limited multi-currency transaction support in core Transaction model

### Authentication & Authorization

**Problem**: Secure user access and data isolation between merchants.

**Solution**: Django's built-in authentication system with user-based data isolation.

**Rationale**: Leverages Django's `User` model with session-based authentication. All financial data models use foreign keys to User to ensure data isolation between merchants.

**Pros**:
- Battle-tested authentication system
- Built-in password hashing and session management
- Easy integration with Django admin

**Cons**:
- No role-based access control (RBAC) for team accounts
- Limited to session-based authentication (no API tokens)

### Reporting & Analytics

**Problem**: Need for financial insights and performance analysis.

**Solution**: Django ORM aggregations for generating reports (income, expenses, profit/loss).

**Rationale**: Uses database-level aggregations (`Sum`, `Count`) with date filtering to generate financial reports without external analytics tools.

**Pros**:
- Fast query performance with database aggregations
- No external dependencies
- Flexible date range filtering

**Cons**:
- Limited to predefined report types
- No data visualization (charts/graphs) currently implemented

## External Dependencies

### Third-Party Services

**Currency Exchange API**: The application integrates with ExchangeRate-API.com for real-time foreign exchange rates. The implementation includes intelligent caching (1-hour cache) to minimize API calls and improve performance. No API key required for basic functionality.

### Database

**Default**: Django's default database configuration (likely SQLite for development based on standard Django project structure).

**Consideration**: While SQLite is suitable for development and small deployments, production environments handling significant transaction volumes should migrate to PostgreSQL or MySQL for better concurrency and data integrity guarantees.

### Static Assets

**Tailwind CSS**: Loaded via CDN (`https://cdn.tailwindcss.com`)
**Google Fonts**: Inter font family loaded from Google Fonts CDN

### Deployment Platform

**Replit Configuration**: The application is configured for Replit deployment with:
- `ALLOWED_HOSTS = ["*"]` for flexible hosting
- `CSRF_TRUSTED_ORIGINS` configured for `*.replit.dev` and `*.replit.app` domains

### Python Dependencies

Based on the Django 5.0 framework, core dependencies include:
- Django 5.0.x
- Python 3.8+ (required for Django 5.0)
- Requests library (for external API calls to currency services)
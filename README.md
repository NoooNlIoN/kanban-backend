# Trello Clone Backend

A FastAPI backend for a Trello-like application with JWT authentication.

## Features

- User authentication (register, login, token refresh)
- Boards management
- Columns management
- Cards management
- JWT-based authentication
- **Superuser functionality** - users with `is_superuser = true` have full access to all boards and cards
- **Complete statistics** - detailed statistics for boards, cards, and user activity

## Project Structure

```
src/
├── backend/
    ├── alembic/             # Database migrations
    ├── api/                 # API endpoints
    │   ├── endpoints/       # API route handlers
    ├── core/                # Core functionality
    ├── db/                  # Database models and configuration  
    ├── models/              # SQLAlchemy models
    ├── schemas/             # Pydantic models
    ├── services/            # Business logic
    ├── main.py              # Application entry point
```

## Installation

1. Make sure you have [Rye](https://rye-up.com/) installed
2. Clone the repository
3. Install dependencies:

```bash
rye sync
```

## Running the Application

```bash
rye run uvicorn backend.main:app --reload
```

The API will be available at http://localhost:8000.

API documentation is available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Database Migrations

Initialize the database:

```bash
rye run alembic upgrade head
```

Create a new migration after model changes:

```bash
rye run alembic revision --autogenerate -m "Description of changes"
```

## API Endpoints

### Authentication

- `POST /api/auth/register` - Register a new user
- `POST /api/auth/login` - Login and get tokens
- `POST /api/auth/refresh` - Refresh access token

### Boards

- `POST /api/boards` - Create a new board
- `GET /api/boards` - Get all user's boards
- `GET /api/boards/{board_id}` - Get a specific board
- `PUT /api/boards/{board_id}` - Update a board
- `DELETE /api/boards/{board_id}` - Delete a board
- `GET /api/boards/{board_id}/complete` - Get complete board with all columns and cards
- **`GET /api/boards/stats/full`** - **Get complete statistics for all user boards**

### Columns

- `POST /api/boards/{board_id}/columns` - Create a new column
- `GET /api/boards/{board_id}/columns` - Get all columns in a board

### Cards

- `POST /api/cards` - Create a new card
- `GET /api/cards` - Get all cards (with optional column filtering)
- `GET /api/cards/{card_id}` - Get a specific card
- `PUT /api/cards/{card_id}` - Update a card
- `DELETE /api/cards/{card_id}` - Delete a card

## Statistics API

### Full Board Statistics

The `/api/boards/stats/full` endpoint provides comprehensive statistics for all boards accessible to the current user:

**Response includes:**
- **Board-level statistics** for each board:
  - Total cards, completed cards, archived cards
  - Total columns, total comments
  - Cards with deadlines, overdue cards
- **Global statistics** across all user boards
- **Complete board data** with all columns and cards

**Superuser access:** Superusers see statistics for ALL boards in the system.

**Example response:**
```json
{
  "boards": [
    {
      "id": 1,
      "title": "Project Board",
      "description": "Main project board",
      "owner_id": 1,
      "created_at": "2023-12-01T10:00:00",
      "updated_at": "2023-12-01T10:00:00",
      "columns": [...],
      "statistics": {
        "total_cards": 25,
        "completed_cards": 12,
        "archived_cards": 3,
        "total_columns": 4,
        "total_comments": 45,
        "cards_with_deadline": 8,
        "overdue_cards": 2
      }
    }
  ],
  "total_boards": 1,
  "global_statistics": {
    "total_cards": 25,
    "completed_cards": 12,
    "archived_cards": 3,
    "total_columns": 4,
    "total_comments": 45,
    "cards_with_deadline": 8,
    "overdue_cards": 2
  }
}
```

# API Documentation for Frontend

This documentation outlines all the API endpoints available for the frontend implementation.

## Table of Contents

1. [Authentication API](auth_api.md) - User registration, login, and token management
2. [Board Permissions API](board_permissions_api.md) - Manage user permissions on boards
3. [Boards API](boards_api.md) - Create, read, update, and delete boards
4. [Columns API](columns_api.md) - Manage columns within boards
5. [Cards API](cards_api.md) - Manage cards within columns
6. [Comments API](comments_api.md) - Add, edit, and delete comments on cards
7. [WebSockets API](websockets_api.md) - Real-time updates and notifications

## Base URL

All API endpoints are prefixed with `/api/v1/`

## Authentication

Most endpoints require authentication using a JWT token. Include the token in the Authorization header:

```
Authorization: Bearer {access_token}
```

You can obtain an access token using the [login endpoint](auth_api.md#login).

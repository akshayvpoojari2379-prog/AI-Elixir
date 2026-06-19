# Elixir AI Assistant

Enterprise Elixir AI Assistant integrated with Elixir Portal and Freshservice.

## Features
- Conversational AI support (Powered by Gemini)
- Semantic Search over KB Articles & FAQs (pgvector + BAAI/bge-small-en-v1.5)
- Automated Freshservice Ticket Creation
- Conversation Memory
- Intent Detection

## Architecture
- **Frontend**: React + Next.js, Tailwind CSS
- **Backend**: Python FastAPI
- **Database**: PostgreSQL with `pgvector`
- **AI Stack**: LangChain, LangGraph, Model (Gemini-3.5-flash)

## Setup

1. Copy `.env.example` to `.env` and fill in the values.
   ```bash
   cp .env.example .env
   ```

2. Start the services using Docker Compose:
   ```bash
   docker-compose up -d
   ```

3. Initialize the database:
   ```bash
   cd backend
   alembic upgrade head
   ```

## Development

Run backend locally:
```bash
cd backend
uvicorn main:app --reload
```

Run frontend locally:
```bash
cd frontend
npm install
npm run dev
```

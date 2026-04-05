\# AI Ticketing System



An intelligent internal support ticketing platform where AI reads incoming tickets, auto-resolves simple ones, and routes complex ones to the correct department and employee.



\## Tech Stack

\- \*\*Backend:\*\* FastAPI, SQLite, SQLAlchemy, Python

\- \*\*Frontend:\*\* Next.js, Tailwind CSS, Recharts

\- \*\*AI:\*\* Groq API (LLaMA 3.3 70B)

\- \*\*Deployment:\*\* Railway (backend), Vercel (frontend)



\## Features

\- \*\*AI Ticket Analysis:\*\* Automatically categorizes, summarizes, and scores sentiment of every ticket

\- \*\*Auto-Resolution:\*\* Simple tickets are resolved instantly with an AI-generated response

\- \*\*Smart Routing:\*\* Complex tickets are routed to the correct department based on category

\- \*\*Assignee Suggestion:\*\* Best employee is selected based on skills and current workload

\- \*\*Admin Dashboard:\*\* Filter, view, and manage all tickets with timeline and notes

\- \*\*Analytics:\*\* Charts showing ticket volume by department and top categories



\## How to Run Locally



\### Backend

```bash

cd backend

python -m venv venv

venv\\Scripts\\activate

pip install -r requirements.txt

\# Create .env file with GROQ\_API\_KEY=your\_key

python seed\_data.py

uvicorn main:app --reload

```



\### Frontend

```bash

cd frontend

npm install

\# Create .env.local with NEXT\_PUBLIC\_API\_URL=http://localhost:8000

npm run dev

```



\## Live Demo

\- \*\*Frontend:\*\* https://ai-ticketing-henna.vercel.app

\- \*\*API Docs:\*\* https://ai-ticketing-production.up.railway.app/docs



\## Known Limitations

\- No real email notifications — ticket assignment is simulated

\- Railway free tier has limited compute hours per month

\- SQLite database resets on Railway redeploy (no persistent disk on free tier)



\## Screenshots

\[Add screenshots here]


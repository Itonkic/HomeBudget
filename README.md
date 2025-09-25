🏠 HomeBudget

HomeBudget is a simple Flask-based web application for managing and tracking personal expenses.
It uses PostgreSQL as the database and runs inside Docker containers for easy setup and deployment.

```text
📂 HomeBudget
│
├── app/ # Flask application
│ ├── static/ # Static files (CSS, JS, images)
│ ├── templates/ # HTML templates
│ ├── app.py # Flask entrypoint
│ ├── main.py # Additional Flask logic
│ ├── budget.db # Local SQLite (legacy, not used in Docker)
│ ├── Dockerfile # Dockerfile for Flask app
│ └── requirements.txt # Python dependencies
│
├── db_init/ # Database initialization
│ └── init.sql # SQL script to bootstrap database
│
├── docker-compose.yml # Docker Compose configuration
├── .gitignore # Git ignore rules
├── README.md # Project documentation
├── test.py # Example/test script
└── tests.txt # Test cases
```

🚀 Getting Started
1. Clone the repository or download (on top right there is green button Code then on bottom download zip)
git clone https://github.com/your-username/HomeBudget.git
cd HomeBudget
If ZIP was downloaded extract it and open cmd in root directory HomeBudget-main

2. Build and start the services
Run from the project root:
docker compose up --build

This will start:

1. Flask app → http://localhost:5000
2. PostgreSQL database (port 5432)
3. pgAdmin → http://localhost:8081

🛠 Services
Web (Flask App)
Runs on port 5000
Connects to PostgreSQL using environment variables set in docker-compose.yml

Database (Postgres)
Image: postgres:15
Database: home_budget
User: postgres
Password: postgres
Mounted with db_init/init.sql for automatic initialization
pgAdmin
Runs on port 8081
Default login:
Email: admin@admin.com
Password: admin



⚙️ Environment Variables
Configured in docker-compose.yml:

Service	Variable	Default Value
web	POSTGRES_HOST	db
web	POSTGRES_DB	home_budget
web	POSTGRES_USER	postgres
web	POSTGRES_PASSWORD	postgres
db	POSTGRES_DB	home_budget
db	POSTGRES_USER	postgres
db	POSTGRES_PASSWORD	postgres
pgadmin	PGADMIN_DEFAULT_EMAIL	admin@admin.com


🧑‍💻 Development
Modify Flask code inside app/
Database schema updates → db_init/init.sql
To rebuild after changes:
docker compose down -v





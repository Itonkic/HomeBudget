🏠 HomeBudget

HomeBudget is a simple Flask-based web application for managing and tracking personal expenses.
It uses PostgreSQL as the database and runs inside Docker containers for easy setup and deployment.

```text
📝 **To Do (HomeBudget)**  
🛠 **Roadmap**

| Feature / Task                                     | Priority | Status      | Target Version |
|----------------------------------------------------|----------|-------------|----------------|
| Refactor to use Blueprints and create tests        | High     | Done        | 0.9            |
| User profile management (update username/password) | High     | Done        | 1.0            |
| Enforce stronger password rules                    | High     | Done        | 1.0            |
| JWT refresh tokens                                 | Medium   | Pending     | 1.0            |
| SSL support (Let’s Encrypt + Docker/Nginx)         | High     | Pending     | 1.2            |
| Recurring expenses (subscriptions, bills)          | High     | Pending     | 1.1            |
| Expense tags for advanced filtering                | Medium   | Pending     | 1.2            |
| Bulk import of expenses (CSV/Excel)                | Medium   | Pending     | 1.2            |
| Receipt capture with OCR                           | High     | Pending     | 1.3            |
| Soft delete / restore expenses                     | Medium   | Pending     | 1.2            |
| Charts & graphs for spending trends & KPIs         | High     | Pending     | 1.1            |
| Budget tracking & alerts                           | High     | Pending     | 1.1            |
| Export reports (CSV / PDF)                         | Medium   | Pending     | 1.2            |
| SPA frontend templates                             | High     | Pending     | 1.3            |
| Mobile-responsive UI                               | High     | Pending     | 1.1            |
| Dark mode / theme switcher                         | Medium   | Pending     | 1.2            |
| Inline editing of expenses                         | Medium   | Pending     | 1.2            |
| Separate dev/prod Docker configs                   | Medium   | Pending     | 1.1            |
| Automated PostgreSQL backups                       | High     | Pending     | 1.1            |
| Logging & error monitoring (Sentry/Loguru)         | Medium   | Pending     | 1.2            |
| CI/CD pipeline for tests & deployment              | Medium   | Pending     | 1.2            |
| Multi-user shared budgets / family accounts        | Medium   | Pending     | 1.3            |
| Predictive analytics for spending trends           | Low      | Pending     | 2.0            |
| Notifications for bills or low balance             | Medium   | Pending     | 1.2            |

```

```text
📂 HomeBudget
.gitignore
CACHED
Dockerfile
├─ README.md
├─ [auth]
├─ [internal]
├─ app
│  ├─ .static
index.html
__init__.py
aggregation
__init__.py
routes.py
app.py
│  ├─ auth
│  │  ├─ __init__.py
│  │  └─ routes.py
│  ├─ categories
│  │  ├─ __init__.py
│  │  └─ routes.py
expenses
│  │  ├─ __init__.py
routes.py
static
│  │  └─ index.html
│  ├─ tba_sio
│  │  ├─ __init__.py
│  │  └─ routes.py
│  ├─ templates
│  │  ├─ categories.html
│  │  ├─ expenses.html
│  │  └─ index.html
│  ├─ users
│  │  ├─ __init__.py
│  │  └─ routes.py
│  └─ utils.py
├─ curl
db_init
│  └─ init.sql
├─ docker
├─ docker-compose.yml
├─ exporting
├─ requirements.txt
├─ resolving
├─ test.py
└─ tests.txt
```


```text
🚀 Getting Started
1. Clone the repository or download (on top right there is green button Code then on bottom download zip)
git clone https://github.com/your-username/HomeBudget.git
cd HomeBudget
If ZIP was downloaded extract it and open cmd in root directory HomeBudget-main

2. Download Docker desktop from official site https://www.docker.com/products/docker-desktop/

3. Build and start the services
Run from the project root:
docker compose up --build





This will start:
1. Flask app → **http://localhost:5000**
2. PostgreSQL database (port 5432)
3. pgAdmin → http://localhost:8081
```


```text
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

```


```text
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

```

```text
🧑‍💻 Development
Modify Flask code inside app/
Database schema updates → db_init/init.sql
To rebuild after changes:
docker compose down -v

```




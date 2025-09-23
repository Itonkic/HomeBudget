from datetime import datetime, timedelta, date
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Depends, status, Query
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from sqlmodel import Field, SQLModel, create_engine, Session, select, or_
from passlib.context import CryptContext
from jose import JWTError, jwt
from pydantic import BaseModel

# --- CONFIG ---
SECRET_KEY = "change_this_to_a_strong_random_secret_in_prod"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # one week

INITIAL_BALANCE = 1000.00  # every new user gets this starting balance

# --- AUTH UTIL ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain, hashed) -> bool:
    return pwd_context.verify(plain, hashed)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_access_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")

# --- DB MODELS ---
class UserBase(SQLModel):
    username: str = Field(index=True)
    full_name: Optional[str] = None

class User(UserBase, table=True):
    __tablename__ = "user"
    __table_args__ = {"extend_existing": True}  # <- add this
    id: Optional[int] = Field(default=None, primary_key=True)
    hashed_password: str
    balance: float = Field(default=INITIAL_BALANCE)


class UserCreate(BaseModel):
    username: str
    password: str
    full_name: Optional[str] = None

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class CategoryBase(SQLModel):
    name: str

class Category(CategoryBase, table=True):
    __tablename__ = "category"
    __table_args__ = {"extend_existing": True}
    id: Optional[int] = Field(default=None, primary_key=True)
    
class ExpenseBase(SQLModel):
    description: Optional[str]
    amount: float
    category_id: int
    occurred_at: datetime = Field(default_factory=datetime.utcnow)
    is_income: bool = Field(default=False)  # if true, increases balance, else decreases

class Expense(ExpenseBase, table=True):
    __tablename__ = "expense"
    __table_args__ = {"extend_existing": True}
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True)



class CategoryRead(CategoryBase):
    id: int

class CategoryCreate(CategoryBase):
    pass


class ExpenseCreate(ExpenseBase):
    pass

class ExpenseRead(ExpenseBase):
    id: int
    category: CategoryRead

# --- DB init ---
sqlite_file_name = "budget.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"
engine = create_engine(sqlite_url, echo=False)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

# seed default categories
DEFAULT_CATEGORIES = ["food", "transport", "accommodation", "gifts", "entertainment", "car", "utilities", "salary"]

def seed_categories():
    with Session(engine) as session:
        existing = session.exec(select(Category)).all()
        if not existing:
            for name in DEFAULT_CATEGORIES:
                session.add(Category(name=name))
            session.commit()

# --- app ---
app = FastAPI(title="Home Budget API", description="Simple home budgeting REST API with JWT auth and aggregation endpoints.", version="1.0")

from fastapi.staticfiles import StaticFiles
app.mount("/", StaticFiles(directory="static", html=True), name="static")




@app.on_event("startup")
def on_startup():
    create_db_and_tables()
    seed_categories()

# --- auth helpers ---
def get_user_by_username(session: Session, username: str) -> Optional[User]:
    return session.exec(select(User).where(User.username == username)).first()

def authenticate_user(session: Session, username: str, password: str) -> Optional[User]:
    user = get_user_by_username(session, username)
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user

async def get_current_user(token: str = Depends(oauth2_scheme)):
    payload = decode_access_token(token)
    username: str = payload.get("sub")
    if username is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication credentials")
    with Session(engine) as session:
        user = get_user_by_username(session, username)
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        return user

# --- auth endpoints ---
@app.post("/register", response_model=Token)
def register(user_in: UserCreate):
    with Session(engine) as session:
        if get_user_by_username(session, user_in.username):
            raise HTTPException(status_code=400, detail="Username already registered")
        user = User(username=user_in.username, full_name=user_in.full_name, hashed_password=get_password_hash(user_in.password))
        session.add(user)
        session.commit()
        session.refresh(user)
        access_token = create_access_token({"sub": user.username})
        return {"access_token": access_token, "token_type": "bearer"}

@app.post("/token", response_model=Token)
def login_for_token(form_data: OAuth2PasswordRequestForm = Depends()):
    with Session(engine) as session:
        user = authenticate_user(session, form_data.username, form_data.password)
        if not user:
            raise HTTPException(status_code=401, detail="Incorrect username or password")
        access_token = create_access_token({"sub": user.username})
        return {"access_token": access_token, "token_type": "bearer"}

# --- category endpoints ---
@app.post("/categories", response_model=CategoryRead)
def create_category(cat: CategoryCreate, current_user: User = Depends(get_current_user)):
    with Session(engine) as session:
        existing = session.exec(select(Category).where(Category.name == cat.name)).first()
        if existing:
            raise HTTPException(status_code=400, detail="Category already exists")
        category = Category(name=cat.name)
        session.add(category)
        session.commit()
        session.refresh(category)
        return category

@app.get("/categories", response_model=List[CategoryRead])
def list_categories(skip: int = 0, limit: int = 100, current_user: User = Depends(get_current_user)):
    with Session(engine) as session:
        cats = session.exec(select(Category).offset(skip).limit(limit)).all()
        return cats

@app.get("/categories/{category_id}", response_model=CategoryRead)
def get_category(category_id: int, current_user: User = Depends(get_current_user)):
    with Session(engine) as session:
        cat = session.get(Category, category_id)
        if not cat:
            raise HTTPException(status_code=404, detail="Category not found")
        return cat

@app.put("/categories/{category_id}", response_model=CategoryRead)
def update_category(category_id: int, category_in: CategoryCreate, current_user: User = Depends(get_current_user)):
    with Session(engine) as session:
        cat = session.get(Category, category_id)
        if not cat:
            raise HTTPException(status_code=404, detail="Category not found")
        cat.name = category_in.name
        session.add(cat)
        session.commit()
        session.refresh(cat)
        return cat

@app.delete("/categories/{category_id}", status_code=204)
def delete_category(category_id: int, current_user: User = Depends(get_current_user)):
    with Session(engine) as session:
        cat = session.get(Category, category_id)
        if not cat:
            raise HTTPException(status_code=404, detail="Category not found")
        session.delete(cat)
        session.commit()
        return

# --- expenses endpoints ---
@app.post("/expenses", response_model=ExpenseRead)
def create_expense(exp_in: ExpenseCreate, current_user: User = Depends(get_current_user)):
    with Session(engine) as session:
        # ensure category exists
        category = session.get(Category, exp_in.category_id)
        if not category:
            raise HTTPException(status_code=404, detail="Category not found")
        # update user's balance
        user = session.get(User, current_user.id)
        if not exp_in.is_income:
            # expense reduces balance
            if user.balance < exp_in.amount:
                raise HTTPException(status_code=400, detail="Insufficient balance for this expense")
            user.balance -= exp_in.amount
        else:
            user.balance += exp_in.amount
        session.add(user)
        expense = Expense(**exp_in.dict(), user_id=user.id)
        session.add(expense)
        session.commit()
        session.refresh(expense)
        # include category in response
        return ExpenseRead(
            id=expense.id,
            description=expense.description,
            amount=expense.amount,
            category_id=expense.category_id,
            occurred_at=expense.occurred_at,
            is_income=expense.is_income,
            category=CategoryRead(id=category.id, name=category.name)
        )

@app.get("/expenses", response_model=List[ExpenseRead])
def list_expenses(
    current_user: User = Depends(get_current_user),
    category_id: Optional[int] = Query(None),
    min_amount: Optional[float] = Query(None, ge=0),
    max_amount: Optional[float] = Query(None, ge=0),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    description: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 100
):
    with Session(engine) as session:
        q = select(Expense).where(Expense.user_id == current_user.id)
        if category_id is not None:
            q = q.where(Expense.category_id == category_id)
        if min_amount is not None:
            q = q.where(Expense.amount >= min_amount)
        if max_amount is not None:
            q = q.where(Expense.amount <= max_amount)
        if date_from is not None:
            q = q.where(Expense.occurred_at >= datetime.combine(date_from, datetime.min.time()))
        if date_to is not None:
            q = q.where(Expense.occurred_at <= datetime.combine(date_to, datetime.max.time()))
        if description:
            q = q.where(Expense.description.contains(description))
        q = q.offset(skip).limit(limit)
        results = session.exec(q).all()
        # attach categories
        expenses_out = []
        for e in results:
            cat = session.get(Category, e.category_id)
            expenses_out.append(ExpenseRead(
                id=e.id,
                description=e.description,
                amount=e.amount,
                category_id=e.category_id,
                occurred_at=e.occurred_at,
                is_income=e.is_income,
                category=CategoryRead(id=cat.id, name=cat.name)
            ))
        return expenses_out

@app.get("/expenses/{expense_id}", response_model=ExpenseRead)
def get_expense(expense_id: int, current_user: User = Depends(get_current_user)):
    with Session(engine) as session:
        e = session.get(Expense, expense_id)
        if not e or e.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Expense not found")
        cat = session.get(Category, e.category_id)
        return ExpenseRead(
            id=e.id,
            description=e.description,
            amount=e.amount,
            category_id=e.category_id,
            occurred_at=e.occurred_at,
            is_income=e.is_income,
            category=CategoryRead(id=cat.id, name=cat.name)
        )

@app.put("/expenses/{expense_id}", response_model=ExpenseRead)
def update_expense(expense_id: int, exp_in: ExpenseCreate, current_user: User = Depends(get_current_user)):
    with Session(engine) as session:
        e = session.get(Expense, expense_id)
        if not e or e.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Expense not found")
        category = session.get(Category, exp_in.category_id)
        if not category:
            raise HTTPException(status_code=404, detail="Category not found")
        # adjust balance: revert previous impact then apply new
        user = session.get(User, current_user.id)
        # revert
        if not e.is_income:
            user.balance += e.amount
        else:
            user.balance -= e.amount
        # apply new
        if not exp_in.is_income:
            if user.balance < exp_in.amount:
                raise HTTPException(status_code=400, detail="Insufficient balance for this updated expense")
            user.balance -= exp_in.amount
        else:
            user.balance += exp_in.amount
        session.add(user)
        # update expense record
        e.description = exp_in.description
        e.amount = exp_in.amount
        e.category_id = exp_in.category_id
        e.occurred_at = exp_in.occurred_at
        e.is_income = exp_in.is_income
        session.add(e)
        session.commit()
        session.refresh(e)
        return ExpenseRead(
            id=e.id,
            description=e.description,
            amount=e.amount,
            category_id=e.category_id,
            occurred_at=e.occurred_at,
            is_income=e.is_income,
            category=CategoryRead(id=category.id, name=category.name)
        )

@app.delete("/expenses/{expense_id}", status_code=204)
def delete_expense(expense_id: int, current_user: User = Depends(get_current_user)):
    with Session(engine) as session:
        e = session.get(Expense, expense_id)
        if not e or e.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Expense not found")
        user = session.get(User, current_user.id)
        # revert balance impact
        if not e.is_income:
            user.balance += e.amount
        else:
            user.balance -= e.amount
        session.add(user)
        session.delete(e)
        session.commit()
        return

# --- user info ---
@app.get("/me")
def read_me(current_user: User = Depends(get_current_user)):
    return {"id": current_user.id, "username": current_user.username, "full_name": current_user.full_name, "balance": current_user.balance}


from fastapi.responses import RedirectResponse

@app.get("/")
def root():
    # Redirects to Swagger UI so users can log in via /token
    return RedirectResponse(url="/docs")


@app.get("/aggregations/summary")
def aggregation_summary(
    current_user: User = Depends(get_current_user),
    period: Optional[str] = Query("month", regex="^(month|quarter|year|custom)$"),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None
):
    """
    Returns aggregated totals for the requested period.
    period: month | quarter | year | custom
    If custom is provided, specify start_date and end_date (inclusive).
    Response includes total_spent, total_income, net, and breakdown by category.
    """
    now = datetime.utcnow()
    if period == "month":
        start = datetime(now.year, now.month, 1)
        # end is now
        end = now
    elif period == "quarter":
        q = (now.month - 1) // 3 + 1
        start_month = 3 * (q - 1) + 1
        start = datetime(now.year, start_month, 1)
        end = now
    elif period == "year":
        start = datetime(now.year, 1, 1)
        end = now
    elif period == "custom":
        if not start_date or not end_date:
            raise HTTPException(status_code=400, detail="start_date and end_date required for custom period")
        start = datetime.combine(start_date, datetime.min.time())
        end = datetime.combine(end_date, datetime.max.time())
    else:
        start = datetime(now.year, now.month, 1)
        end = now

    with Session(engine) as session:
        q = select(Expense).where(Expense.user_id == current_user.id, Expense.occurred_at >= start, Expense.occurred_at <= end)
        expenses = session.exec(q).all()
        total_spent = sum(e.amount for e in expenses if not e.is_income)
        total_income = sum(e.amount for e in expenses if e.is_income)
        net = total_income - total_spent
        # breakdown by category (spent and income per category)
        breakdown = {}
        for e in expenses:
            cat = session.get(Category, e.category_id)
            name = cat.name if cat else f"cat_{e.category_id}"
            if name not in breakdown:
                breakdown[name] = {"spent": 0.0, "income": 0.0}
            if e.is_income:
                breakdown[name]["income"] += e.amount
            else:
                breakdown[name]["spent"] += e.amount
        return {
            "period": period,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "total_spent": round(total_spent, 2),
            "total_income": round(total_income, 2),
            "net": round(net, 2),
            "breakdown_by_category": breakdown
        }
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
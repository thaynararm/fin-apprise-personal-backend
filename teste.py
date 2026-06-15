from src.core.database import engine, Base
from modules.users.model import User

Base.metadata.create_all(bind=engine)

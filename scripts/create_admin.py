import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
import os
from dotenv import load_dotenv
load_dotenv()

from app.models.user import User
from app.services.auth import hash_password

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_async_engine(DATABASE_URL)
Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def create_admin():
    async with Session() as session:
        existing = (await session.execute(select(User).where(User.username == "admin"))).scalar_one_or_none()
        if existing:
            print("Admin already exists")
            return
        admin = User(
            username="admin",
            email="admin@t20datahub.com",
            hashed_password=hash_password("admin123"),
            is_admin=True,
            role="admin",
        )
        session.add(admin)
        await session.commit()
        print("✅ Admin created: username=admin password=admin123")

asyncio.run(create_admin())

from pydantic import BaseModel, EmailStr

class UserRegister(BaseModel):
    username: str
    email: EmailStr
    password: str

class UserOut(BaseModel):
    id: int
    username: str
    email: str
    role: str
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

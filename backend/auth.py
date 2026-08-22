from fastapi import Depends, HTTPException, Header
from typing import Optional

class Session:
    """Mocked session. Format: 'customer:<account_id>' or 'staff:<role>'"""
    def __init__(self, session_str: str):
        parts = session_str.split(":")
        if len(parts) != 2:
            raise ValueError("Invalid session format")
        self.session_type, self.identity = parts

    @property
    def is_customer(self) -> bool:
        return self.session_type == "customer"

    @property
    def is_staff(self) -> bool:
        return self.session_type == "staff"

    @property
    def account_id(self) -> str:
        if not self.is_customer:
            raise RuntimeError("staff sessions don't have account_id")
        return self.identity

    @property
    def staff_role(self) -> str:
        if not self.is_staff:
            raise RuntimeError("customer sessions don't have staff_role")
        return self.identity

    def __str__(self):
        return f"{self.session_type}:{self.identity}"


def get_session(x_session: str = Header(None)) -> Session:
    """Extract session from x-session header. Required."""
    if not x_session:
        raise HTTPException(status_code=401, detail="Missing x-session header")
    try:
        return Session(x_session)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid session format. Use 'customer:<account_id>' or 'staff:<role>'",
        )

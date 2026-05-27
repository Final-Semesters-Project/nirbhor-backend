# Role-based dependencies — build on top of get_current_user

Usage in routes:

```python
# any authenticated user
@router.get("/profile")
async def get_profile(current_user: User = Depends(get_current_user)):
    ...

# seekers only
@router.post("/bookings")
async def create_booking(current_user: User = Depends(get_current_seeker)):
    ...

# providers only
@router.post("/urgent/accept")
async def accept_urgent(current_user: User = Depends(get_current_provider)):
    ...

# admins only
@router.get("/admin/users")
async def list_users(current_user: User = Depends(get_current_admin)):
    ...
```

---
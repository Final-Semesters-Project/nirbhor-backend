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


<!-- RUN TESTS -->
# run all tests
docker exec -it nirbhor_backend_dev pytest

# run with verbose output (see each test name)
docker exec -it nirbhor_backend_dev pytest -v

# run only one file
docker exec -it nirbhor_backend_dev pytest tests/test_auth/test_registration.py -v

# run only one test class
docker exec -it nirbhor_backend_dev pytest tests/test_auth/test_registration.py::TestSeekerRegistration -v

# run only one specific test
docker exec -it nirbhor_backend_dev pytest tests/test_auth/test_registration.py::TestSeekerRegistration::test_seeker_registration_success -v

# stop on first failure
docker exec -it nirbhor_backend_dev pytest -x

# show print statements (useful for debugging)
docker exec -it nirbhor_backend_dev pytest -s
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


<!-- manually check for bn translation -->
```python
from fastapi import APIRouter, Depends, Header
from typing import Annotated

router = APIRouter()

@router.get("/provider/dashboard")
async def get_provider_dashboard(
    current_user: User = Depends(get_current_user),
    # 👈 This forces Swagger UI to show an input box for the header!
    accept_language: Annotated[str | None, Header(alias="Accept-Language")] = "en", 
    db: AsyncSession = Depends(get_db)
):
    # Pass the header value down to your i18n handler or service layer
    lang = "bn" if accept_language and accept_language.startswith("bn") else "en"
    
    return await ProviderService.get_dashboard(current_user, db, lang)
```
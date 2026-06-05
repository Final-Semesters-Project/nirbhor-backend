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


<!-- delete photo from cloudinary if new photo is uploaded/ delete request came -->
```python
from fastapi import APIRouter, Depends, UploadFile, File, status
from app.utils.cloudinary import upload_image_to_cloudinary
from app.services.provider_service import ProviderService

router = APIRouter()

@router.patch("/me/documents", status_code=status.HTTP_200_OK)
async def upload_provider_documents(
    profile_photo: UploadFile = File(None),
    nid_front: UploadFile = File(None),
    nid_back: UploadFile = File(None),
    current_user = Depends(get_current_provider),
    db = Depends(get_db_session)
):
    update_data = {}

    if profile_photo:
        res = await upload_image_to_cloudinary(profile_photo, "profiles")
        update_data["profile_photo_url"] = res["url"]
        update_data["profile_photo_public_id"] = res["public_id"]

    if nid_front:
        res = await upload_image_to_cloudinary(nid_front, "nid_docs")
        update_data["nid_front_url"] = res["url"]
        update_data["nid_front_public_id"] = res["public_id"]

    if nid_back:
        res = await upload_image_to_cloudinary(nid_back, "nid_docs")
        update_data["nid_back_url"] = res["url"]
        update_data["nid_back_public_id"] = res["public_id"]

    return await ProviderService.update_profile(db, current_user.id, update_data)
```


```python
# app/services/provider_service.py

@staticmethod
async def update_profile(db, provider_id, update_data):
    repo = ProviderRepository(db)
    old_profile = await repo.get_by_id(provider_id)

    # If updating profile photo, delete the old one from Cloudinary
    if "profile_photo_public_id" in update_data and old_profile.profile_photo_public_id:
        await delete_image_from_cloudinary(old_profile.profile_photo_public_id)

    # Update database record
    updated_profile = await repo.update(provider_id, update_data)
    await db.commit()
    return updated_profile
```


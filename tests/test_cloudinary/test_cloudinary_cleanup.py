import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from cloudinary.exceptions import Error
from app.jobs.cloudinary_cleanup_job import cleanup_orphan_cloudinary_images

# TODO: Test it


@pytest.mark.asyncio
async def test_cleanup_deletes_orphans(db_session, create_provider_with_photos):
    """
    Orphan in Cloudinary (not in DB) should be deleted.
    """
    provider = await create_provider_with_photos(
        photo_public_id="nirbhor/providers/real_photo",
        nid_front_public_id="nirbhor/nid/real_front",
        nid_back_public_id="nirbhor/nid/real_back",
    )

    # Cloudinary has one extra image not in DB
    cloudinary_resources = [
        {"public_id": "nirbhor/providers/real_photo"},
        {"public_id": "nirbhor/nid/real_front"},
        {"public_id": "nirbhor/nid/real_back"},
        {"public_id": "nirbhor/providers/orphan_photo"},  # orphan
    ]

    with patch("cloudinary.api.resources") as mock_resources, \
            patch("cloudinary.api.delete_resources") as mock_delete:

        mock_resources.return_value = {
            "resources": cloudinary_resources,
            "next_cursor": None,
        }
        mock_delete.return_value = {"deleted": {
            "nirbhor/providers/orphan_photo": "deleted"}}

        await cleanup_orphan_cloudinary_images()

        # Only the orphan should be deleted
        mock_delete.assert_called_once()
        deleted_ids = mock_delete.call_args[0][0]
        assert "nirbhor/providers/orphan_photo" in deleted_ids
        assert "nirbhor/providers/real_photo" not in deleted_ids


@pytest.mark.asyncio
async def test_cleanup_aborts_on_cloudinary_api_error():
    """If Cloudinary API fails during enumeration, do not delete anything."""
    import cloudinary.api

    with patch("cloudinary.api.resources", side_effect=Error("rate limited")), \
            patch("cloudinary.api.delete_resources") as mock_delete:

        await cleanup_orphan_cloudinary_images()

        # Must not delete anything if we can't enumerate
        mock_delete.assert_not_called()


@pytest.mark.asyncio
async def test_cleanup_skips_if_no_orphans(db_session, create_provider_with_photos):
    """No orphans → no delete calls."""
    provider = await create_provider_with_photos(
        photo_public_id="nirbhor/providers/photo_1",
    )

    cloudinary_resources = [{"public_id": "nirbhor/providers/photo_1"}]

    with patch("cloudinary.api.resources") as mock_resources, \
            patch("cloudinary.api.delete_resources") as mock_delete:

        mock_resources.return_value = {
            "resources": cloudinary_resources,
            "next_cursor": None,
        }

        await cleanup_orphan_cloudinary_images()
        mock_delete.assert_not_called()


@pytest.mark.asyncio
async def test_cleanup_handles_pagination():
    """Cloudinary pagination (next_cursor) must be followed completely."""
    page1 = {
        "resources": [{"public_id": "nirbhor/providers/photo_1"}],
        "next_cursor": "cursor_abc",
    }
    page2 = {
        "resources": [{"public_id": "nirbhor/providers/orphan"}],
        "next_cursor": None,
    }

    call_count = 0

    def mock_resources(**kwargs):
        nonlocal call_count
        call_count += 1
        return page1 if call_count == 1 else page2

    with patch("cloudinary.api.resources", side_effect=mock_resources), \
            patch("cloudinary.api.delete_resources") as mock_delete:

        await cleanup_orphan_cloudinary_images()

        assert call_count == 2  # both pages fetched
        mock_delete.assert_called_once()

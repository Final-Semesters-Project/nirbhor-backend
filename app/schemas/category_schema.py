from pydantic import BaseModel, ConfigDict, Field


class CategoryBaseSchema(BaseModel):
    name_en: str = Field(..., description="Category name in English")
    name_bn: str = Field(..., description="Category name in Bangla")


class CategoryCreateSchema(CategoryBaseSchema):
    pass


class CategoryResponse(BaseModel):
    id: int
    name: str   # localized

    model_config = ConfigDict(from_attributes=True)

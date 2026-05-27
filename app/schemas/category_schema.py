from pydantic import BaseModel, ConfigDict, Field


class CategoryBaseSchema(BaseModel):
    name_en: str = Field(..., description="Category name in English")
    name_bn: str = Field(..., description="Category name in Bangla")


class CategoryCreateSchema(CategoryBaseSchema):
    pass

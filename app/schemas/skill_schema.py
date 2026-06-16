from pydantic import BaseModel, ConfigDict


class SkillBaseSchema(BaseModel):
    name_en: str
    name_bn: str
    category_id: int


class SkillCreateSchema(SkillBaseSchema):
    pass


class SkillResponseSchema(BaseModel):
    id: int
    name: str   # localized
    category_id: int

    model_config = ConfigDict(from_attributes=True)

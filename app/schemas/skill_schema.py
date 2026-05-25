from pydantic import BaseModel, ConfigDict


class SkillBaseSchema(BaseModel):
    name_en: str
    name_bn: str
    category_id: int


class SkillCreateSchema(SkillBaseSchema):
    pass


class SkillResponseSchema(BaseModel):
    pass

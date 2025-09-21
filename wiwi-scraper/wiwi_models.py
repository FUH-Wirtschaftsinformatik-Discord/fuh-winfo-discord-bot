import io
import uuid
from datetime import timedelta, datetime

import discord
from discord import Colour
from peewee import *
from peewee import ModelSelect

db = SqliteDatabase("data/wiwi-scraper-db.sqlite3")

class BaseModel(Model):
    class Meta:
        database = db

class StudyModuleModel(BaseModel):
    module_number = CharField()
    module_name = CharField()
    is_summer_semester = BooleanField()
    year = IntegerField()
    examination_period = CharField()
    anonymous = BooleanField(default=False)

    very_good = IntegerField(default=0)
    good = IntegerField(default=0)
    satisfactory = IntegerField(default=0)
    sufficient = IntegerField(default=0)
    insufficient = IntegerField(default=0)

    class Meta:
        composite_key = CompositeKey('module_number', 'year', 'is_summer_semester', 'examination_period')

db.create_tables([StudyModuleModel], safe=True)



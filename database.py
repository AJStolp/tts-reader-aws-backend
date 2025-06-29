from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase



db = SQLAlchemy()

# def init_db():
#     # import all modules here that might define models so that
#     # they will be registered properly on the metadata.  Otherwise
#     # you will have to import them first before calling init_db()
#     import models
#     Base.metadata.create_all()
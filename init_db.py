from app import app, db

with app.app_context():
    if not db.engine.has_table('user'):
        db.create_all()
from database import db
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.dialects.postgresql.base import UUID


# User model with added preferences fields
class User(db.Model):
    __tablename__ = "User"
    user_id = db.Column(UUID(as_uuid=True), primary_key=True)
    username = db.Column(db.String, unique=True)
    email = db.Column(db.String(128), unique=True)
    first_name = db.Column(db.String(128))
    last_name = db.Column(db.String(128))
    remaining_chars = db.Column(db.Integer, default=100)
    password_hash = db.Column(db.String(128))
    engine = db.Column(db.String, default='standard')  # New field for engine preference
    voice_id = db.Column(db.String, default='Joey')    # New field for voice preference
    stripe_subscription_id = db.Column(db.String(128))

    def set_password(self, password: str) -> None:
        """Hash and set the user's password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Check if the provided password matches the stored hash."""
        return check_password_hash(self.password_hash, password)
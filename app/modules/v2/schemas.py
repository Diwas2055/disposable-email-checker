from dataclasses import dataclass
from email_validator import validate_email, EmailNotValidError


@dataclass
class EmailRequest:
    email: str

    def __post_init__(self):
        try:
            # Normalize and validate email
            validated = validate_email(self.email, check_deliverability=False)
            self.email = validated.email
        except EmailNotValidError as e:
            raise ValueError(f"Invalid email address: {str(e)}")

from models import db, LogMessage


def save_log_message(
    module, 
    message, 
    level="info", 
    click=None, 
    campaign=None, 
    event=None, 
    ):
    log_message = LogMessage(
        module=module,
        message=message,
        level=level
    )
    db.session.add(log_message)

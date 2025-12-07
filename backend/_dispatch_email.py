def _dispatch_email(subject=None, recipients=None, body=None, sender=None, **kwargs):
    """
    Mock function to simulate email dispatch.

    Accepts a flexible signature to be compatible with different call sites
    in the codebase and with tests that may pass `sender` or other kwargs.

    :param subject: Email subject
    :param recipients: List of recipient email addresses
    :param body: Email body content
    :param sender: Optional sender address
    """
    try:
        print(f"Email sent!\nSubject: {subject}\nRecipients: {recipients}\nBody: {body}")
    except Exception:
        # Best-effort: do not raise from the mock dispatcher
        pass

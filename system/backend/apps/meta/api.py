from ninja import Router


router = Router(tags=["Meta"])


@router.get("/meta/protocols")
def get_meta_protocols(request):
    return {"protocols": ["TLS", "SSH", "IKE", "SMTP", "IMAP", "POP3", "UNKNOWN"]}

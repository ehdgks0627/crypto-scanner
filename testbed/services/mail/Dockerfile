FROM python:3.12-alpine3.20

COPY services/mail/mail_fixture.py /opt/testbed-mail/mail_fixture.py

EXPOSE 25 465 587 993 995

CMD ["python", "/opt/testbed-mail/mail_fixture.py"]

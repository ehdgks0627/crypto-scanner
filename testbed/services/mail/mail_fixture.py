import os
import socket
import ssl
import threading


RSA_CERT_FILE = "/etc/testbed/certs/mail/server.crt"
RSA_KEY_FILE = "/etc/testbed/certs/mail/server.key"
ECDSA_CERT_FILE = "/etc/testbed/certs/mail-imaps/server.crt"
ECDSA_KEY_FILE = "/etc/testbed/certs/mail-imaps/server.key"
HOSTNAME = os.getenv("MAIL_HOSTNAME", "mail.testbed.local")


def tls_context(
    cert_file: str = RSA_CERT_FILE,
    key_file: str = RSA_KEY_FILE,
    minimum_version: ssl.TLSVersion = ssl.TLSVersion.TLSv1_2,
    maximum_version: ssl.TLSVersion | None = None,
) -> ssl.SSLContext:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert_file, key_file)
    context.minimum_version = minimum_version
    if maximum_version is not None:
      context.maximum_version = maximum_version
    return context


def serve_socket(port: int, handler) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("0.0.0.0", port))
        server.listen(50)
        while True:
            client, _addr = server.accept()
            threading.Thread(target=handler, args=(client,), daemon=True).start()


def send_line(sock, line: str) -> None:
    sock.sendall((line + "\r\n").encode("utf-8"))


def smtp_handler(client: socket.socket, tls13_only: bool = False) -> None:
    with client:
        send_line(client, f"220 {HOSTNAME} ESMTP testbed")
        while True:
            data = client.recv(2048)
            if not data:
                return
            command = data.decode("utf-8", "ignore").strip().upper()
            if command.startswith(("EHLO", "HELO")):
                send_line(client, f"250-{HOSTNAME}")
                send_line(client, "250 STARTTLS")
            elif command.startswith("STARTTLS"):
                send_line(client, "220 Ready to start TLS")
                maximum_version = ssl.TLSVersion.TLSv1_2 if not tls13_only else ssl.TLSVersion.TLSv1_3
                minimum_version = ssl.TLSVersion.TLSv1_3 if tls13_only else ssl.TLSVersion.TLSv1_2
                with tls_context(minimum_version=minimum_version, maximum_version=maximum_version).wrap_socket(client, server_side=True) as tls_client:
                    send_line(tls_client, f"220 {HOSTNAME} ESMTP testbed over TLS")
                    return
            elif command.startswith("QUIT"):
                send_line(client, "221 Bye")
                return
            else:
                send_line(client, "250 OK")


def implicit_tls_handler(
    banner: str,
    cert_file: str = RSA_CERT_FILE,
    key_file: str = RSA_KEY_FILE,
    minimum_version: ssl.TLSVersion = ssl.TLSVersion.TLSv1_2,
    maximum_version: ssl.TLSVersion | None = None,
):
    def handle(client: socket.socket) -> None:
        with client:
            with tls_context(cert_file, key_file, minimum_version, maximum_version).wrap_socket(client, server_side=True) as tls_client:
                send_line(tls_client, banner)
                tls_client.recv(2048)

    return handle


def main() -> None:
    servers = [
        (25, smtp_handler),
        (587, smtp_handler),
        (465, implicit_tls_handler(f"220 {HOSTNAME} ESMTP testbed smtps", minimum_version=ssl.TLSVersion.TLSv1_3, maximum_version=ssl.TLSVersion.TLSv1_3)),
        (993, implicit_tls_handler(f"* OK {HOSTNAME} IMAP4rev1 ready", ECDSA_CERT_FILE, ECDSA_KEY_FILE, minimum_version=ssl.TLSVersion.TLSv1_3, maximum_version=ssl.TLSVersion.TLSv1_3)),
        (995, implicit_tls_handler(f"+OK {HOSTNAME} POP3 ready", maximum_version=ssl.TLSVersion.TLSv1_2)),
    ]
    for port, handler in servers:
        threading.Thread(target=serve_socket, args=(port, handler), daemon=True).start()
    threading.Event().wait()


if __name__ == "__main__":
    main()

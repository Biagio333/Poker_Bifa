import json
import socket


UDP_HOST = "127.0.0.1"
UDP_PORT = 9000
UDP_PROMPT_PORT = 9001


def send_udp_message(payload, host=UDP_HOST, port=UDP_PORT):
    data = json.dumps(payload, ensure_ascii=True).encode("utf-8")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.sendto(data, (host, port))
    finally:
        sock.close()


def send_udp_prompt(payload, host=UDP_HOST, port=UDP_PROMPT_PORT):
    send_udp_message(payload, host=host, port=port)


def send_udp_text(text, host=UDP_HOST, port=UDP_PROMPT_PORT):
    data = str(text).encode("utf-8", errors="replace")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.sendto(data, (host, port))
    finally:
        sock.close()

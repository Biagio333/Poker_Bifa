import json
import socket


HOST = "127.0.0.1"
PORT = 9000

RED = "\033[91m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
GREEN = "\033[92m"
RESET = "\033[0m"


def format_message(message, addr):
    message_type = message.get("type", "")
    label = message.get("label", "")
    x = message.get("x", "?")
    y = message.get("y", "?")
    equity = message.get("equity", "")
    reason = message.get("reason", "")
    debug = message.get("debug", {})
    street = message.get("street", "")
    pot = message.get("pot", "")
    board = message.get("board_cards", [])
    hero = message.get("hero_cards", [])

    lines = [
        f"{CYAN}From:{RESET} {addr[0]}:{addr[1]}",
        f"{CYAN}Type:{RESET} {message_type}",
        f"{RED}Decision:{RESET} {label}",
        f"{YELLOW}Click:{RESET} ({x}, {y})",
        f"{GREEN}Street:{RESET} {street}    {GREEN}Pot:{RESET} {pot}    {GREEN}Equity:{RESET} {equity}",
        f"{GREEN}Hero:{RESET} {hero}",
        f"{GREEN}Board:{RESET} {board}",
        f"{YELLOW}Reason:{RESET} {reason}",
    ]
    if debug:
        lines.append(f"{YELLOW}Debug:{RESET} {debug}")
    return "\n".join(lines)


def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((HOST, PORT))

    print(f"Listening UDP on {HOST}:{PORT}")
    while True:
        data, addr = sock.recvfrom(65535)
        try:
            message = json.loads(data.decode("utf-8"))
            print()
            print(format_message(message, addr))
        except Exception:
            print()
            print(f"{RED}Raw:{RESET} {data.decode('utf-8', errors='replace')}")


if __name__ == "__main__":
    main()

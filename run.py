import logging

from src.core import NexusCore

logging.basicConfig(
    filename="nexus_system.log",
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


def start_interactive_session():
    print("=========================================================")
    print("🧠 NEXUS v0.1.2")
    print("=========================================================\n")

    try:
        nexus = NexusCore()
    except Exception:
        logging.critical("Nexus boot failure.", exc_info=True)
        print("🚨 Nexus could not start. Check your environment configuration.")
        return

    print("Nexus System: Online. Type 'exit' or 'quit' to close.\n")

    while True:
        try:
            user_text = input("👤 You: ").strip()
            if not user_text:
                continue
            if user_text.lower() in {"exit", "quit", "close"}:
                print("\n👋 Nexus shutting down. Goodbye, boss.")
                break

            response = nexus.handle_request(user_text)
            print(f"\n🤖 Nexus:\n{response}\n")
            print("---------------------------------------------------------")
        except KeyboardInterrupt:
            print("\n\n👋 Process interrupted. Goodbye.")
            break
        except EOFError:
            print("\n\n👋 Input stream closed. Goodbye.")
            break
        except Exception:
            logging.exception("Unhandled runtime disruption.")
            print("\n🤖 Nexus:\nI hit an unexpected problem processing that request.\n")


if __name__ == "__main__":
    start_interactive_session()

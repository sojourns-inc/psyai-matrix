import os
from nio import AsyncClient, RoomMessageText, SyncResponse
from dotenv import load_dotenv
import logging
import requests
import re
from supabase import create_client

load_dotenv()


def create_drug_info_card():
    search_url = "https://psychonautwiki.org/w/index.php?search=Gabapentin&title=Special%3ASearch&go=Go"
    info_card = f"""**[Gabapentin]({search_url})**

**🔭 Class**
- ✴️ **Chemical:** ➡️ Gabapentinoids
- ✴️ **Psychoactive:** ➡️ Depressant

**⚖️ Dosages**
- ✴️ **ORAL ✴️**
  - **Threshold:** 200mg
  - **Light:** 200 - 600mg
  - **Common:** 600 - 900mg
  - **Strong:** 900 - 1200mg
  - **Heavy:** 1200mg+

**⏱️ Duration:**
- ✴️ **ORAL ✴️**
  - **Onset:** 30 - 90 minutes
  - **Total:** 5 - 8 hours

**⚠️ Addiction Potential ⚠️**
- No addiction potential information.

**Notes**
- Likely to have a cross-tolerance with other Gabapentinoids, such as Pregabalin and Mirogabalin.

**🧠 Subjective Effects**
  - **Focus enhancement**
  - **Euphoria**

**📈 Tolerance:**
  - **Full:** with prolonged continuous usage
  - **Baseline:** 7-14 days
"""
    return info_card


def escape_markdown_v2(text):
    escape_chars = r"_*[]()~`>#\+=-|{}.!"
    return "".join("\\" + char if char in escape_chars else char for char in text)


# Environment Variables
MATRIX_USER_ID = os.getenv("MATRIX_USER_ID")
MATRIX_PASSWORD = os.getenv("MATRIX_PASSWORD")
MATRIX_HOMESERVER = os.getenv("MATRIX_HOMESERVER")
INFO_PROMPT_SUFFIX = os.getenv("INFO_PROMPT_SUFFIX")
BASE_URL = os.getenv("BASE_URL")
LLM_API_KEY = os.getenv("LLM_API_KEY")  # OpenAI API key
LLM_MODEL_ID = os.getenv("LLM_MODEL_ID")
BEARER_TOKEN = os.getenv("BEARER_TOKEN")  # Bearer token for chat bot language model API

# Text & info message parsing
SORRY_MSG = lambda x: f"Sorry, I couldn't fetch the {x}. Please try again later."
ESCAPE_TEXT = lambda text: text


# Logging. Not to be confused with keylogging. Ya nerds. Standard output logging.
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger("PsyAI Log 🤖")


def post_and_parse_url(url: str, payload: dict):
    try:
        headers = {
            "Openai-Api-Key": LLM_API_KEY,
            "Authorization": f"Bearer {BEARER_TOKEN}",
        }
        response = requests.post(url, json=payload, headers=headers)
        return {"data": response.json()}
    except Exception as error:
        logger.error(f"Error in post_and_parse_url: {error}")
        return None


def fetch_new_chat_id_from_psygpt(query: str):
    try:
        raw = {"name": f"Card => {query}"}
        return post_and_parse_url(f" {BASE_URL}/chat", raw)
    except Exception as error:
        logger.error(f"Error in fetch_new_chat_id_from_psygpt: {error}")
        return None


def fetch_dose_card_from_psygpt(substance_name: str, chat_id: str):
    try:
        raw = {
            "model": LLM_MODEL_ID,
            "question": (
                f"Generate a drug information card for {substance_name}. Respond only with the card. Use the provided example and follow the exact syntax given.\n\n Example drug information card for Gabapentin:\n\n"
                + create_drug_info_card()
                + f"\n\nNotes 1. "
                + INFO_PROMPT_SUFFIX
            ),
            "temperature": 0.5,
            "max_tokens": 4096,
        }
        return post_and_parse_url(f"{BASE_URL}/chat/{chat_id}/question", raw)
    except Exception as error:
        logger.error(f"Error in fetch_question_from_psygpt: {error}")
        return None


def fetch_question_from_psygpt(query: str, chat_id: str):
    try:
        raw = {
            "model": LLM_MODEL_ID,
            "question": f"{query}\n\n(Please respond conversationally to the query. If additional relevant details are available, incorporate that information naturally into your response without directly mentioning the source. If the available information does not fully address the query, feel free to rely on your own knowledge to provide a helpful, friendly response within 30000 characters.)",
            "temperature": 0.5,
            "max_tokens": 4000,
        }
        return post_and_parse_url(f"{BASE_URL}/chat/{chat_id}/question", raw)
    except Exception as error:
        logger.error(f"Error in fetch_question_from_psygpt: {error}")
        return None


async def message_callback(room, event):
    # Only respond to text messages
    if isinstance(event, RoomMessageText):
        message = event.body
        if message.startswith("\start"):
            await handle_start_command(room, event)
        elif message.startswith("\info"):
            await handle_info_command(room, event)
        elif message.startswith("\\ask"):
            await handle_ask_command(room, event)


async def handle_start_command(room, event):
    response = "Welcome to PsyAI Bot! Type /info [Drug Name] for info or /ask [Your question] for general queries."
    await client.room_send(
        room_id=room.room_id,
        message_type="m.room.message",
        content={"msgtype": "m.text", "body": response},
    )


async def handle_info_command(room, event):
    # Extract the user ID and substance name from the event
    user_id = event.sender
    substance_name = event.body.split("\info ")[1].strip()

    # Fetching the information card
    data_chat = fetch_new_chat_id_from_psygpt(substance_name)
    if not data_chat:
        await client.room_send(
            room_id=room.room_id,
            message_type="m.room.message",
            content={
                "msgtype": "m.text",
                "body": "Sorry, I couldn't fetch the chat ID. Please try again later.",
            },
        )
        return

    data_question = fetch_dose_card_from_psygpt(
        substance_name, data_chat["data"]["chat_id"]
    )
    if not data_question:
        await client.room_send(
            room_id=room.room_id,
            message_type="m.room.message",
            content={
                "msgtype": "m.text",
                "body": (
                    "Sorry, I couldn't fetch the information. Please try again later."
                ),
            },
        )
        return

    # Format the reply
    reply_text = data_question["data"]["assistant"]
    print(reply_text)
    try:
        await client.room_send(
            room_id=room.room_id,
            message_type="m.room.message",
            content={"msgtype": "m.text", "body": reply_text},
        )
    except Exception as e:
        print(f"Error sending message: {e}")


# Placeholder for /ask command
async def handle_ask_command(room, event):
    # Extract the user ID and substance name from the event
    user_id = event.sender
    substance_name = event.body.split("\\ask ")[1].strip()

    # Fetching the information card
    data_chat = fetch_new_chat_id_from_psygpt(substance_name)
    if not data_chat:
        await client.room_send(
            room_id=room.room_id,
            message_type="m.room.message",
            content={
                "msgtype": "m.text",
                "body": "Sorry, I couldn't fetch the chat ID. Please try again later.",
            },
        )
        return

    data_question = fetch_question_from_psygpt(
        substance_name, data_chat["data"]["chat_id"]
    )
    if not data_question:
        await client.room_send(
            room_id=room.room_id,
            message_type="m.room.message",
            content={
                "msgtype": "m.text",
                "body": (
                    "Sorry, I couldn't fetch the information. Please try again later."
                ),
            },
        )
        return

    # Format the reply
    reply_text = data_question["data"]["assistant"]
    print(reply_text)
    try:
        await client.room_send(
            room_id=room.room_id,
            message_type="m.room.message",
            content={"msgtype": "m.text", "body": reply_text},
        )
    except Exception as e:
        print(f"Error sending message: {e}")


async def main():
    global client
    client = AsyncClient(MATRIX_HOMESERVER, MATRIX_USER_ID)
    await client.login(MATRIX_PASSWORD)
    client.add_event_callback(message_callback, RoomMessageText)

    await client.sync_forever(timeout=30000)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())

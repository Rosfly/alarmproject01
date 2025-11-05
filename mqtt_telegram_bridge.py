#!/usr/bin/env python3
"""
MQTT Last Will and Testament (LWT) to Telegram Bot Forwarder

This script subscribes to MQTT status topics, monitors device LWT messages,
and forwards offline notifications to a Telegram bot.

Usage:
    1. Install dependencies:
       sudo dnf install python3-paho-mqtt python3-requests
       OR
       pip install paho-mqtt requests

    2. Set up Telegram bot:
       - Talk to @BotFather on Telegram
       - Create a new bot: /newbot
       - Copy the bot token
       - Start a chat with your bot
       - Get your chat ID by visiting:
         https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates

    3. Configure this script:
       - Set TELEGRAM_BOT_TOKEN
       - Set TELEGRAM_CHAT_ID
       - Optionally modify MQTT settings

    4. Run the script:
       python3 mqtt_lwt_telegram_bot.py
"""
import os
import paho.mqtt.client as mqtt
import requests
import json
import time
from datetime import datetime

# ============================================================================
# CONFIGURATION - MODIFY THESE VALUES
# ============================================================================


# MQTT Broker Configuration
#MQTT_BROKER = "broker.hivemq.com"
#MQTT_PORT = 1883
#MQTT_TOPIC_STATUS = "devices/IoT_device_365/status"  # LWT topic
#MQTT_TOPIC_ALIVE = "devices/IoT_device_365/alive"    # Heartbeat topic (optional)
MQTT_CLIENT_ID = "mqtt_lwt_telegram_monitor"

# Configuration from environment variables
MQTT_BROKER = os.getenv('MQTT_BROKER', 'broker.hivemq.com')
MQTT_PORT = int(os.getenv('MQTT_PORT', '1883'))
MQTT_TOPIC_STATUS = os.getenv('MQTT_TOPIC_STATUS', 'devices/IoT_device_365/status')  # Your LWT topic
MQTT_TOPIC_ALIVE = os.getenv('MQTT_TOPIC_ALIVE', 'devices/IoT_device_365/alive')  # RTC
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')



# Monitoring Configuration
MONITOR_ALIVE = True  # Set to True to also monitor alive messages
NOTIFY_ONLINE = True  # Set to True to get notified when device comes online

# ============================================================================
# TELEGRAM BOT FUNCTIONS
# ============================================================================

def send_telegram_message(message, parse_mode="HTML"):
    """
    Send a message to Telegram using the bot API.

    Args:
        message (str): Message text to send
        parse_mode (str): Message formatting (HTML or None)

    Returns:
        bool: True if successful, False otherwise
    """
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
    }

    if parse_mode:
        payload["parse_mode"] = parse_mode

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        print(f"Failed to send Telegram message: {e}")
        # Try again without formatting if it fails
        if parse_mode:
            print("Retrying without formatting...")
            payload.pop("parse_mode", None)
            try:
                response = requests.post(url, json=payload, timeout=10)
                response.raise_for_status()
                return True
            except:
                pass
        return False


def format_offline_message(device_id, reason, timestamp):
    """
    Format an offline notification message for Telegram.

    Args:
        device_id (str): Device identifier
        reason (str): Disconnection reason
        timestamp (str): Current timestamp

    Returns:
        str: Formatted message
    """
    message = f"🔴 <b>Device Offline Alert</b>\n\n"
    message += f"<b>Device:</b> <code>{device_id}</code>\n"
    message += f"<b>Status:</b> Offline\n"
    message += f"<b>Reason:</b> {reason}\n"
    message += f"<b>Time:</b> {timestamp}\n\n"
    message += "⚠️ The device has lost connection unexpectedly."

    return message


def format_online_message(device_id, timestamp):
    """
    Format an online notification message for Telegram.

    Args:
        device_id (str): Device identifier
        timestamp (str): Current timestamp

    Returns:
        str: Formatted message
    """
    message = f"🟢 <b>Device Online</b>\n\n"
    message += f"<b>Device:</b> <code>{device_id}</code>\n"
    message += f"<b>Status:</b> Online\n"
    message += f"<b>Time:</b> {timestamp}\n\n"
    message += "✅ The device has reconnected successfully."

    return message


def format_alive_message(device_id, rtc_time, uptime_sec):
    """
    Format an alive/heartbeat notification message for Telegram.

    Args:
        device_id (str): Device identifier
        rtc_time (str): RTC timestamp from device
        uptime_sec (int): Device uptime in seconds

    Returns:
        str: Formatted message
    """
    hours = uptime_sec // 3600
    minutes = (uptime_sec % 3600) // 60
    seconds = uptime_sec % 60
    uptime_str = f"{hours}h {minutes}m {seconds}s"

    message = f"💚 <b>Device Heartbeat</b>\n\n"
    message += f"<b>Device:</b> <code>{device_id}</code>\n"
    message += f"<b>RTC Time:</b> {rtc_time}\n"
    message += f"<b>Uptime:</b> {uptime_str}\n"

    return message


# ============================================================================
# MQTT CLIENT FUNCTIONS
# ============================================================================

def on_connect(client, userdata, flags, rc, properties=None):
    """
    MQTT connection callback.
    """
    if rc == 0:
        print(f"✅ Connected to MQTT broker: {MQTT_BROKER}:{MQTT_PORT}")

        # Subscribe to status topic (LWT)
        client.subscribe(MQTT_TOPIC_STATUS, qos=1)
        print(f"📡 Subscribed to status topic: {MQTT_TOPIC_STATUS}")

        # Optionally subscribe to alive topic
        if MONITOR_ALIVE:
            client.subscribe(MQTT_TOPIC_ALIVE, qos=1)
            print(f"📡 Subscribed to alive topic: {MQTT_TOPIC_ALIVE}")

        # Startup notification disabled to avoid spam on reconnections
        # The monitor is ready when subscriptions are complete
        print(f"✅ Monitor ready at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        print(f"❌ Connection failed with code {rc}")


def on_disconnect(client, userdata, rc, properties=None):
    """
    MQTT disconnection callback.
    """
    if rc != 0:
        print(f"⚠️ Unexpected disconnection from broker (code: {rc})")
    else:
        print("🔌 Disconnected from broker")


def on_message(client, userdata, msg):
    """
    MQTT message callback - processes incoming messages.
    """
    topic = msg.topic
    payload = msg.payload.decode('utf-8')
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    print(f"\n📩 Message received on '{topic}':")
    print(f"   Payload: {payload}")

    try:
        data = json.loads(payload)

        # Handle status topic (online/offline)
        if topic == MQTT_TOPIC_STATUS:
            device_id = data.get('device_id', 'Unknown')
            status = data.get('status', 'Unknown')

            if status == 'offline':
                reason = data.get('reason', 'unknown')
                print(f"🔴 Device offline detected: {device_id} - Reason: {reason}")

                # Send Telegram notification
                message = format_offline_message(device_id, reason, timestamp)
                if send_telegram_message(message):
                    print("✅ Offline notification sent to Telegram")
                else:
                    print("❌ Failed to send Telegram notification")

            elif status == 'online' and NOTIFY_ONLINE:
                print(f"🟢 Device online detected: {device_id}")

                # Send Telegram notification
                message = format_online_message(device_id, timestamp)
                if send_telegram_message(message):
                    print("✅ Online notification sent to Telegram")
                else:
                    print("❌ Failed to send Telegram notification")

            elif status == 'Motion detection confirmed':
                print(f"🚨 Motion detection confirmed: {device_id}")
                device_timestamp = data.get('timestamp', timestamp)

                # Send Telegram notification
                message = f"🚨 <b>Motion Detection Alert</b>\n\n"
                message += f"<b>Device:</b> <code>{device_id}</code>\n"
                message += f"<b>Status:</b> Motion confirmed\n"
                message += f"<b>Time:</b> {device_timestamp}\n\n"
                message += "⚠️ Unauthorized motion detected in monitored area!"

                if send_telegram_message(message):
                    print("✅ Motion alert sent to Telegram")
                else:
                    print("❌ Failed to send Telegram notification")

            elif status == 'No motion':
                print(f"ℹ️ No motion detected: {device_id}")
                # Optional: Uncomment to send "No motion" notifications
                # device_timestamp = data.get('timestamp', timestamp)
                # message = f"ℹ️ <b>No Motion</b>\n\n"
                # message += f"<b>Device:</b> <code>{device_id}</code>\n"
                # message += f"<b>Time:</b> {device_timestamp}\n\n"
                # message += "Initial motion was a false alarm."
                # send_telegram_message(message)

            elif status == 'Motion detected':
                # Initial motion detection (not yet confirmed)
                print(f"🟡 Initial motion detection: {device_id}")
                device_timestamp = data.get('timestamp', timestamp)

                # Send Telegram notification for initial detection
                message = f"🟡 <b>Motion Detected</b>\n\n"
                message += f"<b>Device:</b> <code>{device_id}</code>\n"
                message += f"<b>Status:</b> Motion detected (awaiting confirmation)\n"
                message += f"<b>Time:</b> {device_timestamp}\n\n"
                message += "Monitoring for continued movement..."

                if send_telegram_message(message):
                    print("✅ Initial motion alert sent to Telegram")
                else:
                    print("❌ Failed to send Telegram notification")

            else:
                # Catch-all for unknown status messages
                print(f"⚠️ Unknown status received: '{status}' from {device_id}")
                print(f"   Full payload: {payload}")

        # Handle alive topic (heartbeat)
        elif topic == MQTT_TOPIC_ALIVE and MONITOR_ALIVE:
            device_id = data.get('device_id', 'Unknown')
            rtc_time = data.get('rtc_time', 'Unknown')
            uptime_sec = data.get('uptime_sec', 0)

            print(f"💚 Device heartbeat: {device_id} - Uptime: {uptime_sec}s")

            # Optional: Only send heartbeat notification every N minutes
            # For now, we just log it (uncomment below to send to Telegram)
            # message = format_alive_message(device_id, rtc_time, uptime_sec)
            # send_telegram_message(message)

    except json.JSONDecodeError:
        print(f"⚠️ Failed to parse JSON payload: {payload}")
    except Exception as e:
        print(f"❌ Error processing message: {e}")


# ============================================================================
# MAIN FUNCTION
# ============================================================================

def main():
    """
    Main entry point - sets up MQTT client and starts monitoring.
    """
    print("=" * 60)
    print("MQTT Last Will and Testament (LWT) to Telegram Monitor")
    print("=" * 60)

    # Validate configuration
    if TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ ERROR: Please configure TELEGRAM_BOT_TOKEN")
        print("   Get your bot token from @BotFather on Telegram")
        return

    if TELEGRAM_CHAT_ID == "YOUR_CHAT_ID_HERE":
        print("❌ ERROR: Please configure TELEGRAM_CHAT_ID")
        print("   Visit: https://api.telegram.org/bot<TOKEN>/getUpdates")
        return

    # Create MQTT client
    print(f"\n🔧 Initializing MQTT client...")
    client = mqtt.Client(
        client_id=MQTT_CLIENT_ID,
        protocol=mqtt.MQTTv311,
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2
    )

    # Set callbacks
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message

    # Connect to broker
    print(f"🔌 Connecting to {MQTT_BROKER}:{MQTT_PORT}...")
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return

    # Start the loop
    print(f"\n👀 Monitoring LWT messages... (Press Ctrl+C to exit)\n")
    print("-" * 60)

    try:
        client.loop_forever()
    except KeyboardInterrupt:
        print("\n\n⏹️ Shutting down...")

        # Send shutdown notification
        shutdown_msg = f"🛑 <b>MQTT LWT Monitor Stopped</b>\n\n"
        shutdown_msg += f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        send_telegram_message(shutdown_msg)

        client.disconnect()
        print("✅ Disconnected cleanly")


if __name__ == "__main__":
    main()

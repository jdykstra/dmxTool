import threading
import time

import serial

# Update this to match your dongle's usual path, or enter a port at startup.
DEFAULT_DMX_PORT = '/dev/cu.usbserial-B0028467'
DMX_CHANNEL_COUNT = 512
DMX_START_CODE = 0
DMX_REFRESH_INTERVAL = 0.025
SERIAL_RETRY_INTERVAL = 1.0


def send_dmx_frame(ser, packet):
    ser.break_condition = True
    time.sleep(0.0001)
    ser.break_condition = False
    time.sleep(0.00001)
    ser.write(packet)


def sender_loop(port, packet, packet_lock, stop_event):
    while not stop_event.is_set():
        try:
            with serial.Serial(port, baudrate=250000, stopbits=2) as ser:
                while not stop_event.is_set():
                    with packet_lock:
                        frame = bytes(packet)
                    send_dmx_frame(ser, frame)
                    time.sleep(DMX_REFRESH_INTERVAL)
        except serial.SerialException as exc:
            print(f'Unable to send on {port}: {exc}')
            if stop_event.wait(SERIAL_RETRY_INTERVAL):
                return


def prompt_port():
    prompt = f'Enter serial port path, press Enter for {DEFAULT_DMX_PORT}, or q to quit: '

    while True:
        raw = input(prompt).strip()
        if not raw:
            return DEFAULT_DMX_PORT
        if raw.lower() == 'q':
            return None
        return raw


def prompt_channel():
    while True:
        raw = input('Enter DMX channel (1-512) or q to quit: ').strip().lower()
        if raw == 'q':
            return None

        try:
            channel = int(raw)
        except ValueError:
            print('Invalid channel. Enter a decimal number from 1 to 512, or q to quit.')
            continue

        if 1 <= channel <= 512:
            return channel - 1

        print('Channel out of range. Enter a decimal number from 1 to 512.')


def prompt_value(channel_index):
    prompt = (
        f'Channel {channel_index + 1}: enter value (0-255), '
        'c to change channel, or q to quit: '
    )

    while True:
        raw = input(prompt).strip().lower()
        if raw in {'c', 'q'}:
            return raw

        try:
            value = int(raw)
        except ValueError:
            print('Invalid value. Enter a decimal number from 0 to 255, c, or q.')
            continue

        if 0 <= value <= 255:
            return value

        print('Value out of range. Enter a decimal number from 0 to 255.')


def input_loop(packet, packet_lock, stop_event):
    while not stop_event.is_set():
        channel_index = prompt_channel()
        if channel_index is None:
            stop_event.set()
            return

        while not stop_event.is_set():
            result = prompt_value(channel_index)
            if result == 'c':
                break
            if result == 'q':
                stop_event.set()
                return

            with packet_lock:
                packet[channel_index + 1] = result

            print(f'Staged channel {channel_index + 1} value {result}.')


def main():
    port = prompt_port()
    if port is None:
        return

    packet = bytearray(DMX_CHANNEL_COUNT + 1)
    packet[0] = DMX_START_CODE
    packet_lock = threading.Lock()
    stop_event = threading.Event()
    sender = threading.Thread(
        target=sender_loop,
        args=(port, packet, packet_lock, stop_event),
        daemon=True,
    )
    sender.start()

    try:
        input_loop(packet, packet_lock, stop_event)
    finally:
        stop_event.set()
        sender.join()


if __name__ == '__main__':
    main()

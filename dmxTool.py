import select
import sys
import threading
import time

import serial

# Update this to match your dongle's usual path, or enter a port at startup.
DEFAULT_DMX_PORT = '/dev/cu.usbserial-B0028467'
DMX_CHANNEL_COUNT = 512
DMX_START_CODE = 0
DMX_REFRESH_INTERVAL = 0.025
SERIAL_RETRY_INTERVAL = 1.0
LED_CONTROLLER_SECTION_COUNT = 8
LED_SECTION_CHANNEL_COUNT = 4
LED_CONTROLLER_CHANNEL_COUNT = LED_CONTROLLER_SECTION_COUNT * LED_SECTION_CHANNEL_COUNT
LED_SECTION_COLORS = ('Red', 'Green', 'Blue', 'White')
LED_RAMP_DURATION = 1.0
STATUS_LINE_SUFFIX = ' | q + Enter to stop'


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


def prompt_mode():
    prompt = 'Choose mode: m for manual control, t for LED tape test, or q to quit: '

    while True:
        raw = input(prompt).strip().lower()
        if raw in {'m', 't', 'q'}:
            return raw

        print('Invalid mode. Enter m, t, or q.')


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


def prompt_controller_start_address():
    max_start_address = DMX_CHANNEL_COUNT - LED_CONTROLLER_CHANNEL_COUNT + 1
    prompt = (
        f'Enter LED controller starting DMX address (1-{max_start_address}) '
        'or q to quit: '
    )

    while True:
        raw = input(prompt).strip().lower()
        if raw == 'q':
            return None

        try:
            address = int(raw)
        except ValueError:
            print(
                f'Invalid starting address. Enter a decimal number from 1 to '
                f'{max_start_address}, or q to quit.'
            )
            continue

        if 1 <= address <= max_start_address:
            return address

        print(
            f'Starting address out of range. Enter a decimal number from 1 to '
            f'{max_start_address}.'
        )


def prompt_controller_test_scope():
    prompt = 'Test one section or all sections? Enter 1, a, or q to quit: '

    while True:
        raw = input(prompt).strip().lower()
        if raw in {'1', 'a', 'q'}:
            return raw

        print('Invalid choice. Enter 1, a, or q.')


def prompt_controller_section_number():
    prompt = f'Enter section number (1-{LED_CONTROLLER_SECTION_COUNT}) or q to quit: '

    while True:
        raw = input(prompt).strip().lower()
        if raw == 'q':
            return None

        try:
            section_number = int(raw)
        except ValueError:
            print(
                f'Invalid section. Enter a decimal number from 1 to '
                f'{LED_CONTROLLER_SECTION_COUNT}, or q to quit.'
            )
            continue

        if 1 <= section_number <= LED_CONTROLLER_SECTION_COUNT:
            return section_number

        print(
            f'Section out of range. Enter a decimal number from 1 to '
            f'{LED_CONTROLLER_SECTION_COUNT}.'
        )


def controller_section_addresses(start_address, section_number):
    section_offset = (section_number - 1) * LED_SECTION_CHANNEL_COUNT
    section_start = start_address + section_offset
    return [section_start + offset for offset in range(LED_SECTION_CHANNEL_COUNT)]


def clear_controller_channels(packet, packet_lock, start_address):
    with packet_lock:
        for address in range(start_address, start_address + LED_CONTROLLER_CHANNEL_COUNT):
            packet[address] = 0


def set_controller_test_value(packet, packet_lock, start_address, active_address, value):
    with packet_lock:
        for address in range(start_address, start_address + LED_CONTROLLER_CHANNEL_COUNT):
            packet[address] = 0
        packet[active_address] = value


def show_test_status(start_address, section_number, color_name, address, ramp_name, value):
    end_address = start_address + LED_CONTROLLER_CHANNEL_COUNT - 1
    message = (
        f'\rController {start_address}-{end_address} | Section {section_number} | '
        f'{color_name:<5} | DMX {address:>3} | {ramp_name:<4} | Value {value:>3}'
        f'{STATUS_LINE_SUFFIX}'
    )
    sys.stdout.write(message.ljust(120))
    sys.stdout.flush()


def clear_status_line():
    sys.stdout.write('\r' + (' ' * 120) + '\r')
    sys.stdout.flush()


def poll_stop_command():
    ready, _, _ = select.select([sys.stdin], [], [], 0)
    if not ready:
        return False

    raw = sys.stdin.readline().strip().lower()
    if not raw:
        return False

    return raw == 'q'


def ramp_controller_channel(packet, packet_lock, start_address, section_number, color_name, address):
    step_count = max(1, round(LED_RAMP_DURATION / DMX_REFRESH_INTERVAL))
    step_interval = LED_RAMP_DURATION / step_count

    for step in range(step_count + 1):
        value = round((255 * step) / step_count)
        set_controller_test_value(packet, packet_lock, start_address, address, value)
        show_test_status(start_address, section_number, color_name, address, 'Up', value)
        if poll_stop_command():
            return True
        if step < step_count:
            time.sleep(step_interval)

    for step in range(step_count + 1):
        value = round((255 * (step_count - step)) / step_count)
        set_controller_test_value(packet, packet_lock, start_address, address, value)
        show_test_status(start_address, section_number, color_name, address, 'Down', value)
        if poll_stop_command():
            return True
        if step < step_count:
            time.sleep(step_interval)

    return False


def led_tape_test_loop(packet, packet_lock):
    start_address = prompt_controller_start_address()
    if start_address is None:
        return

    while True:
        scope = prompt_controller_test_scope()
        if scope == 'q':
            return

        if scope == '1':
            section_number = prompt_controller_section_number()
            if section_number is None:
                continue
            sections = [section_number]
        else:
            sections = list(range(1, LED_CONTROLLER_SECTION_COUNT + 1))

        clear_controller_channels(packet, packet_lock, start_address)
        print('LED tape test running.')

        return_to_scope = False

        try:
            while not return_to_scope:
                for section_number in sections:
                    section_addresses = controller_section_addresses(start_address, section_number)
                    for color_name, address in zip(LED_SECTION_COLORS, section_addresses, strict=True):
                        if ramp_controller_channel(
                            packet,
                            packet_lock,
                            start_address,
                            section_number,
                            color_name,
                            address,
                        ):
                            return_to_scope = True
                            break
                    if return_to_scope:
                        break
        finally:
            clear_controller_channels(packet, packet_lock, start_address)
            clear_status_line()
            print('LED tape test stopped.')


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
        while not stop_event.is_set():
            mode = prompt_mode()
            if mode == 'q':
                return

            if mode == 'm':
                input_loop(packet, packet_lock, stop_event)
            else:
                led_tape_test_loop(packet, packet_lock)
    finally:
        stop_event.set()
        sender.join()


if __name__ == '__main__':
    main()

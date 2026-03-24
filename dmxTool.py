import serial
import time

# Update this to match your dongle's usual path, or enter a port at startup.
DEFAULT_DMX_PORT = '/dev/cu.usbserial-B0028467'

def send_dmx(port, values):
    # DMX512 requires 250kbps, 8 data bits, 2 stop bits
    with serial.Serial(port, baudrate=250000, stopbits=2) as ser:
        # Send BREAK (at least 88us low)
        ser.break_condition = True
        time.sleep(0.0001) 
        ser.break_condition = False
        
        # Send Mark After Break (MAB)
        time.sleep(0.00001)
        
        # Start code (0x00 for dimmers/levels) + 512 channels
        packet = bytearray([0]) + bytearray(values)
        ser.write(packet)


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


def main():
    port = prompt_port()
    if port is None:
        return

    channels = [0] * 512

    while True:
        channel_index = prompt_channel()
        if channel_index is None:
            break

        while True:
            result = prompt_value(channel_index)
            if result == 'c':
                break
            if result == 'q':
                return

            channels[channel_index] = result
            try:
                send_dmx(port, channels)
            except serial.SerialException as exc:
                print(f'Unable to send on {port}: {exc}')
                port = prompt_port()
                if port is None:
                    return
                continue

            print(f'Sent channel {channel_index + 1} value {result} on {port}.')


if __name__ == '__main__':
    main()

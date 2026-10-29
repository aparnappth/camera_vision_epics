"""Touch-controlled RGB LED status indicator."""

import time
from gpiozero import DigitalInputDevice, RGBLED

# GPIO configuration
touch = DigitalInputDevice(17, pull_up=False)
led = RGBLED(red=22, green=23, blue=24, pwm=True)

# LED colours
GREEN = (0, 1, 0)
YELLOW = (1, 0.5, 0)
RED = (1, 0, 0)

touch_start = None
current_color = None

try:
    while True:

        if touch.is_active:

            if touch_start is None:
                touch_start = time.monotonic()

            duration = time.monotonic() - touch_start

            if duration > 6:
                color = RED
                status = "FAULT"

            elif duration >= 1:
                color = YELLOW
                status = "WARNING"

            else:
                color = GREEN
                status = "NORMAL"

        else:
            touch_start = None
            color = GREEN
            status = "NORMAL"

        # Update LED only when the colour changes
        if color != current_color:
            led.color = color
            current_color = color
            print(f"Status: {status}")

        time.sleep(0.05)

except KeyboardInterrupt:
    print("\nProgram stopped")

finally:
    led.off()
    led.close()
    touch.close()

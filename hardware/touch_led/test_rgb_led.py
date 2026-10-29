
"""Test RGB LED connected to Raspberry Pi GPIO."""

from gpiozero import RGBLED
from time import sleep

# BCM GPIO numbering
led = RGBLED(
    red=22,
    green=23,
    blue=24,
    active_high=True,
    pwm=True
)

try:
    while True:
        print("RED")
        led.color = (1, 0, 0)
        sleep(2)

        print("GREEN")
        led.color = (0, 1, 0)
        sleep(2)

        print("BLUE")
        led.color = (0, 0, 1)
        sleep(2)

        print("YELLOW")
        led.color = (1.0, 0.5, 0.0)
        sleep(2)

        print("OFF")
        led.off()
        sleep(2)

except KeyboardInterrupt:
    print("\nLED test stopped")

finally:
    led.close()

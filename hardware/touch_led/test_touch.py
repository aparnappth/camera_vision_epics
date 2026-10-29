from gpiozero import DigitalInputDevice
from signal import pause

touch = DigitalInputDevice(17, pull_up=False)

print("Touch sensor ready")

touch.when_activated = lambda: print("Touched")
touch.when_deactivated = lambda: print("Released")

pause()

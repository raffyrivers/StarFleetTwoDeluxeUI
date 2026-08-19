from pathlib import Path

import pygame

# Initialize the mixer module
pygame.mixer.init()

# Load the sound next to this script, regardless of the current working directory.
sound = pygame.mixer.Sound(Path(__file__).with_name("Carrier5.wav"))

# Play the sound
sound.play()

# Dynamically wait until the audio finishes playing
while pygame.mixer.get_busy():
    pygame.time.Clock().tick(10)  
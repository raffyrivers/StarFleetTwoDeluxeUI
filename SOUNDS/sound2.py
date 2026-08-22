import numpy as np
import sounddevice as sd

SR = 44100
DURATION = 30
VOLUME = 0.40

t = np.arange(int(SR * DURATION)) / SR

# -----------------------------------------
# Stable siren cycle
# -----------------------------------------

cycle = 9.0
p = (t % cycle) / cycle

# 65% rise, 35% fall
shape = np.where(
    p < 0.65,
    p / 0.65,
    1 - (p - 0.65) / 0.35
)

# Smooth curve
shape = shape * shape * (3 - 2 * shape)

# -----------------------------------------
# Frequency movement
# -----------------------------------------

freq = 135 + 210 * shape

# Continuous phase
phase = np.cumsum(freq) * (2 * np.pi / SR)

# -----------------------------------------
# Horn / siren harmonics
# -----------------------------------------

signal = (
    1.25 * np.sin(phase)
    + 0.65 * np.sin(2 * phase)
    + 0.35 * np.sin(3 * phase)
    + 0.15 * np.sin(4 * phase)
    + 0.40 * np.sin(phase / 2)
)

# -----------------------------------------
# Controlled mechanical texture
# -----------------------------------------

signal *= (
    1
    + 0.025 * np.sin(2 * np.pi * 0.12 * t)
    + 0.015 * np.sin(2 * np.pi * 0.23 * t)
)

# -----------------------------------------
# Louder at the peak
# -----------------------------------------

volume_curve = 0.55 + 0.75 * shape
signal *= volume_curve

# -----------------------------------------
# Small amount of industrial air noise
# -----------------------------------------

noise = np.random.randn(len(signal))
noise = np.convolve(
    noise,
    np.ones(500) / 500,
    mode="same"
)

signal += noise * 0.012

# -----------------------------------------
# Warm aggressive saturation
# -----------------------------------------

signal = np.tanh(signal * 3.5)

# -----------------------------------------
# Normalize
# -----------------------------------------

signal /= np.max(np.abs(signal))
signal *= VOLUME

# Fade edges
fade = int(SR * 1.0)

signal[:fade] *= np.linspace(0, 1, fade)
signal[-fade:] *= np.linspace(1, 0, fade)

print("Playing emergency siren...")
 
sd.play(signal.astype(np.float32), SR)
sd.wait()
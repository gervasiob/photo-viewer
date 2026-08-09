# Photo Viewer

A Raspberry Pi photo frame (digital picture frame) driven by a rotary encoder + push-button.
Displays all photos from a folder in full-screen, preserving aspect ratio (images are only
shrunk, never stretched, never cropped). Includes a status LED that blinks while running.

Built with **pygame** (display) + **gpiozero** (encoder / button / LED).

---

## Features

- Full-screen slideshow of `.jpg` / `.jpeg` / `.png` photos
- Aspect-ratio safe:
  - images bigger than the screen are shrunk to fit
  - smaller images are shown at their original size
  - images are centered on a black background (letterbox)
- **Rotary encoder** for prev / next
- **Push-button** (same knob) to toggle PLAY / PAUSE
- **Status LED** (blinking while app is running)
- Auto-play slideshow with configurable interval
- Works **only with the knob** (no keyboard shortcuts for nav — only `Esc` to quit)
- Gracefully degrades when GPIO is unavailable (still runs on PC for testing — but
  navigation through the knob is disabled)

---

## Hardware

### Required

- Raspberry Pi (any model with GPIO)
- A display / monitor / TV connected to the Pi
- A rotary encoder with push-button (the classic KY-040 or equivalent)
- A status LED + a current-limiting resistor (220 Ω – 330 Ω)
- Some photos :)

### Wiring (BCM numbering)

| Component pin   | Raspberry Pi pin (BCM) |
| --------------- | ---------------------- |
| Encoder CLK     | **GPIO 17**            |
| Encoder DT      | **GPIO 18**            |
| Encoder SW      | **GPIO 27**            |
| Encoder GND     | GND (any, e.g. pin 14) |
| LED anode (+)   | **GPIO 22** (via 220Ω – 330Ω resistor) |
| LED cathode (−) | GND                    |

> You can change all pin assignments in the source code. See
> [Configuration](#configuration) below.

---

## Installation (Raspberry Pi)

### 1. Clone the repository

```bash
git clone https://github.com/gervasiob/photo-viewer.git
cd photo-viewer
```

### 2. Create a virtual environment and activate it

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
# system-level packages needed for pygame + gpiozero
sudo apt update
sudo apt install -y python3-pygame python3-gpiozero python3-lgpio

# Pillow (PIL) for image scaling
pip install pillow
```

> `python3-lgpio` is the **recommended** pin factory backend for modern Raspberry Pi OS
> (Bookworm and later). If gpiozero still complains about missing pin factories, also
> try installing `python3-rpi.gpio`.

### 4. Add your photos

The app looks for photos inside a `photos/` folder next to `main.py`. This folder is
**not tracked by git** (see `.gitignore`).

```bash
mkdir -p photos
# copy / symlink your photos into ./photos
```

Supported extensions (case-insensitive): `.jpg`, `.jpeg`, `.png`.
Photos are loaded in **alphabetical order** by filename.

### 5. Run it

```bash
python main.py
```

The app launches in **full-screen** mode. Press **Esc** to quit.

---

## Installation (development on PC / non-Pi)

You can also run it on your dev machine to preview the UI. The GPIO parts (encoder +
LED) will silently be disabled, but the slideshow itself still works.

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

pip install pygame pillow

python main.py
```

> On PC there is no rotary-encoder input, so you can only watch the first image and
> quit with `Esc`. For interactive testing, do it on the Raspberry Pi.

---

## Configuration

All configurable values live as constants near the top of the source files.

| Constant                  | File            | Default     | Meaning                                                      |
| ------------------------- | --------------- | ----------- | ------------------------------------------------------------ |
| `PHOTO_FOLDER`            | `main.py`       | `"photos"`  | Path (relative to `main.py`) where photos are read           |
| `STATUS_LED_PIN`          | `main.py`       | `22`        | BCM GPIO used for the status LED                             |
| `SLIDESHOW_INTERVAL`      | `main.py`       | `1000`      | Milliseconds between slides when auto-play is ON             |
| `SUPPORTED_EXTENSIONS`    | `main.py`       | `(".jpg", ".jpeg", ".png")` | File extensions loaded as photos               |
| `clk_pin` / `dt_pin` / `sw_pin` | `input_controller.py` (passed via `PhotoFrameController`) | `17`, `18`, `27` | BCM GPIOs for the encoder |
| `invert_rotation`         | `input_controller.py` (passed via `PhotoFrameController`) | `False` | Swap CW / CCW if the knob feels backwards |

To change the pins, edit the constants and restart the app.

---

## Controls

| Action                            | Effect                                                         |
| --------------------------------- | -------------------------------------------------------------- |
| Rotate encoder **counter-clockwise** | go to **previous** photo                                       |
| Rotate encoder **clockwise**      | go to **next** photo                                           |
| Press encoder knob                | toggle **PLAY / PAUSE** on the auto slideshow                  |
| `Esc` key                         | exit the application (GPIO is cleaned up, status LED goes off) |

If turning the knob navigates in the **opposite** direction, change
`invert_rotation=True` when constructing `PhotoFrameController` in `main.py`.

---

## Project structure

```
photo-viewer/
├── main.py                # Entry point: pygame loop, image loading, rendering
├── input_controller.py    # Rotary encoder + button input (gpiozero)
├── photos/                # Put your photos here (ignored by git)
├── .gitignore
└── README.md
```

- [main.py](file:///c:/Users/Gervasio/Documents/trae_projects/photo-viewer/main.py)
  - [Image scaling logic](file:///c:/Users/Gervasio/Documents/trae_projects/photo-viewer/main.py#L37-L70) — preserves aspect ratio, never upscales
  - [LED setup + shutdown](file:///c:/Users/Gervasio/Documents/trae_projects/photo-viewer/main.py#L105-L137)
  - [Slideshow + input polling loop](file:///c:/Users/Gervasio/Documents/trae_projects/photo-viewer/main.py#L139-L248)
- [input_controller.py](file:///c:/Users/Gervasio/Documents/trae_projects/photo-viewer/input_controller.py)
  - [EncoderController (gpiozero RotaryEncoder + Button)](file:///c:/Users/Gervasio/Documents/trae_projects/photo-viewer/input_controller.py#L71-L150)
  - [PhotoFrameController wrapper](file:///c:/Users/Gervasio/Documents/trae_projects/photo-viewer/input_controller.py#L12-L68)

---

## Troubleshooting

### `gpiozero.exc.BadPinFactory: Unable to load any default pin factory!`

gpiozero can't find a backend to drive the GPIO pins. Run this on the Pi:

```bash
sudo apt install -y python3-gpiozero python3-lgpio python3-rpi.gpio
```

If you still get the error, make sure you are running on **actual Raspberry Pi hardware**
(not Windows / a VM / a different Linux machine). The app will still launch without
GPIO, but the knob and LED will be disabled.

### LED doesn't light up

1. Double-check the anode/cathode orientation and the 220–330 Ω resistor.
2. Make sure `STATUS_LED_PIN` matches the BCM GPIO you actually wired.
3. Run a quick gpiozero test in a shell:
   ```python
   from gpiozero import LED
   led = LED(22)
   led.on()        # LED should turn on
   led.off()
   ```

### Rotation direction is inverted

Open `main.py` and change:

```python
controller = PhotoFrameController(invert_rotation=True)
```

### Photos look stretched / cropped

The scaling logic explicitly avoids stretching and cropping. If something looks wrong,
verify the photo file itself has the intended aspect ratio (some cameras / phones embed
a rotation EXIF flag without actually rotating the pixel data). If this becomes a
problem, adding an `ImageOps.exif_transpose(image)` call inside
[`load_and_scale_image`](file:///c:/Users/Gervasio/Documents/trae_projects/photo-viewer/main.py#L37-L70)
usually fixes it.

### Slideshow auto-play is too fast / too slow

Tune `SLIDESHOW_INTERVAL` in `main.py` (milliseconds).

---

## License

Use it as you like — build a nice photo frame for the people you love.

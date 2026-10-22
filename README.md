# ascart

ascart is a Python learning project for creating ASCII art from text, photos, GIFs, and videos. ASCII art uses characters such as `@`, `#`, `*`, and `.` to form pictures or stylized text.

The main purpose of this project is to understand how things work while building something practical. It will grow step by step, with an emphasis on learning Python, processing images, organizing code, and using Git and GitHub.

## Planned features

- Convert photos into ASCII art.
- Turn text into character-based banners.
- Convert GIF frames into animated ASCII art.
- Convert video frames into ASCII art.
- Run conversions from the terminal.
- Automatically fit image output to the terminal's available width and height, with an optional manual width setting.
- Automatically choose brightness-to-character mapping for light or dark terminal backgrounds when detection is available, with a manual background override and a documented fallback.
- Save ASCII art to a plain text file without terminal color codes.
- Accept a custom character palette, ordered from least visually dense to most dense.
- Optionally display characters in colors taken from the original image.

These features are planned and have not been implemented yet.

## Simple usage, optional controls

The aim is to make the basic conversion work with one command, while keeping extra controls optional:

```bash
ascart photo.jpg
```

Proposed options include:

```bash
ascart photo.jpg --color
ascart photo.jpg --output art.txt
ascart photo.jpg --width 100
ascart photo.jpg --chars " .:*#@"
ascart photo.jpg --background light
```

These examples describe the intended interface; the commands do not work yet.

Automatic inversion means reversing which characters represent each brightness level. For example, on a dark background, bright image regions can use dense characters such as `@`, while dark regions use spaces or dots. On a light background, the mapping is reversed. Terminal background detection is not always reliable, so users will be able to choose the background manually. Color mode will need separate checks to ensure that characters provide enough coverage to show the image colors.

## First milestone

Our first goal is to convert a single photo into ASCII art and print it in the terminal. The conversion will follow these steps:

1. Open the photo.
2. Resize it to a suitable width and adjust its proportions for terminal characters.
3. Convert it to grayscale so each pixel has a brightness value.
4. Map each brightness value to an ASCII character.
5. Arrange the characters into rows and print the result.

Once this works, we will build on the same conversion logic to support GIFs and videos. Text banners will use a separate approach.

We will add the image features gradually: terminal fitting and text saving, then custom palettes, color output, and automatic background detection.

## Development notes

The project currently contains the basic file structure. Setup and usage instructions will be added as the program develops.

We will record development steps, explanations, and Git commit milestones in [the development log](docs/development-log.md).

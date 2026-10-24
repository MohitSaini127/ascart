# Credits and licensing

## License and credits

ascart's original source code and documentation are licensed under the [MIT License](../LICENSE), copyright (c) 2026 Mohit Saini. Third-party libraries, font designs, and images retain their own licenses and notices; ascart's license does not replace those terms.

Thanks to the projects that make ascart possible:

| Project | Used for | License information |
| --- | --- | --- |
| [Pillow](https://github.com/python-pillow/Pillow) | Reading images/GIFs, resizing frames, and drawing ASCII pictures. | [Pillow license and bundled notices](https://github.com/python-pillow/Pillow/blob/main/LICENSE) |
| [pyfiglet](https://github.com/pwaller/pyfiglet) | Rendering text banners with FIGlet fonts. | [pyfiglet MIT license](https://github.com/pwaller/pyfiglet/blob/main/LICENSE); font files can have additional notices. |
| [OpenCV / opencv-python-headless](https://github.com/opencv/opencv-python) | Decoding video and encoding silent MP4 output. | [Package, OpenCV, and bundled-component licensing](https://github.com/opencv/opencv-python#licensing) |
| [NumPy](https://numpy.org/) | Representing and converting video-frame pixels; installed with OpenCV. | [NumPy license](https://numpy.org/doc/stable/license.html); installed packages also include bundled-component notices. |

The banner fonts are credited in their font-file headers: `standard` was created by Glenn Chappell and Ian Chai; `slant` by Glenn Chappell, based on Standard; and `banner3` by Merlin Greywolf. Thanks also to their later contributors and the original FIGlet project. See [pyfiglet's font notes](https://github.com/pwaller/pyfiglet#faq) and the notices in the installed font files for details. Font files are supplied by pyfiglet rather than copied into this repository.

The bundled Tux image and its ASCII preview are based on the credited [CC0 sample](#sample-image). Its upstream credits and CC0 notice remain separate from ascart's MIT license.

Dependencies are installed separately. These credits acknowledge their authors; they do not replace the license texts and notices required when redistributing third-party software. A future bundled executable must retain the applicable library, font, and bundled-component notices.

## Sample image

The included sample is Tux, the Linux penguin, downloaded from [garrett/Tux](https://github.com/garrett/Tux). Its embedded metadata and the [source README](https://github.com/garrett/Tux/blob/main/README.md) state [CC0](https://creativecommons.org/publicdomain/zero/1.0/). Original illustration by Larry Ewing using GIMP; redrawn in Inkscape by Garrett LeSage, with refinement and cleanup credited upstream to IFo Hancroft. Only this PNG is bundled; supply your own files for GIF and video playback.

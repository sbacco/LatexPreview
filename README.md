# Latex Preview

Quickly and effortlessly preview Latex equations, save them to a `.gif`
file, or copy them to clipboard.

![screenshot in Ubuntu 20.04](screenshot.png)

## Dependencies

The following packages are _required_.
* `python3`
* `python3-gi`
* an installation of `latex`
* `dvigif` (`dvipng`)

The following package is necessary for copying the image to clipboard
and use the clipboard across multiple applications. It is however not
required, and if not installed the feature will simply be disabled.
* `xclip`

> __Note:__ At the moment, only environments with `nautilus` are 
> supported for the clipboard. Contributions are welcome so as to 
> expand this feature for other desktop environments.

## Installation

Simply clone this repository, or download it.

Make sure you extract everything in the same folder, then you can 
simply run the program:
```shell
$ python3 latexpreview.py
```

## Use

Every control is pretty much intuitive. Hover the mouse over a button
to know its shortcut and what it does.

You can also add __extra packages__ for latex that will be used by the
program (c.f. image above).

Hope you enjoy!

This tool a very simple tool for when you need to repeat basic audio editing on multiple audio files.
I wrote this mainly for processing many music files I **legally** downloaded from the internet, because I got annoyed at having to do the same basic tasks every time.

This README and this tool are still work in progress.


# Features
* Convert all audio files to MP3.
* Normalize the maximum peaks to a specific value.
* Remove silence at the beginning and end of audio file.


# Get the tool
## Compile yourself (recommended)
1. Download the repository.
2. Review the config file and adjust it to your needs.
3. Run `pyinstaller --clean normalize_audio.spec` from the repositories directory.
This will compile a completely portable executable.
Since the config file gets compiled into the executable, config changes *after compilation* will be ignored until you compile again and use that new executable.

## Grab latest release
You can grab the latest release [here](https://github.com/TheTimebreaker/Simple-Audio-normalizer-and-converter/releases/latest). This will use the default config.

# How to Use
You can drag-and-drop any audio file(s) onto the .bat file.
Preferably, you will compile the code yourself, which gives you a singular file you can copy/paste whereever you need it and where you can drag-and-drop your files onto aswell.

# Config documentation
* `GENERAL`: General settings.
    * `bitrate`: Target bitrate for final output.
* `normalize`
    * `targetdBFS`: Target peak amplitude for normalization (in dB / dBFS)
* `remove-silence`
    * `silence_threshold_dB`: dB amplitude, below which something is considered *silence*.
    * `keep_silence_seconds`: Maximum length of silence that will be kept (i.e. all silence will be cut out, except for the `keep_silence_seconds` duration next to the actual audio)
* `limits`: Limiters.
    * `ffmpeg`: Maximum amount of ffmpeg processes that are allowed to run in parallel.
    * `fileOperations`: Maximum amount of file operations (moving, deleteing, ...) that are allowed to run in parallel.

# Working on...
* Multiple output formats
* Cross-platform compilation, pyinstaller presets, and venv setup.


# License
This is free and unencumbered software released into the public domain.

Anyone is free to copy, modify, publish, use, compile, sell, or
distribute this software, either in source code form or as a compiled
binary, for any purpose, commercial or non-commercial, and by any
means.

In jurisdictions that recognize copyright laws, the author or authors
of this software dedicate any and all copyright interest in the
software to the public domain. We make this dedication for the benefit
of the public at large and to the detriment of our heirs and
successors. We intend this dedication to be an overt act of
relinquishment in perpetuity of all present and future rights to this
software under copyright law.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
OTHER DEALINGS IN THE SOFTWARE.

For more information, please refer to <https://unlicense.org/>

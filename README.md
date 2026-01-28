<h1 align="center">AVI to MP4</h1>

<p align="center">Easily convert large AVI video files to MP4 while preserving quality with no need for online upload.</p>

<p align="center">
  <a href="#download">Download</a> |
  <a href="#build-it-yourself">Build Yourself</a> |
  <a href="#usage">Usage</a> |
  <a href="#future-plans">Future Plans</a> |
  <a href="#known-issues">Known Issues</a> |
  <a href="#license-and-credits">License and Credits</a>
</p>

## Download
#### To use easily on Windows 11, download the latest version [here.](https://github.com/Woobat-8/AVI-to-MP4/releases) No setup needed!
*Note: Windows may flag the exe as Unsafe. This is because I [cannot afford code signing](https://codesigningstore.com/ov-code-signing-certificates) so the program is [unsigned.](https://learn.microsoft.com/en-us/windows/apps/develop/smart-app-control/code-signing-for-smart-app-control) Click "More" --> "Run Anyway" to use.*
#### View the latest version's release notes [here.](https://github.com/Woobat-8/AVI-to-MP4/releases/latest)

## Build It Yourself
>Building directly from the repository may result in building unfinished "WIP" versions, as I continually update the repository as I work. It is recommended to download the latest prebuilt version.
### Requirements
- Python 3.8 or later
- PyInstaller

### Steps
1. Clone or download the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Modify `avi_to_mp4_gui.py` as desired
4. Run directly as `python avi_to_mp4_gui.py`
5. Or build .exe file:
```
pyinstaller --onefile --windowed --name "AVI to MP4" --icon icon.ico --add-data "icon.ico;." --version-file version.txt avi_to_mp4_gui.py
```

## Usage
>FFmpeg is required. The program will automatically download it if you don't have it.
1. Download or Build
2. Select output folder
3. Select AVI file to convert (or drag and drop)

## Future Plans
>One or more of these will be included in the next **major** version.
### In no particular order:
- Windows 10 support
- File Size vs Quality mode
- Multi-file (queue) support
- General optimizations

## Known Issues
>If you've encountered an issue not listed here, report it [here.](https://github.com/Woobat-8/AVI-to-MP4/issues) This covers known issues or untested features I’m aware of and actively working on. Most will **likely** be fixed in the next version.
- Untested on systems using Intel Graphics (Intel QSV)
- Conversion using an AMD GPUs may lead to bloated MP4 file sizes

## License and Credits
#### Licensed under the [GPLv3 License.](https://github.com/Woobat-8/AVI-to-MP4/blob/main/LICENSE) Powered by [FFmpeg](https://ffmpeg.org/).
#### © 2026 [Woobat8](https://github.com/Woobat-8)

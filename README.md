# Fenn plugins

Three plugins for [Fenn](https://github.com/Geguchh024/nook) (formerly Nook), the floating notch for Windows.

| Plugin | What it does |
| --- | --- |
| [Activity](activity/) | Asks what you did every 15 minutes, logs it by category, and shows your day as a 24-hour grid and an HTML dashboard. |
| [Water](water/) | Reminds you to drink water every 15 minutes and tracks your daily intake against a goal. |
| [Shelf](shelf/) | Keeps the prompts and texts you paste often. Add, edit, delete, and copy any of them in one click. |

## Requirements

- Fenn (or Nook) on Windows
- Python 3.8 or newer, available as `python` on your PATH

## Install

**From the plugin site:** open the plugin's listing and click **Install**.

**By hand:**

1. Download this repository (Code → Download ZIP) and unzip it.
2. Copy the plugin folder (`activity`, `water` or `shelf`) into `%APPDATA%\Fenn\plugins\`.
   On older Nook installs, the folder is `%APPDATA%\Nook\plugins\`.
3. Restart Fenn. The tile appears in the notch.

## Your data

Each plugin saves its data in `%APPDATA%\Fenn\plugin-data\<plugin id>\`, never in the plugin folder.
Updating or reinstalling a plugin keeps your data.

## License

MIT. See [LICENSE](LICENSE).

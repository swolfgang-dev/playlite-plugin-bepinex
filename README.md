# BepInEx Installer for Playlite

Installs stable BepInEx 5 for Windows Unity Mono games. Lutris Integration is optional.

Choose **Install BepInEx…** in a game's plugin actions. Select the game executable or check **Add Lutris integration (copy the existing entry)**. The Lutris option is available when Lutris Integration 1.1.17 or newer and a supported existing Lutris action are present; otherwise choose an executable for files-only installation.

The installer detects x86/x64, downloads the matching official stable package, and extracts it beside the executable. Existing differing files, symlinks, and unsafe archives are rejected. When Lutris integration is unchecked, launcher configurations and Playlite actions are unchanged.

For games linked to Steam, files-only installation shows **Copy launch options** and **Open Steam Properties**. Paste `WINEDLLOVERRIDES="winhttp=n,b" %command%` into **General → Launch Options** after installation. Preserve existing options and add the override before their existing `%command%`, rather than duplicating it. The Properties button targets the linked Steam app (with a selector if multiple Steam actions exist), works through the desktop Steam protocol handler, and does not require debugging mode. Steam settings are never rewritten automatically. These options enable BepInEx for every Steam launch of that game.

When checked, it copies the existing Lutris configuration into a separate **[Game] - Modded** entry and adds **Play [Game] - Modded** to Playlite. The source is unchanged. Its prefix, runner, arguments, environment, and existing DLL overrides are preserved; `winhttp=n,b` is added to the copy. The working directory is the executable directory. Retries reuse the variant; newly installed files are rolled back if copying the Lutris entry fails.

Only stable Unity Mono is supported. IL2CPP, .NET/XNA, and native Linux builds are not offered. No game is launched by the installer. Run the modded entry once to generate BepInEx configuration, then place compatible mods under `BepInEx/plugins`.

Packages are fetched from [BepInEx releases](https://github.com/BepInEx/BepInEx/releases). GitHub asset digests are checked when available; the public-download fallback uses HTTPS when the API is rate limited. Upstream BepInEx is LGPL-2.1 and retains its licence files in the installed package. This plugin does not bundle BepInEx binaries.

[Official Wine/Proton setup](https://docs.bepinex.dev/articles/advanced/proton_wine.html).

Tests: `python3 -m unittest discover -s tests -v`. Package: `python3 tools/build_release.py`.

Choose **Uninstall BepInEx…** to remove the runtime, its modded Lutris entry, and the matching Playlite action. **Keep user data** is checked by default and preserves plugins, configuration, and patchers. Uncheck it to remove the entire BepInEx directory. Game files and Wine prefixes are retained. For Steam-linked games, the uninstall confirmation reminds you to remove the BepInEx `winhttp=n,b` launch-option override manually while preserving other DLL overrides, options, and `%command%`. Steam settings are not changed automatically. Older installations retrieve the original package to verify installed runtime files before removal.

**Include Configuration Manager** is enabled by default. It installs the official BepInEx 5 Mono package under `BepInEx/plugins/ConfigurationManager`, with checksum verification when available. Press F1 in-game to open it. Uncheck the option to install only BepInEx. Keeping user data on uninstall also keeps Configuration Manager.

**Open BepInEx plugins folder** opens the installed game’s `BepInEx/plugins` directory and creates it if missing.

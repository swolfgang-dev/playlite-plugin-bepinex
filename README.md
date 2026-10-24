# BepInEx Installer for Playlite

Installs stable BepInEx 5 for Windows Unity Mono games and BepInEx 6 bleeding-edge builds for Windows Unity IL2CPP games. Lutris Integration is optional.

Choose **Install BepInEx…** in a game's plugin actions. Select the game executable or check **Add Lutris integration (copy the existing entry)**. The Lutris option is available when Lutris Integration 1.1.17 or newer and a supported existing Lutris action are present; otherwise choose an executable for files-only installation.

The installer detects x86/x64, downloads the matching official package for the detected runtime, and extracts it beside the executable. Existing differing files, symlinks, and unsafe archives are rejected. When Lutris integration is unchecked, launcher configurations and Playlite actions are unchanged.

For games linked to Steam, files-only installation shows **Copy launch options** and **Open Steam Properties**. Paste `WINEDLLOVERRIDES="winhttp=n,b" %command%` into **General → Launch Options** after installation. Preserve existing options and add the override before their existing `%command%`, rather than duplicating it. The Properties button targets the linked Steam app (with a selector if multiple Steam actions exist), works through the desktop Steam protocol handler, and does not require debugging mode. Steam settings are never rewritten automatically. These options enable BepInEx for every Steam launch of that game.

When checked, it copies the existing Lutris configuration into a separate **[Game] - Modded** entry and adds **Play [Game] - Modded** to Playlite. The source is unchanged. Its prefix, runner, arguments, environment, and existing DLL overrides are preserved; `winhttp=n,b` is added to the copy. The working directory is the executable directory. Retries reuse the variant; newly installed files are rolled back if copying the Lutris entry fails.

Unity Mono and IL2CPP x86/x64 are supported. IL2CPP detection requires both GameAssembly.dll and matching global-metadata.dat. The dialog identifies the runtime and marks BepInEx 6 as bleeding-edge. .NET/XNA and native Linux builds are not offered. No game is launched by the installer. Run the modded entry once to generate BepInEx configuration, then place compatible mods under `BepInEx/plugins`.

Mono packages are fetched from [BepInEx releases](https://github.com/BepInEx/BepInEx/releases). IL2CPP packages use the latest matching build from the [official build index](https://builds.bepinex.dev/projects/bepinex_be); the resolved version and downloaded package SHA-256 are recorded. These builds do not provide an asset digest in the index, so their package contents are validated after HTTPS download. GitHub asset digests are checked when available; the public-download fallback uses HTTPS when the API is rate limited. Upstream BepInEx is LGPL-2.1 and retains its licence files in the installed package. This plugin does not bundle BepInEx binaries.

[Official Wine/Proton setup](https://docs.bepinex.dev/articles/advanced/proton_wine.html).

Tests: `python3 -m unittest discover -s tests -v`. Package: `python3 tools/build_release.py`.

Choose **Uninstall BepInEx…** to remove the runtime, its modded Lutris entry, and the matching Playlite action. **Keep user data** is checked by default and preserves plugins, configuration, and patchers. Uncheck it to remove the entire BepInEx directory. Game files and Wine prefixes are retained. For Steam-linked games, the uninstall confirmation reminds you to remove the BepInEx `winhttp=n,b` launch-option override manually while preserving other DLL overrides, options, and `%command%`. Steam settings are not changed automatically. Older installations retrieve the original package to verify installed runtime files before removal.

**Include Configuration Manager** is enabled by default for both Mono and IL2CPP. It installs the matching [official Configuration Manager](https://github.com/BepInEx/BepInEx.ConfigurationManager) package for BepInEx 5 Mono or BepInEx 6 IL2CPP under `BepInEx/plugins/ConfigurationManager`, with checksum verification when available. Press F1 in-game to open it. Uncheck the option to install only BepInEx. Keeping user data on uninstall also keeps Configuration Manager. IL2CPP support depends on the game retaining Unity IMGUI functionality; games with stripped IMGUI may require game-specific patches, which this installer does not apply. Missing text can indicate a missing Arial font in the Wine prefix.

**Open BepInEx plugins folder** opens the installed game’s `BepInEx/plugins` directory and creates it if missing.

If a game has no saved executable, the installer checks its installation folder for supported Windows Unity Mono or IL2CPP executables. A single match is selected automatically; multiple matches appear in a selector. Browse remains available when there is no match or a different executable is needed.

New Mono installations seed `HideManagerGameObject = true` to protect BepInEx plugins from games that remove the manager object. Existing BepInEx configuration is preserved.

For IL2CPP, the package includes its .NET runtime. The first game launch may take longer while BepInEx generates interop files; an actual game launch is required to establish compatibility. The installer does not launch the game. IL2CPP configuration is generated by BepInEx rather than seeded with Mono defaults.

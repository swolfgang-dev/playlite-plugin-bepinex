# BepInEx Installer for Playlite

Installs stable BepInEx 5 for Windows Unity Mono games launched through Lutris. Requires Lutris Integration with the `create_variant` and `launch_configuration` APIs.

Choose **Install BepInEx and add modded launch** in a game's plugin actions. The installer detects x86/x64 from the executable, downloads the matching official stable package, and extracts it beside the executable. Existing differing files, symlinks, and unsafe archives are rejected. Files created by this operation are rolled back if Lutris registration fails.

Creates a separate **[Game] - Modded** Lutris entry and appends a **Play [Game] - Modded** Playlite action. The original entry is not edited. The new entry copies its prefix, runner, arguments, and options, sets the working directory to the executable directory, and enables `winhttp=n,b` in the modded entry. Existing unrelated DLL overrides are preserved. Repeating installation reuses the plugin's variant without creating another entry.

Only stable Unity Mono is supported. IL2CPP, .NET/XNA, and native Linux builds are not offered. No game is launched by the installer. Run the modded entry once to generate BepInEx configuration, then place compatible mods under `BepInEx/plugins`.

Packages are fetched from [BepInEx releases](https://github.com/BepInEx/BepInEx/releases). GitHub asset digests are checked when available; the public-download fallback uses HTTPS when the API is rate limited. Upstream BepInEx is LGPL-2.1 and retains its licence files in the installed package. This plugin does not bundle BepInEx binaries.

[Official Wine/Proton setup](https://docs.bepinex.dev/articles/advanced/proton_wine.html).

Tests: `python3 -m unittest discover -s tests -v`. Package: `python3 tools/build_release.py`.

Choose **Uninstall BepInEx…** to remove the runtime, its modded Lutris entry, and the matching Playlite action. **Keep user data** is checked by default and preserves plugins, configuration, and patchers. Uncheck it to remove the entire BepInEx directory. Game files and Wine prefixes are retained. Older installations retrieve the original package to verify installed runtime files before removal.

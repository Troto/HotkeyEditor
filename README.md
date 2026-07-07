# Hotkey Editor
## What
This is the source code for this neat [hotkey editor site]([url](https://hotkeyeditor.pages.dev/)). 

The code is set up to use claude in a docker container, and was largely written by Claude.

## Why
I have always been a huge fan of optimizing hotkeys for video games but had never thought to just create my own hotkey editor instead of using in game interfaces.

Trying AoE2 for the first time, I found the in game editor to be rather lacking so I looked at other options. I was inspired by [this great idea](https://hotkeyeditor.com/) which made the process quite fun. It was a bit out of date though and so I decided to iterate on the idea myself.

This project is updated to work with newer versions of the game, and also includes extra features such as conflict detection of hotkeys (which is confusing in the in-game editor), and converting to the Dvorak keyboard layout.

Now this editor also supports Warcraft 3 and Starcraft 2.

## Acknowledgements
Thank you to everyone elses work that made this possible.

- [Patchnote-v2/hotkeyeditor.com](https://github.com/Patchnote-v2/hotkeyeditor.com) for the original inspiration.

- [crimsoncantab/aok-hotkeys](https://github.com/crimsoncantab/aok-hotkeys) for the AoE2 `.hkp` file format logic.

- [jcfieldsdev's Warcraft III Hotkey Editor](https://github.com/jcfieldsdev/warcraft3-hotkey-editor) for cross checking WC3 command names, cards, grouping and ability icons.

- [jcfieldsdev's StarCraft II Hotkey Editor](https://github.com/jcfieldsdev/starcraft2-hotkey-editor) for cross checking the SC2 melee unit roster.

- [BeedeBdoo/Sc2HotkeyData](https://github.com/BeedeBdoo/Sc2HotkeyData) for the SC2 hotkey-resolution approach and as a validation reference.

- Game info and icons from Age of Empires II: DE (Microsoft / Forgotten Empires), Warcraft III and StarCraft II (Blizzard Entertainment).

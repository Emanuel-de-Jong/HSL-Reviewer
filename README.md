# HSL-Reviewer
Improve your shapes and intuition in the game of Go.<br>
Tailered to your weaknesses from your own games. Using human supervised learning for questions and answers of your skill level.

## Disclaimer
I made this in a few hours for myself and decided last minute that others might find it useful too. The code is a mix of lightvector's KataGo python scripts, mine and ChatGPT's so it's a bit of a mess. I can't guarantee that it works correctly or even works at all on your system. That said, I'd apreciate any suggestions, bug reports or contributions.

## Prerequisites
1. A HSL model. At the time of writing, [this model](https://cdn.discordapp.com/attachments/583775968804732928/1220910607868629042/b18c384nbt-humanv0-test.ckpt?ex=6610a89c&is=65fe339c&hm=72b438db2a9e52911356c86a0c27cc63722b7cceb24422edfcf9a0788a07c1db&) from lightvector is the only one. But it's undertrained and he's planning on releasing a better one soon. Check the [Discord server](https://discord.gg/utV9dsfqFW) for updates.
2. Python. Version 3.10.6 works for me.
3. Run `pip install -r requirements.txt` to install the necessary python packages.
4. Change the parameters in `Reviewer.bat` to your own. If you're not sure about the device, `CPU` is a slow but safe bet. Format: `[HSL_MODEL] [HSL_DEVICE] [KATAGO_EXE] [KATAGO_ANALYSIS_CFG] [KATAGO_MODEL] (SGF) (PLAYER)`

## Create flashcards
1. Run Reviewer.bat
2. Set the color you were in the game you want to review.
3. Optionally change the HSL sliders.
4. Drag & drop your game sgf.
5. Wait until the console says `=== REVIEW DONE ===`

There are also some options you can tweak at the top in `hsl_reviewer.py`.

## Train
1. Run Trainer.bat
2. Load a card and think of a move.
3. Click on the board to see the answer.
4. Delete the card if you feel the answer is easy.
5. Load the next card.

It should also work on linux and mac. Just run `hsl_reviewer.py` or `hsl_trainer.py` directly.

## Screenshots
![Reviewer](/screenshots/Reviewer.png)

![Question](/screenshots/Question.png)

![Answer](/screenshots/Answer.png)

X = Game move<br>
O = HSL move<br>
